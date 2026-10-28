"""Spell-Lock v1: mask-based edge restore for AI-painted titles (no OCR).

The rig's alpha says exactly where letters are. In each AI frame:
  * snap   = a smooth, capped displacement (optical flow from the rig alpha to the frame's "letterness") warps the
             frame so its letters land on the rig silhouette; texture and outlines travel with the letters
  * spill  = pixels outside the silhouette that look like the letters' material -> inpainted with background
  * holes  = pixels inside the silhouette that look like background              -> inpainted from letter material
Colours are small k-means palettes (letters: faces, sides, outlines; background), so multi-material letters work. An
optional shadow mask marks intended shadows so they never count as spill. Drift is 1 - IoU between the frame's own
letter silhouette and the rig alpha (0 = locked to the rig, 1 = lost).
"""
from __future__ import annotations

import cv2
import numpy as np


def _u8(a: np.ndarray) -> np.ndarray:
    return (np.clip(a, 0, 1) * 255).astype(np.uint8)


def _disk(r: int) -> np.ndarray:
    r = max(1, int(r))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def edges_of(img: np.ndarray) -> np.ndarray:
    """Binary edges of an RGB float image (Canny on luminance, light blur first)."""
    lum = cv2.GaussianBlur(cv2.cvtColor(_u8(img), cv2.COLOR_RGB2GRAY), (0, 0), 1.0)
    return cv2.Canny(lum, 40, 120) > 0


def drift(img: np.ndarray, alpha: np.ndarray, tolerance: int = 2, ring: int = 24) -> float:
    """1 - IoU between the frame's letter silhouette (by its own colours) and the rig alpha (0 = locked)."""
    A = (alpha > 0.5).astype(np.uint8)
    if not A.any():
        return 0.0
    inside = cv2.erode(A, _disk(tolerance)) > 0
    band = cv2.dilate(A, _disk(ring)) > 0
    ring_bg = band & ~(cv2.dilate(A, _disk(tolerance)) > 0)
    letter_c, bg_c, _ = palettes(img, inside, ring_bg)
    L = (letterness(img, letter_c, bg_c) > 0.5) & band
    A = A > 0
    return float(1.0 - (L & A).sum() / max((L | A).sum(), 1))


def _colour_model(img: np.ndarray, mask: np.ndarray, k: int = 1) -> np.ndarray:
    """Up to k colour centres (k-means) of the pixels under mask, shape (k, 3)."""
    px = img[mask].reshape(-1, 3).astype(np.float32)
    if len(px) == 0:
        return np.zeros((1, 3), np.float32)
    if k <= 1 or len(px) < 50:
        return np.median(px, axis=0, keepdims=True).astype(np.float32)
    if len(px) > 20000:
        px = px[np.random.default_rng(0).choice(len(px), 20000, replace=False)]
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    cv2.setRNGSeed(0)
    _, labels, centres = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=k)
    return centres[counts > 0.02 * len(px)].astype(np.float32)  # ignore tiny clusters


def _dist(img: np.ndarray, centres: np.ndarray) -> np.ndarray:
    """Distance from each pixel to the nearest centre."""
    return np.min(np.linalg.norm(img[..., None, :] - centres[None, None], axis=-1), axis=-1)


