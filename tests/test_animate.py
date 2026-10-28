import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow  # noqa: E402
from render.animate import (EASINGS, EFFECTS, ORDERS, Anim, Track, ease, letter_ranks, pose,  # noqa: E402
                            render_frames, track_value)

FAST = dict(look=Look3D(extrude=6, bevel=3), shadow=Shadow(on=False), width=320, height=160)


@pytest.mark.parametrize("name", EASINGS)
def test_easing_endpoints(name):
    assert abs(ease(name, 0.0)) < 1e-6 and abs(ease(name, 1.0) - 1) < 1e-6


def test_back_and_elastic_overshoot():
    assert max(ease("back", p / 100) for p in range(101)) > 1.05
    assert max(ease("elastic", p / 100) for p in range(101)) > 1.05
    assert all(0 <= ease("bounce", p / 100) <= 1.0001 for p in range(101))


def test_orders():
    assert letter_ranks("ABC", "forward") == {0: 0, 1: 1, 2: 2}
    assert letter_ranks("ABC", "reverse") == {0: 2, 1: 1, 2: 0}
    assert letter_ranks("A B", "forward") == {0: 0, 2: 1}  # spaces don't take a stagger slot
    co = letter_ranks("ABCDE", "center_out")
    assert co[2] == 0 and co[0] == co[4] == 2
    ei = letter_ranks("ABCDE", "edges_in")
    assert ei[0] == 0 and ei[2] == 2
    assert sorted(letter_ranks("ABCDEF", "random", 3).values()) == list(range(6))
    for o in ORDERS:
        letter_ranks("HELLO", o)


def test_in_settles_to_rest_and_stagger_delays():
    tr = Track(effect="drop", duration=0.5, stagger=0.25, easing="in_out")
    assert track_value(tr, 0, 0, 24) == 1.0
    assert abs(track_value(tr, 0, 12, 24)) < 1e-6           # letter 0 done at 0.5 s
    assert track_value(tr, 1, 12, 24) >= 0.5 > track_value(tr, 0, 12, 24)                  # letter 1 started 0.25 s later
    assert track_value(Track(direction="out", easing="linear"), 0, 0, 24) == 0.0


@pytest.mark.parametrize("effect", EFFECTS)
def test_every_effect_moves_letters_then_rests(effect):
    g = Glyphs(text="AB", size=80)
    lay = Layout(flag_amp=10) if effect == "wave" else Layout()
    anim = Anim([Track(effect=effect, duration=0.25, stagger=0.1, easing="in_out")], fps=12, hold=0.2)
    fr = render_frames(anim, g, lay=lay, passes=("face",), **FAST)["face"]
    assert fr.shape[1:] == (160, 320)
    rest = render_frames(Anim([], fps=12), g, lay=lay, passes=("face",), **FAST)["face"][0]
    assert any(not np.array_equal(f, rest) for f in fr)  # the effect moves the letters ...
    if effect != "wave":  # ... and the last frame is back at rest
        assert np.array_equal(fr[-1], rest)


def test_word_target_moves_whole_word_together():
    g = Glyphs(text="AB", size=80)
    gp, _ = pose(Anim([Track(effect="slide", target="word", amount=100)]), g, Layout(), 0)
    assert gp.word["dx"] == -100 and not any(gp.letters.get(i) for i in range(2))
    assert g.word == {}  # source glyphs are not mutated


def test_pop_back_overshoots_scale():
    anim = Anim([Track(effect="pop", easing="back", duration=1.0, stagger=0)], fps=24)
    scales = [pose(anim, Glyphs(text="A"), Layout(), f)[0].letters[0]["scale"] for f in range(25)]
    assert scales[0] == 0 and max(scales) > 1.05 and abs(scales[-1] - 1) < 1e-6


def test_drive_curve_lags_per_letter():
    curve = np.zeros(20)
    curve[5] = 1.0
    tr = Track(effect="pop", drive=curve, stagger=2 / 24, amount=-50)
    assert track_value(tr, 0, 5, 24) == 1.0 and track_value(tr, 1, 5, 24) == 0.0
    assert track_value(tr, 1, 7, 24) == 1.0
    anim = Anim([tr], fps=24)
    assert anim.n_frames(3) == 20
    assert pose(anim, Glyphs(text="AB"), Layout(), 5)[0].letters[0]["scale"] == pytest.approx(1.5)


def test_frame_count_includes_stagger_and_hold():
    anim = Anim([Track(duration=1.0, stagger=0.5)], fps=10, hold=0.5)
    assert anim.n_frames(3) == 25  # 1.0 + 2*0.5 + 0.5 s
