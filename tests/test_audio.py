import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from render.audio import (AUDIO_MODES, BANDS, audio_curve, curve_preview, follower, load_wav, save_wav,  # noqa: E402
                          synth_beat, to_mono)

SR, FPS = 22050, 24.0


@pytest.fixture(scope="module")
def beat():
    return synth_beat(4.0, 120, SR)


def _match(found, truth, tol):
    return sum(any(abs(f - t) <= tol for f in found) for t in truth)


def test_to_mono_shapes():
    assert to_mono(np.ones(10)).shape == (10,)
    assert to_mono(np.ones((2, 10))).shape == (10,)
    assert to_mono(np.ones((1, 2, 10))).shape == (10,)


def test_bass_band_finds_kicks(beat):
    mono, hits = beat
    c = audio_curve(mono, SR, FPS, band="bass", sensitivity=0.5)
    tol = 1.5 / FPS
    assert _match(c["onsets"], hits["kick"], tol) >= len(hits["kick"]) - 1
    assert len(c["onsets"]) <= len(hits["kick"]) + 1  # bass ignores the hats
    assert len(c["values"]) == int(np.ceil(4.0 * FPS))


def test_highs_band_finds_hats_not_just_kicks(beat):
    mono, hits = beat
    c = audio_curve(mono, SR, FPS, band="highs", sensitivity=0.6)
    assert _match(c["onsets"], hits["hat"], 1.5 / FPS) >= len(hits["hat"]) - 1


def test_sensitivity_monotonic(beat):
    mono, _ = beat
    counts = [len(audio_curve(mono, SR, FPS, band="full", sensitivity=s)["onsets"]) for s in (0.0, 0.5, 1.0)]
    assert counts[0] <= counts[1] <= counts[2] and counts[2] > counts[0]


def test_envelope_tracks_loudness():
    mono, _ = synth_beat(4.0, 120, SR, quiet_after=2.0)
    c = audio_curve(mono, SR, FPS, band="full", mode="envelope", release=0.3)
    n = len(c["values"])
    assert c["values"][: n // 2].mean() > c["values"][n // 2:].mean() + 0.2


def test_follower_attack_release():
    x = np.zeros(48, np.float32)
    x[10] = 1.0
    instant = follower(x, 0.0, 0.5, 24)
    assert instant[10] == 1.0 and 0.5 < instant[14] < 1.0  # slow release
    slow = follower(np.ones(48, np.float32), 0.25, 0.0, 24)
    assert slow[0] < 0.3 and slow[-1] > 0.95


def test_curve_range_modes_bands_and_preview(beat):
    mono, _ = beat
    for b in BANDS:
        for m in AUDIO_MODES:
            v = audio_curve(mono, SR, 12.0, band=b, mode=m)["values"]
            assert v.dtype == np.float32 and v.min() >= 0 and v.max() <= 1
    c = audio_curve(mono, SR, FPS, start=1.0, max_seconds=2.0)
    assert len(c["values"]) == 48
    img = curve_preview(c, 320, 80)
    assert img.shape == (80, 320, 3) and img.max() <= 1


def test_wav_roundtrip(tmp_path, beat):
    mono, _ = beat
    p = str(tmp_path / "b.wav")
    save_wav(p, mono, SR)
    back, sr = load_wav(p)
    assert sr == SR and np.abs(back - np.clip(mono, -1, 1)).max() < 1e-3


def test_spectrum_mode_splits_lows_and_highs():
    sr, fps = 22050, 24.0
    tt = np.arange(int(2 * sr)) / sr
    low = np.sin(2 * np.pi * 80 * tt) * (tt < 1)       # bass first second
    high = np.sin(2 * np.pi * 6000 * tt) * (tt >= 1)   # treble second second
    c = audio_curve((low + high).astype(np.float32), sr, fps, band="full", mode="spectrum", bands=8, release=0.05)
    v = c["values"]
    assert v.shape == (8, 48)
    assert v[:2, 5:20].max(0).mean() > 0.6 and v[:2, 30:45].max() < 0.2   # low bands: loud then quiet
    assert v[-2:, 30:45].max(0).mean() > 0.6 and v[-2:, 5:20].max() < 0.2  # high bands: the reverse
    assert v[3:5, 5:20].max() < 0.5 and v[3:5, 30:45].max() < 0.5  # bands between the tones stay quiet (clicks at 0 s, 1 s are broadband)
    assert curve_preview(c, 200, 60).shape == (60, 200, 3)
