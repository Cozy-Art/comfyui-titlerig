"""ComfyUI's Templates menu lists every *.json in a pack's example_workflows / example / examples / workflow /
workflows folders, but serves files only from the first of those folders that exists. So every UI workflow must be
in example_workflows/ (checked first), and none may sit in the other folders, or its card fails to open."""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "workflows"))
from build_workflows import WORKFLOWS  # noqa: E402

LISTED = ("example_workflows", "example", "examples", "workflow", "workflows")


def test_every_workflow_is_a_template_with_a_thumbnail():
    for name in WORKFLOWS:
        assert os.path.exists(os.path.join(ROOT, "example_workflows", f"{name}.json")), name
        assert os.path.exists(os.path.join(ROOT, "example_workflows", f"{name}.jpg")), name


def test_no_template_is_listed_from_a_folder_comfyui_will_not_serve():
    for folder in LISTED[1:]:
        stray = glob.glob(os.path.join(ROOT, folder, "*.json"))
        assert not stray, f"ComfyUI would list these but can't open them: {stray}"
