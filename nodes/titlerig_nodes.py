"""ComfyUI node wrappers around render/. Keep all drawing logic in render/ so it stays testable without ComfyUI."""
from __future__ import annotations

import json

import numpy as np

from ..render.presets import FORMATS, PRESET_NAMES, TARGETS as PROMPT_TARGETS, build_prompt, flux2_settings, flux3_settings, suggested_look
from ..render.audio import AUDIO_MODES, BANDS, audio_curve, curve_preview
from ..render.animate import DIRECTIONS, EASINGS, EFFECTS, ORDERS, RESPONSES, RETRIGGERS, TARGETS, Anim, Track, render_frames
from ..render import LAYOUT_MODES, SHADOW_TEXTURES, Glyphs, Layout, Look3D, Shadow, bundled_fonts, render_title

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
            "letters_json": ("STRING", {"default": "{}", "tooltip": 'Letter index -> {scale, sx, sy, rot, dx, dy, '
                                        'space_l, space_r, skew_x, skew_y, taper_x, taper_y, corners: [[dx,dy] x4 TL TR BR BL]}'}),
            "word_json": ("STRING", {"default": "{}", "tooltip": 'Whole word: {scale, sx, sy, rot, dx, dy, skew_x, '
                                     'skew_y, taper_x, taper_y, corners} — e.g. {"taper_x": 0.3} narrows the top'}),
        }}

    def build(self, text, font, size, tracking, kerning_json="{}", letters_json="{}", word_json="{}"):
        kern = {int(k): float(v) for k, v in json.loads(kerning_json or "{}").items()}
        letters = {int(k): v for k, v in json.loads(letters_json or "{}").items()}
        word = json.loads(word_json or "{}")
        return (Glyphs(text=text, font=font, size=size, tracking=tracking, kerning=kern, letters=letters, word=word),)


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


class TitleRigLayout:
    CATEGORY = CAT
    RETURN_TYPES = ("TITLERIG_LAYOUT",)
    RETURN_NAMES = ("layout",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "mode": (list(LAYOUT_MODES), {"default": "flat"}),
            "bend": ("FLOAT", {"default": 0.4, "min": -1, "max": 1, "step": 0.01, "tooltip": "arc: + rainbow, - smile"}),
            "align": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "step": 0.01, "tooltip": "arc: text centre along the curve"}),
            "bulge": ("FLOAT", {"default": 0.0, "min": -1, "max": 1, "step": 0.01, "tooltip": "+ swell the middle, - pinch"}),
            "tilt_x": ("FLOAT", {"default": 0.0, "min": -80, "max": 80, "step": 0.5, "tooltip": "+ leans the top away"}),
            "tilt_y": ("FLOAT", {"default": 0.0, "min": -80, "max": 80, "step": 0.5, "tooltip": "+ swings the right side away"}),
            "fov": ("FLOAT", {"default": 50.0, "min": 5, "max": 150, "step": 1}),
            "vanish": ("BOOLEAN", {"default": False, "tooltip": "extrusion converges on the vanishing point"}),
            "vp_x": ("FLOAT", {"default": 0.5, "min": -2, "max": 3, "step": 0.01}),
            "vp_y": ("FLOAT", {"default": 1.4, "min": -2, "max": 3, "step": 0.01}),
            "flag_amp": ("FLOAT", {"default": 0.0, "min": 0, "max": 200, "step": 0.5}),
            "flag_wavelength": ("FLOAT", {"default": 420.0, "min": 20, "max": 4000, "step": 1}),
            "flag_phase": ("FLOAT", {"default": 0.0, "min": -3600, "max": 3600, "step": 1}),
            "flag_shade": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "step": 0.05}),
        }, "optional": {
            "curve_json": ("STRING", {"default": "", "tooltip": "arc: custom cubic bezier [[x,y]x4] in 0..1 canvas coords"}),
        }}

    def build(self, mode, bend, align, bulge, tilt_x, tilt_y, fov, vanish, vp_x, vp_y,
              flag_amp, flag_wavelength, flag_phase, flag_shade, curve_json=""):
        curve = tuple(map(tuple, json.loads(curve_json))) if curve_json.strip() else None
        return (Layout(mode=mode, bend=bend, curve=curve, align=align, bulge=bulge, tilt_x=tilt_x, tilt_y=tilt_y,
                       fov=fov, vanish=vanish, vp_x=vp_x, vp_y=vp_y, flag_amp=flag_amp,
                       flag_wavelength=flag_wavelength, flag_phase=flag_phase, flag_shade=flag_shade),)


