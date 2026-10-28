# TitleRig

**AI can't spell. So we gave it a rig.**

TitleRig is an open-source ComfyUI node pack that renders exact, animated 3D title text — extrusion, bevel, lighting and *textured shadows* (halftone, stripes, checker, noise, pixel, gradient) — and outputs every layer as its own connector. Feed the depth and edge passes to Flux or LTX-2 and the AI paints the material while the letters stay spelled right.

> Built for Comfy's *Open Source Higgsfield* challenge (Oct 2026).

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
python examples/contact_sheet.py   # writes examples/out/*.png
pytest
```

## Models used in the example workflows

- **LTX-2** + Depth / Canny IC-LoRAs (Lightricks, open weights) — animated titles
- **FLUX** (Black Forest Labs) depth-conditioned — stills

Download links and exact files: see `workflows/README.md` (coming with the workflows).

Prompts are written with the open-source [super-skills](https://github.com/Cozy-Art/super-skills) prompting skills (FLUX.2, FLUX 3, Recraft V4) — see `docs/MODEL-SKILLS.md`. Optional API workflows (FLUX 3, Recraft vector) are kept separate from the open-weights workflows.

## Fonts

Only SIL Open Font License fonts are bundled (`fonts/`, licences alongside). Bring your own `.ttf`/`.otf` by path.

## License

MIT © 2026 Jason Cozy
