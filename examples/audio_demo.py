"""Hero demo: audio-reactive titles. Writes examples/assets/titlerig_beat.wav (synthesised, no samples) and:

  audio_react.gif / .mp4     BASS rides the kicks, TREBLE rides the hats, the snare rocks TREBLE as a group,
                             kicks throw the shadow
  audio_spectrum.gif / .mp4  spectrum mode: the letters are an EQ, lows on the left, highs on the right
  audio_easings.gif / .mp4   trigger response: every kick replays an easing (bounce / elastic / spring)

MP4s (with sound) need ffmpeg. Run: python examples/audio_demo.py"""
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow  # noqa: E402
from render.animate import Anim, Track, render_frames  # noqa: E402
from render.audio import audio_curve, load_wav, save_wav, synth_beat  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
WAV = os.path.join(HERE, "assets", "titlerig_beat.wav")
os.makedirs(OUT, exist_ok=True)
FPS, W, H, SR = 24.0, 640, 360, 22050

if not os.path.exists(WAV):
    save_wav(WAV, synth_beat(8.0, 120, SR, arp=True)[0] * 0.75, SR)
mono, sr = load_wav(WAV)
BG = np.array([0.09, 0.08, 0.13])


def write(name, frames, strips, caption):
    """frames: (N,H,W,4) beauty. strips: [(curve values (n,), rgb)] drawn under a playhead (demo overlay only)."""
    imgs = []
    for i, a in enumerate(frames):
        rgb = a[..., :3] * a[..., 3:] + BG * (1 - a[..., 3:])
        im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        n = len(frames)
        for k, (vals, col) in enumerate(strips):
            y0 = H - 14 - 14 * (len(strips) - k)
            d.line([(x, y0 + 12 - vals[min(int(x / (W - 1) * (n - 1)), len(vals) - 1)] * 12) for x in range(0, W, 2)],
                   fill=col, width=1)
        x = i / (n - 1) * (W - 1)
        d.line([(x, H - 16 - 14 * len(strips)), (x, H - 2)], fill=(255, 255, 255))
        d.text((10, 8), caption, fill=(200, 200, 215))
        imgs.append(im)
    gif = [im.resize((480, 270), Image.LANCZOS).quantize(colors=255, method=Image.Quantize.MEDIANCUT,
                                                          dither=Image.Dither.NONE) for im in imgs[:96]]
    gif[0].save(os.path.join(OUT, f"{name}.gif"), save_all=True, append_images=gif[1:], duration=int(1000 / FPS),
                loop=0, optimize=True)
    if shutil.which("ffmpeg"):
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                              f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", WAV, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                              "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                              os.path.join(OUT, f"{name}.mp4")], stdin=subprocess.PIPE)
        for im in imgs:
            p.stdin.write(im.tobytes())
        p.stdin.close()
        p.wait()


# 1 — routing: each word gets its own part of the sound, plus an influence dial per track
kick = audio_curve(mono, sr, FPS, band="bass", mode="beats", sensitivity=0.5, release=0.18)
hat = audio_curve(mono, sr, FPS, band="highs", mode="beats", sensitivity=0.15, release=0.12)
snare = audio_curve(mono, sr, FPS, band="mids", mode="beats", sensitivity=0.05, attack=0.02, release=0.35)
anim = Anim([
    Track(effect="pop", drive=kick["values"], amount=-40, letters="word:1", stagger=1 / FPS, order="center_out"),
    Track(effect="drop", drive=hat["values"], amount=34, letters="word:2", stagger=1 / FPS, influence=0.8),
    Track(effect="roll_z", target="word", letters="word:2", drive=snare["values"], amount=-9),
    Track(effect="shadow_length", drive=kick["values"], amount=40),
    Track(effect="shadow_angle", drive=snare["values"], amount=-25, influence=0.6),
], fps=FPS)
t0 = time.time()
fr = render_frames(anim, Glyphs(text="BASS TREBLE", font="Anton", size=104, tracking=3),
                   Look3D(face="#ff8fd8", face2="#ffd400", side="#7c3aed", bevel=9, extrude=20, gloss=0.9, rim=0.4),
                   Shadow(texture="halftone", color="#38bdf8", length=14, texture_scale=7),
                   W, H, Layout(mode="arc", bend=0.18), passes=("beauty",))["beauty"]
