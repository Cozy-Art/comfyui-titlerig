"""Flip X / spin Y: a letter turning edge-on shows its extrusion as a side wall (a solid card, not a flat bar)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.animate import _apply  # noqa: E402

LOOK = Look3D(extrude=24)


def turned(effect, deg):
    d = {}
    _apply(d, effect, deg, 1.0)
    return render_title(Glyphs(text="I", size=160, letters={0: d}), LOOK, Shadow(on=False), 300, 260, Layout())


@pytest.mark.parametrize("effect,axis", [("spin_y", 1), ("flip_x", 0)])
def test_edge_on_letter_is_a_wall_as_deep_as_the_extrusion(effect, axis):
    p = turned(effect, 90)
    sides = p["sides"] > 0.5
    assert sides.sum() > 0 and p["alpha"].sum() > 0  # not invisible, not a hairline
    extent = np.ptp(np.nonzero(sides)[axis]) + 1  # spin: wall runs across x (cols); flip: down y (rows)
    assert LOOK.extrude - 3 <= extent <= LOOK.extrude + 8  # + the edge-on sliver (4% of the letter)


@pytest.mark.parametrize("extrude,angle", [(24, 55.0), (30, 55.0), (34, 40.0), (18, 125.0)])
def test_unturned_title_extrudes_exactly_as_before(extrude, angle):
    """One whole-pixel step per unit of depth along the title's extrusion angle, like the pre-turn renderer."""
    look = Look3D(extrude=extrude, extrude_angle=angle)
    p = render_title(Glyphs(text="TITLE", size=120), look, Shadow(), 480, 220, Layout())
    import cv2
    fm = (p["face"] > 0.5).astype(np.float32)
    a = np.radians(angle)
    sides = np.zeros_like(fm)
    for k in range(extrude, 0, -1):
        M = np.float32([[1, 0, np.cos(a) * k], [0, 1, np.sin(a) * k]])
        sides = np.maximum(sides, cv2.warpAffine(fm, M, fm.shape[::-1], flags=cv2.INTER_NEAREST))
    assert np.array_equal(p["sides"] > 0.5, (sides * (1 - fm)) > 0.5)


def test_turning_wall_is_lighter_than_a_receding_side():
    flat = render_title(Glyphs(text="I", size=160), LOOK, Shadow(on=False), 300, 260, Layout())
    turn = turned("spin_y", 70)
    lum = lambda p: p["beauty"][..., :3][p["sides"] > 0.5].mean()  # noqa: E731
    assert lum(turn) > lum(flat) + 0.03
