"""Style presets: bright, ad-ready looks for the AI pass, plus a matching rig Look3D / Shadow.

FLUX.2 prompts follow the flux-2-prompts skill v1.0.0 (super-skills skills/image/flux-v2, see docs/skills/flux-v2):
front-load the subject and the quoted text, keep it short, describe only what is wanted (no negative prompt), bind
hex colours to specific objects, lighting last, refer to the rig render as "image 1", Flex settings for typography.
FLUX 3 prompts follow the flux-3-image-prompts skill (skills/image/flux-v3, see docs/skills/flux-v3): layer order,
quoted text with placement, image 1 + preserve list, only valid native settings. LTX-2.3 prompts follow the
ltx-2-3-prompts skill (see docs/skills/ltx-2-3): one present-tense paragraph, motion + light + sound, settings out
of the prose, local defaults for the open weights.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .core import Look3D, Shadow

TARGETS = ("flux2_dev", "flux3", "ltx23_video")
FORMATS = ("prose", "json")
AUDIO_MODES = ("own_track", "generate")
LTX_LOCAL_NEGATIVE = "pc game, console game, video game, cartoon, childish, ugly"  # shipped default (skill)
LTX_SKILL_VERSION = "1.0 (2026-10-18)"
CARTOON_STYLES = ("Ben-Day Pop", "Cel Toon")  # their look IS cartoon, so the default negative drops those words


def ltx_negative(preset: str) -> str:
    if preset in CARTOON_STYLES:
        return "pc game, console game, video game, ugly"
    return LTX_LOCAL_NEGATIVE
FLUX2_SKILL_VERSION = "1.0.0"
FLUX3_FIELDS = ("prompt", "images", "aspect_ratio", "resolution", "safety_tolerance", "grounding", "version")


@dataclass
class Preset:
    name: str
    material: str
    lighting: str
    background: str
    palette: list[str]
    palette_words: str
    motion: str                                   # LTX-2: how the scene moves (the rig drives the letters)
    look: dict = field(default_factory=dict)      # Look3D overrides
    shadow: dict = field(default_factory=dict)    # Shadow overrides
    negative: str = ""                            # extra, preset-specific exclusions
    backdrop: str = "#16161c"                     # preview ground (matches `background` in spirit)
    lead: str = ""                                # 1-3 word material lead for the first words of the prompt
    detail: str = ""                              # short material detail after the quoted text
    camera: str | None = None                     # photographic anchor for real materials (None = graphic style)
    sound: str = ""                               # LTX-2.3 sound brief when the model generates audio


PRESETS: dict[str, Preset] = {p.name: p for p in [
    Preset("Chrome Slam", "mirror-polished chrome with crisp studio reflections along each bevel",
           "hard key light from the upper left with a bright rim on every edge", "a deep cobalt studio sweep",
           ["#f4f6fb", "#7a869a", "#1d4ed8"], "silver chrome on electric cobalt",
           "reflections slide across the chrome",
           dict(face="#f4f6fb", face2="#7a869a", side="#3b4252", gloss=1.0, rim=0.5),
           dict(texture="stripes", color="#1d4ed8")),
    Preset("Fuzzy Grass", "dense fuzzy blue grass fibres covering every face, fine macro detail",
           "soft sunny daylight with a warm bounce from below", "a pale sky-blue backdrop with a soft floor shadow",
           ["#38bdf8", "#1e40af", "#e0f2fe"], "cornflower blue fuzz on pale sky",
           "the grass fibres sway in a light breeze",
           dict(face="#38bdf8", face2="#1e40af", side="#1e3a8a", bevel=14, gloss=0.1, rim=0.3),
           dict(texture="noise", color="#1e3a8a", softness=2, opacity=0.7)),
    Preset("Liquid Glass", "clear refractive glass with soft caustics landing on the floor below",
           "bright overhead softbox with a cool rim light", "a cool slate-blue studio sweep",
           ["#e0f7ff", "#7dd3fc", "#ffffff"], "clear glass with ice-blue edges on slate",
           "caustics ripple across the floor as light passes through the glass",
           dict(face="#e0f7ff", face2="#7dd3fc", side="#0ea5e9", gloss=1.2, rim=0.6, bevel=16),
           dict(texture="solid", color="#7dd3fc", softness=10, opacity=0.45)),
    Preset("Aero Bubble", "glossy translucent aqua plastic like a 2000s desktop icon, bubbly rounded edges",
           "bright frontal light with a big white specular streak across the top", "a fresh green-to-sky gradient",
           ["#5eead4", "#22d3ee", "#a3e635"], "aqua and lime on a sky gradient",
           "soap bubbles float past and the gloss streak glides along the letters",
           dict(face="#5eead4", face2="#22d3ee", side="#0e7490", bevel=20, gloss=1.4, rim=0.4),
           dict(texture="solid", color="#0e7490", softness=8, opacity=0.5)),
    Preset("Ben-Day Pop", "flat printed comic-book ink with bold black outlines and Ben-Day halftone dots",
           "flat even light with solid, unshaded colour", "a sunburst of yellow and red comic rays",
           ["#ffd400", "#e11d48", "#111827"], "primary yellow and red with black ink",
           "the comic rays spin slowly behind the title",
           dict(face="#ffd400", face2=None, side="#e11d48", bevel=4, gloss=0.2, rim=0.0),
           dict(texture="halftone", color="#111827")),
    Preset("Holo Foil", "holographic foil with a rainbow sheen that shifts across each letter",
           "a moving point light that sweeps the rainbow across the foil", "a dark violet velvet backdrop",
           ["#f0abfc", "#67e8f9", "#c4b5fd"], "iridescent pink, cyan and lilac on deep violet",
           "the rainbow sheen sweeps across the foil from left to right",
           dict(face="#f0abfc", face2="#67e8f9", side="#7c3aed", gloss=1.3, rim=0.7),
           dict(texture="gradient", color="#4c1d95", opacity=0.8)),
    Preset("ChromaDepth", "glowing neon gradient paint mapped by depth, red closest, then orange, green and blue "
           "furthest back, like ChromaDepth 3D glasses art", "pure black stage with self-lit glowing letters",
           "a pitch-black background", ["#ef4444", "#22c55e", "#3b82f6"], "red to green to blue depth rainbow",
           "the glow pulses as the depth colours flow from front to back",
           dict(face="#ef4444", face2="#f59e0b", side="#3b82f6", gloss=0.5, rim=0.8),
           dict(texture="solid", color="#1e3a8a", softness=6, opacity=0.6)),
    Preset("Candy Inflatable", "glossy pastel inflatable vinyl, puffed seams, bright specular highlights",
           "soft wraparound studio light", "a candy-pink studio sweep",
           ["#ff8fd8", "#a78bfa", "#fde68a"], "bubblegum pink and lavender with butter yellow",
           "the vinyl highlights flex and glint as the letters bounce",
           dict(face="#ff8fd8", face2="#a78bfa", side="#7c3aed", bevel=22, gloss=1.0, rim=0.3),
           dict(texture="solid", softness=8, color="#4c1d95", opacity=0.6)),
    Preset("Op Art Stripe", "crisp black and white op-art stripes that bend around each letter",
           "flat graphic light", "a field of parallel black and white stripes that warp around the title",
           ["#ffffff", "#111111"], "pure black and white",
           "the background stripes ripple in a hypnotic wave",
           dict(face="#111111", face2=None, side="#111111", bevel=2, extrude=18, gloss=0.2, rim=0.0),
           dict(texture="checker", color="#111111", texture_scale=8)),
    Preset("Vapor Sunset", "glossy pink-to-purple gradient lacquer with a chrome top edge",
           "warm sunset backlight with a magenta rim", "a retro synthwave sunset with a wireframe grid floor",
           ["#f472b6", "#8b5cf6", "#fb923c"], "hot pink, violet and sunset orange",
           "the grid floor scrolls toward the viewer under the setting sun",
           dict(face="#f472b6", face2="#8b5cf6", side="#4c1d95", gloss=1.1, rim=0.6),
           dict(texture="stripes", color="#fb923c", texture_scale=6)),
    Preset("Low Poly", "faceted low-poly polygons with flat-shaded triangular facets on every face",
           "bright directional light that makes each facet a different tone", "a clean mint-to-teal gradient",
           ["#34d399", "#0d9488", "#fef08a"], "mint, teal and lemon facets",
           "the light sweeps so the facets catch it one by one",
           dict(face="#34d399", face2="#0d9488", side="#115e59", bevel=6, bevel_profile="chisel", gloss=0.3),
           dict(texture="pixel", color="#134e4a", texture_scale=10)),
    Preset("Cel Toon", "cel-shaded cartoon paint with two flat tones per face and a thick ink outline",
           "flat cartoon key light with one hard shadow tone", "a bright cartoon sky with puffy clouds",
           ["#facc15", "#f97316", "#1f2937"], "sunny yellow and orange with dark ink",
           "the clouds drift across the sky",
           dict(face="#facc15", face2="#f97316", side="#9a3412", bevel=3, gloss=0.4, rim=0.0),
           dict(texture="solid", color="#1f2937")),
    Preset("Trailer Title", "brushed dark steel with glowing ember edges, cinematic movie-trailer lettering",
           "low dramatic side light, volumetric haze and drifting sparks", "a smoky dark theatre backdrop",
           ["#d4d4d8", "#52525b", "#f97316"], "gunmetal steel with ember orange",
           "haze rolls through the frame as sparks drift upward",
           dict(face="#d4d4d8", face2="#52525b", side="#18181b", gloss=0.9, rim=0.5, light_height=0.4),
           dict(texture="solid", color="#000000", softness=12, opacity=0.7),
           negative="cartoon, flat colours"),
]}

_BACKDROPS = {"Chrome Slam": "#1e3a8a", "Fuzzy Grass": "#bae6fd", "Liquid Glass": "#475569", "Aero Bubble": "#86efac",
              "Ben-Day Pop": "#fde047", "Holo Foil": "#2e1065", "ChromaDepth": "#050505", "Candy Inflatable": "#fbcfe8",
              "Op Art Stripe": "#f5f5f5", "Vapor Sunset": "#3b0764", "Low Poly": "#99f6e4", "Cel Toon": "#7dd3fc",
              "Trailer Title": "#0c0a09"}
for _n, _b in _BACKDROPS.items():
    PRESETS[_n].backdrop = _b

STUDIO = "Shot on Hasselblad X2D, 90mm f/8, sharp focus"
_LEADS = {  # name: (lead, detail, camera)
    "Chrome Slam": ("Mirror-chrome", "crisp studio reflections along each bevel", STUDIO),
    "Fuzzy Grass": ("Fuzzy blue grass", "dense fibres covering every face", "Shot on Sony A7IV, 90mm macro f/8"),
    "Liquid Glass": ("Clear refractive glass", "soft caustics on the floor below", STUDIO),
    "Aero Bubble": ("Glossy aqua plastic", "a bright white gloss streak across the top", STUDIO),
    "Ben-Day Pop": ("Comic-print", "bold black outlines and Ben-Day halftone dots", None),
    "Holo Foil": ("Holographic foil", "a rainbow sheen shifting across each letter", STUDIO),
    "ChromaDepth": ("Glowing neon ChromaDepth", "red in front, through orange and green, to blue behind", None),
    "Candy Inflatable": ("Inflatable pastel vinyl", "puffed seams and bright highlights", STUDIO),
    "Op Art Stripe": ("Black and white op-art", "crisp stripes bending around each letter", None),
    "Vapor Sunset": ("Synthwave lacquer", "a pink-to-purple gradient with a chrome top edge", None),
    "Low Poly": ("Low-poly faceted", "flat-shaded triangular facets", None),
    "Cel Toon": ("Cel-shaded cartoon", "two flat tones per face and a thick ink outline", None),
    "Trailer Title": ("Brushed steel movie-trailer", "glowing ember edges",
                      "Shot on ARRI Alexa 35, 50mm anamorphic, sharp focus on the letters"),
}
_SOUNDS = {
    "Chrome Slam": "Bright metallic clangs land with each hit and a punchy electronic beat drives underneath",
    "Fuzzy Grass": "A soft breeze rustles through the fibres with birdsong far away and a light acoustic pluck",
    "Liquid Glass": "Crystal chimes ring as the light passes and a calm ambient pad holds underneath",
    "Aero Bubble": "Bubbles pop softly over a bright, bouncy synth-pop loop",
    "Ben-Day Pop": "Comic-book whooshes and pops punctuate a playful surf-rock riff",
    "Holo Foil": "A shimmering synth sweep follows the rainbow and a glossy pop beat pulses",
    "ChromaDepth": "A deep electronic hum swells with each pulse over a driving techno beat",
    "Candy Inflatable": "Squeaky vinyl bounces and soft boings sit over a sweet bubblegum-pop beat",
    "Op Art Stripe": "A hypnotic minimal electronic pulse ticks in time with the ripple",
    "Vapor Sunset": "Warm synthwave pads and a gated snare roll under a slow retro beat",
    "Low Poly": "Crisp digital blips ring as each facet lights over a chiptune bassline",
    "Cel Toon": "Cartoon boings and a cheerful whistle play over a bouncy ukulele tune",
    "Trailer Title": "A deep cinematic boom hits, embers crackle and a low orchestral drone builds",
}
for _n, _s in _SOUNDS.items():
    PRESETS[_n].sound = _s
EMBOSSED = ("Chrome Slam", "Candy Inflatable")  # the only presets with a raised bevel; the rest are flat-faced
for _n, (_l, _d, _c) in _LEADS.items():
    PRESETS[_n].lead, PRESETS[_n].detail, PRESETS[_n].camera = _l, _d, _c
for _n, _p in PRESETS.items():
    if _n not in EMBOSSED:
        _p.look.update(bevel=0.0, bevel_profile="flat")

# structural variety: depth, extrusion direction and shadow differ, and some presets have none at all
_STRUCTURE = {  # name: (extrude px, extrude_angle deg, shadow overrides or None for no shadow)
    "Chrome Slam": (34, 55, dict(length=40)),
    "Fuzzy Grass": (18, 60, dict(length=24)),
    "Liquid Glass": (0, 55, dict(length=26, softness=12)),             # floating glass, soft shadow only
    "Aero Bubble": (10, 70, None),                                     # shallow, no shadow
    "Ben-Day Pop": (24, 125, dict(angle=135, length=30)),              # extrudes down-left
    "Holo Foil": (0, 55, None),                                        # flat foil sticker: no depth, no shadow
    "ChromaDepth": (30, 70, None),                                     # deep, glow only, no shadow
    "Candy Inflatable": (0, 55, dict(length=18, softness=10)),         # puffed by its bevel, soft shadow
    "Op Art Stripe": (0, 55, None),                                    # flat graphic: no depth, no shadow
    "Vapor Sunset": (26, 90, dict(length=36)),
    "Low Poly": (14, 40, dict(length=20)),
    "Cel Toon": (12, 45, dict(length=16)),
    "Trailer Title": (6, 70, dict(length=64, softness=16)),            # thin slab, long cinematic shadow
}
for _n, (_e, _a, _sh) in _STRUCTURE.items():
    PRESETS[_n].look.update(extrude=_e, extrude_angle=float(_a))
    if _sh is None:
        PRESETS[_n].shadow = dict(PRESETS[_n].shadow, on=False, length=0.0)
    else:
        PRESETS[_n].shadow = dict(PRESETS[_n].shadow, **_sh)


def _depth(p: Preset) -> tuple[bool, str]:
    """(extruded, prompt word): flat presets say 'flat title lettering' and never mention extrusion."""
    look = Look3D(**p.look)
    if look.extrude > 0:
        return True, "3D title lettering"
    return False, ("raised title lettering" if p.name in EMBOSSED else "flat title lettering")

PRESET_NAMES = tuple(PRESETS)


_NEGATION = re.compile(r"\b(no|not|without|avoid|don't|never)\b", re.I)


def _colours(p: Preset, colour_words: str) -> str:
    """Hex colours bound to specific objects (skill rule), or the user's colour words when given."""
    look = Look3D(**p.look)
    if colour_words.strip():
        return f"Letters in {colour_words.strip()}"
    walls = f", extrusion {look.side.upper()}" if look.extrude > 0 else ""
    return f"Letter faces {look.face.upper()}{walls}, background {p.backdrop.upper()}"


