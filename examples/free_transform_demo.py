"""Free transform (skew, taper, corner pin) on letters, groups and words, still and driven by sound.

Writes examples/out/free_transform_sheet.png and free_transform_audio.gif (+ .mp4 with sound if ffmpeg exists).
Run: python examples/free_transform_demo.py"""
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.animate import Anim, Track, render_frames  # noqa: E402
from render.audio import audio_curve, load_wav  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
BG = np.array([0.09, 0.08, 0.13])
LOOK = Look3D(face="#fde68a", face2="#fb923c", side="#9a3412", bevel=8, extrude=20)
SH = Shadow(texture="halftone", color="#0f172a", length=20, texture_scale=7)


def show(a, label):
    rgb = a[..., :3] * a[..., 3:] + BG * (1 - a[..., 3:])
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    ImageDraw.Draw(im).text((12, 10), label, fill=(225, 225, 235))
    return im


STILLS = [
    ("word taper_x +0.45 (keystone)", Glyphs(text="TAPER", size=120, word={"taper_x": 0.45})),
    ("word taper_x -0.45 (flare)", Glyphs(text="FLARE", size=120, word={"taper_x": -0.45})),
    ("word skew_x 18", Glyphs(text="SKEW", size=120, word={"skew_x": 18})),
    ("letters taper_y alternating", Glyphs(text="ZIGZAG", size=120,
                                           letters={i: {"taper_y": 0.35 if i % 2 else -0.35} for i in range(6)})),
    ("corner pin, one letter (the P)", Glyphs(text="PIN IT", size=120,
                                              letters={0: {"corners": [[-20, -30], [40, -10], [10, 20], [-10, 0]]}})),
    ("word corner pin + arc", Glyphs(text="FREE", size=120, word={"corners": [[-60, 0], [60, -30], [30, 20], [-30, 10]]})),
]
tiles = []
for i, (label, g) in enumerate(STILLS):
    lay = Layout(mode="arc", bend=0.3) if "arc" in label else Layout()
    tiles.append(show(render_title(g, LOOK, SH, 640, 300, lay, guides="none")["beauty"], label))
sheet = Image.new("RGB", (1280, 300 * 3))
for i, t in enumerate(tiles):
    sheet.paste(t, (640 * (i % 2), 300 * (i // 2)))
sheet.save(os.path.join(OUT, "free_transform_sheet.png"))

# sound-driven: kicks keystone TAPER (spring), hats skew SKEW, snares corner-pin PIN as a rigid group
WAV = os.path.join(HERE, "assets", "titlerig_beat.wav")
mono, sr = load_wav(WAV)
FPS = 24.0
kick = audio_curve(mono, sr, FPS, band="bass", release=0.18)
hat = audio_curve(mono, sr, FPS, band="highs", sensitivity=0.15, release=0.12)
snare = audio_curve(mono, sr, FPS, band="mids", sensitivity=0.05, release=0.35)
anim = Anim([
    Track(effect="taper_x", target="word", letters="word:1", drive=kick["values"], response="trigger",
          easing="spring", direction="in", duration=0.45, amount=55, retrigger="layer"),
    Track(effect="skew_x", target="word", letters="word:2", drive=hat["values"], amount=-22, influence=0.9),
    Track(effect="corner_pin", target="word", letters="word:3", drive=snare["values"], amount=100,
          corners=[[-30, -40], [30, -40], [0, 0], [0, 0]]),
], fps=FPS)
fr = render_frames(anim, Glyphs(text="TAPER SKEW PIN", size=80, tracking=3), LOOK, SH, 640, 360, Layout(),
                   passes=("beauty",))["beauty"]
imgs = [show(a, "kicks taper TAPER (spring)   hats skew SKEW   snares pin PIN") for a in fr]
gif = [im.resize((480, 270), Image.LANCZOS).quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
       for im in imgs[:96]]
gif[0].save(os.path.join(OUT, "free_transform_audio.gif"), save_all=True, append_images=gif[1:],
            duration=int(1000 / FPS), loop=0, optimize=True)
if shutil.which("ffmpeg"):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "640x360",
                          "-r", str(FPS), "-i", "-", "-i", WAV, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                          "-c:a", "aac", "-shortest", "-movflags", "+faststart",
                          os.path.join(OUT, "free_transform_audio.mp4")], stdin=subprocess.PIPE)
    for im in imgs:
        p.stdin.write(im.tobytes())
    p.stdin.close()
    p.wait()
print("wrote", OUT)
