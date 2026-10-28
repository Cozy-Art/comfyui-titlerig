import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow  # noqa: E402
from render.animate import (EASINGS, EFFECTS, LAYOUT_EFFECTS, LETTER_EFFECTS, LOOK_EFFECTS, ORDERS,  # noqa: E402
                            SHADOW_EFFECTS, Anim, Track, ease, hits, letter_ranks, pose, render_frames,
                            select_letters, track_value)

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


@pytest.mark.parametrize("effect", LETTER_EFFECTS + LAYOUT_EFFECTS)
def test_every_effect_moves_letters_then_rests(effect):
    g = Glyphs(text="AB", size=80)
    lay = Layout(flag_amp=10) if effect == "wave" else Layout(mode="ticker") if effect == "wrap_spin" else Layout()
    if effect == "shake":
        lay = Layout()
    anim = Anim([Track(effect=effect, duration=0.25, stagger=0.1, easing="in_out")], fps=12, hold=0.2)
    fr = render_frames(anim, g, lay=lay, passes=("face",), **FAST)["face"]
    assert fr.shape[1:] == (160, 320)
    rest = render_frames(Anim([], fps=12), g, lay=lay, passes=("face",), **FAST)["face"][0]
    assert any(not np.array_equal(f, rest) for f in fr)  # the effect moves the letters ...
    if effect not in ("wave", "shake", "wrap_spin"):  # ... and the last frame is back at rest
        assert np.array_equal(fr[-1], rest)


def test_word_target_moves_whole_word_together():
    g = Glyphs(text="AB", size=80)
    gp, *_ = pose(Anim([Track(effect="slide", target="word", amount=100)]), g, Layout(), 0)
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


@pytest.mark.parametrize("effect", SHADOW_EFFECTS)
def test_shadow_effects_change_the_shadow(effect):
    assert effect in EFFECTS
    g = Glyphs(text="AB", size=80)
    sh = Shadow(texture="solid", length=12, opacity=0.6)
    anim = Anim([Track(effect=effect, duration=0.25, stagger=0, easing="linear")], fps=12, hold=0)
    fr = render_frames(anim, g, Look3D(extrude=4, bevel=2), sh, 320, 160, passes=("shadow",))["shadow"]
    rest = render_frames(Anim([], fps=12), g, Look3D(extrude=4, bevel=2), sh, 320, 160, passes=("shadow",))["shadow"][0]
    assert not np.allclose(fr[0], rest)
    _, _, s0, _ = pose(anim, g, Layout(), 0, sh)
    assert sh.length == 12 and sh.opacity == 0.6  # the user's Shadow is not mutated
    assert (s0.length, s0.angle, s0.opacity, s0.softness) != (sh.length, sh.angle, sh.opacity, sh.softness)


def test_select_letters():
    assert select_letters("BIG WORD", "all") == [0, 1, 2, 4, 5, 6, 7]
    assert select_letters("BIG WORD", "word:2") == [4, 5, 6, 7]
    assert select_letters("BIG WORD", "word:1,2") == [0, 1, 2, 4, 5, 6, 7]
    assert select_letters("BIG WORD", "0, 5-6, 3") == [0, 5, 6]  # index 3 is the space


def test_letters_selection_and_influence_dial():
    tr = Track(effect="drop", drive=np.ones(4), amount=100, letters="word:2", stagger=0, influence=0.5)
    g, *_ = pose(Anim([tr]), Glyphs(text="AB CD"), Layout(), 0)
    assert all(g.letters[i]["dy"] == -50 for i in (3, 4))
    assert not any(g.letters.get(i, {}).get("dy") for i in (0, 1))
    off = Track(effect="drop", drive=np.ones(4), amount=100, influence=0.0)
    g, *_ = pose(Anim([off]), Glyphs(text="AB"), Layout(), 0)
    assert all(g.letters[i]["dy"] == 0 for i in (0, 1))


