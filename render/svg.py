"""SVG export: trace the rig's passes into layered vector shapes (open, no API).

Layers, back to front: <g id="shadow"> (every halftone dot / stripe / checker cell is a real shape), <g id="sides">
(extrusion in a few depth tones), <g id="faces"> (one path per letter, vertical gradient). Tracing the rendered rig
(rather than font outlines) keeps every layout: arcs, wraps, free transforms, magnets.
"""
from __future__ import annotations

import copy
import math
from dataclasses import replace
from xml.sax.saxutils import escape

import cv2
import numpy as np

from .core import Glyphs, Look3D, Shadow, _rgb, render_title
from .geometry import Layout


def _hex(c) -> str:
    c = np.clip(np.asarray(c, np.float32), 0, 1)
    return "#{:02x}{:02x}{:02x}".format(*(int(round(v * 255)) for v in c[:3]))


def trace(mask: np.ndarray, scale: float = 1.0, eps: float = 0.8, min_area: float = 2.0) -> list[np.ndarray]:
    """Contours (outer and holes) of a binary mask as float polygons in output coordinates."""
    m = (mask > 0.5).astype(np.uint8)
    contours, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in contours:
        if abs(cv2.contourArea(c)) < min_area:
            continue
        a = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(np.float64)
        if len(a) >= 3:
            out.append((a + 0.5) / scale)  # pixel centres
    return out


def _path(polys: list[np.ndarray], smooth_deg: float = 150.0) -> str:
    """SVG path data: sharp corners stay corners; gentle turns become quadratic curves through midpoints."""
    parts = []
    for p in polys:
        n = len(p)
        mids = (p + np.roll(p, -1, axis=0)) / 2
        cmds = [f"M{mids[-1][0]:.2f} {mids[-1][1]:.2f}"]
        for i in range(n):
            a, b, c = p[i - 1], p[i], p[(i + 1) % n]
            v1, v2 = a - b, c - b
            cosang = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
            ang = math.degrees(math.acos(np.clip(cosang, -1, 1)))
            if ang >= smooth_deg:  # gentle turn: curve through it
                cmds.append(f"Q{b[0]:.2f} {b[1]:.2f} {mids[i][0]:.2f} {mids[i][1]:.2f}")
            else:                  # corner: keep it sharp
                cmds.append(f"L{b[0]:.2f} {b[1]:.2f} L{mids[i][0]:.2f} {mids[i][1]:.2f}")
        parts.append("".join(cmds) + "Z")
    return "".join(parts)


_PX_LETTER_KEYS = ("dx", "dy", "space_l", "space_r")


def _scale_dict(d: dict, s: float) -> dict:
    d = dict(d)
    for k in _PX_LETTER_KEYS:
        if k in d:
            d[k] = d[k] * s
    if d.get("corners") is not None:
        d["corners"] = (np.asarray(d["corners"], np.float64) * s).tolist()
    if isinstance(d.get("group"), dict):
        d["group"] = _scale_dict(d["group"], s)
    return d


def supersampled(g: Glyphs, look: Look3D, shadow: Shadow, lay: Layout, s: float):
    """The same rig with every pixel quantity scaled by s (render at s x, trace, divide by s)."""
    g = copy.deepcopy(g)
    g.size = int(round(g.size * s))
    g.tracking *= s
    g.kerning = {k: v * s for k, v in g.kerning.items()}
    g.letters = {i: _scale_dict(d, s) for i, d in g.letters.items()}
    g.word = _scale_dict(g.word, s)
    look = replace(look, extrude=int(round(look.extrude * s)), bevel=look.bevel * s)
    shadow = replace(shadow, length=shadow.length * s, softness=shadow.softness * s,
                     texture_scale=shadow.texture_scale * s)
    lay = replace(lay, flag_amp=lay.flag_amp * s, flag_wavelength=lay.flag_wavelength * s)
    return g, look, shadow, lay


