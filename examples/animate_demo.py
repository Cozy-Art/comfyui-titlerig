"""Render one GIF cell per Animate effect and tile them into examples/out/animate_grid.gif.
Run: python examples/animate_demo.py"""
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow  # noqa: E402
from render.animate import Anim, Track, render_frames  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
W, H, FPS, N = 480, 220, 15, 36  # every cell loops on the same 36-frame clock

CELLS = [
    ("pop · back · center_out", Track(effect="pop", easing="back", duration=0.5, stagger=0.07, order="center_out"),
     Layout(), Look3D()),
    ("drop · bounce", Track(effect="drop", easing="bounce", duration=0.8, stagger=0.08, amount=260), Layout(),
     Look3D(face="#7dd3fc", face2="#2563eb", side="#1e3a8a")),
    ("flip X · elastic", Track(effect="flip_x", easing="elastic", duration=0.9, stagger=0.06), Layout(),
     Look3D(face="#ff8fd8", face2="#a78bfa", side="#7c3aed", bevel=8)),
    ("spin Y · in_out · reverse", Track(effect="spin_y", easing="in_out", duration=0.8, stagger=0.07, order="reverse"),
     Layout(), Look3D(face="#f4f6fb", face2="#7a869a", side="#3b4252", gloss=1.0, rim=0.5)),
    ("roll Z · back · edges_in", Track(effect="roll_z", easing="back", duration=0.6, stagger=0.06, order="edges_in"),
     Layout(mode="arc", bend=0.35), Look3D(face="#bef264", face2="#16a34a", side="#14532d")),
    ("slide word · back + flag wave", Track(effect="slide", target="word", easing="back", duration=0.7, amount=520),
     Layout(flag_amp=9, flag_wavelength=200), Look3D(face="#ffd400", face2=None, side="#e11d48", bevel=4)),
]


def cell(label, track, lay, look):
    tracks = [track]
    if lay.flag_amp:
        tracks.append(Track(effect="wave", direction="loop", easing="linear", duration=N / FPS, stagger=0))
    anim = Anim(tracks, fps=FPS)
    fr = render_frames(anim, Glyphs(text="TITLE", font="Anton", size=110, tracking=4), look,
                       Shadow(texture="halftone", length=18, texture_scale=6), W, H, lay, passes=("beauty",))["beauty"]
    if len(fr) < N:  # hold the rest pose to the common length
        fr = np.concatenate([fr, np.repeat(fr[-1:], N - len(fr), 0)])
    rgb = fr[:N, ..., :3] * fr[:N, ..., 3:] + 0.11 * (1 - fr[:N, ..., 3:])
    imgs = []
    for a in rgb:
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        ImageDraw.Draw(im).text((10, 8), label, fill=(225, 225, 235))
        imgs.append(im)
    return imgs


t0 = time.time()
cells = [cell(*c) for c in CELLS]
cols = 2
rows = (len(cells) + cols - 1) // cols
frames = []
for f in range(N):
    sheet = Image.new("RGB", (W * cols, H * rows), (20, 20, 24))
    for i, c in enumerate(cells):
        sheet.paste(c[f], (W * (i % cols), H * (i // cols)))
    frames.append(sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
frames[0].save(os.path.join(OUT, "animate_grid.gif"), save_all=True, append_images=frames[1:],
               duration=int(1000 / FPS), loop=0, optimize=True)
print(f"wrote {OUT}/animate_grid.gif in {time.time() - t0:.1f}s")
