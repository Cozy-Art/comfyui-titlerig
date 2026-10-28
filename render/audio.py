"""Audio-reactive curves for TitleRig. numpy only: band-limited spectral-flux onsets + loudness envelope,
shaped by an attack/release follower and sampled at the video frame rate (one value per frame).

The result is a "curve" dict that TitleRig Animate takes as `drive`:
  {"values": float32 (n_frames,) in 0..1, "fps": float, "onsets": [seconds], "envelope": float32 (n_frames,)}
In "spectrum" mode values is (bands, n_frames), low to high: Animate maps letters left to right across it (an EQ).
"""
from __future__ import annotations

import math
import wave

import numpy as np

BANDS = {"full": (20.0, 16000.0), "bass": (20.0, 250.0), "mids": (250.0, 4000.0), "highs": (4000.0, 16000.0)}
AUDIO_MODES = ("beats", "envelope", "beats+envelope", "spectrum")


def to_mono(waveform) -> np.ndarray:
    """(N,), (C, N) or (B, C, N) -> float32 (N,) mono mix of the first batch item."""
    a = np.asarray(waveform, np.float32)
    while a.ndim > 2:
        a = a[0]
    if a.ndim == 2:
        a = a.mean(axis=0)
    return a


def load_wav(path: str) -> tuple[np.ndarray, int]:
    """Read a PCM WAV with the stdlib -> (mono float32, sample_rate)."""
    with wave.open(path, "rb") as w:
        sr, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    dt = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    a = np.frombuffer(raw, dt).astype(np.float32)
    a = (a - 128) / 128 if width == 1 else a / float(np.iinfo(dt).max)
    return a.reshape(-1, ch).mean(axis=1), sr


