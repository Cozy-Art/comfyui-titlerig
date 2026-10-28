"""Cutout text: one image or video inside the letters, another outside, masked by the rig (per frame).

Sources are (N, H, W, 3) float arrays in 0..1 (a still is N = 1). The rig masks are (M, H, W). The output has the
mask's size, and max(M, sources) frames when the mask is a still; shorter sources loop, hold or ping-pong."""
from __future__ import annotations

import cv2
import numpy as np

FITS = ("cover", "contain", "stretch")
MASK_FROM = ("faces + extrusion", "faces", "silhouette + shadow")
TIMING = ("loop", "hold", "pingpong")


def pick_mask(alpha, face=None, shadow=None, mask_from: str = "faces + extrusion") -> np.ndarray:
    """The letter mask the cutout uses. alpha = faces + extrusion (the rig's alpha)."""
    if mask_from == "faces":
        if face is None:
            raise ValueError("mask_from 'faces' needs the rig's face mask connected")
        return face
    if mask_from == "silhouette + shadow":
        if shadow is None:
            raise ValueError("mask_from 'silhouette + shadow' needs the rig's shadow mask connected")
        return np.maximum(alpha, shadow)
    return alpha


def frame_index(f: int, n: int, timing: str = "loop") -> int:
    if n <= 1:
        return 0
    if timing == "hold":
        return min(f, n - 1)
    if timing == "pingpong":
        p = f % (2 * n - 2)
        return p if p < n else 2 * n - 2 - p
    return f % n


def fit(img: np.ndarray, W: int, H: int, mode: str = "cover") -> tuple[np.ndarray, np.ndarray]:
    """Resize one (h, w, 3) frame to W x H. Returns (rgb, coverage): coverage is 0 on contain's letterbox bars."""
    h, w = img.shape[:2]
    if mode == "stretch" or (w, h) == (W, H):
        out = img if (w, h) == (W, H) else cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
        return out, np.ones((H, W), np.float32)
    s = max(W / w, H / h) if mode == "cover" else min(W / w, H / h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    rgb = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    # centre the resized frame on the canvas (crop for cover, bars for contain)
    sx, sy = (nw - W) // 2, (nh - H) // 2
    x0, y0 = max(0, -sx), max(0, -sy)
    cx, cy = max(0, sx), max(0, sy)
    cw, ch = min(W - x0, nw - cx), min(H - y0, nh - cy)
    rgb[y0:y0 + ch, x0:x0 + cw] = r[cy:cy + ch, cx:cx + cw]
    cov[y0:y0 + ch, x0:x0 + cw] = 1
    return rgb, cov


def shape_mask(m: np.ndarray, grow: float = 0.0, feather: float = 0.0) -> np.ndarray:
    """Grow (+) or shrink (-) the mask by px, then feather its edge (px of blur)."""
    m = m.astype(np.float32)
    if grow:
        inside = m > 0.5
        if grow > 0:
            d = cv2.distanceTransform((~inside).astype(np.uint8), cv2.DIST_L2, 5)
            m = np.maximum(m, np.clip(grow + 0.5 - d, 0, 1))
        else:
            d = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5)
            m = np.minimum(m, np.clip(d + grow + 0.5, 0, 1))
    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), feather / 2)
    return np.clip(m, 0, 1)


def stroke_ring(m: np.ndarray, width: float) -> np.ndarray:
    """A width-px outline just outside the mask (soft edged)."""
    d = cv2.distanceTransform((m <= 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    return np.clip(width + 0.5 - d, 0, 1) * (1 - m)


def shade_map(beauty: np.ndarray, m: np.ndarray) -> np.ndarray:
    """The rig's lighting as a multiplier: luminance over the letters' bright level (bevel, extrusion, shadow)."""
    lum = beauty[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    ref = np.percentile(lum[m > 0.5], 95) if (m > 0.5).any() else 1.0
    return np.clip(lum / max(ref, 1e-3), 0, 1.25)


def cutout(inside: np.ndarray, mask: np.ndarray, outside: np.ndarray | None = None, beauty: np.ndarray | None = None,
           fit_inside: str = "cover", fit_outside: str = "cover", grow: float = 0.0, feather: float = 0.0,
           stroke: float = 0.0, stroke_color=(1.0, 1.0, 1.0), shading: float = 0.0, timing: str = "loop",
           outside_color=(0.0, 0.0, 0.0)) -> tuple[np.ndarray, np.ndarray]:
    """Composite inside-the-letters over outside. Returns (rgb (N, H, W, 3), alpha (N, H, W)).

    alpha is the letters (+ stroke): with no `outside` it makes the result a transparent cutout."""
    mask = mask[None] if mask.ndim == 2 else mask
    inside = inside[None] if inside.ndim == 3 else inside
    outside = None if outside is None else (outside[None] if outside.ndim == 3 else outside)
    beauty = None if beauty is None else (beauty[None] if beauty.ndim == 3 else beauty)
    H, W = mask.shape[1:3]
    n = mask.shape[0] if mask.shape[0] > 1 else max(len(inside), len(outside) if outside is not None else 1)
    rgb_out = np.empty((n, H, W, 3), np.float32)
    a_out = np.empty((n, H, W), np.float32)
    sc = np.asarray(stroke_color, np.float32)
    oc = np.asarray(outside_color, np.float32)
    cache: dict = {}

    def src(stack, f, mode, key):
        i = frame_index(f, len(stack), timing)
        k = (key, i)
        if k not in cache:
            if len(cache) > 8:  # stills stay cached; video frames are used once
                cache.clear()
            cache[k] = fit(stack[i].astype(np.float32), W, H, mode)
        return cache[k]

    for f in range(n):
        mf = mask[frame_index(f, len(mask), timing)]
        m = shape_mask(mf, grow, feather)
        ins, ins_cov = src(inside, f, fit_inside, "in")
        if shading and beauty is not None:
            b = beauty[frame_index(f, len(beauty), timing)]
            ins = ins * (1 - shading + shading * shade_map(b, mf))[..., None]
        if outside is not None:
            out, out_cov = src(outside, f, fit_outside, "out")
            base = out * out_cov[..., None] + oc * (1 - out_cov[..., None])
        else:
            base = np.broadcast_to(oc, (H, W, 3))
        a = m * ins_cov
        rgb = base
        if stroke > 0:
            ring = stroke_ring(shape_mask(mf, grow), stroke)
            rgb = rgb * (1 - ring[..., None]) + sc * ring[..., None]
            a = np.maximum(a, ring)
        rgb = rgb * (1 - (m * ins_cov)[..., None]) + ins * (m * ins_cov)[..., None]
        rgb_out[f] = np.clip(rgb, 0, 1)
        a_out[f] = a
    return rgb_out, a_out
