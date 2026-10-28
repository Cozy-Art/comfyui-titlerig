"""Hero clips for the submission video, rig only (no AI), on CPU. Writes docs/media/<name>.mp4 (+ a smaller .gif):

  chrome_slam_flip_in   Chrome Slam: letters flip in one after another and land with a back-ease
  ben_day_beat          Ben-Day Pop: letters pop on the kicks, the halftone shadow is thrown on every kick (with sound)
  sphere_ticker         Vapor Sunset: a ticker of text wrapped on a spinning, tilted globe (seamless loop)
  magnet_snap_back      Candy Inflatable: a magnet word sweeps through, letters repel and spring back into place
  hero.gif              the four GIFs tiled 2 x 2 for the top of the README

MP4s need ffmpeg. Run: python examples/hero_clips.py [name ...]"""
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Shadow  # noqa: E402
from render.animate import Anim, Track, render_frames  # noqa: E402
from render.audio import audio_curve, load_wav  # noqa: E402
from render.magnet import Magnet  # noqa: E402
from render.presets import PRESETS, suggested_look  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(os.path.dirname(HERE), "docs", "media")
WAV = os.path.join(HERE, "assets", "titlerig_beat.wav")
W, H, FPS = 960, 540, 24.0
GIF_W = 480


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def write(name, frames, bg, audio=False):
    rgb = [np.clip(a[..., :3] * a[..., 3:] + bg * (1 - a[..., 3:]), 0, 1) for a in frames]
    imgs = [Image.fromarray((a * 255).astype(np.uint8)) for a in rgb]
    gif = [im.resize((GIF_W, round(GIF_W * H / W)), Image.LANCZOS).quantize(
        255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for im in imgs]
    gif[0].save(os.path.join(MEDIA, f"{name}.gif"), save_all=True, append_images=gif[1:], duration=round(1000 / FPS),
                loop=0, optimize=True)
    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-"]
        cmd += ["-i", WAV, "-c:a", "aac", "-b:a", "128k", "-shortest"] if audio else []
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart",
                os.path.join(MEDIA, f"{name}.mp4")]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for im in imgs:
            p.stdin.write(im.tobytes())
        p.stdin.close()
        p.wait()


def look_of(preset):
    look, shadow = suggested_look(preset)
    return look, shadow, hexrgb(PRESETS[preset].backdrop)


def chrome_slam_flip_in():
    look, shadow, bg = look_of("Chrome Slam")
    anim = Anim([Track(effect="flip_x", easing="back", duration=0.7, stagger=0.09, order="forward"),
                 Track(effect="pop", easing="back", duration=0.5, stagger=0.09, amount=-30)], fps=FPS, hold=1.2)
    return render_frames(anim, Glyphs(text="TITLERIG", font="Anton", size=190, tracking=6), look, shadow, W, H,
                         Layout(mode="arc", bend=0.18), passes=("beauty",))["beauty"], bg, False


def ben_day_beat():
    look, shadow, bg = look_of("Ben-Day Pop")
    shadow.texture = "halftone"
    mono, sr = load_wav(WAV)
    kick = audio_curve(mono, sr, FPS, band="bass", mode="beats", sensitivity=0.5, release=0.18, max_seconds=6.0)
    hat = audio_curve(mono, sr, FPS, band="highs", mode="beats", sensitivity=0.15, release=0.12, max_seconds=6.0)
    anim = Anim([
        Track(effect="pop", drive=kick["values"], amount=-45, stagger=1 / FPS, order="center_out"),
        Track(effect="drop", drive=hat["values"], amount=26, stagger=1 / FPS, response="trigger", easing="bounce",
              duration=0.3, retrigger="finish"),
        Track(effect="shadow_length", drive=kick["values"], amount=45),
    ], fps=FPS)
    return render_frames(anim, Glyphs(text="POW!", font="Anton", size=230, tracking=8), look, shadow, W, H,
                         Layout(tilt_x=8), passes=("beauty",))["beauty"], bg, True


