import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.animate import Anim, pose, render_frames  # noqa: E402
from render.core import letter_anchors  # noqa: E402
from render.magnet import Magnet, field, simulate, stretch_of  # noqa: E402

W, H, FPS = 800, 300, 24.0


def test_field_polarity_and_range():
    rest, mag = np.array([400.0, 150.0]), np.array([450.0, 150.0])
    assert field(Magnet(polarity="repel"), rest, mag)[0] < 0      # pushed away (left)
    assert field(Magnet(polarity="attract"), rest, mag)[0] > 0    # pulled toward (right)
    near = np.hypot(*field(Magnet(range=100), rest, mag))
    far = np.hypot(*field(Magnet(range=100), rest, np.array([700.0, 150.0])))
    assert near > 10 * far
    pulled = field(Magnet(polarity="attract", strength=500), rest, mag)
    assert pulled[0] < 50  # never pulled past the magnet


def test_invalid_names():
    with pytest.raises(ValueError):
        Magnet(polarity="sideways")
    with pytest.raises(ValueError):
        Magnet(path="zigzag")


def _peak_and_final(spring):
    mg = Magnet(path="fixed", x=0.55, y=0.5, strength=60, range=200, spring=spring, lag=0.0, duration=0.01)
    rows = simulate(mg, {0: (400.0, 150.0)}, 72, FPS, W, H)[0]
    disp = -rows[:, 0]  # repel pushes left
    return disp.max(), disp[-1]


def test_spring_controls_overshoot():
    calm_peak, calm_end = _peak_and_final(0.0)
    bouncy_peak, bouncy_end = _peak_and_final(1.0)
    assert calm_peak <= calm_end * 1.02           # critically damped: no overshoot
    assert bouncy_peak > bouncy_end * 1.2         # bouncy: overshoots, then settles
    assert abs(calm_end - bouncy_end) < 1.0


def test_lag_delays_far_letters():
    anchors = {0: (300.0, 150.0), 1: (500.0, 150.0)}
    mg = Magnet(path="sweep", x=0.0, x_end=1.0, duration=1.0, lag=0.5, range=150, strength=60)
    fast = simulate(Magnet(**{**mg.__dict__, "lag": 0.0}), anchors, 24, FPS, W, H)
    slow = simulate(mg, anchors, 24, FPS, W, H)
    assert not np.allclose(fast[1][:, 0], slow[1][:, 0])


def test_squash_stretch_follows_velocity():
    k, a = stretch_of(Magnet(squash=1.0, strength=50), 300.0, 0.0)
    assert k > 1.3 and abs(a) < 1e-6
    assert stretch_of(Magnet(squash=1.0), 0.0, 0.0) == (1.0, 0.0)
    assert stretch_of(Magnet(squash=0.0), 300.0, 0.0)[0] == 1.0
    # the renderer stretches along the angle: a horizontal stretch makes the letter wider and shorter
    plain = render_title(Glyphs(text="O", size=120), Look3D(extrude=0), Shadow(on=False), 400, 240)["face"]
    s = render_title(Glyphs(text="O", size=120, letters={0: {"stretch": 1.5, "stretch_angle": 0}}),
                     Look3D(extrude=0), Shadow(on=False), 400, 240)["face"]
    span = lambda f, ax: np.ptp(np.where(f.any(ax))[0])  # noqa: E731
    assert span(s, 0) > span(plain, 0) * 1.3 and span(s, 1) < span(plain, 1) * 0.85


def test_drive_scales_strength():
    d = np.zeros(24)
    d[12:] = 1.0
    mg = Magnet(path="fixed", x=0.55, y=0.5, drive=d, spring=0, lag=0)
    rows = simulate(mg, {0: (400.0, 150.0)}, 24, FPS, W, H)[0]
    assert abs(rows[11, 0]) < 1e-6 and abs(rows[-1, 0]) > 5


def test_anchors_follow_arc():
    flat = letter_anchors(Glyphs(text="ABCDE"), W, H, Layout())
    arc = letter_anchors(Glyphs(text="ABCDE"), W, H, Layout(mode="arc", bend=0.6))
    assert flat[2][1] == pytest.approx(flat[0][1], abs=2)
    assert arc[2][1] < arc[0][1] - 10  # middle letter lifted on a rainbow arc


def test_pose_applies_magnet_and_magnet_word_renders():
    g = Glyphs(text="REPEL", size=90)
    mg = Magnet(x=0.5, x_end=0.5, y=0.5, path="fixed", strength=80, range=260, spring=0.3, squash=0.8,
                text="M", size=80)
    anim = Anim(magnets=[mg], fps=12, hold=0.5)
    gp, *_ = pose(anim, g, Layout(), 6, size=(W, H))
    left, right = gp.letters[0]["dx"], gp.letters[4]["dx"]
    assert left < -5 and right > 5                     # letters flee the magnet in the middle
    fr = render_frames(anim, g, Look3D(extrude=4), Shadow(on=False), W, H, passes=("alpha", "beauty"))
    a = fr["alpha"][-1]
    assert a[H // 2 - 5:H // 2 + 5, W // 2 - 5:W // 2 + 5].mean() > 0.5   # the magnet word sits in the gap
    assert fr["alpha"].shape[0] == anim.n_frames(5)
