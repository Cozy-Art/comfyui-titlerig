# TitleRig

**AI can't spell. So we gave it a rig.**

TitleRig is an open-source ComfyUI node pack that renders exact, animated 3D title text — extrusion, bevel, lighting and *textured shadows* (halftone, stripes, checker, noise, pixel, gradient) — and outputs every layer as its own connector. Feed the depth and edge passes to Flux or LTX-2 and the AI paints the material while the letters stay spelled right.

> Built for Comfy's *Open Source Higgsfield* challenge (Oct 2026).

## Nodes

| Node | What it does |
| --- | --- |
| **TitleRig Text** | text, font, size, tracking, per-pair kerning, per-letter overrides |
| **TitleRig Look 3D** | face colour/gradient, extrusion, bevel, key light, gloss, rim |
| **TitleRig Shadow** | angle, length, softness, textures: solid · halftone · stripes · checker · noise · pixel · gradient |
| **TitleRig Layout** | flat, **arc** (bend or custom bezier), **ticker** / **sphere** / **cube** wraps, **bulge**, perspective **tilt X/Y** + fov, **vanishing-point** extrusion, **flag** wave |
| **TitleRig Render** | one frame, every pass below; `guide_lines` = all · none · e.g. `baseline,mid` |
| **TitleRig Animate** | one track; chain several. Effects below, per letter or whole word, stagger + order, easing |
| **TitleRig Audio React** | AUDIO → beats / loudness / spectrum curve for Animate's `drive` input |
| **TitleRig Render Animation** | frames → IMAGE batches (beauty, alpha, depth, edges, letter_ids) + frame_count + fps |
| **TitleRig Style Preset** | 13 bright presets → prompts for FLUX.2-dev / FLUX 3 / LTX-2.3 (per the super-skills), a matching Look + Shadow, and settings JSON |
| **TitleRig Magnet** | a moving magnet (or second word) that attracts / repels letters: strength, range, lag, spring, squash & stretch, audio drive |
| **TitleRig SVG Export** | the rig traced to a layered SVG: shadow shapes, extrusion tones, one path per letter |
| **TitleRig Spell-Lock** | snaps AI frames back to the rig's exact silhouette (warp-snap + spill / hole repair, no OCR) and reports drift |

### Animate

- **Effects:** flip X · spin Y · roll Z · pop · drop · slide · squash · shake · extrude · light · tilt X/Y · bend · flag wave · shadow length / angle / opacity / softness
- **Easings:** linear · in · out · in_out · sine · expo · back · elastic · bounce · spring · steps
- **Orders:** forward · reverse · center_out · edges_in · random. **Directions:** in · out · loop
- **letters:** `all`, `0,2,5-7` (character indices) or `word:2`. With target `word`, a selection moves as one rigid group.
- **influence:** a 0–4 dial on how hard the track pushes.
- **Free transform:** `skew_x`, `skew_y`, `taper_x` (keystone; negative flares), `taper_y`, and `corner_pin` (`corners_json`: 4 corner offsets). Set it per letter in `letters_json`, per word in `word_json`, or on any group, and animate it like any other effect, sound included.

### Audio React (the hero)

AUDIO in (numpy only, no extra deps) → onsets by band spectral flux + peak-relative loudness → attack/release → one value per video frame.

- **band:** bass · mids · highs · full. Route each word or letter group to its own band.
- **mode:** beats · envelope · beats+envelope · **spectrum** (the letters become an EQ: lows left, highs right)
- **sensitivity · attack · release · start · max_seconds**
- In Animate, **response = trigger** makes every hit replay the track's easing (a kick lands, then bounces). **retrigger** = restart · finish (keeps bounces tidy on busy music) · layer.

## Outputs

| Connector | Type | Use |
| --- | --- | --- |
| beauty | IMAGE | finished rig render |
| alpha | MASK | title silhouette for compositing |
| depth | IMAGE | Flux depth models · LTX-2 Depth IC-LoRA |
| edges | IMAGE | Canny control (Flux · LTX-2 Canny IC-LoRA) |
| normals | IMAGE | relighting / material nodes |
| face · sides | MASK | style front faces and extrusion walls separately |
| highlight | MASK | glints, bloom, light sweeps |
| shadow | MASK | the textured shadow alone |
| letter_ids | IMAGE | one flat colour per letter |
| guides | IMAGE | dashed baseline / x-height / cap / ascender / descender |

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Cozy-Art/comfyui-titlerig
pip install -r comfyui-titlerig/requirements.txt
```
Restart ComfyUI; the nodes appear under **TitleRig**. The renderer is CPU-only — no GPU needed for the rig itself.

## Try it without ComfyUI

```bash
pip install -r requirements.txt pytest
python examples/contact_sheet.py   # stills + layout sheet → examples/out/*.png
python examples/animate_demo.py    # effect grid → examples/out/animate_grid.gif
python examples/audio_demo.py      # audio-reactive clips (+ MP4 with sound if ffmpeg is installed)
python examples/free_transform_demo.py  # skew / taper / corner pin sheet + sound-driven clip
python -m pytest -q
```

## Models used in the example workflows

- **LTX-2** + Depth / Canny IC-LoRAs (Lightricks, open weights) — animated titles
- **FLUX** (Black Forest Labs) depth-conditioned — stills

Rig-only workflows (no models, CPU): `workflows/titlerig_rig_only.json` and `workflows/titlerig_audio_react.json`. See `workflows/README.md`.

![TitleRig rig-only workflow output](docs/media/rig_only_workflow.gif)

Prompts are written with the open-source [super-skills](https://github.com/Cozy-Art/super-skills) prompting skills (FLUX.2, FLUX 3, Recraft V4) — see `docs/MODEL-SKILLS.md`. Optional API workflows (FLUX 3, Recraft vector) are kept separate from the open-weights workflows.

## Fonts

Only SIL Open Font License fonts are bundled (`fonts/`, licences alongside). Bring your own `.ttf`/`.otf` by path.

## License

MIT © 2026 Jason Cozy
