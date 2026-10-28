"""Comfy Cloud fallback, step 3 (on your Mac): Spell-Lock an LTX video against the rig from export_for_cloud.py,
then put the original track back on. Give it a PNG / JPG instead (a FLUX still made from still_depth.png) and it
locks that against still_alpha.png and writes <name>_spell_locked.png.

The LTX frames are resized to the rig's size if they differ (LTX rounds sizes to its latent grid). Prints the
drift before / after (0 = the AI letters match the rig exactly).

Run: python examples/spell_lock_video.py ltx_result.mp4 [--rig examples/out/cloud] [--out locked.mp4]
                                          [--strength 1.0] [--tolerance 2] [--ring 24] [--max-shift 6]"""
import argparse
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from export_for_cloud import write_mp4  # noqa: E402
from render.spell_lock import spell_lock_batch  # noqa: E402


def read_video(path, size):
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        f = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        if (f.shape[1], f.shape[0]) != size:
            f = cv2.resize(f, size, interpolation=cv2.INTER_AREA)
        frames.append(f.astype(np.float32) / 255)
    if not frames:
        raise SystemExit(f"could not read any frames from {path}")
    return np.stack(frames)


def lock_still(a):
    from PIL import Image
    alpha = np.asarray(Image.open(os.path.join(a.rig, "still_alpha.png")).convert("L"), np.float32) / 255
    shadow = np.asarray(Image.open(os.path.join(a.rig, "still_shadow.png")).convert("L"), np.float32) / 255
    img = Image.open(a.video).convert("RGB").resize((alpha.shape[1], alpha.shape[0]), Image.LANCZOS)
    r = spell_lock_batch(np.asarray(img, np.float32)[None] / 255, alpha, strength=a.strength,
                         tolerance=a.tolerance, ring=a.ring, shadow=shadow, max_shift=a.max_shift)
    out = a.out or os.path.splitext(a.video)[0] + "_spell_locked.png"
    Image.fromarray((np.clip(r["frames"][0], 0, 1) * 255).astype(np.uint8)).save(out)
    print(f"drift before {r['drift_before'][0]:.4f} -> after {r['drift_after'][0]:.4f}; wrote {out}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("--rig", default=os.path.join(HERE, "out", "cloud"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--tolerance", type=int, default=2)
    ap.add_argument("--ring", type=int, default=24)
    ap.add_argument("--max-shift", type=float, default=6.0)
    a = ap.parse_args(argv)
    if a.video.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return lock_still(a)
    rig = np.load(os.path.join(a.rig, "rig.npz"))
    alpha = rig["alpha"].astype(np.float32) / 255
    shadow = rig["shadow"].astype(np.float32) / 255
    frames = read_video(a.video, (alpha.shape[2], alpha.shape[1]))
    n = min(len(frames), len(alpha))
    if len(frames) != len(alpha):
        print(f"note: video has {len(frames)} frames, rig has {len(alpha)}; locking the first {n}")
    r = spell_lock_batch(frames[:n], alpha[:n], strength=a.strength, tolerance=a.tolerance, ring=a.ring,
                         shadow=shadow[:n], max_shift=a.max_shift)
    out = a.out or os.path.splitext(a.video)[0] + "_spell_locked.mp4"
    track = os.path.join(a.rig, "track.wav")
    write_mp4(out, r["frames"], audio=track if os.path.exists(track) else None, fps=float(rig["fps"]))
    print(f"drift before {np.mean(r['drift_before']):.4f} -> after {np.mean(r['drift_after']):.4f}; wrote {out}")


if __name__ == "__main__":
    main()
