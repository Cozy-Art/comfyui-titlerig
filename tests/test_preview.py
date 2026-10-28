"""Server side of the canvas preview: payload trees (as the web widget sends them) -> PNG."""
import importlib.util
import io
import os
import sys

import numpy as np
import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="module")
def pack():
    spec = importlib.util.spec_from_file_location("titlerig_pack_pv", os.path.join(ROOT, "__init__.py"),
                                                  submodule_search_locations=[ROOT])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["titlerig_pack_pv"] = mod
    spec.loader.exec_module(mod)
    return mod


def defaults(cls):
    out = {}
    for group in ("required", "optional"):
        for k, spec in cls.INPUT_TYPES().get(group, {}).items():
            if isinstance(spec[0], list):
                out[k] = spec[1].get("default", spec[0][0]) if len(spec) > 1 else spec[0][0]
            elif len(spec) > 1 and "default" in spec[1]:
                out[k] = spec[1]["default"]
    return out


def tree(pack, typ, inputs=None, **widgets):
    cls = pack.NODE_CLASS_MAPPINGS[typ]
    return {"type": typ, "widgets": {**defaults(cls), **widgets}, "inputs": inputs or {}}


def link(node, slot=0):
    return {"node": node, "slot": slot}


def run(pack, node, **kw):
    from titlerig_pack_pv.nodes.preview import preview
    png, info = preview({"node": node, **kw}, pack.NODE_CLASS_MAPPINGS)
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGB")), info


def test_render_preview_from_upstream_tree(pack):
    text = tree(pack, "TitleRigText", text="HELLO", size=120)
    node = tree(pack, "TitleRigRender", {"glyphs": link(text)}, width=1280, height=720)
    img, info = run(pack, node, max_width=480)
    assert img.shape == (270, 480, 3) and info["error"] == ""
    assert img.std() > 10  # a title, not an empty frame


def test_passes_guides_and_widget_changes_show(pack):
    text = tree(pack, "TitleRigText", text="AB", size=120)
    node = tree(pack, "TitleRigRender", {"glyphs": link(text)}, width=640, height=360)
    beauty, _ = run(pack, node, max_width=320)
    depth, _ = run(pack, node, max_width=320, **{"pass": "depth"})
    guided, _ = run(pack, node, max_width=320, guides=True)
    assert not np.array_equal(beauty, depth) and not np.array_equal(beauty, guided)
    text2 = tree(pack, "TitleRigText", text="AB", size=120, tracking=60)
    wider, _ = run(pack, tree(pack, "TitleRigRender", {"glyphs": link(text2)}, width=640, height=360), max_width=320)
    assert not np.array_equal(beauty, wider)


def test_look_layout_and_style_preset_feed_through(pack):
    text = tree(pack, "TitleRigText", text="ARC", size=120)
    preset = tree(pack, "TitleRigStylePreset", preset="Op Art Stripe")
    lay = tree(pack, "TitleRigLayout", mode="arc", bend=0.6)
    plain, _ = run(pack, tree(pack, "TitleRigRender", {"glyphs": link(text)}, width=640, height=360))
    styled, _ = run(pack, tree(pack, "TitleRigRender", {"glyphs": link(text), "look": link(preset, 2),
                                                        "shadow": link(preset, 3), "layout": link(lay)},
                               width=640, height=360))
    assert np.abs(plain.astype(int) - styled.astype(int)).mean() > 3


def test_animation_frames_scrub_and_audio_tracks_are_skipped(pack):
    text = tree(pack, "TitleRigText", text="POP", size=120)
    pop = tree(pack, "TitleRigAnimate", effect="pop", duration=0.5, fps=12.0)
    audio = {"type": "LoadAudio", "widgets": {"audio": "x.wav"}, "inputs": {}}
    react = tree(pack, "TitleRigAudioReact", {"audio": link(audio)})
    driven = tree(pack, "TitleRigAnimate", {"anim": link(pop), "drive": link(react)}, effect="drop")
    node = tree(pack, "TitleRigRenderAnimation", {"glyphs": link(text), "anim": link(driven)}, width=640, height=360)
    f0, info = run(pack, node, frame=0)
    f9, _ = run(pack, node, frame=9)
    assert info["frame_count"] > 9 and info["fps"] == 12.0
    assert not np.array_equal(f0, f9)  # the time-based pop still plays; the audio-driven drop is left out
    late, _ = run(pack, node, frame=10_000)  # clamped to the last frame
    assert late.shape == f0.shape


def test_missing_glyphs_and_bad_json_do_not_crash(pack):
    img, info = run(pack, tree(pack, "TitleRigRender", width=640, height=360), max_width=320)
    assert "connect" in info["error"] and img.shape == (180, 320, 3)
    text = tree(pack, "TitleRigText", text="OK", letters_json="{not json")
    img, info = run(pack, tree(pack, "TitleRigRender", {"glyphs": link(text)}, width=640, height=360))
    assert "connect" in info["error"]  # the broken node is treated as unresolved, not a 500
