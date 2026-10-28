"""Cutout demo: big blocky letters with one picture or video inside and another outside.

  1  video inside, still outside:  the Ben-Day clip plays inside "WILD", a sunset sky outside, white stroke
  2  animated mask + shading:      letters pop in; a plasma video fills them, lit by the rig (extrusion reads darker)
  3  transparent cutout:           silhouette + shadow mask, no outside (checkerboard shows the alpha)

Writes examples/out/cutout_demo.gif (+ .mp4) and docs/media/cutout.gif. Needs docs/media/ben_day_beat.mp4
(python examples/hero_clips.py). Run: python examples/cutout_demo.py"""
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.animate import Anim, Track, render_frames  # noqa: E402
from render.cutout import cutout  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
W, H, FPS, N = 640, 300, 24.0, 72
FLAT = Look3D(face="#ffffff", face2=None, extrude=0, bevel=0, bevel_profile="flat")


def read_video(path, n, size=(W, H)):
    cap = cv2.VideoCapture(path)
    frames = []
    while len(frames) < n:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2RGB), size).astype(np.float32) / 255)
    return np.stack(frames)


def sky(w=W, h=H):
    """A procedural sunset still: gradient, sun, soft cloud bands."""
    y = np.linspace(0, 1, h)[:, None, None]
    x = np.linspace(0, 1, w)[None, :, None]
    top, mid, low = np.array([0.15, 0.2, 0.55]), np.array([0.98, 0.45, 0.45]), np.array([1.0, 0.8, 0.35])
    g = np.where(y < 0.6, top + (mid - top) * (y / 0.6), mid + (low - mid) * ((y - 0.6) / 0.4))
    sun = np.exp(-(((x - 0.72) * w / h) ** 2 + (y - 0.62) ** 2) / 0.012)[..., 0:1]
    clouds = 0.12 * np.sin(x * 9 + np.sin(y * 13) * 2) * np.exp(-((y - 0.35) ** 2) / 0.02)
    return np.clip(g * np.ones((h, w, 3)) + sun * np.array([1, 0.95, 0.7]) * 0.8 + clouds, 0, 1)[None].astype(np.float32)


def plasma(n, w=W, h=H):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) / 60
    out = np.empty((n, h, w, 3), np.float32)
    for f in range(n):
        t = f / n * 2 * np.pi
        v = np.sin(xx + t) + np.sin(yy * 0.8 - t) + np.sin((xx + yy) * 0.6 + 2 * t)
        out[f] = 0.5 + 0.5 * np.stack([np.sin(v), np.sin(v + 2.1), np.sin(v + 4.2)], -1)
    return out


def checker(h=H, w=W):
    yy, xx = np.mgrid[0:h, 0:w]
    return np.where(((yy // 12) + (xx // 12)) % 2 == 0, 0.28, 0.36).astype(np.float32)[..., None]


rows = []
# 1 — video inside, still outside
mask = render_title(Glyphs(text="WILD", font="Anton", size=260, tracking=10), FLAT, Shadow(on=False), W, H,
                    Layout())["alpha"]
ben = read_video(os.path.join(ROOT, "docs", "media", "ben_day_beat.mp4"), N)
rgb, _ = cutout(ben, mask, outside=sky(), stroke=4, stroke_color=(1, 1, 1))
rows.append(("video inside · sunset outside · 4 px stroke", rgb))

# 2 — animated mask with the rig's lighting on the inside
anim = Anim([Track(effect="pop", easing="back", duration=0.6, stagger=0.1)], fps=FPS, hold=2)
p = render_frames(anim, Glyphs(text="POP!", font="Anton", size=230, tracking=8),
                  Look3D(face="#ffffff", face2=None, extrude=22, bevel=6, side="#888888"), Shadow(on=False), W, H,
                  Layout(), passes=("beauty", "alpha"))
rgb, _ = cutout(plasma(N), p["alpha"][:N], outside=np.full((1, H, W, 3), 0.08, np.float32), beauty=p["beauty"][:N],
                shading=0.8, timing="hold")
rows.append(("animated mask · plasma inside · rig shading 0.8", rgb))

# 3 — silhouette + shadow, transparent
q = render_title(Glyphs(text="CUT", font="Anton", size=240, tracking=10), Look3D(extrude=18, bevel=0,
                 bevel_profile="flat"), Shadow(texture="halftone", length=26, texture_scale=6), W, H, Layout())
rgb, a = cutout(sky(), np.maximum(q["alpha"], q["shadow"]), feather=1.0)
rgb = rgb * a[..., None] + checker() * (1 - a[..., None])
rows.append(("silhouette + shadow · no outside = alpha cutout", np.repeat(rgb, N, 0)))

frames = []
for f in range(N):
    sheet = Image.new("RGB", (W, H * len(rows)))
    for r, (label, clip) in enumerate(rows):
        im = Image.fromarray((np.clip(clip[min(f, len(clip) - 1)], 0, 1) * 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        d.rectangle((6, 6, 12 + 6 * len(label), 22), fill=(0, 0, 0))
        d.text((10, 8), label, fill=(235, 235, 240))
        sheet.paste(im, (0, H * r))
    frames.append(sheet)
probe = Image.new("RGB", (W, H * len(rows) * 2))
probe.paste(frames[N // 3], (0, 0))
probe.paste(frames[-1], (0, H * len(rows)))
pal = probe.quantize(255, method=Image.Quantize.MEDIANCUT)
gif = [f.resize((480, int(480 * f.height / f.width)), Image.LANCZOS).quantize(palette=pal, dither=Image.Dither.NONE)
       for f in frames]
for path in (os.path.join(OUT, "cutout_demo.gif"), os.path.join(ROOT, "docs", "media", "cutout.gif")):
    gif[0].save(path, save_all=True, append_images=gif[1:], duration=round(1000 / FPS), loop=0, optimize=True)
if shutil.which("ffmpeg"):
    pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                           f"{W}x{H * len(rows)}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-crf", "20", "-movflags", "+faststart", os.path.join(OUT, "cutout_demo.mp4")],
                          stdin=subprocess.PIPE)
    for f in frames:
        pr.stdin.write(f.tobytes())
    pr.stdin.close()
    pr.wait()
print("wrote", OUT)
