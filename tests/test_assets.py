"""Example inputs are copied into ComfyUI's input folder once, never over a user's file."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nodes"))
from assets import seed_inputs  # noqa: E402


def test_seed_copies_once_and_never_overwrites(tmp_path):
    copied = seed_inputs(str(tmp_path))
    dst = tmp_path / "titlerig_beat.wav"
    assert copied == [str(dst)] and dst.stat().st_size > 1000
    dst.write_bytes(b"mine")
    assert seed_inputs(str(tmp_path)) == [] and dst.read_bytes() == b"mine"


def test_outside_comfyui_is_a_no_op():
    assert seed_inputs() == []
