import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, render_title  # noqa: E402
from render.presets import PRESET_NAMES, PRESETS, TARGETS, build_prompt, suggested_look  # noqa: E402

PRD = ["Chrome Slam", "Fuzzy Grass", "Liquid Glass", "Aero Bubble", "Ben-Day Pop", "Holo Foil", "ChromaDepth",
       "Candy Inflatable", "Op Art Stripe", "Vapor Sunset", "Low Poly", "Cel Toon", "Trailer Title"]


def test_every_prd_preset_exists():
    assert list(PRESET_NAMES) == PRD


@pytest.mark.parametrize("name", PRD)
@pytest.mark.parametrize("target", TARGETS)
def test_prompt_quotes_exact_text_and_states_material(name, target):
    pos, neg = build_prompt(name, 'BADD "ASS"', target=target)
    assert "BADD 'ASS'" in pos and PRESETS[name].material in pos
    assert "misspelled" in neg
    assert " no " not in f" {pos.lower()} "  # say what IS there


def test_flux3_uses_image_one_and_colour_words_override():
    pos, _ = build_prompt("Holo Foil", "TITLE", "teal and hot pink", "flux3")
    assert "image 1" in pos and "teal and hot pink" in pos
    pos, _ = build_prompt("Holo Foil", "TITLE", "", "flux2_dev")
    assert PRESETS["Holo Foil"].palette_words in pos and "control image" in pos


def test_unknown_preset_or_target():
    with pytest.raises(ValueError):
        build_prompt("Nope", "A")
    with pytest.raises(ValueError):
        build_prompt("Chrome Slam", "A", target="sdxl")


@pytest.mark.parametrize("name", PRD)
def test_suggested_look_renders(name):
    look, shadow = suggested_look(name)
    p = render_title(Glyphs(text="AB", size=80), look, shadow, 300, 160)
    assert p["face"].sum() > 100
