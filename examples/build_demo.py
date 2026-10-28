"""Assemble the 75-second submission video (docs/demo/SCRIPT.md) with ffmpeg.

Title cards are rendered by TitleRig itself; the passes grid and the audio-react shot are rendered from the rig on
the spot (the audio-react letters are driven by the exact slice of the music they play over). Build-night results
go in docs/demo/slots/ (see the README there); a missing slot becomes a labelled placeholder card (or the rig-only
fallback clip), so the cut always builds. Every section boundary is snapped to the nearest kick in the music bed.
Each shot carries a lower-third naming the tools and models in it, as the contest requires.

Run: python examples/build_demo.py [--audio track.wav|.mp3] [--slots docs/demo/slots] [--out examples/out/demo]
                                   [--fast]   (--fast = 640x360 preview; default 1280x720, 24 fps)"""
import argparse
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from render import Glyphs, Layout, Look3D, Shadow, render_title  # noqa: E402
from render.animate import Anim, Track, render_frames  # noqa: E402
from render.audio import audio_curve, load_wav  # noqa: E402
from render.core import layout as measure  # noqa: E402
from render.presets import PRESETS, suggested_look  # noqa: E402

FPS = 24
MEDIA = os.path.join(ROOT, "docs", "media")
FONT = os.path.join(ROOT, "fonts", "Anton-Regular.ttf")
REPO = "github.com/Cozy-Art/comfyui-titlerig"

# (key, planned start s, kind, what, lower-third caption). The video ends at END_AT.
# kinds: card (TitleRig title card: text, preset) | slot (build-night file, fallback) | passes | react
TIMELINE = [
    ("hook", 0, "slot", ("hook_mangled", None, "PLAIN PROMPT"),
     "FLUX.1 [dev], plain prompt: \"3D chrome title that says TITLERIG\". No rig."),
    ("cant_spell", 6, "card", ("AI CAN'T SPELL.", "Trailer Title"), ""),
    ("gave_rig", 8, "card", ("SO WE GAVE IT A RIG.", "Chrome Slam"), "Title cards rendered by TitleRig"),
    ("rig", 12, "slot", ("comfyui_canvas", "preview_widget_dark.png", "THE RIG"),
     "TitleRig: 13 open-source ComfyUI nodes. Text, Look 3D, Shadow, Layout, Animate, Render"),
    ("passes", 22, "passes", None, "TitleRig Render: beauty, depth, edges, alpha, normals, letter IDs"),
    ("ltx_card", 30, "card", ("LTX-2", "Chrome Slam"), ""),
    ("ltx", 32, "slot", ("ltx_result", None, "LTX-2 RESULT"),
     "LTX-2 19B + Depth Control IC-LoRA (Lightricks), guided by the rig's depth, then TitleRig Spell-Lock"),
    ("flux", 42, "slot", ("flux_still", None, "FLUX STILL"),
     "FLUX.1 Depth [dev] (Black Forest Labs) on the rig's depth, then Spell-Lock and a transparent cutout"),
    ("presets_card", 46, "card", ("PRESETS", "Holo Foil"), ""),
    ("preset_1", 48, "slot", ("preset_1", "ben_day_beat.mp4", "PRESET 1"), "Style Preset: Ben-Day Pop"),
    ("preset_2", 52, "slot", ("preset_2", "sphere_ticker.mp4", "PRESET 2"), "Style Preset: Vapor Sunset, sphere wrap"),
    ("preset_3", 56, "slot", ("preset_3", "magnet_snap_back.mp4", "PRESET 3"), "Style Preset: Candy Inflatable, Magnet"),
    ("react_card", 60, "card", ("AUDIO REACT", "Ben-Day Pop"), ""),
    ("react", 62, "react", None, "TitleRig Audio React: kicks pop the letters, hats make them hop, kicks throw the shadow"),
    ("end", 70, "card", ("TITLERIG", "Chrome Slam"),
     f"Open source, MIT · {REPO} · ComfyUI · LTX-2 · FLUX.1 [dev] · Gemma 3 · fonts: Anton, Shrikhand (OFL)"),
]
END_AT = 75.0


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def snap_to_kicks(starts, wav, end):
    """Move each planned cut to the nearest kick (bass onset) within a quarter second; keep order and the end."""
    mono, sr = load_wav(wav)
    kicks = np.array([0.0] + list(audio_curve(mono, sr, FPS, band="bass", mode="beats", sensitivity=0.5,
                                              release=0.18)["onsets"]))
    out = []
    for t in starts:
        k = kicks[np.argmin(np.abs(kicks - t))] if len(kicks) else t
        t2 = float(k) if abs(k - t) <= 0.25 else float(t)
        out.append(max(t2, out[-1] + 1.0 / FPS) if out else 0.0)
    return out, [b - a for a, b in zip(out, out[1:] + [end])]


