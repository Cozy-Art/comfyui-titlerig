"""Spell-Lock demo: a painted rig clip with simulated AI drift (wobbling letterforms, a stray stroke, a dropped
chunk), then Spell-Lock with the rig's alpha. Writes examples/out/spell_lock_demo.mp4 / .gif and a still sheet.
Run: python examples/spell_lock_demo.py"""
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow  # noqa: E402
from render.animate import Anim, Track, render_frames  # noqa: E402
from render.presets import PRESETS, suggested_look  # noqa: E402
from render.spell_lock import spell_lock_batch  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
W, H, FPS, N = 480, 200, 24.0, 48
look, shadow = suggested_look("Cel Toon")
bg = np.array([int(PRESETS["Cel Toon"].backdrop[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
anim = Anim([Track(effect="drop", easing="bounce", duration=0.8, stagger=0.06, amount=120)], fps=FPS, hold=1.2)
rig = render_frames(anim, Glyphs(text="SPELLED", size=96, tracking=4), look, shadow, W, H, Layout(),
                    passes=("beauty", "alpha", "edges", "shadow"))
rig = {k: v[:N] for k, v in rig.items()}
rng = np.random.default_rng(4)


def ai_paint(beauty, f):
    """Stand-in for an AI pass: painterly texture + per-frame elastic drift + misspelling damage."""
    rgb = beauty[..., :3] * beauty[..., 3:] + bg * (1 - beauty[..., 3:])
    rgb = cv2.stylization((rgb * 255).astype(np.uint8), sigma_s=20, sigma_r=0.25).astype(np.float32) / 255
    t = f / FPS
    dx = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 9) * 60 * (0.6 + 0.4 * np.sin(t * 9))
    dy = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 9) * 60
    mx, my = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    rgb = cv2.remap(rgb, (mx + dx).astype(np.float32), (my + dy).astype(np.float32), cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT)
    a = rig["alpha"][f]
    ys, xs = np.nonzero(a > 0.5)
    if len(xs) and f > 20:  # an extra bar after the last letter and a chunk missing from the second
        face = np.median(rgb[a > 0.5], axis=0)
        rgb[ys.min() + 8:ys.max() - 6, xs.max() + 5:xs.max() + 15] = face
        cx = int(np.percentile(xs, 22))
        rgb[int(ys.mean()) - 10:int(ys.mean()) + 10, cx - 6:cx + 6] = bg
    return np.clip(rgb, 0, 1)


ai = np.stack([ai_paint(rig["beauty"][f], f) for f in range(N)])
res = spell_lock_batch(ai, rig["alpha"], rig["edges"], shadow=rig["shadow"])
print("drift before %.3f  after %.3f" % (np.mean(res["drift_before"]), np.mean(res["drift_after"])))


def tile(img, label, val=None):
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.text((8, 6), label + (f"   drift {val:.3f}" if val is not None else ""), fill=(20, 20, 28))
    return im


frames = []
for f in range(N):
    rgb_rig = rig["beauty"][f][..., :3] * rig["beauty"][f][..., 3:] + bg * (1 - rig["beauty"][f][..., 3:])
    fixed = res["frames"][f]
    overlay = fixed * 0.55 + np.dstack([res["fix_masks"][f], np.zeros((H, W)), res["fix_masks"][f] * 0.6]) * 0.45
    row = [tile(rgb_rig, "rig"), tile(ai[f], "AI pass (simulated drift)", res["drift_before"][f]),
           tile(fixed, "Spell-Lock", res["drift_after"][f]), tile(np.clip(overlay, 0, 1), "what was fixed")]
    s = Image.new("RGB", (W * 2, H * 2))
    for i, t in enumerate(row):
        s.paste(t, (W * (i % 2), H * (i // 2)))
    frames.append(s)
frames[-1].save(os.path.join(OUT, "spell_lock_sheet.png"))
gif = [f.quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
gif[0].save(os.path.join(OUT, "spell_lock_demo.gif"), save_all=True, append_images=gif[1:], duration=int(1000 / FPS),
            loop=0, optimize=True)
if shutil.which("ffmpeg"):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{W * 2}x{H * 2}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "18", "-movflags", "+faststart", os.path.join(OUT, "spell_lock_demo.mp4")],
                         stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()
print("wrote", OUT)