def save_wav(path: str, mono: np.ndarray, sr: int) -> None:
    pcm = (np.clip(mono, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def band_spectra(mono: np.ndarray, sr: int, fps: float, band: str = "full", return_freqs: bool = False):
    """Magnitude spectra restricted to `band`, one row per video frame (window centred on the frame time)."""
    lo, hi = BANDS[band]
    hop = sr / fps
    win = 1 << max(10, int(math.ceil(math.log2(2 * hop))))  # >= 2 hops, >= 1024 so bass bins exist
    n = max(1, int(math.ceil(len(mono) / hop)))
    pad = np.pad(mono, (win // 2, win))
    starts = (np.arange(n) * hop).astype(np.int64)
    frames = pad[starts[:, None] + np.arange(win)[None, :]] * np.hanning(win).astype(np.float32)
    mag = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    keep = (freqs >= lo) & (freqs < min(hi, sr / 2))
    out = mag[:, keep].astype(np.float32)
    return (out, freqs[keep]) if return_freqs else out


def spectrum_bands(spec: np.ndarray, freqs: np.ndarray, bands: int, range_db: float = 30.0,
                   headroom_db: float = 24.0) -> np.ndarray:
    """(n, bins) -> (bands, n): log-spaced band loudness in 0..1.

    Each band is scaled to its own peak (so quiet treble still dances), but never more than `headroom_db`
    below the loudest band, so near-silent bands and clicks don't light up."""
    lo, hi = max(freqs[0], 30.0), freqs[-1]
    edges = np.geomspace(lo, hi, bands + 1)
    dbs = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (freqs >= a) & (freqs < b)
        if not m.any():  # very narrow low band: borrow the nearest bin
            m = np.zeros_like(freqs, bool)
            m[np.argmin(np.abs(freqs - (a + b) / 2))] = True
        dbs.append(10 * np.log10((spec[:, m].astype(np.float64) ** 2).sum(axis=1) + 1e-12))
    dbs = np.stack(dbs)
    tops = np.percentile(dbs, 98, axis=1)
    tops = np.maximum(tops, tops.max() - headroom_db)[:, None]
    return np.clip((dbs - (tops - range_db)) / range_db, 0, 1).astype(np.float32)


def follower(x: np.ndarray, attack: float, release: float, fps: float) -> np.ndarray:
    """One-pole envelope follower: rises with time constant `attack` s, falls with `release` s (0 = instant)."""
    ka = 1.0 if attack <= 0 else 1 - math.exp(-1.0 / (attack * fps))
    kr = 1.0 if release <= 0 else 1 - math.exp(-1.0 / (release * fps))
    y = np.zeros(len(x), np.float32)
    v = 0.0
    for i, s in enumerate(x):
        v += (s - v) * (ka if s > v else kr)
        y[i] = v
    return y


def _local_median(x: np.ndarray, half: int) -> np.ndarray:
    p = np.pad(x, half, mode="edge")
    return np.array([np.median(p[i:i + 2 * half + 1]) for i in range(len(x))], np.float32)


def onsets(spec: np.ndarray, fps: float, sensitivity: float = 0.5, min_gap: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
    """Spectral-flux onset detection -> (flux (n,), onset frame indices).

    sensitivity 0..1: higher catches quieter hits (lower adaptive threshold)."""
    logm = np.log1p(spec / (spec.max() * 0.01 + 1e-12))  # bins under ~1% of the peak barely count
    flux = np.zeros(len(spec), np.float32)
    flux[0] = logm[0].sum()  # a hit on the very first frame rises from silence
    flux[1:] = np.maximum(0.0, np.diff(logm, axis=0)).sum(axis=1)
    if flux.max() <= 0:
        return flux, np.zeros(0, np.int64)
    flux /= flux.max()
    half = max(2, int(round(0.25 * fps)))
    med = _local_median(flux, half)
    s = float(np.clip(sensitivity, 0.0, 1.0))
    thr = med + (1.0 - s) * 0.7 + 0.03  # s=0: only hits near the strongest; s=1: anything above the floor
    gap = max(1, int(round(min_gap * fps)))
    picks, last = [], -10 ** 9
    for i in range(len(flux)):
        lo, hi = max(0, i - 2), min(len(flux), i + 3)
        if flux[i] > thr[i] and flux[i] == flux[lo:hi].max() and i - last >= gap:
            picks.append(i)
            last = i
    return flux, np.array(picks, np.int64)


def loudness(spec: np.ndarray, range_db: float = 36.0) -> np.ndarray:
    """Band loudness in dB mapped to 0..1 over the `range_db` below the (98th percentile) peak."""
    db = 10 * np.log10((spec.astype(np.float64) ** 2).sum(axis=1) + 1e-12)
    top = np.percentile(db, 98)
    return np.clip((db - (top - range_db)) / range_db, 0, 1).astype(np.float32)


def audio_curve(waveform, sr: int, fps: float = 24.0, band: str = "bass", mode: str = "beats",
                sensitivity: float = 0.5, attack: float = 0.0, release: float = 0.25,
                start: float = 0.0, max_seconds: float = 0.0, min_gap: float = 0.1, bands: int = 12) -> dict:
    """Analyse audio into a per-frame 0..1 drive curve for TitleRig Animate."""
    if band not in BANDS:
        raise ValueError(f"unknown band: {band}")
    if mode not in AUDIO_MODES:
        raise ValueError(f"unknown mode: {mode}")
    mono = to_mono(waveform)
    a = int(start * sr)
    mono = mono[a:a + int(max_seconds * sr)] if max_seconds > 0 else mono[a:]
    spec, freqs = band_spectra(mono, sr, fps, band, return_freqs=True)
    n = int(math.ceil(len(mono) / sr * fps)) or 1
    spec = spec[:n]
    flux, picks = onsets(spec, fps, sensitivity, min_gap)
    env = loudness(spec)
    imp = np.zeros(len(spec), np.float32)
    imp[picks] = 1.0
    beats = follower(imp, attack, release, fps)
    if mode == "beats":
        vals = beats
    elif mode == "envelope":
        vals = follower(env, attack, release, fps)
    elif mode == "spectrum":
        vals = np.stack([follower(r, attack, release, fps) for r in spectrum_bands(spec, freqs, max(1, bands))])
    else:
        vals = np.maximum(beats, follower(env, attack, release, fps) * 0.6)
    return {"values": np.clip(vals, 0, 1).astype(np.float32), "fps": float(fps),
            "onsets": [float(p / fps) for p in picks], "envelope": env, "flux": flux}


def curve_preview(curve: dict, width: int = 640, height: int = 160) -> np.ndarray:
    """RGB float image of the drive curve (filled), loudness (line) and onset ticks, for a ComfyUI preview."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), (22, 22, 28))
    d = ImageDraw.Draw(img)
    v, env = curve["values"], curve["envelope"]
    if v.ndim == 2:  # spectrum: heat strip, lows at the bottom
        heat = (np.clip(v[::-1], 0, 1) * 255).astype(np.uint8)
        img.paste(Image.fromarray(heat).resize((width, height), Image.NEAREST).convert("RGB")
                  .point(lambda c: c), (0, 0))
        v = v.mean(axis=0)
    n = max(len(v), 2)
    xs = np.linspace(0, width - 1, len(v))
    for t in curve["onsets"]:
        x = t * curve["fps"] / (n - 1) * (width - 1)
        d.line([(x, 0), (x, height)], fill=(80, 82, 150))
    d.polygon([(0, height)] + [(x, height - y * (height - 8)) for x, y in zip(xs, v)] + [(width - 1, height)],
              fill=(255, 207, 46))
    d.line([(x, height - y * (height - 8)) for x, y in zip(xs, env)], fill=(143, 145, 255), width=2)
    return np.asarray(img, np.float32) / 255.0


def synth_beat(seconds: float = 8.0, bpm: float = 120.0, sr: int = 22050, seed: int = 1,
               quiet_after: float | None = None, arp: bool = False) -> tuple[np.ndarray, dict]:
    """Deterministic test/demo drum loop: kick on every beat, hat on the off-beats, snare on 2 and 4.

    arp adds a 16th-note arpeggio that climbs C4 -> C7 across each bar (sweeps a spectrum display).
    Returns (mono float32, {"kick": [s], "hat": [s], "snare": [s]}). quiet_after drops the level by 18 dB."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    out = np.zeros(n, np.float32)
    beat = 60.0 / bpm
    hits = {"kick": [], "hat": [], "snare": []}

    def add(t, sig):
        i = int(t * sr)
        j = min(n, i + len(sig))
        if i < n:
            out[i:j] += sig[: j - i]

    tk = np.arange(int(0.35 * sr)) / sr
    kick = np.sin(2 * np.pi * (45 * tk + 90 * (1 - np.exp(-tk * 30)) / 30)) * np.exp(-tk * 9)
    kick *= np.minimum(1.0, (tk[-1] - tk) / 0.05)  # fade the tail: no click when the buffer ends
    th = np.arange(int(0.06 * sr)) / sr
    ts = np.arange(int(0.18 * sr)) / sr
    k = 0
    t = 0.0
    while t < seconds:
        add(t, 0.9 * kick)
        hits["kick"].append(t)
        if k % 2 == 1:
            sn = rng.standard_normal(len(ts)) * np.exp(-ts * 22) * 0.35 + np.sin(2 * np.pi * 190 * ts) * np.exp(-ts * 30) * 0.3
            add(t, sn)
            hits["snare"].append(t)
        th_t = t + beat / 2
        if th_t < seconds:
            hat = np.diff(rng.standard_normal(len(th) + 1)) * np.exp(-th * 70) * 0.25  # differenced noise = bright
            add(th_t, hat)
            hits["hat"].append(th_t)
        t += beat
        k += 1
    if arp:
        step = beat / 4
        tn = np.arange(int(step * 0.9 * sr)) / sr
        env = np.minimum(1, tn / 0.005) * np.exp(-tn * 9)
        k = 0
        while k * step < seconds:
            semis = (k % 16) * 36 / 15  # C4 .. C7 over one bar
            f = 261.63 * 2 ** (semis / 12)
            tone = sum(np.sin(2 * np.pi * f * h * tn) / h for h in (1, 2, 3)) * env * 0.16
            add(k * step, tone)
            k += 1
    if quiet_after is not None:
        out[int(quiet_after * sr):] *= 10 ** (-18 / 20)
    return out.astype(np.float32), hits
