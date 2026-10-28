from .titlerig_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .preview import register as _register_preview
from .assets import seed_inputs as _seed_inputs

_register_preview(NODE_CLASS_MAPPINGS)  # live canvas preview route (only inside ComfyUI)
_seed_inputs()  # the example beat track into ComfyUI/input, so the audio template runs straight away

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
