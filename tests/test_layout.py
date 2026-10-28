import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.geometry import ArcPath, bend_curve, flag_offset, tilt_homography  # noqa: E402

PLAIN = dict(look=Look3D(extrude=0), shadow=Shadow(on=False), width=900, height=420)


def face(text="HHHHH", size=120, **lay):
    return render_title(Glyphs(text=text, size=size), lay=Layout(**lay), **PLAIN)


def letter_centroids(p, n):
    ids = (p["letter_ids"] * 1000).round().astype(int)
    out = []
    for c in np.unique(ids.reshape(-1, 3), axis=0):
        if not c.any():
            continue
        yy, xx = np.nonzero((ids == c).all(-1) & (p["face"] > 0))
        out.append((xx.mean(), yy.mean(), len(xx)))
    out.sort()
    assert len(out) == n
    return out


def test_bend_curve_arc_length_matches_text():
    p = bend_curve(0.7, 500, 450, 200)
    assert abs(ArcPath(p).length - 500) < 1.0


def test_arc_with_zero_bend_matches_flat():
    a, b = face()["face"], face(mode="arc", bend=0.0)["face"]
    iou = (a * b).sum() / np.maximum(a, b).sum()
    assert iou > 0.95


def test_arc_up_lifts_middle_letters_and_smile_drops_them():
    up = letter_centroids(face(mode="arc", bend=0.6), 5)
    down = letter_centroids(face(mode="arc", bend=-0.6), 5)
    assert up[2][1] < up[0][1] - 20 and up[2][1] < up[4][1] - 20
    assert down[2][1] > down[0][1] + 20 and down[2][1] > down[4][1] + 20


def test_bulge_swells_middle():
    c = letter_centroids(face(bulge=0.5), 5)
    assert c[2][2] > c[0][2] * 1.15 and c[2][2] > c[4][2] * 1.15
    c = letter_centroids(face(bulge=-0.4), 5)
    assert c[2][2] < c[0][2] * 0.9


def test_tilt_identity_and_foreshortening():
    assert np.allclose(tilt_homography(900, 420, 0, 0), np.eye(3))
    f = face(text="IIIIIIII", tilt_x=40)["face"]
    rows = np.where(f.any(1))[0]
    span = lambda r: np.ptp(np.where(f[r])[0])  # noqa: E731
    assert span(rows.min() + 3) < span(rows.max() - 3) * 0.95  # top leans away -> narrower


def test_tilt_y_pushes_right_side_away():
    f = face(text="IIIIIIII", tilt_y=35)["face"]
    cols = np.where(f.any(0))[0]
    h = lambda c: f[:, c].sum()  # noqa: E731
    left = max(h(c) for c in cols[:15])
    right = max(h(c) for c in cols[-15:])
    assert right < left * 0.95


def test_vanishing_point_extrusion_converges():
    p = render_title(Glyphs(text="HI", size=140), Look3D(extrude=40), Shadow(on=False), 900, 420,
                     Layout(vanish=True, vp_x=0.5, vp_y=2.0))
    fy = np.nonzero(p["face"])[0].mean()
    sy, sx = np.nonzero(p["sides"])
    assert sy.mean() > fy  # sides recede toward the VP below
    assert abs(sx.mean() - 450) < 60  # and stay centred on it (no parallel sideways offset)


def test_flag_follows_wave():
    lay = dict(flag_amp=30, flag_wavelength=300)
    flat, wav = face(text="IIIIIIIIIIII")["face"], face(text="IIIIIIIIIIII", **lay)["face"]
    off = flag_offset(900, Layout(**lay))
    cols = [c for c in range(900) if flat[:, c].any() and wav[:, c].any()]
    shift = [np.nonzero(wav[:, c])[0].mean() - np.nonzero(flat[:, c])[0].mean() for c in cols]
    assert np.corrcoef(shift, off[cols])[0, 1] > 0.9


def test_full_layout_keeps_pass_contract():
    p = render_title(Glyphs(text="TITLE"), Look3D(), Shadow(), 640, 320,
                     Layout(mode="arc", bend=0.4, bulge=0.3, tilt_x=20, tilt_y=-10, vanish=True, flag_amp=12))
    for k, a in p.items():
        assert a.shape[:2] == (320, 640) and a.dtype == np.float32, k
        assert a.min() >= 0 and a.max() <= 1.0001, k
    assert p["face"].sum() > 500 and p["sides"].sum() > 50
    assert (p["face"] * p["sides"]).sum() == 0


def test_mid_guide_sits_on_cap_midline_and_follows_arc():
    from render.core import draw_guides, layout
    _, _, _, m = layout(Glyphs(text="H", size=120))
    g = draw_guides(600, 300, 100, 200, m)
    mid = 200 - (m["ascent"] - m["cap_top"]) / 2
    assert g[int(round(mid)) - 1:int(round(mid)) + 2, 100:400, 3].max() > 0.3
    arc = face(mode="arc", bend=0.6)["guides"][..., 3]
    flat = face()["guides"][..., 3]
    assert not np.allclose(arc, flat)
