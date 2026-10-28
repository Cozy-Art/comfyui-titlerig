"""pyproject.toml (ComfyUI registry / Manager) and requirements.txt must ask for the same packages."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_pyproject_dependencies_match_requirements():
    req = [l.strip() for l in open(os.path.join(ROOT, "requirements.txt")) if l.strip() and not l.startswith("#")]
    deps = re.search(r"dependencies = \[(.*?)\]", open(os.path.join(ROOT, "pyproject.toml")).read()).group(1)
    assert sorted(re.findall(r'"([^"]+)"', deps)) == sorted(req)
