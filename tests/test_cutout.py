import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.cutout import cutout, fit, frame_index, pick_mask, shape_mask, stroke_ring  # noqa: E402

RED, BLUE = np.array([1.0, 0, 0], np.float32), np.array([0, 0, 1.0], np.float32)


def solid(c, n=1, h=40, w=60):
    return np.broadcast_to(c, (n, h, w, 3)).astype(np.float32)


def box(h=40, w=60):
    m = np.zeros((h, w), np.float32)
    m[10:30, 20:40] = 1
    return m


def test_inside_in_letters_outside_elsewhere():
    rgb, a = cutout(solid(RED), box(), outside=solid(BLUE))
    assert np.allclose(rgb[0, 20, 30], RED) and np.allclose(rgb[0, 2, 2], BLUE)
    assert a[0, 20, 30] == 1 and a[0, 2, 2] == 0


def test_no_outside_is_a_transparent_cutout():
    rgb, a = cutout(solid(RED), box())
    assert a[0].sum() == box().sum() and np.allclose(rgb[0, 2, 2], 0)


def test_fit_modes():
    tall = np.zeros((100, 20, 3), np.float32)
    tall[:, :10] = 1  # left half white
    c, cov = fit(tall, 60, 40, "contain")
    assert cov[:, :5].sum() == 0 and cov[:, 26:34].all() and cov.sum() == 8 * 40  # letterbox bars left and right
    c, cov = fit(tall, 60, 40, "cover")
    assert cov.all() and c[:, :25].mean() > 0.9 and c[:, 35:].mean() < 0.1
    c, cov = fit(tall, 60, 40, "stretch")
    assert c.shape == (40, 60, 3) and cov.all()


def test_video_lengths_loop_hold_pingpong():
    assert [frame_index(f, 3, "loop") for f in range(5)] == [0, 1, 2, 0, 1]
    assert [frame_index(f, 3, "hold") for f in range(5)] == [0, 1, 2, 2, 2]
    assert [frame_index(f, 3, "pingpong") for f in range(6)] == [0, 1, 2, 1, 0, 1]
    vid = np.stack([solid(np.array([f / 4, 0, 0]))[0] for f in range(5)])
    rgb, _ = cutout(vid, box())  # still mask: output runs as long as the video
    assert len(rgb) == 5 and rgb[3, 20, 30, 0] == pytest.approx(0.75)
    masks = np.stack([box()] * 7)
    rgb, _ = cutout(vid, masks, timing="hold")  # animated mask sets the length
    assert len(rgb) == 7 and rgb[6, 20, 30, 0] == pytest.approx(1.0)


def test_grow_feather_stroke():
    m = box()
    assert shape_mask(m, grow=3).sum() > m.sum() > shape_mask(m, grow=-3).sum()
    f = shape_mask(m, feather=4)
    assert 0 < f[10, 30] < 1 and f[20, 30] > 0.95
    ring = stroke_ring(m, 2)
    assert ring[20, 30] == 0 and ring[9, 30] == 1 and ring[2, 30] == 0
    rgb, a = cutout(solid(RED), m, outside=solid(BLUE), stroke=2, stroke_color=(1, 1, 1))
    assert np.allclose(rgb[0, 9, 30], 1) and a[0, 9, 30] == 1


def test_mask_from_and_shading_on_a_real_rig():
    p = render_title(Glyphs(text="CUT", size=120), Look3D(extrude=20), Shadow(length=20), 320, 200, Layout())
    faces = pick_mask(p["alpha"], p["face"], p["shadow"], "faces")
    both = pick_mask(p["alpha"], p["face"], p["shadow"], "faces + extrusion")
    sil = pick_mask(p["alpha"], p["face"], p["shadow"], "silhouette + shadow")
    assert faces.sum() < both.sum() < sil.sum()
    with pytest.raises(ValueError):
        pick_mask(p["alpha"], None, None, "faces")
    white = solid(np.ones(3, np.float32), h=200, w=320)
    flat, _ = cutout(white, both)
    lit, _ = cutout(white, both, beauty=p["beauty"], shading=1.0)
    on_sides = (p["sides"] > 0.5) & (p["face"] < 0.5)
    assert lit[0][on_sides].mean() < flat[0][on_sides].mean() - 0.1  # the extrusion reads darker
