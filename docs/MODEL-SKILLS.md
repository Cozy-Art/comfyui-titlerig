# Prompting skills used with TitleRig

TitleRig's example workflows are prompted with Jason Cozy's open-source (MIT) skills from
[Cozy-Art/super-skills](https://github.com/Cozy-Art/super-skills). Load the matching skill before writing
prompts for that model — don't guess syntax from older versions.

| Workflow | Model | Skill | Open weights? |
| --- | --- | --- | --- |
| Main still (open entry) | FLUX.2-dev / FLUX.1 Depth [dev] | [`skills/image/flux-v2`](https://github.com/Cozy-Art/super-skills/tree/main/skills/image/flux-v2) | yes |
| FLUX 3 bonus | FLUX 3 Image (`/v1/flux-3-image`) | [`skills/image/flux-v3`](https://github.com/Cozy-Art/super-skills/tree/main/skills/image/flux-v3) — see `FLUX3.md` | no (API) |
| FLUX 3 video (optional) | FLUX 3 Video | [`skills/video/flux-v3-video`](https://github.com/Cozy-Art/super-skills/tree/main/skills/video/flux-v3-video) | no (API) |
| Vector (optional) | Recraft V4 Vector / Pro Vector, Recraft vectorize | [`skills/image/recraft-v4`](https://github.com/Cozy-Art/super-skills/tree/main/skills/image/recraft-v4) | no (API) |

**Applied in the TitleRig Style Preset node (`render/presets.py`):**
- `flux2_dev` follows **flux-2-prompts v1.0.0** (`skills/image/flux-v2`); its schema is vendored in
  `docs/skills/flux-v2/schema.json` and the node's `settings` output is tested against it.
- `flux3` follows **flux-3-image-prompts** (`skills/image/flux-v3`); rules in `docs/skills/flux-v3/README.md`.
- `ltx2_video` is provisional until an LTX-2 skill is added here.

Anything marked "no (API)" lives in its own workflow, is named in the demo video, and never appears in the
open-weights entry.

## Recraft vector — two routes

1. **Vectorize a TitleRig still** (cheapest, keeps the exact letterforms): send the rig beauty pass — or an
   AI-painted still — to Recraft's vectorize tool (~$0.01/image) → editable SVG.
2. **Generate vector from the rig** (`recraftv4_vector` / `recraftv4_pro_vector`, image-to-image with the
   rig render as `image_url` and a low `strength`): restyles the title as clean flat vector art.

Recraft V4 rules (from the skill): always set `model` explicitly; no `negative_prompt` (exclusions are a
short plain clause); size as a ratio only (`"16:9"`) on vector models; vector prompts use geometry, not
raster words.

```
Flat vector title lockup of the word "[TEXT]" in bold extruded block letters. Keep the letterforms,
spacing and three-quarter extrusion from the source image. Strict three-colour system: [COLOR A],
[COLOR B] and [COLOR C] on a transparent ground. Uniform edge geometry, crisp corners, the extrusion
built from flat stepped facets, a striped drop shadow made of parallel bands. Remains legible at
48 pixels wide. No extra text or logos.
```
Settings: `model: recraftv4_vector · size: 16:9 · controls.colors: [A, B, C]` (+ `image_url`, `strength: 0.3` for image-to-image)

Never call these from tests or CI — paid APIs.
