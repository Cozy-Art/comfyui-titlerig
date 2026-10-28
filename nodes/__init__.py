from .titlerig_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .preview import register as _register_preview

_register_preview(NODE_CLASS_MAPPINGS)  # live canvas preview route (only inside ComfyUI)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
