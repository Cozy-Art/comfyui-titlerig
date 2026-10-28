"""Style presets: bright, ad-ready looks for the AI pass, plus a matching rig Look3D / Shadow.

FLUX.2 prompts follow the flux-2-prompts skill v1.0.0 (super-skills skills/image/flux-v2, see docs/skills/flux-v2):
front-load the subject and the quoted text, keep it short, describe only what is wanted (no negative prompt), bind
hex colours to specific objects, lighting last, refer to the rig render as "image 1", Flex settings for typography.
FLUX 3 prompts follow the flux-3-image-prompts skill (skills/image/flux-v3, see docs/skills/flux-v3): layer order,
quoted text with placement, image 1 + preserve list, only valid native settings. LTX-2 prompts are provisional
until checked against an LTX-2 skill.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .core import Look3D, Shadow

TARGETS = ("flux2_dev", "flux3", "ltx2_video")
FORMATS = ("prose", "json")
FLUX2_SKILL_VERSION = "1.0.0"
FLUX3_FIELDS = ("prompt", "images", "aspect_ratio", "resolution", "safety_tolerance", "grounding", "version")
NEGATIVE = ("misspelled text, extra letters, missing letters, warped letterforms, duplicate words, watermark, "
            "logo, signature, blurry, low resolution, jpeg artifacts")


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


PRESETS: dict[str, Preset] = {p.name: p for p in [
    Preset("Chrome Slam", "mirror-polished chrome with crisp studio reflections along each bevel",
           "hard key light from the upper left with a bright rim on every edge", "a deep cobalt studio sweep",
           ["#f4f6fb", "#7a869a", "#1d4ed8"], "silver chrome on electric cobalt",
           "reflections slide across the chrome as the camera drifts",
           dict(face="#f4f6fb", face2="#7a869a", side="#3b4252", gloss=1.0, rim=0.5),
           dict(texture="stripes", color="#1d4ed8")),
    Preset("Fuzzy Grass", "dense fuzzy blue grass fibres covering every face, fine macro detail",
           "soft sunny daylight with a warm bounce from below", "a pale sky-blue backdrop with a soft floor shadow",
           ["#38bdf8", "#1e40af", "#e0f2fe"], "cornflower blue fuzz on pale sky",
           "the grass fibres sway in a light breeze",
           dict(face="#38bdf8", face2="#1e40af", side="#1e3a8a", bevel=14, gloss=0.1, rim=0.3),
           dict(texture="noise", color="#1e3a8a", softness=2, opacity=0.7)),
    Preset("Liquid Glass", "clear refractive glass with soft caustics landing on the floor below",
           "bright overhead softbox with a cool rim light", "a white seamless studio floor",
           ["#e0f7ff", "#7dd3fc", "#ffffff"], "clear glass with ice-blue edges on white",
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
           "the glow pulses and the depth colours flow from front to back",
           dict(face="#ef4444", face2="#f59e0b", side="#3b82f6", gloss=0.5, rim=0.8),
           dict(texture="solid", color="#1e3a8a", softness=6, opacity=0.6)),
    Preset("Candy Inflatable", "glossy pastel inflatable vinyl, puffed seams, bright specular highlights",
           "soft wraparound studio light", "a candy-pink studio sweep",
           ["#ff8fd8", "#a78bfa", "#fde68a"], "bubblegum pink and lavender with butter yellow",
           "the inflatable letters wobble and squash gently as if bouncing",
           dict(face="#ff8fd8", face2="#a78bfa", side="#7c3aed", bevel=22, gloss=1.0, rim=0.3),
           dict(texture="solid", softness=8, color="#4c1d95", opacity=0.6)),
    Preset("Op Art Stripe", "crisp black and white op-art stripes that bend around each letter",
           "flat graphic light", "a field of parallel black and white stripes that warp around the title",
           ["#ffffff", "#111111"], "pure black and white",
           "the background stripes ripple in a hypnotic wave",
           dict(face="#ffffff", face2=None, side="#111111", bevel=2, extrude=18, gloss=0.2, rim=0.0),
           dict(texture="checker", color="#111111", texture_scale=8)),
    Preset("Vapor Sunset", "glossy pink-to-purple gradient lacquer with a chrome top edge",
           "warm sunset backlight with a magenta rim", "a retro synthwave sunset with a wireframe grid floor",
           ["#f472b6", "#8b5cf6", "#fb923c"], "hot pink, violet and sunset orange",
           "the grid floor scrolls toward the camera under the setting sun",
           dict(face="#f472b6", face2="#8b5cf6", side="#4c1d95", gloss=1.1, rim=0.6),
           dict(texture="stripes", color="#fb923c", texture_scale=6)),
    Preset("Low Poly", "faceted low-poly polygons with flat-shaded triangular facets on every face",
           "bright directional light that makes each facet a different tone", "a clean mint-to-teal gradient",
           ["#34d399", "#0d9488", "#fef08a"], "mint, teal and lemon facets",
           "the camera orbits slowly so the facets catch the light one by one",
           dict(face="#34d399", face2="#0d9488", side="#115e59", bevel=6, bevel_profile="chisel", gloss=0.3),
           dict(texture="pixel", color="#134e4a", texture_scale=10)),
    Preset("Cel Toon", "cel-shaded cartoon paint with two flat tones per face and a thick ink outline",
           "flat cartoon key light with one hard shadow tone", "a bright cartoon sky with puffy clouds",
           ["#facc15", "#f97316", "#1f2937"], "sunny yellow and orange with dark ink",
           "the clouds drift and the title bobs with a cartoon bounce",
           dict(face="#facc15", face2="#f97316", side="#9a3412", bevel=3, gloss=0.4, rim=0.0),
           dict(texture="solid", color="#1f2937")),
    Preset("Trailer Title", "brushed dark steel with glowing ember edges, cinematic movie-trailer lettering",
           "low dramatic side light, volumetric haze and drifting sparks", "a smoky dark theatre backdrop",
           ["#d4d4d8", "#52525b", "#f97316"], "gunmetal steel with ember orange",
           "the camera pushes in slowly through haze as sparks drift upward",
           dict(face="#d4d4d8", face2="#52525b", side="#18181b", gloss=0.9, rim=0.5, light_height=0.4),
           dict(texture="solid", color="#000000", softness=12, opacity=0.7),
           negative="cartoon, flat colours"),
]}

_BACKDROPS = {"Chrome Slam": "#1e3a8a", "Fuzzy Grass": "#bae6fd", "Liquid Glass": "#e2e8f0", "Aero Bubble": "#86efac",
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
EMBOSSED = ("Chrome Slam", "Candy Inflatable")  # the only presets with a raised bevel; the rest are flat-faced
for _n, (_l, _d, _c) in _LEADS.items():
    PRESETS[_n].lead, PRESETS[_n].detail, PRESETS[_n].camera = _l, _d, _c
for _n, _p in PRESETS.items():
    if _n not in EMBOSSED:
        _p.look.update(bevel=0.0, bevel_profile="flat")

PRESET_NAMES = tuple(PRESETS)


_NEGATION = re.compile(r"\b(no|not|without|avoid|don't|never)\b", re.I)


def _colours(p: Preset, colour_words: str) -> str:
    """Hex colours bound to specific objects (skill rule), or the user's colour words when given."""
    look = Look3D(**p.look)
    if colour_words.strip():
        return f"Letters in {colour_words.strip()}"
    return f"Letter faces {look.face.upper()}, extrusion {look.side.upper()}, background {p.backdrop.upper()}"


