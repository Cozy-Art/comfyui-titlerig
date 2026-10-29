"""Preview the rig half of titlerig_ltx2_duo on CPU, straight from the workflow graph (no ComfyUI, no torch).

Builds the API graph with workflows/build_workflows.py, evaluates the TitleRig nodes that feed the two Render
Animation nodes (layer 1: the title, layer 2: the line underneath), then renders every frame at full size:
  top     both layers composited over the Cloud Puff sky (what LTX gets to paint)
  bottom  the two depth guides combined (each LTX pass sees only its own layer)
Writes docs/media/ltx2_duo_rig.gif and, with ffmpeg, docs/media/ltx2_duo_rig.mp4 with the track.
Run: python examples/duo_preview.py"""
import importlib.util
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "workflows"))
from build_workflows import ltx2_duo  # noqa: E402
from render.animate import render_frame  # noqa: E402
from render.audio import audio_curve, load_wav  # noqa: E402
from render.presets import PRESETS  # noqa: E402

MEDIA = os.path.join(ROOT, "docs", "media")
WAV = os.path.join(ROOT, "examples", "assets", "titlerig_beat.wav")
GIF_W = 480


def pack():
    """The node classes, imported as a package the way ComfyUI does (the wrappers import torch only to output)."""
    spec = importlib.util.spec_from_file_location("titlerig_pack", os.path.join(ROOT, "__init__.py"),
                                                  submodule_search_locations=[ROOT])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["titlerig_pack"] = mod
    spec.loader.exec_module(mod)
    return mod.NODE_CLASS_MAPPINGS


def evaluate(g, nid, nodes, memo):
    """Output tuple of node nid. LoadAudio and Audio React are done here (their wrappers hand torch tensors)."""
    if nid in memo:
        return memo[nid]
    n = g[nid]
    args = {k: evaluate(g, v[0], nodes, memo)[v[1]] if isinstance(v, list) and len(v) == 2 and v[0] in g else v
            for k, v in n["inputs"].items()}
    cls = n["class_type"]
    if cls == "LoadAudio":
        a, sr = load_wav(WAV)
        out = ({"waveform": a[None, None], "sample_rate": sr},)
    elif cls == "TitleRigAudioReact":
        au = args.pop("audio")
        args.pop("spectrum_bands", None)
        out = (audio_curve(au["waveform"], au["sample_rate"], **args),)
    else:
        obj = nodes[cls]()
        out = getattr(obj, obj.FUNCTION)(**args)
    memo[nid] = out
    return out


def main():
    g = ltx2_duo()
    nodes, memo = pack(), {}
    layers = []
    for rid in ("26", "126"):  # layer 1 (title), layer 2 (line)
        r = g[rid]["inputs"]
        get = lambda k: evaluate(g, r[k][0], nodes, memo)[r[k][1]]  # noqa: E731
        layers.append(dict(g=get("glyphs"), anim=get("anim"), look=get("look"), shadow=get("shadow"),
                           lay=get("layout"), W=r["width"], H=r["height"]))
    n = max(L["anim"].n_frames(sum(1 for c in L["g"].text if c.strip())) for L in layers)
    sky = np.array([int(PRESETS["Cloud Puff"].backdrop[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    frames, t0 = [], time.time()
    for f in range(n):
        p = [render_frame(L["anim"], L["g"], L["look"], L["shadow"], L["W"], L["H"], L["lay"], f,
                          ("beauty", "depth")) for L in layers]
        rgb = sky
        for q in p[::-1]:  # line first, title on top
            b = q["beauty"]
            rgb = rgb * (1 - b[..., 3:]) + b[..., :3] * b[..., 3:]
        d = np.maximum(p[0]["depth"], p[1]["depth"])
        d = np.repeat(d[..., None], 3, -1) if d.ndim == 2 else d[..., :3]
        im = Image.fromarray((np.clip(np.concatenate([rgb, d], 0), 0, 1) * 255).astype(np.uint8))
        frames.append(im)
    print(f"{n} frames in {time.time() - t0:.0f}s")
    os.makedirs(MEDIA, exist_ok=True)
    W, H = frames[0].size
    small = [im.resize((GIF_W, GIF_W * H // W), Image.LANCZOS) for im in frames]
    gif = os.path.join(MEDIA, "ltx2_duo_rig.gif")
    small[0].save(gif, save_all=True, append_images=small[1:], duration=round(1000 / layers[0]["anim"].fps), loop=0,
                  optimize=True)
    print("wrote", os.path.relpath(gif, ROOT))
    if shutil.which("ffmpeg"):
        mp4 = os.path.join(MEDIA, "ltx2_duo_rig.mp4")
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W // 2}x{H // 2}",
               "-r", str(layers[0]["anim"].fps), "-i", "-", "-i", WAV, "-t", f"{n / layers[0]['anim'].fps:.3f}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-c:a", "aac", "-shortest", mp4]
        raw = b"".join(np.asarray(im.resize((W // 2, H // 2), Image.LANCZOS)).tobytes() for im in frames)
        subprocess.run(cmd, input=raw, check=True)
        print("wrote", os.path.relpath(mp4, ROOT))


if __name__ == "__main__":
    main()
