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

from .geometry import (ArcPath, Layout, bend_curve, bulge_scale, flag_maps, flag_shading,
                       tilt_homography)

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
GUIDE_LINES = ("ascender", "cap", "x-height", "mid", "baseline", "descender")
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
    letters: dict[int, dict] = field(default_factory=dict)   # i -> {scale, sx, sy, rot, dx, dy, space_l, space_r}
    word: dict = field(default_factory=dict)                 # whole-word {scale, sx, sy, rot, dx, dy} about the centre


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


def _affine(rot=0.0, sx=1.0, sy=1.0, cx=0.0, cy=0.0, dx=0.0, dy=0.0) -> np.ndarray:
    """3x3: scale (sx, sy) then rotate `rot` degrees clockwise about (cx, cy), then translate."""
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    A = np.array([[c * sx, -s * sy, 0], [s * sx, c * sy, 0], [0, 0, 1]], np.float64)
    T = np.array([[1, 0, cx + dx], [0, 1, cy + dy], [0, 0, 1]], np.float64)
    Ti = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]], np.float64)
    return T @ A @ Ti


FREE_KEYS = ("skew_x", "skew_y", "taper_x", "taper_y", "corners")


def _has_free(d: dict) -> bool:
    return any(d.get(k) is not None and np.any(d.get(k)) for k in FREE_KEYS)


def _free(d: dict, bbox) -> np.ndarray:
    """3x3 free transform of a box (x0, y0, x1, y1): skew (deg), taper (fraction) and corner pin (px, TL TR BR BL).

    taper_x narrows the top edge (negative widens it); taper_y shortens the right side."""
    if bbox is None or not _has_free(d):
        return np.eye(3)
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    src = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float64)
    dst = src.copy()
    tx, ty = d.get("taper_x", 0.0), d.get("taper_y", 0.0)
    dst[:2, 0] = cx + (dst[:2, 0] - cx) * max(0.02, 1 - tx)       # top edge
    dst[1:3, 1] = cy + (dst[1:3, 1] - cy) * max(0.02, 1 - ty)     # right edge
    kx, ky = math.tan(math.radians(d.get("skew_x", 0.0))), math.tan(math.radians(d.get("skew_y", 0.0)))
    dst = np.column_stack([dst[:, 0] - kx * (dst[:, 1] - cy), dst[:, 1] + ky * (dst[:, 0] - cx)])
    if d.get("corners") is not None:
        dst = dst + np.asarray(d["corners"], np.float64).reshape(4, 2)
    if x1 - x0 < 1 or y1 - y0 < 1:
        return np.eye(3)
    return cv2.getPerspectiveTransform(src.astype(np.float32), dst.astype(np.float32)).astype(np.float64)


def _tf(d: dict, cx: float, cy: float, bbox=None) -> np.ndarray:
    """Letter / group / word transform: free transform of its box first, then scale, rotate and move."""
    s = d.get("scale", 1.0)
    return _affine(d.get("rot", 0.0), s * d.get("sx", 1.0), s * d.get("sy", 1.0), cx, cy,
                   d.get("dx", 0.0), d.get("dy", 0.0)) @ _free(d, bbox)


def _union(boxes):
    b = np.array(boxes, np.float64)
    return b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()


def _warp(a: np.ndarray, M: np.ndarray, W: int, H: int, interp=cv2.INTER_LINEAR) -> np.ndarray:
    if np.allclose(M[2], [0, 0, 1]):
        return cv2.warpAffine(a, M[:2].astype(np.float32), (W, H), flags=interp)
    return cv2.warpPerspective(a, M.astype(np.float64), (W, H), flags=interp)


