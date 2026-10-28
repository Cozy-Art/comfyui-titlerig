"""Demo assembly: the timeline is 75 s, cuts snap to kicks, and a fast build makes a 75 s video with sound."""
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "examples"))
import build_demo  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


def test_timeline_is_75_seconds_and_names_the_models():
    starts = [t[1] for t in build_demo.TIMELINE]
    assert starts == sorted(starts) and starts[0] == 0 and build_demo.END_AT == 75.0
    text = " ".join(t[4] for t in build_demo.TIMELINE)
    for name in ("LTX-2", "FLUX.1", "Gemma 3", "ComfyUI", "MIT", "TitleRig"):
        assert name in text, name


@needs_ffmpeg
def test_cuts_snap_to_kicks(tmp_path):
    wav = str(tmp_path / "bed.wav")
    build_demo.bed(os.path.join(ROOT, "examples", "assets", "titlerig_beat.wav"), wav, 20.0)
    starts, durs = build_demo.snap_to_kicks([0, 3.1, 6.2, 9.9], wav, 20.0)
    assert starts == [0.0, 3.0, 6.0, 10.0]  # kicks every 0.5 s at 120 BPM
    assert abs(sum(durs) - 20.0) < 1e-6


@needs_ffmpeg
def test_fast_build_makes_the_whole_video(tmp_path):
    build_demo.main(["--fast", "--out", str(tmp_path), "--slots", str(tmp_path / "no_slots")])
    out = tmp_path / "titlerig_demo.mp4"
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout
    assert "video" in probe and "audio" in probe
    assert abs(float(probe.strip().splitlines()[-1]) - 75.0) < 0.2
