"""Render a contact sheet of looks and passes into examples/out/. Run: python examples/contact_sheet.py"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Look3D, Shadow, render_title  # noqa: E402

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
print("wrote", OUT)
