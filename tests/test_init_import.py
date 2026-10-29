"""Inside ComfyUI a missing requirement must fail loudly (IMPORT FAILED + the pip command), never load zero nodes."""
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = r"""
import builtins, importlib.util, sys, types
if {inside}:
    sys.modules["folder_paths"] = types.ModuleType("folder_paths")
real = builtins.__import__
def no_cv2(name, *a, **k):
    if name == "cv2":
        raise ImportError("No module named 'cv2'")
    return real(name, *a, **k)
builtins.__import__ = no_cv2
spec = importlib.util.spec_from_file_location("titlerig_pack", {init!r}, submodule_search_locations=[{root!r}])
m = importlib.util.module_from_spec(spec); sys.modules["titlerig_pack"] = m
try:
    spec.loader.exec_module(m)
    print("LOADED", len(m.NODE_CLASS_MAPPINGS))
except ImportError as e:
    print("FAILED", e)
"""


def run(inside):
    code = CODE.format(inside=inside, init=os.path.join(ROOT, "__init__.py"), root=ROOT)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd="/").stdout


def test_missing_requirement_fails_loudly_inside_comfyui():
    out = run(True)
    assert out.startswith("FAILED") and "cv2" in out and "-m pip install -r" in out and "requirements.txt" in out


def test_outside_comfyui_it_still_imports_empty():
    assert run(False).strip() == "LOADED 0"
