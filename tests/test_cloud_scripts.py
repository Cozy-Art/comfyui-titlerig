"""Comfy Cloud fallback scripts: export the rig guides, then Spell-Lock a video and a still against them."""
import os
import shutil
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "examples"))
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


def test_export_then_spell_lock(tmp_path, capsys):
    import export_for_cloud
    import spell_lock_video
    out = str(tmp_path)
    export_for_cloud.main(["--seconds", "0.5", "--width", "320", "--height", "180", "--out", out])
    for f in ("depth.mp4", "edges.mp4", "beauty.mp4", "rig.npz", "prompt.txt", "negative.txt", "track.wav",
              "still_depth.png", "still_alpha.png", "flux_prompt.txt"):
        assert os.path.getsize(os.path.join(out, f)) > 0, f
    rig = np.load(os.path.join(out, "rig.npz"))
    assert (len(rig["alpha"]) - 1) % 8 == 0  # LTX 8n+1
    spell_lock_video.main([os.path.join(out, "beauty.mp4"), "--rig", out])
    assert os.path.exists(os.path.join(out, "beauty_spell_locked.mp4"))
    spell_lock_video.main([os.path.join(out, "still_depth.png"), "--rig", out, "--out", os.path.join(out, "s.png")])
    assert os.path.exists(os.path.join(out, "s.png"))
    assert "drift before" in capsys.readouterr().out
