"""TitleRig — exact, animated 3D title text for ComfyUI. AI can't spell, so we gave it a rig."""
import os
import sys

try:
    from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
except ImportError as e:
    try:
        import folder_paths  # noqa: F401  (exists only inside ComfyUI)
    except ImportError:  # imported outside ComfyUI (e.g. by pytest) — the renderer is tested directly
        NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = {}, {}
    else:  # inside ComfyUI a missing package must show as IMPORT FAILED, not as silently missing nodes
        req = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
        raise ImportError(f"TitleRig: {e}. Install its requirements into the Python that runs ComfyUI: "
                          f"{sys.executable} -m pip install -r {req}") from e

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
