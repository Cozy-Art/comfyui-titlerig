import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from render import Glyphs, render_title  # noqa: E402
from render.presets import (FLUX3_FIELDS, LTX_LOCAL_NEGATIVE, ltx_negative, flux3_settings, ltx23_settings, ltx_frames, EMBOSSED, PRESET_NAMES, PRESETS, TARGETS, build_prompt, flux2_settings,  # noqa: E402
                            flux2_structured, suggested_look)

PRD = ["Chrome Slam", "Fuzzy Grass", "Liquid Glass", "Aero Bubble", "Ben-Day Pop", "Holo Foil", "ChromaDepth",
       "Candy Inflatable", "Op Art Stripe", "Vapor Sunset", "Low Poly", "Cel Toon", "Trailer Title",
       "Shaggy Fur", "Cloud Puff"]
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
    assert ("extrusion" in pos) == (look.extrude > 0)      # flat presets never mention extrusion


@pytest.mark.parametrize("name", PRD)
@pytest.mark.parametrize("target", TARGETS)
def test_every_target_quotes_text_and_says_what_is_there(name, target):
    pos, neg = build_prompt(name, 'BADD "ASS"', target=target)
    assert "BADD" in pos and "ASS" in pos
    assert not NEGATION.search(pos), pos
    assert (neg == "") == (target != "ltx23_video")
    if target == "flux1_depth":
        assert "image 1" not in pos  # depth conditioning, no reference image


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


@pytest.mark.parametrize("name", PRD)
@pytest.mark.parametrize("audio", ("own_track", "generate"))
def test_ltx23_prompt_follows_skill(name, audio):
    pos, neg = build_prompt(name, "BADD ASS", target="ltx23_video", audio=audio)
    assert "\n" not in pos and 60 <= len(pos.split()) <= 180          # one paragraph, sweet-spot length
    assert '"BADD ASS"' in pos and "control video" in pos
    assert "camera stays locked" in pos                                 # prose agrees with camera_motion: static
    for setting in ("fps", "1080", "720p", "4K", "seconds", "dolly", "duration"):
        assert setting not in pos, setting                              # settings never in the prose
    assert (PRESETS[name].sound in pos) == (audio == "generate")
    assert neg == ltx_negative(name)                                    # the shipped default, not a pile-on
    assert neg == LTX_LOCAL_NEGATIVE or "cartoon" not in neg            # cartoon looks drop the contradiction


def test_ltx23_settings_and_frames():
    assert [ltx_frames(n) for n in (1, 2, 9, 10, 121, 192)] == [1, 9, 9, 17, 121, 193]
    s = ltx23_settings(192, 24, "own_track")
    assert s["local"]["frames"] == 193 and s["local"]["width"] % 32 == 0 and s["local"]["height"] % 32 == 0
    assert s["local"]["cfg_scale"] == 1.0 and s["local"]["steps"] == 8
    assert s["api"]["generate_audio"] is False and s["api"]["camera_motion"] == "static"
    assert s["api"]["duration"] in (6, 8, 10) and s["api"]["fps"] in (24, 25, 48, 50)
    assert not set(s["api"]) & {"negative_prompt", "seed", "aspect_ratio", "cfg_scale", "steps"}
    assert ltx23_settings(audio="generate")["api"]["generate_audio"] is True


def test_cartoon_presets_do_not_negate_their_own_style():
    assert "cartoon" not in ltx_negative("Cel Toon") and "cartoon" not in ltx_negative("Ben-Day Pop")
    assert ltx_negative("Chrome Slam") == LTX_LOCAL_NEGATIVE
    assert "cartoon" not in ltx23_settings(preset="Cel Toon")["local"]["negative_prompt"]


def test_presets_show_structural_variety():
    looks = {n: suggested_look(n) for n in PRD}
    flat_no_shadow = [n for n, (lk, sh) in looks.items() if lk.extrude == 0 and not sh.on]
    assert len(flat_no_shadow) >= 1
    assert any(lk.extrude == 0 and sh.on for lk, sh in looks.values())      # flat with a shadow
    assert any(lk.extrude > 0 and not sh.on for lk, sh in looks.values())   # extruded, no shadow
    assert len({lk.extrude for lk, _ in looks.values()}) >= 6               # many depths
    assert len({lk.extrude_angle for lk, _ in looks.values() if lk.extrude}) >= 4  # several directions
    for n in flat_no_shadow:
        p = render_title(Glyphs(text="AB", size=80), *looks[n], 300, 160)
        assert p["sides"].sum() == 0 and p["shadow"].sum() == 0


def test_pad_frames_holds_last_frame():
    import numpy as np
    from render.animate import pad_frames
    from render.presets import ltx_frames
    p = {"a": np.arange(10).reshape(10, 1).astype(np.float32), "b": np.zeros((10, 2, 2), np.float32)}
    q = pad_frames(p, ltx_frames(10))
    assert q["a"].shape[0] == 17 and q["b"].shape[0] == 17 and (q["a"][10:] == 9).all()
    assert pad_frames(p, 5)["a"].shape[0] == 10  # never trims


def test_recraft_vector_prompt_follows_model_skills_template():
    pos, neg = build_prompt("Chrome Slam", "TITLERIG", target="recraft_v4_vector")
    assert pos.startswith('Flat vector title lockup of the word "TITLERIG"') and neg == ""
    assert "Strict three-colour system" in pos and "48 pixels" in pos and "#" in pos
    flat, _ = build_prompt("Holo Foil", "TITLERIG", target="recraft_v4_vector")
    assert "extrusion" not in flat  # Holo Foil has no extrusion
