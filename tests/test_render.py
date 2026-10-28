import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import SHADOW_TEXTURES, Glyphs, Look3D, Shadow, bundled_fonts, render_title  # noqa: E402

PASSES = ("beauty", "alpha", "depth", "edges", "normals", "face", "sides", "highlight", "shadow", "letter_ids", "guides")


def test_bundled_fonts_present():
    assert "Anton-Regular" in bundled_fonts()


def test_all_passes_shapes_and_ranges():
    p = render_title(Glyphs(text="TITLE"), width=640, height=320)
    assert set(PASSES) <= set(p)
    for k in PASSES:
        a = p[k]
        assert a.shape[:2] == (320, 640), k
        assert a.dtype == np.float32, k
        assert a.min() >= 0 and a.max() <= 1.0001, k
    assert p["face"].sum() > 1000
    assert p["sides"].sum() > 100
    assert (p["face"] * p["sides"]).sum() == 0  # face and sides never overlap
    assert (p["shadow"] * p["alpha"]).sum() == 0  # shadow sits behind the letters


@pytest.mark.parametrize("tex", SHADOW_TEXTURES)
def test_shadow_textures_render(tex):
    p = render_title(Glyphs(text="AB"), shadow=Shadow(texture=tex), width=400, height=240)
    assert p["shadow"].sum() > 0


def test_tracking_and_kerning_widen_layout():
    base = render_title(Glyphs(text="AVA", size=120), width=800, height=240)["face"]
    wide = render_title(Glyphs(text="AVA", size=120, tracking=40, kerning={0: 30}), width=800, height=240)["face"]
    span = lambda f: np.ptp(np.where(f.any(0))[0])  # noqa: E731
    assert span(wide) > span(base) + 60


def test_letter_ids_distinct():
    p = render_title(Glyphs(text="ABC", size=120), Look3D(extrude=0), Shadow(on=False), 600, 240)
    colors = {tuple(c) for c in p["letter_ids"].reshape(-1, 3)[p["face"].reshape(-1) > 0].round(3)}
    assert len(colors) >= 3


def test_guides_can_be_hidden_or_picked():
    from render.core import parse_guides
    kw = dict(look=Look3D(extrude=0), shadow=Shadow(on=False), width=500, height=240)
    assert render_title(Glyphs(text="AB", size=100), guides="none", **kw)["guides"].max() == 0
    full = render_title(Glyphs(text="AB", size=100), **kw)["guides"][..., 3].sum()
    some = render_title(Glyphs(text="AB", size=100), guides="baseline, mid", **kw)["guides"][..., 3].sum()
    assert 0 < some < full
    assert parse_guides(["mid", "cap"]) == ("cap", "mid")
    with pytest.raises(ValueError):
        parse_guides("baseline,bogus")