def rig_layers(g: Glyphs, look: Look3D | None = None, shadow: Shadow | None = None, width: int = 1280,
               height: int = 720, lay: Layout | None = None, supersample: int = 2, tones: int = 4) -> dict:
    """Trace the rig into layers: {'shadow': [(colour, polys)], 'sides': [...], 'faces': [(letter, polys)], ...}."""
    look = look or Look3D()
    shadow = shadow or Shadow()
    lay = lay or Layout()
    s = max(1, int(supersample))
    gs, ls, ss, ys = supersampled(g, look, shadow, lay, s)
    p = render_title(gs, ls, ss, width * s, height * s, ys, guides="none")
    eps = 0.6 * s
    layers = {"width": width, "height": height, "shadow": [], "sides": [], "faces": []}
    if p["shadow"].max() > 0:
        layers["shadow"].append((_hex(_rgb(shadow.color)), shadow.opacity, trace(p["shadow"] > 0.01, s, eps)))
    sides = p["sides"] > 0
    if sides.any():  # depth pass on the sides is 0.3 + 0.5 * side_depth: band it into a few tones
        sd = np.clip((p["depth"][..., 0] - 0.3) / 0.5, 0, 1)
        band = np.minimum((sd * tones).astype(int), tones - 1)
        sc = _rgb(look.side)
        for t in range(tones):
            m = sides & (band == t)
            if m.any():
                shade = 0.55 + 0.45 * (t + 0.5) / tones
                layers["sides"].append((_hex(sc * shade), 1.0, trace(m, s, eps)))
    ids = (p["letter_ids"] * 1000).round().astype(np.int64)
    key = ids[..., 0] * 1_000_000 + ids[..., 1] * 1000 + ids[..., 2]
    face = p["face"] > 0
    keys = [k for k in np.unique(key[face]) if k]
    rows = np.where(face.any(axis=1))[0]
    y0, y1 = (rows.min() / s, (rows.max() + 1) / s) if len(rows) else (0, height)
    for n, k in enumerate(sorted(keys, key=lambda k: np.nonzero(key == k)[1].mean())):
        layers["faces"].append((n, trace(face & (key == k), s, eps)))
    layers["gradient"] = (_hex(_rgb(look.face)), _hex(_rgb(look.face2 or look.face)), y0, y1)
    return layers


def to_svg(layers: dict, background: str | None = None, title: str = "TitleRig") -> str:
    W, H = layers["width"], layers["height"]
    c1, c2, y0, y1 = layers["gradient"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f"<title>{escape(title)}</title>",
           f'<defs><linearGradient id="face" gradientUnits="userSpaceOnUse" x1="0" y1="{y0:.2f}" x2="0" '
           f'y2="{y1:.2f}"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
           f"</linearGradient></defs>"]
    if background:
        out.append(f'<rect id="background" width="{W}" height="{H}" fill="{background}"/>')
    for name in ("shadow", "sides"):
        out.append(f'<g id="{name}">')
        for colour, opacity, polys in layers[name]:
            if polys:
                op = f' fill-opacity="{opacity:.3f}"' if opacity < 1 else ""
                seam = (f' stroke="{colour}" stroke-width="0.6" stroke-linejoin="round"'
                        if name == "sides" else "")  # hairline in its own colour closes anti-alias seams
                out.append(f'<path fill="{colour}"{op}{seam} fill-rule="evenodd" d="{_path(polys)}"/>')
        out.append("</g>")
    out.append('<g id="faces" fill="url(#face)">')
    for n, polys in layers["faces"]:
        if polys:
            out.append(f'<path id="letter-{n}" fill-rule="evenodd" d="{_path(polys)}"/>')
    out.append("</g></svg>")
    return "\n".join(out)


def rig_svg(g: Glyphs, look: Look3D | None = None, shadow: Shadow | None = None, width: int = 1280,
            height: int = 720, lay: Layout | None = None, supersample: int = 2, tones: int = 4,
            background: str | None = None) -> str:
    """The rig as a layered SVG string."""
    return to_svg(rig_layers(g, look, shadow, width, height, lay, supersample, tones), background, g.text)


def rasterize(layers: dict, scale: int = 1) -> dict[str, np.ndarray]:
    """Fill the traced polygons back into masks (even-odd), for checks and previews."""
    W, H = layers["width"] * scale, layers["height"] * scale
    out = {}
    for name in ("shadow", "sides"):
        m = np.zeros((H, W), np.uint8)
        for _, _, polys in layers[name]:
            m ^= _fill(polys, W, H, scale)
        out[name] = m.astype(np.float32)
    f = np.zeros((H, W), np.uint8)
    for _, polys in layers["faces"]:
        f |= _fill(polys, W, H, scale)
    out["faces"] = f.astype(np.float32)
    return out


def _fill(polys, W, H, scale):
    m = np.zeros((H, W), np.uint8)
    for p in polys:  # even-odd: xor each ring
        r = np.zeros((H, W), np.uint8)
        cv2.fillPoly(r, [np.round(p * scale - 0.5).astype(np.int32)], 1)
        m ^= r
    return m
