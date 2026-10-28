import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.geometry import WRAP_MODES, wrap_maps  # noqa: E402

KW = dict(look=Look3D(extrude=0, bevel=0, bevel_profile="flat", face2=None), shadow=Shadow(on=False),
          width=800, height=320)


def face(text="IIIIIIIIIIII", **lay):
    return render_title(Glyphs(text=text, size=100), lay=Layout(**lay), **KW)


def stroke_widths(f):
    """Widths of each vertical stroke along the middle row, left to right."""
    row = f[f.shape[0] // 2] > 0
    edges = np.flatnonzero(np.diff(row.astype(int)))
    return [b - a for a, b in zip(edges[::2], edges[1::2])]


@pytest.mark.parametrize("mode", ["ticker", "sphere"])
def test_wraps_foreshorten_toward_the_edges(mode):
    w = stroke_widths(face(mode=mode, wrap_radius=0.4 if mode == "sphere" else 0.2, wrap_repeat=False)["face"])
    assert len(w) >= 6
    assert min(w[0], w[-1]) < max(w[len(w) // 2 - 1:len(w) // 2 + 1]) * 0.8


def test_ticker_phase_scrolls_and_full_spin_returns():
    a = face(mode="ticker")["face"]
    b = face(mode="ticker", wrap_phase=25)["face"]
    c = face(mode="ticker", wrap_phase=360)["face"]
    assert not np.array_equal(a, b)
    assert np.abs(a - c).mean() < 1e-3  # a whole turn is seamless


def test_cube_full_turn_seamless_and_faces_shaded_differently():
    a = face(text="TITLERIG", mode="cube", wrap_phase=0)["face"]
    c = face(text="TITLERIG", mode="cube", wrap_phase=360)["face"]
    assert np.abs(a - c).mean() < 1e-3
    _, _, shade = wrap_maps(800, 320, Layout(mode="cube", wrap_phase=30), 500, 400, 160, 60)
    vals = np.unique(np.round(shade[160][shade[160] > 0], 3))
    assert len(vals) == 2  # two visible faces, two tones


def test_sphere_is_a_disc_and_guides_wrap():
    _, _, shade = wrap_maps(800, 320, Layout(mode="sphere", wrap_radius=0.4), 500, 400, 160, 60)
    assert shade[160, 400] > shade[160, 400 + 120] > 0 and shade[160, 10] == 0
    p = face(mode="sphere", wrap_radius=0.45)
    flat = face()
    assert not np.allclose(p["guides"], flat["guides"])


@pytest.mark.parametrize("mode", WRAP_MODES)
def test_wraps_keep_pass_contract(mode):
    p = render_title(Glyphs(text="TITLE"), Look3D(), Shadow(), 640, 320, Layout(mode=mode))
    for k, a in p.items():
        assert a.shape[:2] == (320, 640) and a.dtype == np.float32 and a.min() >= 0 and a.max() <= 1.0001, k
    assert p["face"].sum() > 300 and (p["face"] * p["sides"]).sum() == 0