def test_word_target_on_selection_moves_group_rigidly():
    kw = dict(look=Look3D(extrude=0), shadow=Shadow(on=False), width=500, height=200, passes=("face",))
    g = Glyphs(text="AA BB", size=70)
    rest = render_frames(Anim([], fps=12), g, **kw)["face"][0]
    tr = Track(effect="slide", target="word", letters="word:2", drive=np.ones(1), amount=-60)
    moved = render_frames(Anim([tr], fps=12), g, **kw)["face"][0]
    cols = lambda f: np.where(f.any(0))[0]  # noqa: E731
    assert cols(moved).max() == pytest.approx(cols(rest).max() + 60, abs=2)  # second word slid right
    assert cols(moved).min() == cols(rest).min()  # first word untouched
    g2, *_ = pose(Anim([Track(effect="roll_z", target="word", letters="word:2", drive=np.ones(1), amount=30)]), g,
                    Layout(), 0)
    assert g2.letters[3]["group"] == g2.letters[4]["group"] and g2.letters[3]["group"]["rot"] == 30


def test_spectrum_drive_maps_letters_left_to_right():
    spec = np.zeros((4, 6))
    spec[0] = 1.0  # only the lowest band is loud
    tr = Track(effect="drop", drive=spec, amount=100, stagger=0)
    g, *_ = pose(Anim([tr]), Glyphs(text="ABCD"), Layout(), 0)
    assert g.letters[0]["dy"] == -100 and g.letters[3]["dy"] == 0
    assert Anim([tr]).n_frames(4) == 6


@pytest.mark.parametrize("effect", LOOK_EFFECTS)
def test_look_effects(effect):
    tr = Track(effect=effect, drive=np.ones(2))
    _, _, _, lk = pose(Anim([tr]), Glyphs(text="A"), Layout(), 0, look=Look3D(extrude=10, light_angle=0))
    assert (lk.extrude, lk.light_angle) != (10, 0)


def test_new_easings_shapes():
    assert ease("in", 0.5) < 0.5 < ease("out", 0.5)
    assert ease("steps", 0.3) == 0.25 and ease("steps", 0.99) == 0.75
    assert max(ease("spring", p / 100) for p in range(101)) > 1.05  # overshoots
    assert abs(ease("sine", 0.5) - 0.5) < 1e-9 and ease("expo", 0.5) > 0.9


def test_squash_stretch():
    g, *_ = pose(Anim([Track(effect="squash", drive=np.ones(1), amount=40)]), Glyphs(text="A"), Layout(), 0)
    assert g.letters[0]["sy"] < 1 < g.letters[0]["sx"]
    g, *_ = pose(Anim([Track(effect="squash", drive=np.ones(1), amount=-40)]), Glyphs(text="A"), Layout(), 0)
    assert g.letters[0]["sy"] > 1 > g.letters[0]["sx"]


def test_hits_rising_edges():
    c = np.array([0, 0.2, 0.9, 1.0, 0.6, 0.3, 0.7, 0.4, 0.0])
    assert hits(c) == [(2, 1.0), (6, 0.7)]


def test_trigger_response_replays_easing_each_hit():
    c = np.zeros(48)
    c[[0, 24]] = 1.0  # two hits, a second apart
    tr = Track(effect="drop", drive=c, response="trigger", easing="bounce", duration=0.5, amount=100, stagger=0)
    v = [track_value(tr, 0, f, 24) for f in range(48)]
    assert v[0] == 1.0 and v[24] == 1.0 and v[12] == 0.0 and v[36] == 0.0
    assert any(v[k] > v[k - 1] + 0.05 for k in range(2, 12))  # bounce: rises again after the first fall
    follow = Track(effect="drop", drive=c, stagger=0)
    assert track_value(follow, 0, 1, 24) == 0.0  # follow mode just reads the curve
    loop = Track(effect="spin_y", drive=c, response="trigger", direction="loop", easing="in_out", duration=0.5)
    assert track_value(loop, 0, 6, 24) == pytest.approx(0.5) and track_value(loop, 0, 20, 24) == 1.0


def test_retrigger_modes_tame_busy_hits():
    c = np.zeros(48)
    c[[0, 6]] = 1.0  # second hit lands mid-bounce
    base = dict(effect="drop", drive=c, response="trigger", easing="bounce", duration=0.75, stagger=0)
    restart = [track_value(Track(**base), 0, f, 24) for f in range(30)]
    finish = [track_value(Track(**base, retrigger="finish"), 0, f, 24) for f in range(30)]
    layer = [track_value(Track(**base, retrigger="layer"), 0, f, 24) for f in range(30)]
    assert restart[6] == 1.0                  # restart: snaps back to the top
    assert finish[6] < 1.0 and finish[18] == 0.0   # finish: the first bounce plays out, the second hit is dropped
    assert layer[6] == 1.0 and all(layer[k] >= restart[k] - 1e-9 for k in range(30))
