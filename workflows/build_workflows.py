"""Build the example workflows in ComfyUI API format (workflows/api/*.json).

The UI-format files (workflows/*.json, drag-and-drop into ComfyUI) are made from these by
workflows/to_ui.py, which loads each one into the real ComfyUI frontend and saves the graph it builds.
Run: python workflows/build_workflows.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

TEXT = {"text": "TITLERIG", "font": "Anton-Regular", "size": 200, "tracking": 4.0,
        "kerning_json": "{}", "letters_json": "{}"}
LOOK = {"face": "#ff8fd8", "face_gradient_to": "#ffd400", "side": "#7c3aed", "extrude": 30, "extrude_angle": 55.0,
        "bevel": 12.0, "bevel_profile": "round", "light_angle": 225.0, "light_height": 0.6, "gloss": 0.9, "rim": 0.4}
SHADOW = {"texture": "halftone", "color": "#0f172a", "angle": 45.0, "length": 36.0, "softness": 0.0,
          "texture_scale": 10.0, "texture_angle": 45.0, "opacity": 1.0}
LAYOUT = {"mode": "arc", "bend": 0.22, "align": 0.5, "bulge": 0.0, "tilt_x": 0.0, "tilt_y": 0.0, "fov": 50.0,
          "vanish": False, "vp_x": 0.5, "vp_y": 1.4, "flag_amp": 0.0, "flag_wavelength": 420.0, "flag_phase": 0.0,
          "flag_shade": 0.5, "curve_json": ""}
ANIM = {"effect": "pop", "target": "letters", "direction": "in", "easing": "back", "duration": 0.6, "stagger": 0.06,
        "order": "center_out", "amount": 0.0, "start": 0.0, "fps": 24.0, "hold": 0.8, "shuffle_seed": 0,
        "letters": "all", "influence": 1.0, "response": "follow", "retrigger": "restart"}


def node(cls, inputs, title=None):
    n = {"class_type": cls, "inputs": inputs}
    if title:
        n["_meta"] = {"title": title}
    return n


def rig(width=1280, height=720):
    """Shared Text -> Look -> Shadow -> Layout nodes (ids 1-4)."""
    return {
        "1": node("TitleRigText", dict(TEXT)),
        "2": node("TitleRigLook3D", dict(LOOK)),
        "3": node("TitleRigShadow", dict(SHADOW)),
        "4": node("TitleRigLayout", dict(LAYOUT)),
    }


def rig_only():
    """No AI, no models: a still with every pass + an animated title saved as WEBP (beauty and depth)."""
    g = rig()
    g["5"] = node("TitleRigRender", {"glyphs": ["1", 0], "width": 1280, "height": 720, "look": ["2", 0],
                                     "shadow": ["3", 0], "layout": ["4", 0], "guide_lines": "all"}, "Render still")
    g["6"] = node("SaveImage", {"images": ["5", 0], "filename_prefix": "titlerig/still_beauty"})
    g["7"] = node("SaveImage", {"images": ["5", 2], "filename_prefix": "titlerig/still_depth"})
    g["8"] = node("PreviewImage", {"images": ["5", 10]}, "Guides")
    g["9"] = node("TitleRigAnimate", dict(ANIM), "Pop in (back, centre out)")
    g["10"] = node("TitleRigAnimate", {**ANIM, "effect": "roll_z", "easing": "elastic", "duration": 0.8,
                                       "order": "forward", "amount": 25.0, "anim": ["9", 0]}, "Roll in (elastic)")
    g["11"] = node("TitleRigRenderAnimation", {"glyphs": ["1", 0], "anim": ["10", 0], "width": 960, "height": 540,
                                               "look": ["2", 0], "shadow": ["3", 0], "layout": ["4", 0]})
    g["12"] = node("SaveAnimatedWEBP", {"images": ["11", 0], "filename_prefix": "titlerig/anim_beauty", "fps": 24.0,
                                        "lossless": False, "quality": 85, "method": "default"})
    g["13"] = node("SaveAnimatedWEBP", {"images": ["11", 2], "filename_prefix": "titlerig/anim_depth", "fps": 24.0,
                                        "lossless": False, "quality": 85, "method": "default"})
    return g


def audio_react():
    """Hero, still no AI: kicks pump BASS, hats bounce TREBLE, kicks throw the shadow -> MP4 with the sound."""
    g = rig()
    g["1"]["inputs"].update(text="BASS TREBLE", size=150)
    g["20"] = node("LoadAudio", {"audio": "titlerig_beat.wav"})
    react = {"fps": 24.0, "mode": "beats", "sensitivity": 0.5, "attack": 0.0, "release": 0.18, "start": 0.0,
             "max_seconds": 0.0, "spectrum_bands": 12}
    g["21"] = node("TitleRigAudioReact", {**react, "audio": ["20", 0], "band": "bass"}, "Kicks (bass)")
    g["22"] = node("TitleRigAudioReact", {**react, "audio": ["20", 0], "band": "highs", "sensitivity": 0.15,
                                          "release": 0.12}, "Hats (highs)")
    g["23"] = node("TitleRigAnimate", {**ANIM, "effect": "pop", "amount": -40.0, "stagger": 0.042, "letters": "word:1",
                                       "drive": ["21", 0]}, "BASS pops on kicks")
    g["24"] = node("TitleRigAnimate", {**ANIM, "effect": "drop", "amount": 40.0, "stagger": 0.042, "letters": "word:2",
                                       "response": "trigger", "easing": "bounce", "duration": 0.3,
                                       "retrigger": "finish", "drive": ["22", 0], "anim": ["23", 0]},
                   "TREBLE bounces on hats")
    g["25"] = node("TitleRigAnimate", {**ANIM, "effect": "shadow_length", "amount": 50.0, "drive": ["21", 0],
                                       "anim": ["24", 0]}, "Kicks throw the shadow")
    g["26"] = node("TitleRigRenderAnimation", {"glyphs": ["1", 0], "anim": ["25", 0], "width": 960, "height": 540,
                                               "look": ["2", 0], "shadow": ["3", 0], "layout": ["4", 0]})
    g["27"] = node("CreateVideo", {"images": ["26", 0], "fps": ["26", 6], "audio": ["20", 0]})
    g["28"] = node("SaveVideo", {"video": ["27", 0], "filename_prefix": "titlerig/audio_react", "format": "mp4",
                                 "codec": "h264"})
    g["29"] = node("PreviewImage", {"images": ["21", 1]}, "Kick curve")
    return g


WORKFLOWS = {"titlerig_rig_only": rig_only, "titlerig_audio_react": audio_react}

if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "api"), exist_ok=True)
    for name, fn in WORKFLOWS.items():
        with open(os.path.join(HERE, "api", f"{name}.json"), "w") as f:
            json.dump(fn(), f, indent=2)
        print("wrote", f"workflows/api/{name}.json")
