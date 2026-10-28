"""Render a contact sheet of looks and passes into examples/out/. Run: python examples/contact_sheet.py"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

LOOKS = {
    "chrome_slam": (Look3D(face="#f4f6fb", face2="#7a869a", side="#3b4252", gloss=1.0, rim=0.5),
                    Shadow(texture="stripes", color="#1d4ed8")),
    "ben_day_pop": (Look3D(face="#ffd400", face2=None, side="#e11d48", bevel=4),
                    Shadow(texture="halftone", color="#111827")),
    "candy_inflatable": (Look3D(face="#ff8fd8", face2="#a78bfa", side="#7c3aed", bevel=22),
                         Shadow(texture="solid", softness=8, color="#4c1d95", opacity=0.6)),
    "op_art": (Look3D(face="#ffffff", face2=None, side="#111111", bevel=2, extrude=18),
               Shadow(texture="checker", color="#111111", texture_scale=8)),
}


def to_img(a):
    a = np.clip(a, 0, 1)
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, 2)
    if a.shape[2] == 4:  # composite on dark checker for viewing
        bg = np.full(a.shape[:2] + (3,), 0.12, np.float32)
        a = a[..., :3] * a[..., 3:] + bg * (1 - a[..., 3:])
    return Image.fromarray((a * 255).astype(np.uint8))


tiles = []
for name, (look, sh) in LOOKS.items():
    p = render_title(Glyphs(text="BADD ASS", font="Anton", size=200, tracking=6), look, sh, 1100, 420)
    img = to_img(p["beauty"])
    img.save(os.path.join(OUT, f"{name}.png"))
    tiles.append(img)

passes = render_title(Glyphs(text="TITLE", font="Shrikhand", size=200), Look3D(), Shadow(), 900, 380)
for k in ("depth", "edges", "normals", "shadow", "highlight", "letter_ids", "guides"):
    to_img(passes[k]).save(os.path.join(OUT, f"pass_{k}.png"))

sheet = Image.new("RGB", (1100, 420 * len(tiles)), (20, 20, 24))
for i, t in enumerate(tiles):
    sheet.paste(t, (0, 420 * i))
sheet.save(os.path.join(OUT, "contact_sheet.png"))

# P0b layouts: arc + bulge, perspective tilt, vanishing point, flag warp (guides overlaid)
LAYOUTS = {
    "arc  bend +0.5": Layout(mode="arc", bend=0.5),
    "smile  bend -0.5  bulge +0.3": Layout(mode="arc", bend=-0.5, bulge=0.3),
    "bulge +0.6": Layout(bulge=0.6),
    "tilt_x 40 (crawl)": Layout(tilt_x=40),
    "tilt_y 30": Layout(tilt_y=30),
    "vanishing point (0.5, 1.6)": Layout(vanish=True, vp_x=0.5, vp_y=1.6),
    "flag  amp 26  wave 360": Layout(flag_amp=26, flag_wavelength=360),
    "arc + tilt_x 35 + flag": Layout(mode="arc", bend=0.35, tilt_x=35, flag_amp=10, flag_wavelength=300),
}
look, sh = LOOKS["chrome_slam"]
lt = []
for i, (label, lay) in enumerate(LAYOUTS.items()):
    lk = look if i % 2 else Look3D()
    p = render_title(Glyphs(text="BADD ASS", font="Anton", size=130, tracking=4), lk, sh if i % 2 else Shadow(),
                     760, 360, lay)
    b, gd = p["beauty"], p["guides"]
    rgb = b[..., :3] * b[..., 3:] + 0.11 * (1 - b[..., 3:])
    rgb = rgb * (1 - gd[..., 3:] * 0.7) + gd[..., :3] * gd[..., 3:] * 0.7
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    ImageDraw.Draw(img).text((14, 12), label, fill=(230, 230, 240))
    lt.append(img)
cols = 2
ls = Image.new("RGB", (760 * cols, 360 * ((len(lt) + 1) // cols)), (20, 20, 24))
for i, t in enumerate(lt):
    ls.paste(t, (760 * (i % cols), 360 * (i // cols)))
ls.save(os.path.join(OUT, "layout_sheet.png"))
print("wrote", OUT)
