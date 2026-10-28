"""ComfyUI node wrappers around render/. Keep all drawing logic in render/ so it stays testable without ComfyUI."""
from __future__ import annotations

import json

from ..render import SHADOW_TEXTURES, Glyphs, Look3D, Shadow, bundled_fonts, render_title

CAT = "TitleRig"


def _t(a, mask=False):
    import torch  # imported lazily: render/ and tests never need torch

    t = torch.from_numpy(a.copy()).float()
    return t.unsqueeze(0) if mask or t.ndim == 3 else t


class TitleRigText:
    CATEGORY = CAT
    RETURN_TYPES = ("TITLERIG_GLYPHS",)
    RETURN_NAMES = ("glyphs",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "text": ("STRING", {"default": "TITLE", "multiline": False}),
            "font": (bundled_fonts(),),
            "size": ("INT", {"default": 220, "min": 16, "max": 1024}),
            "tracking": ("FLOAT", {"default": 0.0, "min": -200, "max": 400, "step": 0.5}),
        }, "optional": {
            "kerning_json": ("STRING", {"default": "{}", "tooltip": 'Pair index -> px, e.g. {"0": -12}'}),
            "letters_json": ("STRING", {"default": "{}", "tooltip": 'Letter index -> {scale, rot, dx, dy, space_l, space_r}'}),
        }}

    def build(self, text, font, size, tracking, kerning_json="{}", letters_json="{}"):
        kern = {int(k): float(v) for k, v in json.loads(kerning_json or "{}").items()}
        letters = {int(k): v for k, v in json.loads(letters_json or "{}").items()}
        return (Glyphs(text=text, font=font, size=size, tracking=tracking, kerning=kern, letters=letters),)


class TitleRigLook3D:
    CATEGORY = CAT
    RETURN_TYPES = ("TITLERIG_LOOK",)
    RETURN_NAMES = ("look",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "face": ("STRING", {"default": "#ffcf2e"}),
            "face_gradient_to": ("STRING", {"default": "#ff6a2b", "tooltip": "Empty = flat colour"}),
            "side": ("STRING", {"default": "#c2410c"}),
            "extrude": ("INT", {"default": 28, "min": 0, "max": 300}),
            "extrude_angle": ("FLOAT", {"default": 55.0, "min": 0, "max": 360}),
            "bevel": ("FLOAT", {"default": 10.0, "min": 0, "max": 80}),
            "bevel_profile": (["round", "chisel", "flat"],),
            "light_angle": ("FLOAT", {"default": 225.0, "min": 0, "max": 360}),
            "light_height": ("FLOAT", {"default": 0.6, "min": 0.05, "max": 1.0, "step": 0.05}),
            "gloss": ("FLOAT", {"default": 0.6, "min": 0, "max": 2, "step": 0.05}),
            "rim": ("FLOAT", {"default": 0.25, "min": 0, "max": 1, "step": 0.05}),
        }}

    def build(self, face, face_gradient_to, side, extrude, extrude_angle, bevel, bevel_profile,
              light_angle, light_height, gloss, rim):
        return (Look3D(face=face, face2=face_gradient_to or None, side=side, extrude=extrude,
                       extrude_angle=extrude_angle, bevel=bevel, bevel_profile=bevel_profile,
                       light_angle=light_angle, light_height=light_height, gloss=gloss, rim=rim),)


class TitleRigShadow:
    CATEGORY = CAT
    RETURN_TYPES = ("TITLERIG_SHADOW",)
    RETURN_NAMES = ("shadow",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "texture": (list(SHADOW_TEXTURES), {"default": "halftone"}),
            "color": ("STRING", {"default": "#15161c"}),
            "angle": ("FLOAT", {"default": 45.0, "min": 0, "max": 360}),
            "length": ("FLOAT", {"default": 40.0, "min": 0, "max": 400}),
            "softness": ("FLOAT", {"default": 0.0, "min": 0, "max": 60}),
            "texture_scale": ("FLOAT", {"default": 10.0, "min": 2, "max": 80}),
            "texture_angle": ("FLOAT", {"default": 45.0, "min": 0, "max": 180}),
            "opacity": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "step": 0.05}),
        }}

    def build(self, texture, color, angle, length, softness, texture_scale, texture_angle, opacity):
        return (Shadow(on=length > 0, color=color, angle=angle, length=length, softness=softness,
                       texture=texture, texture_scale=texture_scale, texture_angle=texture_angle, opacity=opacity),)


class TitleRigRender:
    CATEGORY = CAT
    RETURN_TYPES = ("IMAGE", "MASK", "IMAGE", "IMAGE", "IMAGE", "MASK", "MASK", "MASK", "MASK", "IMAGE", "IMAGE")
    RETURN_NAMES = ("beauty", "alpha", "depth", "edges", "normals", "face", "sides", "highlight", "shadow",
                    "letter_ids", "guides")
    FUNCTION = "render"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "glyphs": ("TITLERIG_GLYPHS",),
            "width": ("INT", {"default": 1280, "min": 64, "max": 4096, "step": 8}),
            "height": ("INT", {"default": 720, "min": 64, "max": 4096, "step": 8}),
        }, "optional": {
            "look": ("TITLERIG_LOOK",),
            "shadow": ("TITLERIG_SHADOW",),
        }}

    def render(self, glyphs, width, height, look=None, shadow=None):
        p = render_title(glyphs, look, shadow, width, height)
        b = p["beauty"]
        return (_t(b[..., :3]), _t(p["alpha"], True), _t(p["depth"]), _t(p["edges"]), _t(p["normals"]),
                _t(p["face"], True), _t(p["sides"], True), _t(p["highlight"], True), _t(p["shadow"], True),
                _t(p["letter_ids"]), _t(p["guides"][..., :3]))


NODE_CLASS_MAPPINGS = {
    "TitleRigText": TitleRigText,
    "TitleRigLook3D": TitleRigLook3D,
    "TitleRigShadow": TitleRigShadow,
    "TitleRigRender": TitleRigRender,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "TitleRigText": "TitleRig Text",
    "TitleRigLook3D": "TitleRig Look 3D",
    "TitleRigShadow": "TitleRig Shadow",
    "TitleRigRender": "TitleRig Render",
}
