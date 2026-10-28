import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from render import Glyphs, render_title  # noqa: E402
from render.presets import (FLUX3_FIELDS, flux3_settings, EMBOSSED, PRESET_NAMES, PRESETS, TARGETS, build_prompt, flux2_settings,  # noqa: E402
                            flux2_structured, suggested_look)

PRD = ["Chrome Slam", "Fuzzy Grass", "Liquid Glass", "Aero Bubble", "Ben-Day Pop", "Holo Foil", "ChromaDepth",
       "Candy Inflatable", "Op Art Stripe", "Vapor Sunset", "Low Poly", "Cel Toon", "Trailer Title"]
NEGATION = re.compile(r"\b(no|not|without|avoid|don't|never)\b", re.I)
SCHEMA = json.load(open(os.path.join(ROOT, "docs", "skills", "flux-v2", "schema.json")))


def _validate(obj, schema):
    """The subset of JSON Schema the flux-v2 schema uses: required, enum, type, min/max, additionalProperties."""
    for k in schema.get("required", []):
        assert k in obj, f"missing {k}"
    if schema.get("additionalProperties") is False:
        assert set(obj) <= set(schema["properties"]), set(obj) - set(schema["properties"])
    for k, v in obj.items():
        spec = schema["properties"].get(k, {})
        if "enum" in spec:
            assert v in spec["enum"], (k, v)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            assert spec.get("minimum", -1e9) <= v <= spec.get("maximum", 1e9), (k, v)
        if isinstance(v, dict) and "properties" in spec:
            _validate(v, spec)


def test_every_prd_preset_exists():
    assert list(PRESET_NAMES) == PRD


@pytest.mark.parametrize("name", PRD)
def test_flux2_prompt_follows_skill(name):
    pos, neg = build_prompt(name, "BADD ASS", target="flux2_dev")
    assert neg == ""                                       # FLUX.2 has no negative prompt
    assert not NEGATION.search(pos), pos                   # describe only what is wanted
    assert len(pos.split()) <= 60                          # short, focused
    assert "'BADD ASS'" in " ".join(pos.split()[:10])      # text front-loaded
    assert "image 1" in pos
    look, _ = suggested_look(name)
    assert f"Letter faces {look.face.upper()}" in pos      # hex bound to objects, not the scene


@pytest.mark.parametrize("name", PRD)
@pytest.mark.parametrize("target", TARGETS)
def test_every_target_quotes_text_and_says_what_is_there(name, target):
    pos, neg = build_prompt(name, 'BADD "ASS"', target=target)
    assert "BADD" in pos and "ASS" in pos
    assert not NEGATION.search(pos), pos
    assert (neg == "") == (target != "ltx2_video")


def test_colour_words_replace_hex():
    pos, _ = build_prompt("Holo Foil", "TITLE", "teal and hot pink", "flux2_dev")
    assert "teal and hot pink" in pos and "#" not in pos
    pos, _ = build_prompt("Holo Foil", "TITLE", "", "flux3")
    assert "image 1" in pos


def test_json_structured_prompt_is_valid_and_in_prompt_string():
    pos, neg = build_prompt("Chrome Slam", "TITLERIG", fmt="json")
    d = json.loads(pos)
    assert neg == "" and "'TITLERIG'" in d["subjects"][0]["description"]
    _validate(d, SCHEMA["properties"]["structured_prompt"])
    assert flux2_structured(PRESETS["Ben-Day Pop"], "A").get("camera") is None  # graphic style: no camera


def test_settings_validate_against_vendored_skill_schema():
    s = flux2_settings("TITLERIG")
    _validate({"prompt": "x" * 10, **s}, SCHEMA)
    assert s["variant"] == "flex" and 40 <= s["steps"] <= 50 and 7 <= s["guidance"] <= 8


def test_only_two_presets_are_embossed():
    assert len(EMBOSSED) == 2
    for name in PRD:
        look, _ = suggested_look(name)
        assert (look.bevel > 0 and look.bevel_profile != "flat") == (name in EMBOSSED), name


def test_unknown_preset_target_or_format():
    for kw in ({"preset": "Nope"}, {"target": "sdxl"}, {"fmt": "yaml"}):
        args = {"preset": "Chrome Slam", "text": "A", **kw}
        with pytest.raises(ValueError):
            build_prompt(**args)


@pytest.mark.parametrize("name", PRD)
def test_suggested_look_renders(name):
    look, shadow = suggested_look(name)
    p = render_title(Glyphs(text="AB", size=80), look, shadow, 300, 160)
    assert p["face"].sum() > 100


@pytest.mark.parametrize("name", PRD)
def test_flux3_prompt_follows_skill(name):
    pos, neg = build_prompt(name, "BADD ASS", target="flux3")
    assert neg == "" and not NEGATION.search(pos)
    assert pos.startswith("A bright")                                  # layer 1: image type
    assert 'The title reads "BADD ASS"' in pos and "centred" in pos    # quoted text + placement, front-loaded
    assert pos.index("BADD ASS") < pos.index(PRESETS[name].material)
    assert "image 1" in pos and "keeps the exact" in pos               # preserve list against image 1
    for filler in ("8K", "masterpiece", "best quality"):
        assert filler not in pos
    assert 30 <= len(pos.split()) <= 120


def test_flux3_settings_only_valid_native_fields():
    for final in (True, False):
        s = flux3_settings(final)
        assert set(s) <= set(FLUX3_FIELDS)
        assert not set(s) & {"seed", "guidance", "steps", "width", "height", "negative_prompt", "mode"}
    assert flux3_settings()["aspect_ratio"] == "auto" and flux3_settings(False)["resolution"] == "1k"
