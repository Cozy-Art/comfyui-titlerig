# FLUX 3 bonus workflow (API, kept separate from the open-weights entry)

FLUX 3 Image (BFL `/v1/flux-3-image`) is closed/API-only: no `seed`, `negative_prompt`, `guidance`, `steps`,
`width`/`height` — unknown fields return HTTP 422. It edits/restyles/composites from up to 10 reference images,
and continuity lives in the images, not seeds. That makes TitleRig's beauty pass the perfect **image 1**.

## Pattern (from Jason's flux-3-image-prompts skill)
Describe the finished image in sentences, most important constraint first, say what IS there (never "no X"),
quote exact text with placement.

```
A glossy studio product shot of 3D title lettering. Keep the exact letterforms, spacing, extrusion
depth and camera angle from image 1, and rebuild the letters as [MATERIAL]. The title reads "[TEXT]".
[LIGHTING]. [BACKGROUND]. Palette [HEX, HEX].
```
Settings: `images: [titlerig beauty]` · `aspect_ratio: "auto"` (follows image 1) · `resolution: 2k` · `grounding: false`

## Preset material lines
| Preset | [MATERIAL] |
| --- | --- |
| Fuzzy Grass | dense fuzzy blue grass fibres covering every face and bevel, fine macro detail |
| Chrome Slam | mirror-polished chrome with crisp studio reflections along each bevel |
| Liquid Glass | clear refractive glass with soft caustics landing on the floor below |
| Candy Inflatable | glossy pastel inflatable vinyl, puffed seams, bright specular highlights |
| Holo Foil | holographic foil with a rainbow sheen that shifts across each letter |

Iterate at `1k`, download the approved draft (URLs expire ~1h), then finish at `2k` with the draft as image 1.
Never call this from tests or CI — paid API.
