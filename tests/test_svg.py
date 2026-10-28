import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.svg import rasterize, rig_layers, rig_svg, to_svg  # noqa: E402

NS = {"s": "http://www.w3.org/2000/svg"}
FLAT = dict(bevel=0, bevel_profile="flat")


def raster(L):
    """Traced polygons back to 1x masks without fillPoly's edge bias: fill at 4x, area-downsample."""
    import cv2
    r4 = rasterize(L, 4)
    return {k: (cv2.resize(v, (L["width"], L["height"]), interpolation=cv2.INTER_AREA) > 0.5).astype(np.float32)
            for k, v in r4.items()}


def iou(a, b):
    a, b = a > 0.5, b > 0.5
    return (a & b).sum() / max((a | b).sum(), 1)


def test_svg_is_valid_xml_with_layers_and_one_path_per_letter():
    svg = rig_svg(Glyphs(text="AB C", size=100), Look3D(**FLAT), Shadow(texture="stripes"), 500, 240)
    root = ET.fromstring(svg)
    groups = {g.get("id") for g in root.findall("s:g", NS)}
    assert groups == {"shadow", "sides", "faces"}
    letters = root.findall("s:g[@id='faces']/s:path", NS)
    assert len(letters) == 3 and all(p.get("fill-rule") == "evenodd" for p in letters)
    assert root.find("s:defs/s:linearGradient", NS) is not None


@pytest.mark.parametrize("lay", [Layout(), Layout(mode="arc", bend=0.4), Layout(mode="ticker")])
def test_traced_shapes_match_the_rig(lay):
    g, look, sh = Glyphs(text="BOAR", size=110), Look3D(extrude=14, **FLAT), Shadow(texture="solid", length=20)
    L = rig_layers(g, look, sh, 500, 240, lay)
    r = raster(L)
    p = render_title(g, look, sh, 500, 240, lay)
    assert iou(r["faces"], p["face"]) > 0.93
    assert iou(r["sides"], p["sides"]) > 0.85
    assert iou(r["shadow"], p["shadow"] > 0.01) > 0.85


def test_holes_survive():
    L = rig_layers(Glyphs(text="O", size=160), Look3D(extrude=0, **FLAT), Shadow(on=False), 300, 240)
    f = raster(L)["faces"]
    ys, xs = np.nonzero(f)
    assert f[int(ys.mean()), int(xs.mean())] == 0  # the counter of the O stays open


def test_textured_shadow_is_many_shapes_and_off_means_empty():
    L = rig_layers(Glyphs(text="AB", size=110), Look3D(**FLAT), Shadow(texture="halftone", texture_scale=8), 400, 240)
    assert sum(len(polys) for _, _, polys in L["shadow"]) > 30
    L = rig_layers(Glyphs(text="AB", size=110), Look3D(extrude=0, **FLAT), Shadow(on=False), 400, 240)
    assert L["shadow"] == [] and L["sides"] == []
    root = ET.fromstring(to_svg(L, background="#112233"))
    assert root.find("s:rect", NS).get("fill") == "#112233"


def test_supersample_keeps_scale():
    a = raster(rig_layers(Glyphs(text="H", size=120), Look3D(extrude=0, **FLAT), Shadow(on=False), 300, 200,
                             supersample=1))["faces"]
    b = raster(rig_layers(Glyphs(text="H", size=120, tracking=4, letters={0: {"dx": 10}}),
                             Look3D(extrude=0, **FLAT), Shadow(on=False), 300, 200, supersample=3))["faces"]
    c = raster(rig_layers(Glyphs(text="H", size=120, tracking=4, letters={0: {"dx": 10}}),
                             Look3D(extrude=0, **FLAT), Shadow(on=False), 300, 200, supersample=1))["faces"]
    true = render_title(Glyphs(text="H", size=120), Look3D(extrude=0, **FLAT), Shadow(on=False), 300, 200)["face"]
    assert abs(b.sum() - true.sum()) / true.sum() < 0.02  # 3x supersample: true size, not 3x bigger
    assert abs(a.sum() - true.sum()) / true.sum() < 0.07  # 1x trace erodes half a pixel
    assert iou(b, c) > 0.93                          # per-letter px offsets scale too
