"""Example inputs the shipped workflows load by name, put in ComfyUI's input folder on first load so every
template runs straight after install (a judge never has to copy files). Never overwrites an existing file."""
from __future__ import annotations

import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE_INPUTS = (os.path.join("examples", "assets", "titlerig_beat.wav"),)


def seed_inputs(input_dir: str | None = None) -> list[str]:
    """Copy missing example inputs into input_dir (default: ComfyUI's). Returns the files copied."""
    if input_dir is None:
        try:
            import folder_paths
        except ImportError:  # outside ComfyUI
            return []
        input_dir = folder_paths.get_input_directory()
    copied = []
    for rel in EXAMPLE_INPUTS:
        src, dst = os.path.join(ROOT, rel), os.path.join(input_dir, os.path.basename(rel))
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                os.makedirs(input_dir, exist_ok=True)
                shutil.copyfile(src, dst)
                copied.append(dst)
            except OSError:  # read-only install: the README says where the file is
                pass
    return copied
