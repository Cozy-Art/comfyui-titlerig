"""ComfyUI node wrappers around render/. Keep all drawing logic in render/ so it stays testable without ComfyUI."""
from __future__ import annotations

import json

import numpy as np

from ..render.presets import AUDIO_MODES as PRESET_AUDIO, FORMATS, PRESET_NAMES, ltx23_settings, ltx_frames, TARGETS as PROMPT_TARGETS, build_prompt, flux2_settings, flux3_settings, suggested_look
from ..render.magnet import PATHS as MAGNET_PATHS, POLARITIES, Magnet
from ..render.svg import rig_svg
from ..render.spell_lock import spell_lock_batch
from ..render.cutout import FITS, MASK_FROM, TIMING, cutout, pick_mask
from ..render.core import _rgb
from ..render.audio import AUDIO_MODES, BANDS, audio_curve, curve_preview
from ..render.animate import pad_frames
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
            "wrap_radius": ("FLOAT", {"default": 0.32, "min": 0.02, "max": 3, "step": 0.01,
                                      "tooltip": "ticker / cube: x canvas width · sphere: x canvas height"}),
            "wrap_phase": ("FLOAT", {"default": 0.0, "min": -36000, "max": 36000, "step": 1,
                                     "tooltip": "degrees the wrap is turned (animate with wrap_spin)"}),
            "wrap_tilt": ("FLOAT", {"default": 15.0, "min": -89, "max": 89, "step": 1, "tooltip": "sphere lean"}),
            "wrap_repeat": ("BOOLEAN", {"default": True, "tooltip": "repeat the text around the band"}),
            "wrap_shade": ("FLOAT", {"default": 0.6, "min": 0, "max": 1, "step": 0.05}),
            "curve_json": ("STRING", {"default": "", "tooltip": "arc: custom cubic bezier [[x,y]x4] in 0..1 canvas coords"}),
        }}

    def build(self, mode, bend, align, bulge, tilt_x, tilt_y, fov, vanish, vp_x, vp_y,
              flag_amp, flag_wavelength, flag_phase, flag_shade, wrap_radius=0.32, wrap_phase=0.0, wrap_tilt=15.0,
              wrap_repeat=True, wrap_shade=0.6, curve_json=""):
        curve = tuple(map(tuple, json.loads(curve_json))) if curve_json.strip() else None
        return (Layout(mode=mode, bend=bend, curve=curve, align=align, bulge=bulge, tilt_x=tilt_x, tilt_y=tilt_y,
                       fov=fov, vanish=vanish, vp_x=vp_x, vp_y=vp_y, flag_amp=flag_amp,
                       flag_wavelength=flag_wavelength, flag_phase=flag_phase, flag_shade=flag_shade,
                       wrap_radius=wrap_radius, wrap_phase=wrap_phase, wrap_tilt=wrap_tilt, wrap_repeat=wrap_repeat,
                       wrap_shade=wrap_shade),)


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
                       "(rig render = image 1) · flux3: API bonus, rig beauty = image 1 · ltx23_video: LTX-2.3 with rig depth"}),
            "colour_words": ("STRING", {"default": "", "tooltip": "optional, e.g. 'teal and hot pink' (replaces the "
                             "preset's palette words)"}),
            "text": ("STRING", {"default": "TITLE", "tooltip": "used when no glyphs are connected"}),
            "format": (list(FORMATS), {"default": "prose", "tooltip": "flux2_dev: prose, or a JSON structured prompt "
                       "(pasted into the prompt string, per the flux-v2 skill)"}),
            "audio": (list(PRESET_AUDIO), {"default": "own_track", "tooltip": "ltx23_video: own_track = your music "
                      "is muxed in (generate_audio false) · generate = LTX writes the sound from the prompt"}),
        }, "optional": {
            "glyphs": ("TITLERIG_GLYPHS", {"tooltip": "take the exact text from the rig"}),
            "frame_count": ("INT", {"default": 121, "min": 1, "max": 2000, "tooltip": "ltx23_video: rig frames "
                            "(snapped up to 8n+1 in settings)"}),
        }}

    def build(self, preset, target, colour_words, text, format="prose", audio="own_track", glyphs=None,
              frame_count=121):
        word = glyphs.text if glyphs is not None else text
        pos, neg = build_prompt(preset, word, colour_words, target, format, audio)
        look, shadow = suggested_look(preset)
        settings = json.dumps(flux2_settings(word) if target == "flux2_dev" else
                              flux3_settings() if target == "flux3" else ltx23_settings(frame_count, audio=audio, preset=preset))
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


