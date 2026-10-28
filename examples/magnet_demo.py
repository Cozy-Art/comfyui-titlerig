"""Magnet demo: repel sweep with a magnet word, springy attract orbit, and a kick-driven repel blast.
Writes examples/out/magnet_demo.gif (+ .mp4). Run: python examples/magnet_demo.py"""
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow  # noqa: E402
from render.animate import Anim, render_frames  # noqa: E402
from render.audio import audio_curve, load_wav  # noqa: E402
from render.magnet import Magnet  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
W, H, FPS, N = 640, 220, 24.0, 96
BG = np.array([0.09, 0.08, 0.13])
mono, sr = load_wav(os.path.join(HERE, "assets", "titlerig_beat.wav"))
kick = audio_curve(mono, sr, FPS, band="bass", release=0.2, max_seconds=N / FPS)

ROWS = [
    ("repel · magnet word sweeps through · spring 0.6 · squash 0.7",
     Glyphs(text="REPEL ME", size=96, tracking=4),
     Look3D(face="#fde68a", face2="#fb923c", side="#9a3412", extrude=14, bevel=0, bevel_profile="flat"),
     Magnet(polarity="repel", strength=70, range=170, lag=0.12, spring=0.6, squash=0.7, x=-0.1, x_end=1.1,
            y=0.66, y_end=0.66, duration=N / FPS, text="MAGNET", size=40)),
    ("attract · orbit · spring 0.9 (bouncy)",
     Glyphs(text="ATTRACT", size=96, tracking=6),
     Look3D(face="#bef264", face2="#22d3ee", side="#0f766e", extrude=10, bevel=0, bevel_profile="flat"),
     Magnet(polarity="attract", strength=60, range=200, lag=0.2, spring=0.9, squash=0.5, path="orbit",
            x=0.5, y=0.5, radius=0.55, duration=N / FPS)),
    ("repel · fixed centre · strength driven by kicks",
     Glyphs(text="KICK BLAST", size=96, tracking=4),
     Look3D(face="#ff8fd8", face2="#a78bfa", side="#7c3aed", extrude=12, bevel=0, bevel_profile="flat"),
     Magnet(polarity="repel", strength=110, range=260, lag=0.08, spring=0.7, squash=0.6, path="fixed",
            x=0.5, y=0.5, drive=kick["values"])),
]
rows = []
for label, g, look, mg in ROWS:
    fr = render_frames(Anim(magnets=[mg], fps=FPS, hold=0), g, look, Shadow(on=False), W, H, Layout(),
                       passes=("beauty",))["beauty"][:N]
    if len(fr) < N:
        fr = np.concatenate([fr, np.repeat(fr[-1:], N - len(fr), 0)])
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
gif[0].save(os.path.join(OUT, "magnet_demo.gif"), save_all=True, append_images=gif[1:], duration=int(1000 / FPS),
            loop=0, optimize=True)
if shutil.which("ffmpeg"):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{W}x{H * len(rows)}", "-r", str(FPS), "-i", "-", "-i",
                          os.path.join(HERE, "assets", "titlerig_beat.wav"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "20", "-c:a", "aac", "-shortest", "-movflags", "+faststart",
                          os.path.join(OUT, "magnet_demo.mp4")], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()
print("wrote", OUT)