def palettes(img: np.ndarray, inside: np.ndarray, ring_bg: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Letter palette (faces, sides, outlines), background palette, and their separation.

    Each side's palette drops centres that are near-copies of the other side's majority colour: a stray letter-coloured
    stroke in the ring is spill, not background; a background-coloured dropped chunk inside is a hole, not letter."""
    letter = _colour_model(img, inside, 3)
    bg = _colour_model(img, ring_bg, 2)
    bg_main = _colour_model(img, ring_bg, 1)
    letter_main = _colour_model(img, inside, 1)
    scale = float(_dist(letter_main, bg_main)[0, 0]) or 1.0
    bg = bg[_dist(bg[None], letter)[0] > 0.25 * scale] if len(bg) > 1 else bg
    bg = bg if len(bg) else bg_main
    letter = letter[_dist(letter[None], bg)[0] > 0.25 * scale] if len(letter) > 1 else letter
    letter = letter if len(letter) else letter_main
    sep = float(np.min(_dist(letter[None], bg)))
    return letter, bg, sep


def letterness(img: np.ndarray, letter_c: np.ndarray, bg_c: np.ndarray) -> np.ndarray:
    """0..1 per pixel: how much a pixel looks like the letters' material rather than the background."""
    d_l = _dist(img, letter_c)
    d_b = _dist(img, bg_c)
    return (d_b / (d_b + d_l + 1e-6)).astype(np.float32)


def snap(img: np.ndarray, alpha: np.ndarray, letter_c: np.ndarray, bg_c: np.ndarray, max_shift: float,
         band: np.ndarray, protected: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Warp the frame so its letters sit on the rig silhouette. Returns (warped frame, shift magnitude px).

    The warp only acts where the frame's letterness and the rig disagree (a clean frame stays put), never inside
    protected (intended shadow) areas."""
    L = cv2.GaussianBlur(letterness(img, letter_c, bg_c), (0, 0), 1.2)
    A = cv2.GaussianBlur((alpha > 0.5).astype(np.float32), (0, 0), 1.2)
    mismatch = cv2.GaussianBlur(np.abs(L - A), (0, 0), 2.0)
    active = np.clip((mismatch - 0.12) / 0.18, 0, 1)  # smooth gate: ~0 where the frame already matches the rig
    if not (active > 0.05).any():
        return img, np.zeros(alpha.shape, np.float32)
    flow = cv2.calcOpticalFlowFarneback(_u8(A), _u8(L), None, 0.5, 3, 15, 5, 5, 1.1, 0)
    weight = cv2.GaussianBlur(band.astype(np.float32), (0, 0), 3.0) * cv2.GaussianBlur(active, (0, 0), 3.0)
    if protected is not None:
        guard = cv2.dilate(protected.astype(np.uint8), _disk(int(max_shift) + 4)).astype(np.float32)
        weight *= 1.0 - cv2.GaussianBlur(guard, (0, 0), 2.0)
    flow = flow * weight[..., None]
    mag = np.linalg.norm(flow, axis=2)
    scale = np.minimum(1.0, max_shift / np.maximum(mag, 1e-6))
    flow = flow * scale[..., None]
    H, W = alpha.shape
    mx, my = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    warped = cv2.remap(img, mx + flow[..., 0], my + flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return warped.astype(np.float32), np.minimum(mag, max_shift)


def spell_lock(img: np.ndarray, alpha: np.ndarray, strength: float = 1.0, tolerance: int = 2, ring: int = 24,
               shadow: np.ndarray | None = None, inpaint_radius: int = 5,
               max_shift: float = 6.0) -> tuple[np.ndarray, np.ndarray]:
    """Restore one AI frame (H,W,3 float 0..1) to the rig's silhouette `alpha` (H,W). Returns (frame, fix_mask).

    max_shift: px the snap warp may move letter material (0 = no warp, recolour only)."""
    H, W = img.shape[:2]
    if alpha.shape != (H, W):
        alpha = cv2.resize(alpha.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    if shadow is not None and shadow.shape != (H, W):
        shadow = cv2.resize(shadow.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    a = (alpha > 0.5).astype(np.uint8)
    inside = cv2.erode(a, _disk(tolerance)) > 0
    near = cv2.dilate(a, _disk(tolerance)) > 0
    band = cv2.dilate(a, _disk(ring)) > 0
    ring_bg = band & ~near
    if shadow is not None:
        protected = cv2.dilate((shadow > 0.05).astype(np.uint8), _disk(tolerance)) > 0
        ring_bg &= ~protected
    else:
        protected = np.zeros((H, W), bool)

    letter_c, bg_c, contrast = palettes(img, inside, ring_bg)
    orig = img
    shift = np.zeros((H, W), np.float32)
    if max_shift > 0:
        img, shift = snap(img, alpha, letter_c, bg_c, max_shift, band, protected)
    d_letter = _dist(img, letter_c)
    d_bg = _dist(img, bg_c)
    margin = 0.15 * contrast  # be sure before calling a pixel the wrong material
    if shadow is not None and protected.any():  # intended shadow is protected only where it looks like shadow
        shadow_zone = protected & ~near
        sh_c = _colour_model(img, shadow_zone, 2)
        d_sh = _dist(img, sh_c)
        protected = protected & ~(d_letter + margin < d_sh)

    spill = band & ~near & ~protected & (d_letter + margin < d_bg)
    holes = inside & (d_bg + margin < d_letter)
    spill = cv2.morphologyEx(spill.astype(np.uint8), cv2.MORPH_OPEN, _disk(1)) > 0
    holes = cv2.morphologyEx(holes.astype(np.uint8), cv2.MORPH_OPEN, _disk(1)) > 0
    # take the soft halo around each fix too (half-letter, half-ground pixels), but stay on the right side
    grow = _disk(max(1, tolerance))
    spill = (cv2.dilate(spill.astype(np.uint8), grow) > 0) & ~near & ~protected
    holes = (cv2.dilate(holes.astype(np.uint8), grow) > 0) & inside

    fixed = _u8(img)
    if spill.any():  # background from the surroundings, letters hidden from the inpainter
        fill = fixed.copy()
        fill[near] = (bg_c[0] * 255).astype(np.uint8)
        out = cv2.inpaint(fill, cv2.dilate(spill.astype(np.uint8), _disk(1)), inpaint_radius, cv2.INPAINT_TELEA)
        fixed[spill] = out[spill]
    if holes.any():  # letter material from the surrounding letter interior, background hidden
        fill = fixed.copy()
        fill[~near] = (letter_c[0] * 255).astype(np.uint8)
        out = cv2.inpaint(fill, cv2.dilate(holes.astype(np.uint8), _disk(1)), inpaint_radius, cv2.INPAINT_TELEA)
        fixed[holes] = out[holes]
    fixed = fixed.astype(np.float32) / 255.0
    rec = (spill | holes).astype(np.float32)
    feather = np.maximum(np.minimum(cv2.GaussianBlur(rec, (0, 0), 0.8) * 1.5, 1.0) * (rec > 0),
                         cv2.GaussianBlur(rec, (0, 0), 0.8))[..., None]
    corrected = img * (1 - feather) + fixed * feather           # snapped frame + feathered recolour fixes
    fix_mask = np.maximum(rec, (shift > 1.0).astype(np.float32))
    k = float(np.clip(strength, 0, 1))
    result = orig * (1 - k) + corrected * k
    return result.astype(np.float32), fix_mask


def spell_lock_batch(frames: np.ndarray, alpha: np.ndarray, edges: np.ndarray | None = None, strength: float = 1.0,
                     tolerance: int = 2, ring: int = 24, shadow: np.ndarray | None = None,
                     max_shift: float = 6.0) -> dict:
    """Frames (N,H,W,3) + rig alpha (N or 1, H, W) [+ shadow] -> corrected frames, fix masks, drift.

    `edges` is accepted for API compatibility; drift is measured on silhouettes (robust to AI outlines)."""
    frames = np.asarray(frames, np.float32)
    if frames.ndim == 3:
        frames = frames[None]

    def as_masks(arr, rgb_ok=False):
        """Normalise to (M, H, W): (H,W) / (N,H,W) masks, or (H,W,3) / (N,H,W,3) images when rgb_ok."""
        if arr is None:
            return None
        arr = np.asarray(arr, np.float32)
        if rgb_ok and arr.ndim == 4:
            arr = arr[..., 0]
        elif rgb_ok and arr.ndim == 3 and arr.shape[-1] == 3:  # one RGB image (no mask is 3 px wide)
            arr = arr[..., 0]
        return arr[None] if arr.ndim == 2 else arr

    alpha, shadow, edges = as_masks(alpha), as_masks(shadow), as_masks(edges, rgb_ok=True)

    def pick(arr, i):
        return None if arr is None else arr[min(i, len(arr) - 1)]

    out, masks, before, after = [], [], [], []
    for i, fr in enumerate(frames):
        a = pick(alpha, i)
        sh = pick(shadow, i)
        sc = fr.shape[1] / a.shape[1]  # AI frames often run at a different resolution than the rig
        res, m = spell_lock(fr, a, strength, max(1, round(tolerance * sc)), max(2, round(ring * sc)), sh,
                            max_shift=max_shift * sc)
        out.append(res)
        masks.append(m)
        aa = a if a.shape == fr.shape[:2] else cv2.resize(a, (fr.shape[1], fr.shape[0]))
        t, rg = max(1, round(tolerance * sc)), max(2, round(ring * sc))
        before.append(drift(fr, aa, t, rg))
        after.append(drift(res, aa, t, rg))
    return {"frames": np.stack(out), "fix_masks": np.stack(masks), "drift_before": before, "drift_after": after}