class TitleRigMagnet:
    """A moving magnet (optionally a second word) that attracts or repels the title's letters, with springy
    lag and squash & stretch. Adds to an Animate chain; feed the result to Render Animation."""
    CATEGORY = CAT
    RETURN_TYPES = ("TITLERIG_ANIM",)
    RETURN_NAMES = ("anim",)
    FUNCTION = "build"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "polarity": (list(POLARITIES), {"default": "repel"}),
            "strength": ("FLOAT", {"default": 90.0, "min": 0, "max": 2000, "step": 1, "tooltip": "px of push"}),
            "range": ("FLOAT", {"default": 220.0, "min": 1, "max": 4000, "step": 1, "tooltip": "px falloff radius"}),
            "lag": ("FLOAT", {"default": 0.15, "min": 0, "max": 5, "step": 0.01,
                              "tooltip": "s: far letters respond this much later"}),
            "spring": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "step": 0.01, "tooltip": "0 smooth, 1 bouncy"}),
            "squash": ("FLOAT", {"default": 0.4, "min": 0, "max": 1, "step": 0.01,
                                 "tooltip": "squash & stretch along each letter's velocity"}),
            "path": (list(MAGNET_PATHS), {"default": "sweep"}),
            "x": ("FLOAT", {"default": -0.15, "min": -2, "max": 3, "step": 0.01}),
            "y": ("FLOAT", {"default": 0.5, "min": -2, "max": 3, "step": 0.01}),
            "x_end": ("FLOAT", {"default": 1.15, "min": -2, "max": 3, "step": 0.01}),
            "y_end": ("FLOAT", {"default": 0.5, "min": -2, "max": 3, "step": 0.01}),
            "radius": ("FLOAT", {"default": 0.3, "min": 0, "max": 3, "step": 0.01, "tooltip": "orbit, x canvas height"}),
            "duration": ("FLOAT", {"default": 2.5, "min": 0.05, "max": 600, "step": 0.05}),
            "start": ("FLOAT", {"default": 0.0, "min": 0, "max": 600, "step": 0.05}),
            "fps": ("FLOAT", {"default": 24.0, "min": 1, "max": 120, "step": 1}),
            "hold": ("FLOAT", {"default": 0.8, "min": 0, "max": 60, "step": 0.05}),
        }, "optional": {
            "anim": ("TITLERIG_ANIM", {"tooltip": "chain: tracks and magnets from earlier nodes"}),
            "drive": ("TITLERIG_CURVE", {"tooltip": "per-frame curve (e.g. Audio React) that scales strength"}),
            "magnet_text": ("STRING", {"default": "", "tooltip": "render this word as the magnet (empty = invisible)"}),
            "magnet_size": ("INT", {"default": 120, "min": 8, "max": 1024}),
        }}

    def build(self, polarity, strength, range, lag, spring, squash, path, x, y, x_end, y_end, radius, duration,
              start, fps, hold, anim=None, drive=None, magnet_text="", magnet_size=120):
        mg = Magnet(polarity=polarity, strength=strength, range=range, lag=lag, spring=spring, squash=squash,
                    path=path, x=x, y=y, x_end=x_end, y_end=y_end, radius=radius, duration=duration, start=start,
                    drive=None if drive is None else drive["values"], text=magnet_text, size=magnet_size)
        if drive is not None:
            fps = drive["fps"]
        if anim is None:
            return (Anim([], fps=fps, hold=hold, magnets=[mg]),)
        return (Anim(list(anim.tracks), fps=anim.fps, hold=max(anim.hold, hold), magnets=list(anim.magnets) + [mg]),)