class TitleRigStylePreset:
    """Bright, ad-ready style: prompts for the AI pass + a matching rig Look and Shadow."""
    CATEGORY = CAT
    RETURN_TYPES = ("STRING", "STRING", "TITLERIG_LOOK", "TITLERIG_SHADOW", "STRING")
    RETURN_NAMES = ("positive", "negative", "look", "shadow", "settings")
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "preset": (list(PRESET_NAMES), {"default": "Chrome Slam"}),
            "target": (list(PROMPT_TARGETS), {"default": "flux2_dev", "tooltip": "flux2_dev: open-weights still "
                       "(depth/canny) · flux3: API bonus, rig beauty = image 1 · ltx2_video: animated"}),
            "colour_words": ("STRING", {"default": "", "tooltip": "optional, e.g. 'teal and hot pink' (replaces the "
                             "preset's palette words)"}),
            "text": ("STRING", {"default": "TITLE", "tooltip": "used when no glyphs are connected"}),
            "format": (list(FORMATS), {"default": "prose", "tooltip": "flux2_dev: prose, or a JSON structured prompt "
                       "(pasted into the prompt string, per the flux-v2 skill)"}),
        }, "optional": {
            "glyphs": ("TITLERIG_GLYPHS", {"tooltip": "take the exact text from the rig"}),
        }}

    def build(self, preset, target, colour_words, text, format="prose", glyphs=None):
        word = glyphs.text if glyphs is not None else text
        pos, neg = build_prompt(preset, word, colour_words, target, format)
        look, shadow = suggested_look(preset)
        settings = json.dumps(flux2_settings(word) if target == "flux2_dev" else
                              flux3_settings() if target == "flux3" else {"target": target, "status": "provisional"})
        return (pos, neg, look, shadow, settings)


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
            "layout": ("TITLERIG_LAYOUT",),
            "guide_lines": ("STRING", {"default": "all", "tooltip": "all, none, or a comma list of: "
                                       "ascender, cap, x-height, mid, baseline, descender"}),
        }}

    def render(self, glyphs, width, height, look=None, shadow=None, layout=None, guide_lines="all"):
        p = render_title(glyphs, look, shadow, width, height, layout, guides=guide_lines)
        b = p["beauty"]
        return (_t(b[..., :3]), _t(p["alpha"], True), _t(p["depth"]), _t(p["edges"]), _t(p["normals"]),
                _t(p["face"], True), _t(p["sides"], True), _t(p["highlight"], True), _t(p["shadow"], True),
                _t(p["letter_ids"]), _t(p["guides"][..., :3]))


