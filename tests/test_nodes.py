"""Node wrappers: loaded as a package exactly like ComfyUI does. Torch-dependent renders skip without torch."""
import importlib.util
import inspect
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="module")
def pack():
    spec = importlib.util.spec_from_file_location("titlerig_pack", os.path.join(ROOT, "__init__.py"),
                                                  submodule_search_locations=[ROOT])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["titlerig_pack"] = mod
    spec.loader.exec_module(mod)
    assert mod.NODE_CLASS_MAPPINGS, "nodes failed to import"
    return mod


def _defaults(cls):
    out = {}
    for group in ("required", "optional"):
        for k, spec in cls.INPUT_TYPES().get(group, {}).items():
            if isinstance(spec[0], list):
                out[k] = spec[1]["default"] if len(spec) > 1 and "default" in spec[1] else spec[0][0]
            elif len(spec) > 1 and "default" in spec[1]:
                out[k] = spec[1]["default"]
    return out


def test_inputs_match_function_signatures(pack):
    for name, cls in pack.NODE_CLASS_MAPPINGS.items():
        fn = getattr(cls, cls.FUNCTION)
        params = set(inspect.signature(fn).parameters) - {"self"}
        inputs = set(cls.INPUT_TYPES()["required"]) | set(cls.INPUT_TYPES().get("optional", {}))
        assert inputs == params, name
        assert len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES), name
        assert name in pack.NODE_DISPLAY_NAME_MAPPINGS


def test_builder_nodes_with_defaults(pack):
    m = pack.NODE_CLASS_MAPPINGS
    for name in ("TitleRigText", "TitleRigLook3D", "TitleRigShadow", "TitleRigLayout", "TitleRigAnimate",
                 "TitleRigStylePreset", "TitleRigMagnet"):
        out = getattr(m[name](), m[name].FUNCTION)(**_defaults(m[name]))
        assert len(out) == len(m[name].RETURN_TYPES) and out[0] is not None


def test_animate_chains_and_takes_drive(pack):
    import numpy as np
    A = pack.NODE_CLASS_MAPPINGS["TitleRigAnimate"]
    kw = _defaults(A)
    (a1,) = A().build(**{**kw, "effect": "drop"})
    (a2,) = A().build(**{**kw, "effect": "pop", "anim": a1, "drive": {"values": np.ones(10), "fps": 12.0}})
    assert [t.effect for t in a2.tracks] == ["drop", "pop"] and a2.fps == 12.0
    assert a2.tracks[0].drive is None and len(a2.tracks[1].drive) == 10


def test_render_nodes_return_tensors(pack):
    torch = pytest.importorskip("torch")
    m = pack.NODE_CLASS_MAPPINGS
    (g,) = m["TitleRigText"]().build(text="AB", font="Anton", size=60, tracking=0)
    out = m["TitleRigRender"]().render(g, 160, 96)
    assert out[0].shape == (1, 96, 160, 3) and out[1].shape == (1, 96, 160)
    (a,) = m["TitleRigAnimate"]().build(**{**_defaults(m["TitleRigAnimate"]), "fps": 8.0, "duration": 0.25})
    o = m["TitleRigRenderAnimation"]().render(g, a, 160, 96)
    assert o[0].shape[1:] == (96, 160, 3) and o[0].shape[0] == o[5] > 1 and isinstance(o[0], torch.Tensor)


def test_audio_react_node_drives_animate(pack):
    pytest.importorskip("torch")
    import numpy as np
    from render.audio import synth_beat  # noqa: E402
    mono, _ = synth_beat(2.0, 120, 22050)
    m = pack.NODE_CLASS_MAPPINGS
    kw = _defaults(m["TitleRigAudioReact"])
    curve, prev, n, onsets = m["TitleRigAudioReact"]().analyse(audio={"waveform": mono[None, None], "sample_rate": 22050}, **kw)
    assert n == 48 and prev.shape[0] == 1 and onsets
    (a,) = m["TitleRigAnimate"]().build(**{**_defaults(m["TitleRigAnimate"]), "drive": curve})
    assert a.n_frames(3) == 48 and np.allclose(a.tracks[0].drive, curve["values"])


def test_magnet_node_chains_after_animate(pack):
    m = pack.NODE_CLASS_MAPPINGS
    (a,) = m["TitleRigAnimate"]().build(**_defaults(m["TitleRigAnimate"]))
    (b,) = m["TitleRigMagnet"]().build(**{**_defaults(m["TitleRigMagnet"]), "anim": a, "magnet_text": "M"})
    assert len(b.tracks) == 1 and len(b.magnets) == 1 and b.magnets[0].text == "M"


def test_svg_export_node_writes_file(pack, tmp_path, monkeypatch):
    import types
    fp = types.ModuleType("folder_paths")
    fp.get_output_directory = lambda: str(tmp_path)

    def save_path(prefix, out, w, h):
        d = os.path.join(out, os.path.dirname(prefix))
        os.makedirs(d, exist_ok=True)
        return d, os.path.basename(prefix), 1, os.path.dirname(prefix), prefix

    fp.get_save_image_path = save_path
    monkeypatch.setitem(sys.modules, "folder_paths", fp)
    m = pack.NODE_CLASS_MAPPINGS
    (g,) = m["TitleRigText"]().build(text="AB", font="Anton", size=60, tracking=0)
    res = m["TitleRigSVGExport"]().export(g, 200, 120, "titlerig/t", 1, 3, "")
    svg, path = res["result"]
    assert svg.startswith("<svg") and os.path.isfile(path) and open(path).read() == svg