def _letter_layers(g: Glyphs, W: int, H: int, lay: Layout):
    font, chars, xs, m = layout(g)
    total_h = m["ascent"] + m["descent"]
    ox = (W - m["width"]) / 2.0
    oy = (H - total_h) / 2.0
    baseline = oy + m["ascent"]
    cap_h = m["ascent"] - m["cap_top"]
    mid_y = baseline - cap_h / 2  # optical centre of the caps: bulge / word transforms pivot here

    path = None
    if lay.mode == "arc":
        if lay.curve is not None:
            path = ArcPath(np.asarray(lay.curve, np.float64) * np.array([W, H]))
        else:
            path = ArcPath(bend_curve(lay.bend, max(m["width"], 1.0), W / 2, mid_y))
    s_centre = (lay.align * path.length) if path is not None else 0.0
    word_M = _tf(g.word, W / 2, mid_y) if g.word else np.eye(3)

    face = np.zeros((H, W), np.float32)
    ids = np.zeros((H, W), np.int32)
    centres, boxes = {}, {}
    for i, ch in enumerate(chars):
        bb = font.getbbox(ch)
        centres[i] = (ox + xs[i] + (bb[0] + bb[2]) / 2, oy + (bb[1] + bb[3]) / 2)
        boxes[i] = (ox + xs[i] + bb[0], oy + bb[1], ox + xs[i] + bb[2], oy + bb[3])
    groups = {}  # rigid letter groups (Animate target "word" on a letter selection) pivot on their mean centre
    for i, lt in g.letters.items():
        if "group" in lt and i in centres:
            groups.setdefault(lt["group"].get("id"), []).append(i)
    for i, ch in enumerate(chars):
        if not ch.strip():
            continue
        lt = g.letters.get(i, {})
        layer = Image.new("L", (W, H), 0)
        ImageDraw.Draw(layer).text((ox + xs[i], oy), ch, font=font, fill=255)
        a = np.asarray(layer, np.float32) / 255.0
        cx, cy = centres[i]
        M = _tf(lt, cx, cy, boxes[i]) if lt else np.eye(3)
        if "group" in lt:
            members = groups[lt["group"].get("id")]
            gx, gy = np.mean([centres[j] for j in members], axis=0)
            M = _tf(lt["group"], gx, gy, _union([boxes[j] for j in members])) @ M
        if lay.bulge:
            u = (cx - ox) / max(m["width"], 1.0)
            M = _affine(0, 1.0, bulge_scale(u, lay.bulge), cx, mid_y) @ M
        if path is not None:
            pt, ang = path.at(s_centre + (cx - (ox + m["width"] / 2)))
            M = _affine(math.degrees(ang), 1, 1, cx, mid_y, pt[0] - cx, pt[1] - mid_y) @ M
        M = word_M @ M
        if not np.allclose(M, np.eye(3)):
            a = _warp(a, M, W, H)
        ids[a > 0.5] = i + 1
        face = np.maximum(face, a)
    if _has_free(g.word):  # whole-word free transform: warp the laid-out title by its real box
        ys_, xs_ = np.nonzero(face > 0.5)
        if len(ys_):
            P = _free(g.word, (xs_.min(), ys_.min(), xs_.max() + 1, ys_.max() + 1))
            face = _warp(face, P, W, H)
            ids = _warp(ids.astype(np.float32), P, W, H, cv2.INTER_NEAREST).astype(np.int32)
    geo = {"ox": ox, "baseline": baseline, "mid_y": mid_y, "path": path, "s_centre": s_centre, "word_M": word_M}
    return face, ids, m, geo, chars


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


def _texture(kind: str, H: int, W: int, scale: float, angle: float, intensity: np.ndarray,
             ox: int = 0, oy: int = 0, FW: int | None = None, FH: int | None = None) -> np.ndarray:
    """Return a 0/1 coverage map for a shadow texture, modulated by intensity (0..1).

    The H x W tile sits at (ox, oy) on an FW x FH canvas: patterns stay locked to the canvas, so a moving
    crop never makes them swim."""
    FW, FH = FW or W, FH or H
    if kind in ("noise", "pixel") and (W, H) != (FW, FH):
        full = np.zeros((FH, FW), np.float32)
        full[oy:oy + H, ox:ox + W] = intensity
        return _texture(kind, FH, FW, scale, angle, full)[oy:oy + H, ox:ox + W]
    yy, xx = np.mgrid[oy:oy + H, ox:ox + W].astype(np.float32)
    a = math.radians(angle)
    u = xx * math.cos(a) + yy * math.sin(a)
    v = -xx * math.sin(a) + yy * math.cos(a)
    cv_ = [-x * math.sin(a) + y * math.cos(a) for x in (0, FW - 1) for y in (0, FH - 1)]
    vmin, vptp = min(cv_), max(cv_) - min(cv_)
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
        return intensity * np.clip(1 - (v - vmin) / (vptp + 1e-6) * 0.8, 0, 1)
    raise ValueError(f"unknown shadow texture: {kind}")


