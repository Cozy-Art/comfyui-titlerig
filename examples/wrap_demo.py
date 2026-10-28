"""Wraps demo: spinning ticker, globe and cube (seamless loops). Writes examples/out/wrap_demo.gif (+ .mp4).
Run: python examples/wrap_demo.py"""
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow  # noqa: E402
from render.animate import Anim, Track, render_frames  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
W, H, FPS, N = 640, 240, 24.0, 96
BG = np.array([0.09, 0.08, 0.13])
FLAT = dict(bevel=0, bevel_profile="flat")
ROWS = [
    ("ticker · wrap_spin loop · text repeats around the band",
     Glyphs(text="BREAKING TITLES", size=80, tracking=3), Layout(mode="ticker", wrap_radius=0.27),
     Look3D(face="#fde68a", face2="#fb923c", side="#9a3412", extrude=8, **FLAT), Shadow(on=False)),
    ("sphere · globe tilted 15° · wrap_spin loop",
     Glyphs(text="WORLDWIDE", size=72, tracking=4), Layout(mode="sphere", wrap_radius=0.46, wrap_tilt=15),
     Look3D(face="#7dd3fc", face2="#2563eb", side="#1e3a8a", extrude=6, **FLAT), Shadow(on=False)),
    ("cube · one word per face · wrap_spin loop",
     Glyphs(text="CUBE", size=84, tracking=4), Layout(mode="cube", wrap_radius=0.2),
     Look3D(face="#ff8fd8", face2="#a78bfa", side="#7c3aed", extrude=6, **FLAT), Shadow(on=False)),
]
rows = []
for label, g, lay, look, sh in ROWS:
    spin = Track(effect="wrap_spin", direction="loop", easing="linear", duration=N / FPS, stagger=0,
                 amount=-360 if lay.mode != "cube" else -360)
    fr = render_frames(Anim([spin], fps=FPS, hold=0), g, look, sh, W, H, lay, passes=("beauty",))["beauty"][:N]
    imgs = []
    for a in fr:
        rgb = a[..., :3] * a[..., 3:] + BG * (1 - a[..., 3:])
        im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
        ImageDraw.Draw(im).text((10, 8), label, fill=(210, 210, 225))
        imgs.append(im)
    rows.append(imgs)
frames = []
for f in range(N):
    s = Image.new("RGB", (W, H * len(rows)))
    for r, imgs in enumerate(rows):
        s.paste(imgs[f], (0, H * r))
    frames.append(s)
gif = [f.resize((480, int(480 * f.height / f.width)), Image.LANCZOS).quantize(
    255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
gif[0].save(os.path.join(OUT, "wrap_demo.gif"), save_all=True, append_images=gif[1:], duration=int(1000 / FPS),
            loop=0, optimize=True)
if shutil.which("ffmpeg"):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{W}x{H * len(rows)}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "20", "-movflags", "+faststart", os.path.join(OUT, "wrap_demo.mp4")],
                         stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()
print("wrote", OUT)
