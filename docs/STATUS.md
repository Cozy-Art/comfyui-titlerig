# TitleRig status

Last updated 2026-10-28. Contest deadline **Oct 30, 2026, 9am PT**. Working rules and the backlog live in `CLAUDE.md`;
this file says where things stand and what a fresh session should know before touching anything.

## Done

| Area | What exists | Where |
| --- | --- | --- |
| Renderer (P0a) | glyph layout, tracking / kerning / per-letter transforms, bevel, extrusion, lighting, 7 textured shadows, 11 passes, type guides | `render/core.py` |
| Layout (P0b) | flat, arc (bend or custom bezier) + bulge, tilt X/Y homography, vanishing-point extrusion, flag wave, ticker / sphere / cube wraps | `render/geometry.py` |
| Free transform | skew, taper (keystone / flare), corner pin, stretch, on letters, groups and the whole word | `render/core.py` (`_tf`, `_free`) |
| Animate (P1a) | 24 effects (letters, layout, shadow, look), 11 easings, 5 orders, in / out / loop, letter selection (`word:2`, `0,3-5`), influence, trigger response + retrigger | `render/animate.py` |
| Audio React (P1b) | numpy onsets (band spectral flux), loudness, spectrum mode, attack / release | `render/audio.py` |
| Magnet (P2) | attract / repel, strength, range, lag, spring, squash & stretch, sweep / orbit / fixed, magnet word, audio drive | `render/magnet.py` |
| Style Preset (P2) | 13 PRD presets; prompts for FLUX.2-dev, FLUX 3, LTX-2.3 written to the super-skills; matching Look / Shadow; settings JSON | `render/presets.py`, `docs/skills/` |
| SVG export (P2) | rig traced to layered SVG (shadow cells, extrusion tones, one path per letter) | `render/svg.py` |
| Spell-Lock v1 (P2) | warp-snap + spill / hole repair against the rig alpha, shadow protection, drift score | `render/spell_lock.py` |
| Canvas preview (P2) | live preview widget on Render / Render Animation: pass chips, guides, frame scrubber, dark + light palettes | `web/titlerig_preview.js`, `nodes/preview.py` |
| Workflows (P1c) | rig-only and audio-react example workflows (no models, CPU) | `workflows/` |
| ComfyUI | 12 nodes load in a CPU ComfyUI; both workflows run headless and round-trip through the frontend | see "Environment" |

Nodes (all under **TitleRig**): Text, Look 3D, Shadow, Layout, Render, Animate, Audio React, Render Animation,
Style Preset, Magnet, SVG Export, Spell-Lock.

## Verified vs not

- **Verified:**
  - Pure-Python tests: 241 pass and 3 skip (the skips need torch) under the system Python; all pass under the ComfyUI env.
  - All 12 nodes register in ComfyUI.
  - `workflows/run_headless.py` runs both workflows to success.
  - `workflows/to_ui.js --verify` loads each UI file in the real frontend, builds the prompt and runs it.
  - `tests/e2e/preview_check.js` checks the preview widget: it appears, updates on widget changes, the chips toggle, the scrubber works, and both palettes render.
- **Not verified against real models:**
  - No FLUX / LTX generation has been run. Paid APIs are off-limits, and there are no local weights or GPU here.
  - The Style Preset prompts follow the skills but are untested on the models.
  - Spell-Lock has only seen *simulated* AI damage (painterly filter, elastic wobble, stray stroke, dropped chunk). Try it on one real FLUX / LTX output before relying on it.
- **Not tested:** fonts other than the bundled Anton and Shrikhand; very long text; 4K renders.

## Known issues and rough edges

- **Spell-Lock:**
  - An inpainted stray stroke that touches the shadow can leave a faint streak.
  - Wobble larger than `max_shift` (6 px) is only partly pulled back.
  - It fixes *shape*, not spelling: an entirely wrong letter inside the right silhouette passes.
  - The `edges` input is accepted but unused (drift is measured on silhouettes).
