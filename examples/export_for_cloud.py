"""Comfy Cloud fallback, step 1 (on your Mac, no ComfyUI needed): render the hero rig and write the guides an LTX-2
workflow on Comfy Cloud can load with core nodes only.

Writes to OUT (default examples/out/cloud/):
  depth.mp4    the rig depth frames + your track: load it in example_workflows/titlerig_cloud_ltx2.json
  edges.mp4    the rig edges (for a Canny IC-LoRA instead of Depth)
  beauty.mp4   the rig render, for reference
  rig.npz      alpha + shadow masks per frame: what spell_lock_video.py needs afterwards
  prompt.txt   the Style Preset's LTX-2.3 prompt (paste into the Prompt node) and negative.txt
  still_depth.png / still_alpha.png / flux_prompt.txt   the settled last pose, for a FLUX.1 Depth still on Cloud
  track.wav    the exact audio the motion was cut to

Same motion as example_workflows/titlerig_ltx2_animated.json: kicks pop the letters, hats make them hop (bounce,
retrigger finish), kicks throw the shadow; frames padded to LTX's 8n+1 rule.

Run: python examples/export_for_cloud.py [--text TITLERIG] [--preset "Chrome Slam"] [--audio track.wav|.mp3]
                                         [--seconds 5] [--width 1280 --height 720] [--out DIR]"""
import argparse
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from render import Glyphs, Layout  # noqa: E402
from render.animate import Anim, Track, pad_frames, render_frames  # noqa: E402
from render.audio import audio_curve, load_wav  # noqa: E402
from render.presets import PRESETS, build_prompt, ltx_frames, suggested_look  # noqa: E402

FPS = 24.0
LTX_NEGATIVE = "blurry, low quality, still frame, frames, watermark, overlay, has blurbox, has subtitles"


def to_wav(src, dst):
    """Any audio ffmpeg reads -> 16-bit PCM WAV (load_wav reads WAV only)."""
    if src.lower().endswith(".wav"):
        shutil.copy(src, dst)
        return
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le",
                    dst], check=True)


def write_mp4(path, frames, audio=None, fps=FPS):
    """(N, H, W, 3) float frames -> H.264 MP4 (lossless-ish crf 12: these are control signals)."""
    n, h, w = frames.shape[:3]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-"]
    cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"] if audio else []
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "12", "-movflags", "+faststart", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write((np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"ffmpeg failed writing {path}")


def hero_anim(wav, seconds):
    mono, sr = load_wav(wav)
    kick = audio_curve(mono, sr, FPS, band="bass", mode="beats", sensitivity=0.5, release=0.18, max_seconds=seconds)
    hat = audio_curve(mono, sr, FPS, band="highs", mode="beats", sensitivity=0.15, release=0.12, max_seconds=seconds)
    return Anim([
        Track(effect="pop", drive=kick["values"], amount=-35, stagger=0.042, order="center_out"),
        Track(effect="drop", drive=hat["values"], amount=28, stagger=0.042, order="center_out", response="trigger",
              easing="bounce", duration=0.3, retrigger="finish"),
        Track(effect="shadow_length", drive=kick["values"], amount=40),
    ], fps=FPS)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--text", default="TITLERIG")
    ap.add_argument("--preset", default="Chrome Slam")
    ap.add_argument("--audio", default=os.path.join(HERE, "assets", "titlerig_beat.wav"))
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "cloud"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    wav = os.path.join(a.out, "track.wav")
    to_wav(a.audio, wav)

    look, shadow = suggested_look(a.preset)
    anim = hero_anim(wav, a.seconds)
    p = render_frames(anim, Glyphs(text=a.text, font="Anton", size=200, tracking=4.0), look, shadow, a.width,
                      a.height, Layout(mode="arc", bend=0.15), passes=("beauty", "alpha", "depth", "edges", "shadow"))
    n = ltx_frames(p["beauty"].shape[0])
    p = pad_frames(p, n)
    pos, _ = build_prompt(a.preset, a.text, target="ltx23_video")

    write_mp4(os.path.join(a.out, "depth.mp4"), p["depth"], audio=wav)
    write_mp4(os.path.join(a.out, "edges.mp4"), p["edges"])
    b = p["beauty"]
    bg = np.array([int(PRESETS[a.preset].backdrop[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)
    write_mp4(os.path.join(a.out, "beauty.mp4"), b[..., :3] * b[..., 3:] + bg * (1 - b[..., 3:]))
    np.savez_compressed(os.path.join(a.out, "rig.npz"), alpha=(p["alpha"] * 255).astype(np.uint8),
                        shadow=(p["shadow"] * 255).astype(np.uint8), fps=FPS)
    with open(os.path.join(a.out, "prompt.txt"), "w") as f:
        f.write(pos + "\n")
    with open(os.path.join(a.out, "negative.txt"), "w") as f:
        f.write(LTX_NEGATIVE + "\n")  # the hero workflow's negative (ComfyUI template, minus "titles")
    from PIL import Image
    Image.fromarray((p["depth"][-1] * 255).astype(np.uint8)).save(os.path.join(a.out, "still_depth.png"))
    Image.fromarray((p["alpha"][-1] * 255).astype(np.uint8)).save(os.path.join(a.out, "still_alpha.png"))
    Image.fromarray((p["shadow"][-1] * 255).astype(np.uint8)).save(os.path.join(a.out, "still_shadow.png"))
    with open(os.path.join(a.out, "flux_prompt.txt"), "w") as f:
        f.write(build_prompt(a.preset, a.text, target="flux1_depth")[0] + "\n")
    print(f"{n} frames ({n / FPS:.2f} s at {a.width}x{a.height}) -> {a.out}")
    print("next: upload depth.mp4 to Comfy Cloud, open titlerig_cloud_ltx2.json, paste prompt.txt into the Prompt node")


if __name__ == "__main__":
    main()