class Encoder:
    """Pipe RGB frames to an H.264 segment, optionally with a lower-third caption burned in."""

    def __init__(self, path, size, caption=""):
        w, h = size
        vf = lower_third(caption, path, h)
        self.p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                   "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", *(["-vf", vf] if vf else []),
                                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-r", str(FPS), path],
                                  stdin=subprocess.PIPE)

    def write(self, rgb):
        self.p.stdin.write((np.clip(rgb, 0, 1) * 255).astype(np.uint8).tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait():
            raise SystemExit("ffmpeg failed")


def lower_third(caption, path, h):
    """drawtext filter for a caption box at the bottom left (text read from a file: no escaping trouble)."""
    if not caption:
        return ""
    txt = path + ".caption.txt"
    with open(txt, "w") as f:
        f.write(caption)
    fs = max(12, round(h / 34))
    return (f"drawtext=fontfile='{FONT}':textfile='{txt}':fontsize={fs}:fontcolor=white:"
            f"box=1:boxcolor=0x0b0b10@0.72:boxborderw={fs // 2}:x={fs}:y=h-{fs * 3}")


def fit_size(text, max_w, max_h, start=260):
    """Largest Anton size (<= start) whose line fits max_w x max_h."""
    size = start
    while size > 24:
        _, _, _, m = measure(Glyphs(text=text, font="Anton", size=size, tracking=size / 40))
        if m["width"] <= max_w and m["ascent"] + m["descent"] <= max_h:
            return size
        size -= 8
    return size


def card_frames(text, preset, n, size, sub=""):
    """A TitleRig title card: the letters flip in as solid cards, then hold; optional second line under it."""
    W, H = size
    look, shadow = suggested_look(preset)
    bg = hexrgb(PRESETS[preset].backdrop)
    fs = fit_size(text, W * 0.86, H * (0.42 if sub else 0.6))
    anim = Anim([Track(effect="flip_x", easing="back", duration=0.45, stagger=0.05),
                 Track(effect="pop", easing="back", duration=0.4, stagger=0.05, amount=-25)],
                fps=FPS, hold=0)
    k = min(n, anim.n_frames(sum(1 for c in text if c.strip())))
    lay = Layout()
    glyphs = Glyphs(text=text, font="Anton", size=fs, tracking=fs / 40)
    head = render_frames(anim, glyphs, look, shadow, W, H, lay, passes=("beauty",))["beauty"][:k]
    rest = render_title(glyphs, look, shadow, W, H, lay, guides="none")["beauty"]
    under = None
    if sub:
        sl, ss = Look3D(face="#ffffff", face2=None, extrude=0, bevel=0, bevel_profile="flat"), Shadow(on=False)
        sfs = fit_size(sub, W * 0.8, H * 0.12, start=72)
        under = render_title(Glyphs(text=sub, font="Anton", size=sfs, tracking=2), sl, ss, W, H,
                             Layout(), guides="none")["beauty"]
        under = np.roll(under, int(H * 0.28), axis=0)
    for f in range(n):
        b = head[f] if f < len(head) else rest
        rgb = b[..., :3] * b[..., 3:] + bg * (1 - b[..., 3:])
        if under is not None and f >= k:
            a = under[..., 3:] * min(1.0, (f - k + 1) / 8)
            rgb = under[..., :3] * a + rgb * (1 - a)
        yield np.roll(rgb, -int(H * 0.08), axis=0) if under is not None else rgb


def placeholder_frames(label, slot, n, size):
    """A clearly-marked empty slot: TitleRig label on grey, dashed frame, the file it wants."""
    W, H = size
    g = Glyphs(text=label, font="Anton", size=fit_size(label, W * 0.7, H * 0.3, 160), tracking=4)
    b = render_title(g, Look3D(face="#9ca3af", face2=None, side="#4b5563", extrude=10, bevel=0,
                               bevel_profile="flat"), Shadow(on=False), W, H, Layout(), guides="none")["beauty"]
    rgb = b[..., :3] * b[..., 3:] + 0.13 * (1 - b[..., 3:])
    im = Image.fromarray((rgb * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    m = int(W * 0.04)
    for x in range(m, W - m, 24):
        d.line([(x, m), (x + 12, m)], fill=(160, 160, 170), width=2)
        d.line([(x, H - m), (x + 12, H - m)], fill=(160, 160, 170), width=2)
    for y in range(m, H - m, 24):
        d.line([(m, y), (m, y + 12)], fill=(160, 160, 170), width=2)
        d.line([(W - m, y), (W - m, y + 12)], fill=(160, 160, 170), width=2)
    font = ImageFont.truetype(FONT, max(14, H // 26))
    msg = f"SLOT: docs/demo/slots/{slot}.mp4 / .png  (build night)"
    d.text((W / 2, H * 0.72), msg, font=font, fill=(255, 212, 0), anchor="mm")
    still = np.asarray(im, np.float32) / 255
    for _ in range(n):
        yield still


def passes_frames(n, size):
    """The rig and its passes, live: beauty, depth, edges, alpha, normals, letter IDs as a 3 x 2 grid."""
    W, H = size
    cw, ch = W // 3, H // 2
    look, shadow = suggested_look("Chrome Slam")
    anim = Anim([Track(effect="flip_x", easing="back", duration=0.5, stagger=0.06),
                 Track(effect="wave", direction="loop", easing="linear", duration=2.0, stagger=0)],
                fps=FPS, hold=0)
    names = ("beauty", "depth", "edges", "alpha", "normals", "letter_ids")
    fs = fit_size("TITLERIG", cw * 0.72, ch * 0.45, start=int(ch * 0.55))
    p = render_frames(anim, Glyphs(text="TITLERIG", font="Anton", size=fs, tracking=3), look, shadow,
                      cw, ch, Layout(mode="arc", bend=0.15, flag_amp=4, flag_wavelength=cw / 1.5), passes=names)
    bg = hexrgb(PRESETS["Chrome Slam"].backdrop)
    font = ImageFont.truetype(FONT, max(12, ch // 10))
    m = len(p["beauty"])
    for f in range(n):
        i = min(f, m - 1) if f < m else (m - 1)
        sheet = np.zeros((H, W, 3), np.float32)
        for t, name in enumerate(names):
            a = p[name][i]
            if name == "beauty":
                a = a[..., :3] * a[..., 3:] + bg * (1 - a[..., 3:])
            elif a.ndim == 2:
                a = np.repeat(a[..., None], 3, 2)
            tile = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
            ImageDraw.Draw(tile).text((10, 6), name.replace("_", " ").upper(), font=font, fill=(255, 212, 0))
            r, c = divmod(t, 3)
            sheet[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = np.asarray(tile, np.float32) / 255
        yield sheet


def react_frames(n, size, wav, start):
    """Ben-Day Pop driven by the slice of the music bed this shot plays over: the hits land on the cut."""
    W, H = size
    mono, sr = load_wav(wav)
    secs = n / FPS
    kick = audio_curve(mono, sr, FPS, band="bass", mode="beats", sensitivity=0.5, release=0.18, start=start,
                       max_seconds=secs)
    hat = audio_curve(mono, sr, FPS, band="highs", mode="beats", sensitivity=0.15, release=0.12, start=start,
                      max_seconds=secs)
    anim = Anim([Track(effect="pop", drive=kick["values"], amount=-45, stagger=1 / FPS, order="center_out"),
                 Track(effect="drop", drive=hat["values"], amount=26, stagger=1 / FPS, response="trigger",
                       easing="bounce", duration=0.3, retrigger="finish"),
                 Track(effect="shadow_length", drive=kick["values"], amount=45)], fps=FPS)
    look, shadow = suggested_look("Ben-Day Pop")
    shadow.texture = "halftone"
    bg = hexrgb(PRESETS["Ben-Day Pop"].backdrop)
    b = render_frames(anim, Glyphs(text="POW!", font="Anton", size=int(H * 0.42), tracking=8), look, shadow, W, H,
                      Layout(tilt_x=8), passes=("beauty",))["beauty"]
    for f in range(n):
        x = b[min(f, len(b) - 1)]
        yield x[..., :3] * x[..., 3:] + bg * (1 - x[..., 3:])


def find_slot(slots, name):
    for ext in (".mp4", ".mov", ".webm", ".gif", ".png", ".jpg", ".jpeg", ".webp"):
        p = os.path.join(slots, name + ext)
        if os.path.exists(p):
            return p
    return None


def normalize(src, out, dur, size, caption):
    """Any video / image -> exactly dur seconds at size and FPS (fit inside, letterboxed; looped if short)."""
    W, H = size
    still = src.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x16161c,"
          f"fps={FPS},format=yuv420p")
    lt = lower_third(caption, out, H)
    vf = vf + ("," + lt if lt else "")
    inp = ["-loop", "1", "-i", src] if still else ["-stream_loop", "-1", "-i", src]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-t", f"{dur:.4f}", "-an", "-vf", vf,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-r", str(FPS), out], check=True)


def bed(audio, out, total):
    """The music bed: the track looped to the video's length, as WAV (for kick detection) with a fade at the end."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", audio, "-t", f"{total:.3f}",
                    "-af", f"afade=t=out:st={total - 1.5:.3f}:d=1.5", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le",
                    out], check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--audio", default=os.path.join(HERE, "assets", "titlerig_beat.wav"))
    ap.add_argument("--slots", default=os.path.join(ROOT, "docs", "demo", "slots"))
    ap.add_argument("--out", default=os.path.join(HERE, "out", "demo"))
    ap.add_argument("--fast", action="store_true", help="640x360 preview")
    ap.add_argument("--only", default="", help="comma list of segment keys to (re)build, for quick checks")
    a = ap.parse_args(argv)
    if not shutil.which("ffmpeg"):
        raise SystemExit("needs ffmpeg")
    size = (640, 360) if a.fast else (1280, 720)
    os.makedirs(a.out, exist_ok=True)
    wav = os.path.join(a.out, "bed.wav")
    bed(a.audio, wav, END_AT)
    starts, durs = snap_to_kicks([t[1] for t in TIMELINE], wav, END_AT)
    only = set(filter(None, a.only.split(",")))
    segs = []
    for (key, _, kind, what, caption), start, dur in zip(TIMELINE, starts, durs):
        n = max(1, round(dur * FPS))
        out = os.path.join(a.out, f"{len(segs):02d}_{key}.mp4")
        segs.append(out)
        if only and key not in only and os.path.exists(out):
            continue
        used = "rendered"
        if kind == "slot":
            slot, fallback, label = what
            src = find_slot(a.slots, slot)
            if src is None and fallback:
                src, used = os.path.join(MEDIA, fallback), f"fallback {fallback}"
            if src:
                used = used if used != "rendered" else f"slot {os.path.basename(src)}"
                normalize(src, out, n / FPS, size, caption)
            else:
                used = "placeholder"
                enc = Encoder(out, size, caption)
                for fr in placeholder_frames(label, slot, n, size):
                    enc.write(fr)
                enc.close()
        else:
            enc = Encoder(out, size, caption)
            frames = (card_frames(what[0], what[1], n, size, sub="OPEN SOURCE · MIT" if key == "end" else "")
                      if kind == "card" else passes_frames(n, size) if kind == "passes"
                      else react_frames(n, size, wav, start))
            for fr in frames:
                enc.write(fr)
            enc.close()
        print(f"{start:6.2f}s  {dur:5.2f}s  {key:13s} {used}")
    lst = os.path.join(a.out, "segments.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(s)}'\n" for s in segs)
    final = os.path.join(a.out, "titlerig_demo.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", final], check=True)
    print("wrote", final)


if __name__ == "__main__":
    main()