write("audio_react", fr, [(kick["values"], (255, 207, 46)), (hat["values"], (56, 189, 248)),
                          (snare["values"], (143, 145, 255))],
      "BASS <- kicks   TREBLE <- hats   snare rocks TREBLE   kicks throw the shadow")
print(f"routing: {len(fr)} frames {time.time() - t0:.1f}s; kicks {len(kick['onsets'])} hats {len(hat['onsets'])} "
      f"snares {len(snare['onsets'])}")

# 2 — spectrum: the letters are an equaliser
spec = audio_curve(mono, sr, FPS, band="full", mode="spectrum", bands=9, attack=0.0, release=0.12)
anim = Anim([Track(effect="squash", drive=spec["values"], amount=-45, stagger=0),
             Track(effect="drop", drive=spec["values"], amount=30, stagger=0)], fps=FPS)
t0 = time.time()
fr = render_frames(anim, Glyphs(text="EQUALIZER", font="Anton", size=88, tracking=8),
                   Look3D(face="#bef264", face2="#22d3ee", side="#0f766e", bevel=8, extrude=18),
                   Shadow(texture="stripes", color="#f472b6", length=18, texture_scale=6), W, H, Layout(),
                   passes=("beauty",))["beauty"]
write("audio_spectrum", fr, [(spec["values"][0], (255, 207, 46)), (spec["values"][-1], (56, 189, 248))],
      "spectrum mode: lows on the left, highs on the right")
print(f"spectrum: {len(fr)} frames {time.time() - t0:.1f}s")

# 3 — trigger response: each kick replays the track's easing; retrigger keeps busy beats tidy
ROWS = [("BOUNCE", Track(effect="drop", drive=kick["values"], response="trigger", easing="bounce", amount=24,
                         duration=0.45, retrigger="finish", stagger=1 / FPS),
         Look3D(face="#7dd3fc", face2="#2563eb", side="#1e3a8a", extrude=14, bevel=6)),
        ("ELASTIC", Track(effect="squash", drive=kick["values"], response="trigger", easing="elastic", amount=45,
                          duration=0.45, retrigger="restart", stagger=1 / FPS, order="center_out"),
         Look3D(face="#ff8fd8", face2="#a78bfa", side="#7c3aed", extrude=14, bevel=6)),
        ("SPRING", Track(effect="roll_z", drive=kick["values"], response="trigger", easing="spring", amount=25,
                         duration=0.45, retrigger="layer", stagger=1 / FPS),
         Look3D(face="#bef264", face2="#16a34a", side="#14532d", extrude=14, bevel=6))]
t0 = time.time()
rows = []
for word, tr, lk in ROWS:
    tr.direction = "in"
    rows.append(render_frames(Anim([tr], fps=FPS), Glyphs(text=word, font="Anton", size=70, tracking=4), lk,
                              Shadow(texture="halftone", color="#0f172a", length=10, texture_scale=5), W, (H - 40) // 3,
                              Layout(), passes=("beauty",))["beauty"])
n = min(len(r) for r in rows)
fr = np.concatenate([np.zeros((n, 22, W, 4), np.float32)] + [r[:n] for r in rows], axis=1)  # room for the caption
fr = np.concatenate([fr, np.zeros((n, H - fr.shape[1], W, 4), np.float32)], axis=1)
write("audio_easings", fr, [(kick["values"], (255, 207, 46))],
      "kick-triggered easings: bounce (finish) / elastic (restart) / spring (layer)")
print(f"easings: {n} frames {time.time() - t0:.1f}s")