def flux2_structured(p: Preset, text: str, colour_words: str = "") -> dict:
    """Skill-format JSON structured prompt (serialised into the prompt string)."""
    look = Look3D(**p.look)
    palette = [look.face.upper(), look.side.upper()] if not colour_words.strip() else []
    subj = {"description": f"{p.lead} 3D title lettering reading '{text}', with {p.detail}",
            "position": "centred, filling the frame",
            "action": "letterforms, spacing and extrusion follow image 1 exactly"}
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
                 fmt: str = "prose") -> tuple[str, str]:
    """(positive, negative) prompt for `preset` on the word `text`, written for `target`.

    FLUX.2 and FLUX 3 take no negative prompt, so negative is empty for them."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {preset}; choose from {PRESET_NAMES}")
    if target not in TARGETS:
        raise ValueError(f"unknown target: {target}; choose from {TARGETS}")
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}; choose from {FORMATS}")
    p = PRESETS[preset]
    colours = colour_words.strip() or p.palette_words
    quoted = text.replace("'", "\u2019").replace('"', "\u201d")
    if target == "flux2_dev":
        if fmt == "json":
            return json.dumps(flux2_structured(p, quoted, colour_words), ensure_ascii=False), ""
        parts = [f"{p.lead} 3D title lettering reading '{quoted}', centred, with {p.detail}.",
                 "Letterforms, spacing and extrusion follow image 1 exactly.",
                 f"{_colours(p, colour_words)}: {p.background}."]
        if p.camera:
            parts.append(f"{p.camera}.")
        parts.append(f"{p.lighting.capitalize()}.")
        return " ".join(parts), ""
    if target == "flux3":  # skill layer order; image 1 = the TitleRig beauty pass
        look = Look3D(**p.look)
        kind = "A bright studio product shot of 3D title lettering" if p.camera else "A bright graphic title card"
        frame = ("Eye-level, straight-on 90mm view with deep focus across every letter" if p.camera
                 else "Straight-on, flat graphic framing with the title filling the centre")
        palette = (f"Colours: {colour_words.strip()}" if colour_words.strip() else
                   f"Letter faces {look.face.upper()}, extrusion walls {look.side.upper()}, "
                   f"background {p.backdrop.upper()}")
        pos = (f'{kind}. The title reads "{quoted}" in bold block capitals, centred, and keeps the exact '
               f"letterforms, spacing, extrusion depth and camera angle of image 1. Every letter is rebuilt as "
               f"{p.material}. {p.background.capitalize()} sits behind the title. {p.lighting.capitalize()}. "
               f"{frame}. {palette}, {p.palette_words}.")
        return pos, ""
    pos = (f'Bold 3D title lettering that reads "{quoted}", centred in frame, made of {p.material}. '  # ltx2_video
           f"The letters keep the exact shapes and motion of the control video. {p.lighting.capitalize()}. "
           f"{p.background.capitalize()}, {p.motion}. Colours: {colours}. Smooth, high-detail, ad-ready.")
    return pos, NEGATIVE + (f", {p.negative}" if p.negative else "")


def suggested_look(preset: str) -> tuple[Look3D, Shadow]:
    """Rig Look3D + Shadow that preview the preset (and give the AI a matching base)."""
    p = PRESETS[preset]
    return Look3D(**p.look), Shadow(**p.shadow)
