"""TitleRig core renderer: pure Python (numpy, Pillow, SciPy, OpenCV), CPU only, no ComfyUI imports.

render_title() builds a 2.5D title (bevelled face + stacked extrusion + textured shadow) and returns
every pass as a float32 numpy array in [0, 1]:

  beauty (H,W,4 RGBA) · alpha · depth · edges · normals (H,W,3) · face · sides · highlight · shadow
  letter_ids (H,W,3) · guides (H,W,4 RGBA overlay)
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
SHADOW_TEXTURES = ("solid", "halftone", "stripes", "checker", "noise", "pixel", "gradient")


def font_path(name: str) -> str:
    """Resolve a bundled font name ('Anton') or an absolute path."""
    if os.path.isfile(name):
        return name
    for f in os.listdir(FONT_DIR):
        if f.lower().startswith(name.lower().replace(" ", "")) and f.lower().endswith((".ttf", ".otf")):
            return os.path.join(FONT_DIR, f)
    raise FileNotFoundError(f"font not found: {name}")


def bundled_fonts() -> list[str]:
    return sorted(os.path.splitext(f)[0] for f in os.listdir(FONT_DIR) if f.lower().endswith((".ttf", ".otf")))


def _rgb(hex_or_tuple) -> np.ndarray:
    if isinstance(hex_or_tuple, str):
        h = hex_or_tuple.lstrip("#")
        return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0
    return np.asarray(hex_or_tuple, np.float32)


@dataclass
class Glyphs:
    text: str = "TITLE"
    font: str = "Anton"
    size: int = 220
    tracking: float = 0.0                                   # px added between every pair
    kerning: dict[int, float] = field(default_factory=dict)  # pair index i -> px between letter i and i+1
    letters: dict[int, dict] = field(default_factory=dict)   # i -> {scale, rot, dx, dy, space_l, space_r}


@dataclass
class Look3D:
    face: str = "#ffcf2e"
    face2: str | None = "#ff6a2b"          # vertical gradient bottom colour, None = flat
    side: str = "#c2410c"
    extrude: int = 28                       # px
    extrude_angle: float = 55.0             # degrees, direction the extrusion recedes (screen space, y down)
    bevel: float = 10.0                     # px
    bevel_profile: str = "round"            # round | chisel | flat
    light_angle: float = 225.0              # degrees, where the key light comes from
    light_height: float = 0.6               # 0 grazing .. 1 overhead
    gloss: float = 0.6
    rim: float = 0.25


@dataclass
class Shadow:
    on: bool = True
    color: str = "#15161c"
    angle: float = 45.0
    length: float = 40.0
    softness: float = 0.0
    texture: str = "halftone"
    texture_scale: float = 10.0
    texture_angle: float = 45.0
    opacity: float = 1.0


def layout(g: Glyphs):
    """Return per-letter placement: list of (char, x, baseline_shift, transform dict) plus font metrics."""
    font = ImageFont.truetype(font_path(g.font), g.size)
    xs, x = [], 0.0
    chars = list(g.text)
    for i, ch in enumerate(chars):
        lt = g.letters.get(i, {})
        x += lt.get("space_l", 0.0)
        xs.append(x)
        adv = font.getlength(ch) * lt.get("scale", 1.0)
        if i < len(chars) - 1:
            pair = font.getlength(ch + chars[i + 1]) - font.getlength(ch) - font.getlength(chars[i + 1])
            adv += pair + g.tracking + g.kerning.get(i, 0.0) + lt.get("space_r", 0.0)
        x += adv
    ascent, descent = font.getmetrics()
    cap = font.getbbox("H")[1]
    xh = font.getbbox("x")[1]
    metrics = {"ascent": ascent, "descent": descent, "cap_top": cap, "x_top": xh, "width": x}
    return font, chars, xs, metrics


def _letter_layers(g: Glyphs, W: int, H: int):
    font, chars, xs, m = layout(g)
    total_h = m["ascent"] + m["descent"]
    ox = (W - m["width"]) / 2.0
    oy = (H - total_h) / 2.0
    face = np.zeros((H, W), np.float32)
    ids = np.zeros((H, W), np.int32)
    for i, ch in enumerate(chars):
        if not ch.strip():
            continue
        lt = g.letters.get(i, {})
        layer = Image.new("L", (W, H), 0)
        ImageDraw.Draw(layer).text((ox + xs[i], oy), ch, font=font, fill=255)
        a = np.asarray(layer, np.float32) / 255.0
        s, rot = lt.get("scale", 1.0), lt.get("rot", 0.0)
        if s != 1.0 or rot or lt.get("dx") or lt.get("dy"):
            bb = font.getbbox(ch)
            cx = ox + xs[i] + (bb[0] + bb[2]) / 2
            cy = oy + (bb[1] + bb[3]) / 2
            M = cv2.getRotationMatrix2D((cx, cy), -rot, s)
            M[0, 2] += lt.get("dx", 0.0)
            M[1, 2] += lt.get("dy", 0.0)
            a = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)
        ids[a > 0.5] = i + 1
        face = np.maximum(face, a)
    baseline = oy + m["ascent"]
    return face, ids, m, ox, baseline, chars


def _bevel_height(face: np.ndarray, bevel: float, profile: str) -> np.ndarray:
    if bevel <= 0 or profile == "flat":
        return face.copy()
    d = ndimage.distance_transform_edt(face > 0.5).astype(np.float32)
    t = np.clip(d / bevel, 0, 1)
    if profile == "round":
        t = np.sqrt(1 - (1 - t) ** 2)
    return t * (face > 0.5)


def _normals(h: np.ndarray, strength: float = 6.0) -> np.ndarray:
    hs = cv2.GaussianBlur(h, (0, 0), 1.0)
    gx = cv2.Sobel(hs, cv2.CV_32F, 1, 0, ksize=3) * strength
    gy = cv2.Sobel(hs, cv2.CV_32F, 0, 1, ksize=3) * strength
    n = np.dstack([-gx, -gy, np.ones_like(h)])
    return n / np.linalg.norm(n, axis=2, keepdims=True)


def _texture(kind: str, H: int, W: int, scale: float, angle: float, intensity: np.ndarray) -> np.ndarray:
    """Return a 0/1 coverage map for a shadow texture, modulated by intensity (0..1)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    a = math.radians(angle)
    u = xx * math.cos(a) + yy * math.sin(a)
    v = -xx * math.sin(a) + yy * math.cos(a)
    s = max(2.0, scale)
    if kind == "solid":
        return intensity
    if kind == "halftone":
        cu, cv_ = (u / s) % 1 - 0.5, (v / s) % 1 - 0.5
        r = np.sqrt(cu ** 2 + cv_ ** 2)
        return (r < 0.5 * np.sqrt(intensity) * 1.1).astype(np.float32)
    if kind == "stripes":
        return (((u / s) % 1) < 0.5 * intensity + 0.15 * (intensity > 0)).astype(np.float32)
    if kind == "checker":
        return (((np.floor(u / s) + np.floor(v / s)) % 2) == 0).astype(np.float32) * (intensity > 0.05)
    if kind == "noise":
        rng = np.random.default_rng(7)  # fixed seed: frames stay stable
        return (rng.random((H, W)).astype(np.float32) < intensity).astype(np.float32)
    if kind == "pixel":
        small = cv2.resize(intensity, (max(1, int(W / s)), max(1, int(H / s))), interpolation=cv2.INTER_AREA)
        return (cv2.resize(small, (W, H), interpolation=cv2.INTER_NEAREST) > 0.35).astype(np.float32)
    if kind == "gradient":
        return intensity * np.clip(1 - (v - v.min()) / (np.ptp(v) + 1e-6) * 0.8, 0, 1)
    raise ValueError(f"unknown shadow texture: {kind}")