def flux2_structured(p: Preset, text: str, colour_words: str = "") -> dict:
    """Skill-format JSON structured prompt (serialised into the prompt string)."""
    look = Look3D(**p.look)
    deep, kind = _depth(p)
    palette = ([look.face.upper()] + ([look.side.upper()] if deep else [])) if not colour_words.strip() else []
    subj = {"description": f"{p.lead} {kind} reading '{text}', with {p.detail}",
            "position": "centred, filling the frame",
            "action": f"letterforms, spacing{' and extrusion' if deep else ''} follow image 1 exactly"}
    if palette:
        subj["color_palette"] = palette
    out = {"scene": f"title card: {p.background}", "subjects": [subj],
           "style": "bright ad-ready 3D lettering" + ("" if p.camera else ", graphic illustration"),
           "background": p.background + (f", {p.backdrop.upper()}" if not colour_words.strip() else ""),
           "lighting": p.lighting, "composition": "centred title lockup"}
    if colour_words.strip():
        out["style"] += f", colours {colour_words.strip()}"
    if p.camera:
        out["camera"] = {"angle": "straight on", "lens": p.camera.split(", ")[1] if ", " in p.camera else p.camera,
                         "depth_of_field": "sharp focus across every letter"}
    return out


def flux2_settings(text: str, target_mp: float = 1.0) -> dict:
    """Skill-schema request settings: Flex for typography (steps 50, guidance 8), size from image 1."""
    return {"variant": "flex", "steps": 50, "guidance": 8.0, "aspect_ratio": "match_input_image", "seed": None,
            "metadata": {"skill_version": FLUX2_SKILL_VERSION, "generation_intent": "typography_comp",
                         "variant_rationale": f"Flex for legible typography ('{text}'): 50 steps, guidance 8. "
                                              "Open-weights local run: flux2-dev in ComfyUI with the TitleRig "
                                              "render as reference image 1."}}