class TitleRigSVGExport:
    """Trace the rig into a layered SVG (shadow shapes, extrusion tones, one path per letter) and save it."""
    CATEGORY = CAT
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("svg", "path")
    FUNCTION = "export"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "glyphs": ("TITLERIG_GLYPHS",),
            "width": ("INT", {"default": 1280, "min": 64, "max": 4096, "step": 8}),
            "height": ("INT", {"default": 720, "min": 64, "max": 4096, "step": 8}),
            "filename_prefix": ("STRING", {"default": "titlerig/title"}),
            "supersample": ("INT", {"default": 2, "min": 1, "max": 4, "tooltip": "trace at this multiple for smoother edges"}),
            "side_tones": ("INT", {"default": 4, "min": 1, "max": 12, "tooltip": "extrusion depth bands"}),
            "background": ("STRING", {"default": "", "tooltip": "hex fill behind the title (empty = transparent)"}),
        }, "optional": {
            "look": ("TITLERIG_LOOK",),
            "shadow": ("TITLERIG_SHADOW",),
            "layout": ("TITLERIG_LAYOUT",),
        }}

    def export(self, glyphs, width, height, filename_prefix, supersample, side_tones, background,
               look=None, shadow=None, layout=None):
        import os

        import folder_paths  # ComfyUI

        svg = rig_svg(glyphs, look, shadow, width, height, layout, supersample, side_tones, background or None)
        full, name, counter, sub, _ = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_output_directory(),
                                                                         width, height)
        fname = f"{name}_{counter:05}_.svg"
        path = os.path.join(full, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        return {"ui": {"text": [os.path.join(sub, fname)]}, "result": (svg, path)}


class TitleRigSpellLock:
    """Spell-Lock v1: restore AI frames to the rig's exact silhouette (mask-based, no OCR)."""
    CATEGORY = CAT
    RETURN_TYPES = ("IMAGE", "MASK", "FLOAT", "STRING")
    RETURN_NAMES = ("images", "fix_mask", "drift", "report")
    FUNCTION = "lock"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE", {"tooltip": "AI frames (FLUX / LTX output)"}),
            "alpha": ("MASK", {"tooltip": "TitleRig alpha (one frame or one per frame)"}),
            "strength": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "step": 0.05}),
            "tolerance": ("INT", {"default": 2, "min": 0, "max": 32, "tooltip": "px slack at the rig edge (rig res)"}),
            "ring": ("INT", {"default": 24, "min": 2, "max": 256, "tooltip": "px band around the title that is checked"}),
        }, "optional": {
            "edges": ("IMAGE", {"tooltip": "optional TitleRig edges (accepted; drift is measured on silhouettes)"}),
            "shadow": ("MASK", {"tooltip": "TitleRig shadow: intended shadow never counts as spill"}),
        }}

    def lock(self, images, alpha, strength, tolerance, ring, edges=None, shadow=None):
        import torch

        np_ = lambda t: None if t is None else t.detach().cpu().numpy()  # noqa: E731
        r = spell_lock_batch(np_(images), np_(alpha), np_(edges), strength, tolerance, ring, np_(shadow))
        drift = float(np.mean(r["drift_after"])) if r["drift_after"] else -1.0
        report = json.dumps({"drift_before": [round(x, 4) for x in r["drift_before"]],
                             "drift_after": [round(x, 4) for x in r["drift_after"]],
                             "fixed_px": [int(m.sum()) for m in r["fix_masks"]]})
        return (torch.from_numpy(r["frames"]), torch.from_numpy(r["fix_masks"]), drift, report)