- **Flip X / spin Y:** a letter turning edge-on keeps its extrusion, so it reads as a flat bar for a frame or two.
- **SVG export:** faces carry their gradient, not the raster bevel lighting (Chrome Slam's emboss highlights are lost).
- **Wraps:** front faces only (no back-side letters); cube is a band (no top or bottom face); sphere text is not
  designed for the poles.
- **Magnet:** the magnet word always draws in front of the title, in Anton, with a fixed look (`MAGNET_LOOK`).
- **Audio:**
  - Tuned on the synthesised loop in `examples/assets/titlerig_beat.wav`.
  - On real music, `mids` can pick up hats. Lower `sensitivity` or use `spectrum`.
- **Render Animation:**
  - Outputs only beauty, alpha, depth, edges and letter_ids. All 11 passes × N frames would be several GB at 720p.
  - It doesn't pad to LTX's `8n + 1` frame rule. Style Preset's settings report the snapped count.
- **Speed:** about 0.5 s per 720p frame on CPU (4 threads in Render Animation). The canvas preview "plays" at render speed.
- **Preview:**
  - Audio-driven tracks show their rest pose, because there's no audio until the workflow runs.
  - The widget polls its upstream graph every 400 ms.
- **Arc:** the brief said "port Glyph Bench's bezier + bulge", but Glyph Bench's source was never available, so the arc is a fresh implementation.
- **LTX settings:** per the LTX skill's build notes, the ComfyUI two-stage template sizes and the default local negative are from research and unverified. The settings output says so.

## For a fresh session

- **Run tests with `python -m pytest -q`.** The bare `pytest` on PATH may be a uv tool without numpy.
- **Visual proof:** `python examples/contact_sheet.py`, `preset_sheet.py`, `animate_demo.py`, `audio_demo.py`,
  `magnet_demo.py`, `wrap_demo.py`, `free_transform_demo.py`, `svg_demo.py`, `spell_lock_demo.py`. Output goes to
  `examples/out/` (gitignored). Committed media lives in `docs/media/`.
- **Changing a node's inputs changes the saved workflows' widget order.** After any `INPUT_TYPES` change:
  1. Update `workflows/build_workflows.py` if needed.
  2. Run `python workflows/build_workflows.py`.
  3. Start ComfyUI, then run `node workflows/to_ui.js <url> --verify`.
- **ComfyUI on CPU in the cloud sandbox:**
  - `download.pytorch.org` is blocked, and PyPI's Linux torch needs about 3 GB of CUDA libraries.
  - Use conda-forge instead (steps in `workflows/README.md`): `micromamba create -p /opt/comfyenv -c conda-forge python=3.13 "pytorch=*=cpu*" torchvision ...`
  - Then `pip install` the rest of `ComfyUI/requirements.txt`.
  - Link this repo into `ComfyUI/custom_nodes/`, copy `examples/assets/titlerig_beat.wav` into `ComfyUI/input/`, and run `main.py --cpu`.
  - The sandbox resets between sessions, so expect to redo this.
- **Prompting skills:** the user supplies the super-skills prompting skills (`add_repo` for `Cozy-Art/super-skills` was refused by the session's permission check). Versions applied:
  - flux-2-prompts v1.0.0 (schema vendored in `docs/skills/flux-v2/`)
  - flux-3-image-prompts
  - ltx-2-3-prompts v1.0 (2026-10-18)

  Ask for the current version before changing prompts. The user cares that prompts match the right model version.
- **Style direction from the user:** bright, ad-ready, with variety. Not every preset is embossed or extruded or has a shadow. Easings are loved; keep the bounce tamed on audio (`retrigger`).
- **Never** call paid generation APIs (Magnific, Recraft, MachGen, FLUX Pro, etc.), even though their tools may show up in the session.
- **Branch:** `claude/titlerig-p0b-arc-layout-7lyt5h`, restarted from `main` after each merged PR.

## Next

- **Backlog:** only P3 is left. It's optional, separate and API-only: Recraft vectorize via ComfyUI's partner nodes, never in the open-weights entry.
- **The contest entry still needs the PRD's AI workflows**, which aren't in the CLAUDE.md backlog yet:
  - (1) FLUX still: rig depth / canny → composite with alpha → PNG.
  - (2) the animated hero: LTX-2.3 + depth IC-LoRA → Spell-Lock → MP4.

  Both need model weights, which this sandbox can't run, so they can be authored and validated structurally but not executed here.
- **Demo video / README polish** for submission.