class TitleRigAnimate:
    """One animation track. Chain several by feeding one node's anim into the next."""
    CATEGORY = CAT
    RETURN_TYPES = ("TITLERIG_ANIM",)
    RETURN_NAMES = ("anim",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "effect": (list(EFFECTS), {"default": "pop"}),
            "target": (list(TARGETS), {"default": "letters"}),
            "direction": (list(DIRECTIONS), {"default": "in"}),
            "easing": (list(EASINGS), {"default": "back"}),
            "duration": ("FLOAT", {"default": 0.6, "min": 0.02, "max": 30, "step": 0.01, "tooltip": "seconds per letter"}),
            "stagger": ("FLOAT", {"default": 0.06, "min": 0, "max": 5, "step": 0.005, "tooltip": "seconds between letters"}),
            "order": (list(ORDERS), {"default": "forward"}),
            "amount": ("FLOAT", {"default": 0.0, "min": -5000, "max": 5000, "step": 1,
                                 "tooltip": "0 = effect default. deg: flip/spin/roll/wave/shadow_angle · "
                                            "% shrink: pop, % fade: shadow_opacity (negative grows/darkens) · "
                                            "px: drop/slide/shake/extrude/shadow_length/shadow_softness · "
                                            "% squash (negative stretches) · deg: light/tilt_x/tilt_y/skew_x/skew_y · % bend/taper_x/taper_y · "
                                            "% of corners_json for corner_pin"}),
            "start": ("FLOAT", {"default": 0.0, "min": 0, "max": 600, "step": 0.01}),
            "fps": ("FLOAT", {"default": 24.0, "min": 1, "max": 120, "step": 1}),
            "hold": ("FLOAT", {"default": 0.6, "min": 0, "max": 60, "step": 0.05, "tooltip": "seconds of rest at the end"}),
            "shuffle_seed": ("INT", {"default": 0, "min": 0, "max": 2 ** 31 - 1, "tooltip": "random order only"}),
            "letters": ("STRING", {"default": "all", "tooltip": 'which letters: all · 0,2,5-7 (character indices) · '
                                   'word:2 (1-based). With target "word" the selection moves as one rigid group'}),
            "influence": ("FLOAT", {"default": 1.0, "min": 0, "max": 4, "step": 0.01,
                                    "tooltip": "dial: how hard this track (or the sound driving it) pushes"}),
            "response": (list(RESPONSES), {"default": "follow", "tooltip": "with a drive curve: follow it, or "
                         "trigger = every hit replays the easing over duration (bounce / elastic / spring on each beat)"}),
            "retrigger": (list(RETRIGGERS), {"default": "restart", "tooltip": "trigger: a new hit restarts the easing, "
                          "waits for the current one to finish (keeps bounces tidy on busy music), or layers (max)"}),
        }, "optional": {
            "anim": ("TITLERIG_ANIM", {"tooltip": "chain: tracks from an earlier Animate node"}),
            "corners_json": ("STRING", {"default": "", "tooltip": "corner_pin target: [[dx,dy],[dx,dy],[dx,dy],[dx,dy]] px, "
                                        "TL TR BR BL (empty = top corners flare out)"}),
            "drive": ("TITLERIG_CURVE", {"tooltip": "per-frame 0..1 curve (e.g. TitleRig Audio React) replaces time + easing"}),
        }}

    def build(self, effect, target, direction, easing, duration, stagger, order, amount, start, fps, hold, shuffle_seed,
              letters="all", influence=1.0, response="follow", retrigger="restart", anim=None, corners_json="", drive=None):
        tr = Track(effect=effect, target=target, direction=direction, easing=easing, duration=duration,
                   stagger=stagger, order=order, amount=amount or None, start=start, seed=shuffle_seed,
                   letters=letters, influence=influence, response=response, retrigger=retrigger,
                   corners=json.loads(corners_json) if corners_json.strip() else None,
                   drive=None if drive is None else drive["values"])
        if drive is not None:
            fps = drive["fps"]
        tracks = list(anim.tracks) if anim is not None else []
        return (Anim(tracks + [tr], fps=fps, hold=hold),)


