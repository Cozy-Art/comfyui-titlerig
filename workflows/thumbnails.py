"""Template thumbnails: example_workflows/<name>.jpg, shown on the cards in ComfyUI's Templates menu.

Rig-only frames from docs/media (python examples/hero_clips.py, cutout_demo.py) and two rig renders for the FLUX
stills (depth -> beauty). Run: python workflows/thumbnails.py"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from render import Glyphs, Layout, render_title  # noqa: E402
from render.presets import PRESETS, suggested_look  # noqa: E402

MEDIA = os.path.join(ROOT, "docs", "media")
OUT = os.path.join(ROOT, "example_workflows")
SIZE = 512
FONT = ImageFont.truetype(os.path.join(ROOT, "fonts", "Anton-Regular.ttf"), 40)


def gif_frame(name, at=0.5, crop=None):
    g = Image.open(os.path.join(MEDIA, name))
    g.seek(min(g.n_frames - 1, int(g.n_frames * at)))
    im = g.convert("RGB")
    return im.crop(crop) if crop else im


def rig_pair(preset, text):
    """Depth on the left, beauty on the right: what the FLUX workflow turns into."""
    look, shadow = suggested_look(preset)
    p = render_title(Glyphs(text=text, font="Anton", size=200, tracking=6), look, shadow, 640, 360, Layout())
    bg = np.array([int(PRESETS[preset].backdrop[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    b = p["beauty"]
    beauty = b[..., :3] * b[..., 3:] + bg * (1 - b[..., 3:])
    top = Image.fromarray((np.clip(p["depth"], 0, 1) * 255).astype(np.uint8))
    bottom = Image.fromarray((np.clip(beauty, 0, 1) * 255).astype(np.uint8))
    im = Image.new("RGB", (640, 720))
    im.paste(top, (0, 0))
    im.paste(bottom, (0, 360))
    return im


def card(im, label, name):
    bg = im.getpixel((2, 2))
    sheet = Image.new("RGB", (SIZE, SIZE), bg)
    fit = im.copy()
    fit.thumbnail((SIZE, SIZE - 70), Image.LANCZOS)
    sheet.paste(fit, ((SIZE - fit.width) // 2, (SIZE - 70 - fit.height) // 2))
    d = ImageDraw.Draw(sheet)
    d.rectangle((0, SIZE - 70, SIZE, SIZE), fill=(20, 20, 28))
    d.text((20, SIZE - 64), label, font=FONT, fill=(255, 212, 0))
    sheet.save(os.path.join(OUT, f"{name}.jpg"), quality=88)


CARDS = {
    "titlerig_rig_only": (lambda: gif_frame("rig_only_workflow.gif", 0.9), "RIG ONLY · NO MODELS"),
    "titlerig_audio_react": (lambda: gif_frame("ben_day_beat.gif", 0.45), "AUDIO REACT · NO MODELS"),
    "titlerig_cutout": (lambda: gif_frame("cutout.gif", 0.6, (0, 22, 480, 225)), "CUTOUT · NO MODELS"),
    "titlerig_ltx2_animated": (lambda: gif_frame("chrome_slam_flip_in.gif", 0.95), "LTX-2 · DEPTH VIDEO"),
    "titlerig_flux_still": (lambda: rig_pair("Chrome Slam", "TITLE"), "FLUX.1 DEPTH · STILL"),
    "titlerig_flux2_still": (lambda: rig_pair("Holo Foil", "TITLE"), "FLUX.2 DEV · STILL"),
}

if __name__ == "__main__":
    for name, (make, label) in CARDS.items():
        card(make(), label, name)
        print("wrote", os.path.join("example_workflows", f"{name}.jpg"))
