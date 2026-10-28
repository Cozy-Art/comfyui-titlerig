"""scripts/runpod_setup.sh is generated from MODELS: it must be current and fetch every model into its folder."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "workflows"))
from build_workflows import MODELS  # noqa: E402
from make_setup import GROUPS, SCRIPT, model_lines  # noqa: E402

SH = os.path.join(ROOT, "scripts", "runpod_setup.sh")


def test_script_is_current_and_fetches_every_model():
    text = open(SH).read()
    fresh = SCRIPT.replace("@LTX@", model_lines("ltx")).replace("@FLUX1@", model_lines("flux1")) \
                  .replace("@FLUX2@", model_lines("flux2"))
    assert text == fresh, "run python workflows/make_setup.py"
    assert sorted(k for g in GROUPS.values() for k in g) == sorted(MODELS)
    for name, folder, _, _ in MODELS.values():
        assert any(line.endswith(f"/{name} {folder}") or f" {name} {folder}" in line for line in text.splitlines())


def test_script_parses():
    assert subprocess.run(["bash", "-n", SH]).returncode == 0
