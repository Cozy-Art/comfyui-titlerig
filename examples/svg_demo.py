"""SVG export demo: trace several rigs to layered SVGs -> examples/out/svg/*.svg. Run: python examples/svg_demo.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow  # noqa: E402
from render.presets import PRESETS, suggested_look  # noqa: E402
from render.svg import rig_svg  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "svg")
os.makedirs(OUT, exist_ok=True)
CASES = {
    "ben_day_arc": ("Ben-Day Pop", Glyphs(text="BADD ASS", size=130), Layout(mode="arc", bend=0.3)),
    "chrome_slam": ("Chrome Slam", Glyphs(text="TITLERIG", size=130), Layout()),
    "vapor_ticker": ("Vapor Sunset", Glyphs(text="BREAKING TITLES", size=90), Layout(mode="ticker", wrap_radius=0.3)),
    "low_poly_taper": ("Low Poly", Glyphs(text="KEYSTONE", size=120, word={"taper_x": 0.35}), Layout()),
}
for name, (preset, g, lay) in CASES.items():
    look, shadow = suggested_look(preset)
    svg = rig_svg(g, look, shadow, 900, 360, lay, supersample=2, background=PRESETS[preset].backdrop)
    with open(os.path.join(OUT, f"{name}.svg"), "w") as f:
        f.write(svg)
    print(f"{name}.svg {len(svg) // 1024} KB")
