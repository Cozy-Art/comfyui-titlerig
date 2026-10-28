import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render import Glyphs, Look3D, Shadow, render_title  # noqa: E402
from render.spell_lock import drift, spell_lock, spell_lock_batch  # noqa: E402

BG = np.array([0.08, 0.10, 0.30], np.float32)
FG = np.array([0.95, 0.75, 0.20], np.float32)


@pytest.fixture(scope="module")
def rig():
    p = render_title(Glyphs(text="TITLE", size=120), Look3D(extrude=0, bevel=0, bevel_profile="flat", face2=None),
                     Shadow(on=False), 560, 220)
    return p["alpha"], p["edges"]


def paint(alpha, noise=0.03, seed=0):
    """A stand-in 'AI frame': textured letters on a textured ground, following the rig exactly."""
    rng = np.random.default_rng(seed)
    a = cv2.GaussianBlur(alpha, (0, 0), 0.8)[..., None]
    img = FG * a + BG * (1 - a)
    return np.clip(img + rng.normal(0, noise, img.shape), 0, 1).astype(np.float32)


def corrupt(img, alpha):
    """Typical AI misspelling damage: an extra stroke beside a letter and a dropped stroke inside one."""
    bad = img.copy()
    ys, xs = np.nonzero(alpha > 0.5)
    x1, y0, y1 = xs.max(), ys.min(), ys.max()
    bad[y0 + 10:y1 - 10, x1 + 6:x1 + 20] = FG            # extra bar after the last letter
    cy, cx = int(ys.mean()), int(xs.min() + 20)
    bad[cy - 14:cy + 14, cx - 8:cx + 8] = BG             # chunk missing from the first letter
    return bad


def test_clean_frame_is_left_alone(rig):
    alpha, edges = rig
    img = paint(alpha)
    out, fix = spell_lock(img, alpha)
    assert fix.mean() < 0.002 and np.abs(out - img).mean() < 0.002
    assert drift(img, alpha) < 0.1


def test_spill_and_holes_are_restored(rig):
    alpha, edges = rig
    clean = paint(alpha)
    bad = corrupt(clean, alpha)
    out, fix = spell_lock(bad, alpha)
    err_before = np.abs(bad - clean).mean()
    err_after = np.abs(out - clean).mean()
    assert err_after < err_before * 0.35
    assert drift(out, alpha) < drift(bad, alpha)
    assert fix.sum() > 300


def test_strength_zero_is_identity_and_half_is_between(rig):
    alpha, _ = rig
    bad = corrupt(paint(alpha), alpha)
    out0, _ = spell_lock(bad, alpha, strength=0.0)
    out1, _ = spell_lock(bad, alpha, strength=1.0)
    outh, _ = spell_lock(bad, alpha, strength=0.5)
    assert np.allclose(out0, bad)
    assert np.allclose(outh, (out1 + bad) / 2, atol=1e-5)


def test_shadow_mask_protects_intended_shadow(rig):
    alpha, _ = rig
    img = paint(alpha)
    shadow = np.zeros_like(alpha)
    ys, xs = np.nonzero(alpha > 0.5)
    shadow[ys.max() + 4:ys.max() + 14, xs.min():xs.max()] = 1
    img[shadow > 0] = FG * 0.98  # a letter-coloured glow the designer wanted
    _, fix_unprotected = spell_lock(img, alpha)
    _, fix_protected = spell_lock(img, alpha, shadow=shadow)
    assert fix_unprotected[shadow > 0].mean() > 0.5 and fix_protected[shadow > 0].mean() == 0


def test_batch_broadcasts_alpha_and_resizes(rig):
    alpha, edges = rig
    frames = np.stack([corrupt(paint(alpha, seed=i), alpha) for i in range(3)])
    big = np.stack([cv2.resize(f, (1120, 440)) for f in frames])  # AI ran at 2x the rig resolution
    res = spell_lock_batch(big, alpha, edges)
    assert res["frames"].shape == big.shape and len(res["drift_before"]) == 3
    assert all(a < b for a, b in zip(res["drift_after"], res["drift_before"]))
    res = spell_lock_batch(frames, np.stack([alpha] * 3), np.stack([edges] * 3))
    assert res["fix_masks"].shape == (3, 220, 560)


def test_snap_pulls_wobbled_letters_back_onto_the_rig(rig):
    alpha, _ = rig
    clean = paint(alpha, noise=0.01)
    H, W = alpha.shape
    mx, my = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    wob = cv2.remap(clean, mx + 2.5 * np.sin(my / 9).astype(np.float32), my, cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT)
    snapped, _ = spell_lock(wob, alpha, max_shift=6)
    recolour_only, _ = spell_lock(wob, alpha, max_shift=0)
    assert drift(snapped, alpha) < drift(wob, alpha) * 0.7
    assert drift(snapped, alpha) <= drift(recolour_only, alpha) + 1e-6


def test_multi_material_letters_are_not_holes():
    """Faces + dark extrusion + outline are all letter: none of it may be 'fixed' on a clean frame."""
    p = render_title(Glyphs(text="TITLE", size=110), Look3D(extrude=16, bevel=0, bevel_profile="flat"),
                     Shadow(on=False), 560, 220)
    b = p["beauty"]
    img = (b[..., :3] * b[..., 3:] + BG * (1 - b[..., 3:])).astype(np.float32)
    _, fix = spell_lock(img, p["alpha"])
    assert fix.mean() < 0.003 and drift(img, p["alpha"]) < 0.1