def render_title(g: Glyphs, look: Look3D | None = None, shadow: Shadow | None = None,
                 width: int = 1280, height: int = 720) -> dict[str, np.ndarray]:
    look = look or Look3D()
    shadow = shadow or Shadow()
    W, H = width, height
    face, ids, m, ox, baseline, chars = _letter_layers(g, W, H)
    fm = (face > 0.5).astype(np.float32)

    # extrusion: stack offset copies receding along extrude_angle
    ea = math.radians(look.extrude_angle)
    dx, dy = math.cos(ea), math.sin(ea)
    sides = np.zeros_like(face)
    side_depth = np.zeros_like(face)
    for k in range(look.extrude, 0, -1):
        M = np.float32([[1, 0, dx * k], [0, 1, dy * k]])
        sh = cv2.warpAffine(fm, M, (W, H), flags=cv2.INTER_NEAREST)
        newpix = (sh > 0) & (sides == 0)
        sides[newpix] = 1
        side_depth[newpix] = 1 - k / max(look.extrude, 1)
    sides = sides * (1 - fm)
    silhouette = np.clip(fm + sides, 0, 1)

    # face lighting
    hgt = _bevel_height(face, look.bevel, look.bevel_profile)
    n = _normals(hgt)
    la = math.radians(look.light_angle)
    L = np.array([math.cos(la) * (1 - look.light_height), math.sin(la) * (1 - look.light_height), look.light_height], np.float32)
    L /= np.linalg.norm(L)
    lam = np.clip((n @ L), 0, 1)
    Hv = (L + np.array([0, 0, 1], np.float32)); Hv /= np.linalg.norm(Hv)
    spec = np.clip(n @ Hv, 0, 1) ** 40 * look.gloss
    rim = (1 - n[..., 2]) * look.rim

    rows = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    ys = np.where(fm.any(axis=1))[0]
    t = np.clip((rows - (ys.min() / H if len(ys) else 0)) / ((np.ptp(ys) + 1) / H if len(ys) else 1), 0, 1)
    c1 = _rgb(look.face)
    c2 = _rgb(look.face2) if look.face2 else c1
    base = c1[None, None] * (1 - t[..., None]) + c2[None, None] * t[..., None]
    base = np.broadcast_to(base, (H, W, 3))
    face_rgb = np.clip(base * (0.55 + 0.45 * lam[..., None]) + spec[..., None] + rim[..., None], 0, 1)

    sc = _rgb(look.side)
    side_rgb = sc[None, None] * (0.55 + 0.45 * side_depth[..., None])

    # shadow: silhouette pushed along shadow angle, textured, kept behind the letters
    shadow_mask = np.zeros_like(face)
    if shadow.on and shadow.length > 0:
        sa = math.radians(shadow.angle)
        acc = np.zeros_like(face)
        steps = int(shadow.length)
        for k in range(1, steps + 1):
            M = np.float32([[1, 0, math.cos(sa) * k], [0, 1, math.sin(sa) * k]])
            acc = np.maximum(acc, cv2.warpAffine(silhouette, M, (W, H), flags=cv2.INTER_NEAREST))
        if shadow.softness > 0:
            acc = cv2.GaussianBlur(acc, (0, 0), shadow.softness)
        acc = acc * (1 - silhouette)
        shadow_mask = _texture(shadow.texture, H, W, shadow.texture_scale, shadow.texture_angle, acc) * (acc > 0.02)
        shadow_mask = shadow_mask * shadow.opacity

    # composite beauty (straight alpha)
    rgb = np.zeros((H, W, 3), np.float32)
    alpha = np.clip(silhouette + shadow_mask, 0, 1)
    scol = _rgb(shadow.color)
    rgb = np.where(shadow_mask[..., None] > 0, scol[None, None], rgb)
    rgb = np.where(sides[..., None] > 0, side_rgb, rgb)
    rgb = np.where(fm[..., None] > 0, face_rgb, rgb)
    beauty = np.dstack([rgb, alpha]).astype(np.float32)

    depth = np.where(fm > 0, 0.85 + 0.15 * hgt, 0) + np.where(sides > 0, 0.3 + 0.5 * side_depth, 0)
    edges = cv2.Canny((np.clip(fm * (0.6 + 0.4 * hgt) + sides * 0.3, 0, 1) * 255).astype(np.uint8), 40, 120).astype(np.float32) / 255
    highlight = np.clip(spec * fm * 3, 0, 1)

    rng = np.random.default_rng(3)
    palette = rng.random((len(chars) + 1, 3)).astype(np.float32) * 0.8 + 0.2
    palette[0] = 0
    letter_ids = palette[ids]

    guides = draw_guides(W, H, ox, baseline, m)

    return {
        "beauty": beauty,
        "alpha": silhouette.astype(np.float32),
        "depth": np.repeat(depth[..., None], 3, 2).astype(np.float32),
        "edges": np.repeat(edges[..., None], 3, 2),
        "normals": ((n * 0.5 + 0.5) * fm[..., None]).astype(np.float32),
        "face": fm,
        "sides": sides.astype(np.float32),
        "highlight": highlight.astype(np.float32),
        "shadow": shadow_mask.astype(np.float32),
        "letter_ids": letter_ids,
        "guides": guides,
    }


def draw_guides(W: int, H: int, ox: float, baseline: float, m: dict, color=(0.56, 0.57, 1.0)) -> np.ndarray:
    """Dashed type guides (RGBA): ascender, cap line, x-height, baseline (solid-ish), descender."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top = baseline - m["ascent"]
    lines = {
        "ascender": top,
        "cap": top + m["cap_top"],
        "x-height": top + m["x_top"],
        "baseline": baseline,
        "descender": baseline + m["descent"],
    }
    c = tuple(int(v * 255) for v in color)
    x0, x1 = max(0, int(ox - 40)), min(W, int(ox + m["width"] + 40))
    for name, y in lines.items():
        dash = 14 if name != "baseline" else 40
        for x in range(x0, x1, dash + 8):
            d.line([(x, y), (min(x + dash, x1), y)], fill=c + (230 if name == "baseline" else 150,), width=2)
        d.text((x1 + 6, y - 8), name, fill=c + (200,))
    return np.asarray(img, np.float32) / 255.0