def render_title(g: Glyphs, look: Look3D | None = None, shadow: Shadow | None = None,
                 width: int = 1280, height: int = 720, lay: Layout | None = None,
                 guides="all") -> dict[str, np.ndarray]:
    """guides: "all", "none"/"" or an iterable / comma string of GUIDE_LINES to draw in the guides pass."""
    look = look or Look3D()
    shadow = shadow or Shadow()
    lay = lay or Layout()
    W, H = width, height
    face, ids, m, geo, chars = _letter_layers(g, W, H, lay)
    if lay.flag_amp:
        mx, my = flag_maps(W, H, lay)
        face = cv2.remap(face, mx, my, cv2.INTER_LINEAR, borderValue=0)
        ids = cv2.remap(ids.astype(np.float32), mx, my, cv2.INTER_NEAREST, borderValue=0).astype(np.int32)

    # work only on the title's box (+ room for extrusion, bevel and shadow); pasted back into the canvas at the end
    FW, FH = W, H
    x0, y0, x1, y1 = 0, 0, W, H
    ys_, xs_ = np.nonzero(face > 0.01)
    if len(ys_) and not lay.vanish:  # a vanishing point can pull the extrusion anywhere: keep the full canvas
        pad = int(look.extrude + look.bevel + (shadow.length + 3 * shadow.softness if shadow.on else 0)) + 8
        x0, x1 = max(0, xs_.min() - pad), min(W, xs_.max() + pad + 1)
        y0, y1 = max(0, ys_.min() - pad), min(H, ys_.max() + pad + 1)
        face, ids = face[y0:y1, x0:x1], ids[y0:y1, x0:x1]
        W, H = x1 - x0, y1 - y0
    fm = (face > 0.5).astype(np.float32)

    # extrusion: stack copies receding along extrude_angle, or converging on a vanishing point
    ea = math.radians(look.extrude_angle)
    dx, dy = math.cos(ea), math.sin(ea)
    sides = np.zeros_like(face)
    side_depth = np.zeros_like(face)
    vp = np.array([lay.vp_x * W, lay.vp_y * H])
    if lay.vanish:
        yy, xx = np.nonzero(fm)
        centroid = np.array([xx.mean(), yy.mean()]) if len(xx) else np.array([W / 2, H / 2])
        dist = max(float(np.linalg.norm(vp - centroid)), 1.0)
    steps = [k / 2 for k in range(2 * look.extrude, 0, -1)] if lay.vanish else range(look.extrude, 0, -1)
    for k in steps:
        if lay.vanish:  # shrink toward the VP so the centroid travels k px
            s = max(0.0, 1 - k / dist)
            M = np.float32([[s, 0, (1 - s) * vp[0]], [0, s, (1 - s) * vp[1]]])
        else:
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
    if lay.flag_amp and lay.flag_shade:
        shade = flag_shading(FW, lay)[None, x0:x1, None]
        face_rgb = np.clip(face_rgb * shade, 0, 1)
        side_rgb = np.clip(side_rgb * shade, 0, 1)

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
        shadow_mask = _texture(shadow.texture, H, W, shadow.texture_scale, shadow.texture_angle, acc,
                               x0, y0, FW, FH) * (acc > 0.02)
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

    show = parse_guides(guides)
    W, H = FW, FH
    guides = (draw_guides(W, H, geo["ox"], geo["baseline"], m, path=geo["path"], s_centre=geo["s_centre"],
                          mid_y=geo["mid_y"], show=show) if show else np.zeros((H, W, 4), np.float32))
    if lay.flag_amp and show:
        guides = cv2.remap(guides, mx, my, cv2.INTER_LINEAR, borderValue=0)

    out = {
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
    if (x1 - x0, y1 - y0) != (W, H):
        for k, a in out.items():
            if k != "guides":
                full = np.zeros((H, W) + a.shape[2:], np.float32)
                full[y0:y1, x0:x1] = a
                out[k] = full
    if lay.tilt_x or lay.tilt_y:
        Hm = tilt_homography(W, H, lay.tilt_x, lay.tilt_y, lay.fov)
        for k, a in out.items():
            interp = cv2.INTER_NEAREST if k in ("face", "sides", "alpha", "letter_ids") else cv2.INTER_LINEAR
            out[k] = cv2.warpPerspective(a, Hm, (W, H), flags=interp, borderValue=0).astype(np.float32)
    return out


def parse_guides(spec) -> tuple[str, ...]:
    """'all' | 'none' | 'baseline,mid' | iterable -> the guide lines to draw, in canonical order."""
    if spec is None or spec is True or (isinstance(spec, str) and spec.strip().lower() == "all"):
        return GUIDE_LINES
    if spec is False:
        return ()
    if isinstance(spec, str):
        spec = [] if spec.strip().lower() in ("", "none", "off") else spec.split(",")
    want = {s.strip().lower() for s in spec}
    bad = want - set(GUIDE_LINES)
    if bad:
        raise ValueError(f"unknown guide lines: {sorted(bad)}; choose from {GUIDE_LINES}")
    return tuple(n for n in GUIDE_LINES if n in want)


def _dashed(d: ImageDraw.ImageDraw, pts: np.ndarray, dash: float, gap: float, fill, width=2):
    """Dashed polyline: walk the points, toggling pen every dash/gap px of arc length."""
    on, left = True, dash
    for p, q in zip(pts[:-1], pts[1:]):
        seg = q - p
        L = float(np.hypot(*seg))
        pos = 0.0
        while L - pos > 1e-6:
            step = min(left, L - pos)
            a, b = p + seg * (pos / L), p + seg * ((pos + step) / L)
            if on:
                d.line([tuple(a), tuple(b)], fill=fill, width=width)
            pos += step
            left -= step
            if left <= 1e-6:
                on = not on
                left = dash if on else gap


def draw_guides(W: int, H: int, ox: float, baseline: float, m: dict, color=(0.56, 0.57, 1.0),
                path: ArcPath | None = None, s_centre: float = 0.0, mid_y: float = 0.0,
                show=GUIDE_LINES) -> np.ndarray:
    """Dashed type guides (RGBA): ascender, cap line, x-height, mid (cap midline), baseline (long dashes), descender.

    With an arc path the guides follow the curve, offset along its normal."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top = baseline - m["ascent"]
    lines = {
        "ascender": top,
        "cap": top + m["cap_top"],
        "x-height": top + m["x_top"],
        "mid": baseline - (baseline - top - m["cap_top"]) / 2,  # cap midline: arcs, bulge and word pivots run here
        "baseline": baseline,
        "descender": baseline + m["descent"],
    }
    c = tuple(int(v * 255) for v in color)
    x0, x1 = max(0, int(ox - 40)), min(W, int(ox + m["width"] + 40))
    for name, y in lines.items():
        if name not in show:
            continue
        dash = {"baseline": 40, "mid": 5}.get(name, 14)
        fill = c + (230 if name == "baseline" else 150,)
        if path is not None:
            half = m["width"] / 2 + 40
            pts = path.polyline(mid_y - y, s_centre - half, s_centre + half, 240)
            _dashed(d, pts, dash, 8, fill)
            d.text((pts[-1][0] + 6, pts[-1][1] - 8), name, fill=c + (200,))
            continue
        _dashed(d, np.array([[x0, y], [x1, y]], np.float64), dash, 8, fill)
        d.text((x1 + 6, y - 8), name, fill=c + (200,))
    return np.asarray(img, np.float32) / 255.0