def globe(n, R, tilt, cy, colour):
    """Demo backdrop only: a shaded globe whose graticule turns with the text, so the sphere reads."""
    X = (np.arange(W)[None, :] - W / 2) / R
    Y = (np.arange(H)[:, None] - cy) / R
    r2 = X ** 2 + Y ** 2
    inside = r2 < 1
    Z = np.sqrt(np.clip(1 - r2, 0, 1))
    t = np.radians(tilt)
    Y2, Z2 = Y * np.cos(t) - Z * np.sin(t), Y * np.sin(t) + Z * np.cos(t)
    lat = np.degrees(np.arcsin(np.clip(Y2, -1, 1)))
    body = colour * (0.35 + 0.65 * Z[..., None])
    out = []
    for f in range(n):
        lon = np.degrees(np.arctan2(X, Z2)) - 360 * f / n
        grid = (np.abs((lon + 15) % 30 - 15) < 0.8) | (np.abs((lat + 15) % 30 - 15) < 0.8)
        rgb = body + (grid & inside)[..., None] * 0.12
        out.append(np.where(inside[..., None], rgb, np.nan))
    return out


def sphere_ticker():
    look, shadow, bg = look_of("Vapor Sunset")
    n, R, tilt = 120, 0.42, 18
    spin = Track(effect="wrap_spin", direction="loop", easing="linear", duration=n / FPS, stagger=0, amount=-360)
    fr = render_frames(Anim([spin], fps=FPS, hold=0), Glyphs(text="BREAKING TITLES •", font="Anton", size=84,
                                                              tracking=4),
                       look, Shadow(on=False), W, H, Layout(mode="sphere", wrap_radius=R, wrap_tilt=tilt),
                       passes=("beauty",))["beauty"][:n]
    back = globe(n, R * H, tilt, H / 2, hexrgb("#6d28d9"))
    out = []
    for a, g in zip(fr, back):
        ground = np.where(np.isnan(g), bg, g)
        out.append(np.concatenate([a[..., :3] * a[..., 3:] + ground * (1 - a[..., 3:]), np.ones_like(a[..., 3:])], -1))
    return np.stack(out), bg, False


def magnet_snap_back():
    look, shadow, bg = look_of("Candy Inflatable")
    mg = Magnet(polarity="repel", strength=120, range=230, lag=0.12, spring=0.75, squash=0.7, x=-0.15, x_end=1.15,
                y=0.62, y_end=0.62, duration=3.0, start=0.3, text="MAGNET", size=70)
    return render_frames(Anim(magnets=[mg], fps=FPS, hold=1.2), Glyphs(text="SNAP BACK", font="Anton", size=170,
                                                                        tracking=6),
                         look, shadow, W, H, Layout(), passes=("beauty",))["beauty"], bg, False


def hero(names, n=120, cell=(320, 180)):
    gifs = [Image.open(os.path.join(MEDIA, f"{k}.gif")) for k in names]
    sheets = []
    for f in range(n):
        sheet = Image.new("RGB", (cell[0] * 2, cell[1] * 2))
        for i, g in enumerate(gifs):
            g.seek(f % g.n_frames)
            sheet.paste(g.convert("RGB").resize(cell, Image.LANCZOS), (cell[0] * (i % 2), cell[1] * (i // 2)))
        sheets.append(sheet)
    # one shared palette, so unchanged pixels stay identical frame to frame and the GIF only stores what moves
    probe = Image.new("RGB", (sheets[0].width, sheets[0].height * 4))
    for k in range(4):
        probe.paste(sheets[k * n // 4], (0, sheets[0].height * k))
    pal = probe.quantize(255, method=Image.Quantize.MEDIANCUT)
    frames = [s.quantize(palette=pal, dither=Image.Dither.NONE) for s in sheets]
    frames[0].save(os.path.join(MEDIA, "hero.gif"), save_all=True, append_images=frames[1:],
                   duration=round(1000 / FPS), loop=0, optimize=True)


CLIPS = {f.__name__: f for f in (chrome_slam_flip_in, ben_day_beat, sphere_ticker, magnet_snap_back)}

if __name__ == "__main__":
    os.makedirs(MEDIA, exist_ok=True)
    for name in sys.argv[1:] or CLIPS:
        t0 = time.time()
        frames, bg, audio = CLIPS[name]()
        write(name, frames, bg, audio)
        print(f"{name}: {len(frames)} frames in {time.time() - t0:.0f}s")
    hero(list(CLIPS))