def flux3_settings(final: bool = True) -> dict:
    """Valid native FLUX 3 fields only; aspect follows image 1 (the rig render). Iterate at 1k, finish at 2k."""
    return {"images": ["TitleRig beauty pass (image 1)"], "aspect_ratio": "auto",
            "resolution": "2k" if final else "1k", "grounding": False}


def build_prompt(preset: str, text: str, colour_words: str = "", target: str = "flux2_dev",
                 fmt: str = "prose", audio: str = "own_track") -> tuple[str, str]:
    """(positive, negative) prompt for `preset` on the word `text`, written for `target`.

    FLUX.2 and FLUX 3 take no negative prompt, so negative is empty for them; LTX-2.3 gets the local default.
    audio (LTX-2.3): own_track = your music is muxed in (generate_audio false); generate = write the sound."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {preset}; choose from {PRESET_NAMES}")
    if target not in TARGETS:
        raise ValueError(f"unknown target: {target}; choose from {TARGETS}")
    if audio not in AUDIO_MODES:
        raise ValueError(f"unknown audio mode: {audio}; choose from {AUDIO_MODES}")
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}; choose from {FORMATS}")
    p = PRESETS[preset]
    colours = colour_words.strip() or p.palette_words
    quoted = text.replace("'", "\u2019").replace('"', "\u201d")
    if target == "flux2_dev":
        if fmt == "json":
            return json.dumps(flux2_structured(p, quoted, colour_words), ensure_ascii=False), ""
        deep, kind = _depth(p)
        parts = [f"{p.lead} {kind} reading '{quoted}', centred, with {p.detail}.",
                 f"Letterforms, spacing{' and extrusion' if deep else ''} follow image 1 exactly.",
                 f"{_colours(p, colour_words)}: {p.background}."]
        if p.camera:
            parts.append(f"{p.camera}.")
        parts.append(f"{p.lighting.capitalize()}.")
        return " ".join(parts), ""
    if target == "flux3":  # skill layer order; image 1 = the TitleRig beauty pass
        look = Look3D(**p.look)
        deep, word = _depth(p)
        kind = f"A bright studio product shot of {word}" if p.camera else "A bright graphic title card"
        frame = ("Eye-level, straight-on 90mm view with deep focus across every letter" if p.camera
                 else "Straight-on, flat graphic framing with the title filling the centre")
        palette = (f"Colours: {colour_words.strip()}" if colour_words.strip() else
                   f"Letter faces {look.face.upper()}" + (f", extrusion walls {look.side.upper()}" if deep else "") +
                   f", background {p.backdrop.upper()}")
        keep = "letterforms, spacing, extrusion depth and camera angle" if deep else "letterforms, spacing and camera angle"
        pos = (f'{kind}. The title reads "{quoted}" in bold block capitals, centred, and keeps the exact '
               f"{keep} of image 1. Every letter is rebuilt as "
               f"{p.material}. {p.background.capitalize()} sits behind the title. {p.lighting.capitalize()}. "
               f"{frame}. {palette}, {p.palette_words}.")
        return pos, ""
    # ltx23_video: one chronological present-tense paragraph; the rig's control video carries the letterforms
    look = Look3D(**p.look)
    deep, word = _depth(p)
    colours_line = (f"The palette stays {colour_words.strip()}" if colour_words.strip() else
                    f"The letter faces stay {look.face.upper()}" +
                    (f" and the extrusion walls {look.side.upper()}" if deep else ""))
    parts = [f'The {word.replace(" lettering", "")} "{quoted}" holds the centre of the frame while its letters move exactly as the '
             f"control video drives them, each one made of {p.material}.",
             f"{p.background.capitalize()} fills the space behind the title, and {p.motion}.",
             "The camera stays locked in a straight-on medium frame on the title.",
             f"{p.lighting.capitalize()} plays across the letters, and {colours_line.lower()[0]}{colours_line[1:]}.",
             "By the final moment the title settles crisp and fully legible."]
    if audio == "generate":
        parts.append(f"{p.sound}.")
    return " ".join(parts), ltx_negative(preset)


def ltx_frames(n: int) -> int:
    """Smallest LTX-2.3 frame count (8n + 1) that holds n rig frames."""
    return 8 * max(0, -(-(max(n, 1) - 1) // 8)) + 1


def ltx23_settings(frames: int = 121, fps: int = 24, audio: str = "own_track", preset: str = "") -> dict:
    """Local open-weights settings (distilled) + the equivalent native API request, prose kept out of both."""
    f = ltx_frames(frames)
    gen = audio == "generate"
    return {"local": {"checkpoint": "ltx-2.3-22b-distilled", "steps": 8, "cfg_scale": 1.0, "width": 960,
                      "height": 544, "frames": f, "fps": fps, "negative_prompt": ltx_negative(preset),
                      "control": "TitleRig depth via an LTX-2.3 depth IC-LoRA (LTX-2 LoRAs do not transfer)",
                      "generate_audio": gen, "skill_version": LTX_SKILL_VERSION,
                      "note": "template sizes and the default negative are from the skill's research, unverified"},
            "api": {"model": "ltx-2-3-pro", "resolution": "1920x1080", "fps": fps,
                    "duration": min((6, 8, 10), key=lambda d: abs(d - f / fps)), "generate_audio": gen,
                    "camera_motion": "static"}}


def suggested_look(preset: str) -> tuple[Look3D, Shadow]:
    """Rig Look3D + Shadow that preview the preset (and give the AI a matching base)."""
    p = PRESETS[preset]
    return Look3D(**p.look), Shadow(**p.shadow)
