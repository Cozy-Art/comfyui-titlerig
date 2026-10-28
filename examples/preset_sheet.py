"""Render every Style Preset's suggested rig look on one word -> examples/out/preset_sheet.png (+ prompts JSON).
Run: python examples/preset_sheet.py [WORD]"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, render_title  # noqa: E402
from render.presets import PRESET_NAMES, PRESETS, TARGETS, build_prompt, suggested_look  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
WORD = sys.argv[1] if len(sys.argv) > 1 else "TITLERIG"
TW, TH, COLS = 520, 230, 3

tiles, prompts = [], {}
for name in PRESET_NAMES:
    look, shadow = suggested_look(name)
    b = render_title(Glyphs(text=WORD, size=96, tracking=3), look, shadow, TW, TH, guides="none")["beauty"]
    bg = np.array([int(PRESETS[name].backdrop[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    rgb = b[..., :3] * b[..., 3:] + bg * (1 - b[..., 3:])
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 10, 18 + 7 * len(name), 30), 9, fill=(255, 255, 255))
    d.text((16, 14), name, fill=(20, 20, 28))
    tag = (f"extrude {look.extrude}" if look.extrude else "no extrusion") + " · " + \
          (f"{shadow.texture} shadow" if shadow.on else "no shadow") + (" · embossed" if look.bevel else "")
    d.rounded_rectangle((10, TH - 30, 18 + 6 * len(tag), TH - 10), 9, fill=(16, 16, 20))
    d.text((16, TH - 26), tag, fill=(230, 230, 240))
    for k, hx in enumerate(PRESETS[name].palette):
        d.ellipse((TW - 24 - 20 * k, 12, TW - 10 - 20 * k, 26), fill=hx, outline=(255, 255, 255))
    tiles.append(im)
    prompts[name] = {t: dict(zip(("positive", "negative"), build_prompt(name, WORD, target=t))) for t in TARGETS}
rows = (len(tiles) + COLS - 1) // COLS
sheet = Image.new("RGB", (TW * COLS, TH * rows), (16, 16, 20))
for i, t in enumerate(tiles):
    sheet.paste(t, (TW * (i % COLS), TH * (i // COLS)))
sheet.save(os.path.join(OUT, "preset_sheet.png"))
json.dump(prompts, open(os.path.join(OUT, "preset_prompts.json"), "w"), indent=2)
print("wrote", OUT)