class TitleRigAudioReact:
    """AUDIO -> per-frame 0..1 drive curve (beats and/or loudness) for TitleRig Animate's `drive` input."""
    CATEGORY = CAT
    RETURN_TYPES = ("TITLERIG_CURVE", "IMAGE", "INT", "STRING")
    RETURN_NAMES = ("curve", "preview", "frame_count", "onsets")
    FUNCTION = "analyse"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "audio": ("AUDIO",),
            "fps": ("FLOAT", {"default": 24.0, "min": 1, "max": 120, "step": 1}),
            "band": (list(BANDS), {"default": "bass"}),
            "mode": (list(AUDIO_MODES), {"default": "beats"}),
            "sensitivity": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "step": 0.01, "tooltip": "higher catches quieter hits"}),
            "attack": ("FLOAT", {"default": 0.0, "min": 0, "max": 5, "step": 0.01, "tooltip": "seconds to rise"}),
            "release": ("FLOAT", {"default": 0.25, "min": 0, "max": 5, "step": 0.01, "tooltip": "seconds to fall"}),
            "start": ("FLOAT", {"default": 0.0, "min": 0, "max": 36000, "step": 0.01}),
            "max_seconds": ("FLOAT", {"default": 0.0, "min": 0, "max": 36000, "step": 0.1, "tooltip": "0 = to the end"}),
        }, "optional": {
            "spectrum_bands": ("INT", {"default": 12, "min": 2, "max": 64,
                                       "tooltip": "spectrum mode: bands spread across the letters, lows on the left"}),
        }}

    def analyse(self, audio, fps, band, mode, sensitivity, attack, release, start, max_seconds, spectrum_bands=12):
        wf = audio["waveform"]
        wf = wf.detach().cpu().numpy() if hasattr(wf, "detach") else np.asarray(wf)
        c = audio_curve(wf, int(audio["sample_rate"]), fps, band, mode, sensitivity, attack, release, start, max_seconds,
                        bands=spectrum_bands)
        import torch

        prev = torch.from_numpy(curve_preview(c)).unsqueeze(0)
        return (c, prev, len(c["values"]), ", ".join(f"{t:.3f}" for t in c["onsets"]))


class TitleRigRenderAnimation:
    CATEGORY = CAT
    RETURN_TYPES = ("IMAGE", "MASK", "IMAGE", "IMAGE", "IMAGE", "INT", "FLOAT")
    RETURN_NAMES = ("beauty", "alpha", "depth", "edges", "letter_ids", "frame_count", "fps")
    FUNCTION = "render"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "glyphs": ("TITLERIG_GLYPHS",),
            "anim": ("TITLERIG_ANIM",),
            "width": ("INT", {"default": 1280, "min": 64, "max": 4096, "step": 8}),
            "height": ("INT", {"default": 720, "min": 64, "max": 4096, "step": 8}),
        }, "optional": {
            "look": ("TITLERIG_LOOK",),
            "shadow": ("TITLERIG_SHADOW",),
            "layout": ("TITLERIG_LAYOUT",),
        }}

    def render(self, glyphs, anim, width, height, look=None, shadow=None, layout=None):
        p = render_frames(anim, glyphs, look, shadow, width, height, layout,
                          passes=("beauty", "alpha", "depth", "edges", "letter_ids"))
        import torch

        t = lambda a: torch.from_numpy(np.ascontiguousarray(a)).float()  # noqa: E731
        return (t(p["beauty"][..., :3]), t(p["alpha"]), t(p["depth"]), t(p["edges"]), t(p["letter_ids"]),
                int(p["beauty"].shape[0]), float(anim.fps))


NODE_CLASS_MAPPINGS = {
    "TitleRigText": TitleRigText,
    "TitleRigLook3D": TitleRigLook3D,
    "TitleRigShadow": TitleRigShadow,
    "TitleRigLayout": TitleRigLayout,
    "TitleRigRender": TitleRigRender,
    "TitleRigAnimate": TitleRigAnimate,
    "TitleRigRenderAnimation": TitleRigRenderAnimation,
    "TitleRigAudioReact": TitleRigAudioReact,
    "TitleRigStylePreset": TitleRigStylePreset,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "TitleRigText": "TitleRig Text",
    "TitleRigLook3D": "TitleRig Look 3D",
    "TitleRigShadow": "TitleRig Shadow",
    "TitleRigLayout": "TitleRig Layout",
    "TitleRigRender": "TitleRig Render",
    "TitleRigAnimate": "TitleRig Animate",
    "TitleRigRenderAnimation": "TitleRig Render Animation",
    "TitleRigAudioReact": "TitleRig Audio React",
    "TitleRigStylePreset": "TitleRig Style Preset",
}