class TitleRigCutout:
    """Cutout text: an image or video inside the letters, another outside, masked by the rig per frame."""
    CATEGORY = CAT
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("images", "letters")
    FUNCTION = "cut"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "inside": ("IMAGE", {"tooltip": "image or video frames shown inside the letters"}),
            "alpha": ("MASK", {"tooltip": "TitleRig alpha (faces + extrusion), one frame or one per frame"}),
            "mask_from": (list(MASK_FROM), {"default": "faces + extrusion"}),
            "fit_inside": (list(FITS), {"default": "cover"}),
            "fit_outside": (list(FITS), {"default": "cover"}),
            "timing": (list(TIMING), {"default": "loop", "tooltip": "what a source shorter than the clip does"}),
            "grow": ("FLOAT", {"default": 0.0, "min": -64, "max": 64, "step": 0.5, "tooltip": "px, + fattens the letters"}),
            "feather": ("FLOAT", {"default": 0.0, "min": 0, "max": 64, "step": 0.5, "tooltip": "px of soft edge"}),
            "stroke": ("FLOAT", {"default": 0.0, "min": 0, "max": 64, "step": 0.5, "tooltip": "px outline outside the letters"}),
            "stroke_color": ("STRING", {"default": "#ffffff"}),
            "shading": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "step": 0.05,
                                  "tooltip": "lay the rig's lighting over the inside (needs beauty)"}),
            "background": ("STRING", {"default": "#000000", "tooltip": "fills outside when nothing is connected"}),
        }, "optional": {
            "outside": ("IMAGE", {"tooltip": "image or video frames shown everywhere else"}),
            "face": ("MASK", {"tooltip": "TitleRig face mask (for mask_from = faces)"}),
            "shadow": ("MASK", {"tooltip": "TitleRig shadow mask (for mask_from = silhouette + shadow)"}),
            "beauty": ("IMAGE", {"tooltip": "TitleRig beauty, for shading"}),
        }}

    def cut(self, inside, alpha, mask_from, fit_inside, fit_outside, timing, grow, feather, stroke, stroke_color,
            shading, background, outside=None, face=None, shadow=None, beauty=None):
        np_ = lambda t: None if t is None else t.detach().cpu().numpy()  # noqa: E731
        mask = pick_mask(np_(alpha), np_(face), np_(shadow), mask_from)
        rgb, a = cutout(np_(inside), mask, np_(outside), np_(beauty), fit_inside, fit_outside, grow, feather, stroke,
                        _rgb(stroke_color), shading, timing, _rgb(background))
        import torch

        return (torch.from_numpy(rgb), torch.from_numpy(a))


class TitleRigRenderAnimation:
    CATEGORY = CAT
    RETURN_TYPES = ("IMAGE", "MASK", "IMAGE", "IMAGE", "IMAGE", "INT", "FLOAT", "MASK", "MASK")
    RETURN_NAMES = ("beauty", "alpha", "depth", "edges", "letter_ids", "frame_count", "fps", "face", "shadow")
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
            "pad_ltx": ("BOOLEAN", {"default": False, "tooltip": "pad to LTX's 8n+1 frame rule by holding the last "
                        "frame, so depth guide, Spell-Lock alpha and audio stay aligned"}),
        }}

    def render(self, glyphs, anim, width, height, look=None, shadow=None, layout=None, pad_ltx=False):
        p = render_frames(anim, glyphs, look, shadow, width, height, layout,
                          passes=("beauty", "alpha", "depth", "edges", "letter_ids", "face", "shadow"))
        if pad_ltx:
            p = pad_frames(p, ltx_frames(p["beauty"].shape[0]))
        import torch

        t = lambda a: torch.from_numpy(np.ascontiguousarray(a, np.float32))  # noqa: E731  (no copy when contiguous)
        beauty = t(p.pop("beauty")[..., :3])  # the one copy: RGB out of RGBA, then the RGBA frames are freed
        return (beauty, t(p["alpha"]), t(p["depth"]), t(p["edges"]), t(p["letter_ids"]),
                int(beauty.shape[0]), float(anim.fps), t(p["face"]), t(p["shadow"]))


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
    "TitleRigMagnet": TitleRigMagnet,
    "TitleRigSVGExport": TitleRigSVGExport,
    "TitleRigSpellLock": TitleRigSpellLock,
    "TitleRigCutout": TitleRigCutout,
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
    "TitleRigMagnet": "TitleRig Magnet",
    "TitleRigSVGExport": "TitleRig SVG Export",
    "TitleRigSpellLock": "TitleRig Spell-Lock",
    "TitleRigCutout": "TitleRig Cutout",
}
