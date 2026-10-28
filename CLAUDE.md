# TitleRig — working rules

Contest deadline: **Oct 30, 2026, 9am PT** (Comfy "Open Source Higgsfield"). Every milestone must leave the repo shippable.
Full PRD: https://claude.ai/artifact/2qzTkJzmj6nwPUjcdNAad4 (summary in docs/PRD.md).
**Read docs/STATUS.md first**: what's done, verified vs not, known rough edges, environment gotchas.

## Architecture
- `render/` = pure Python (numpy, Pillow, scipy, opencv-python-headless). **No ComfyUI or torch imports.** CPU only.
- `nodes/` = thin ComfyUI wrappers; torch is imported lazily inside them.
- 2.5D approach: per-letter glyph planes, distance-field bevel/emboss, stacked extrusion, key light + gloss + rim,
  perspective via homography. Video = list of frames → ComfyUI IMAGE batch.
- Only OFL fonts in `fonts/` (fetch from github.com/google/fonts `ofl/<name>/`, keep the OFL.txt beside it).

## Workflow for every change
1. Add/extend tests in `tests/` (renderer tests run without ComfyUI).
2. `pytest -q` must pass.
3. Render visual proof: `python examples/contact_sheet.py` (stills) or a GIF for motion; look at it.
4. Commit with a clear message, push, keep the PR description's checklist current.
5. Never call paid generation APIs (Magnific, Recraft, Machgen, FLUX Pro, etc.).

## Backlog (in order — see docs/PRD.md)
- [x] P0a renderer: glyph layout with tracking/kerning/per-letter transforms, bevel, extrusion, lighting, textured shadows, all passes, guides
- [x] P0b: arc layout (port Glyph Bench's bezier + bulge), perspective tilt + vanishing point, flag warp
- [x] P1a Animate: flip X / spin Y / roll Z / pop / drop / slide; whole word or per letter; stagger + order; easing (in-out, back, elastic, bounce); frames → IMAGE batch
- [x] P1b Audio-reactive (hero demo): AUDIO in → onset/beat times + loudness envelope (numpy, no heavy deps); sensitivity, attack, release, band (bass/mids/highs); drives any Animate property
- [x] P1c rig-only example workflow JSON + GIF
- [x] P2: Style Preset node (prompts in docs/PRD.md), Magnet (polarity attract/repel, strength, range, lag, spring, squash/stretch), sphere/cube/ticker wraps, Spell-Lock, preview widget in `web/` (dark default + light theme)
- [x] P2: SVG export from the rig (faces, sides, textured shadow as shapes) — open, no API
- [ ] P3 (optional, separate workflow, API — never in the open-weights entry): Recraft vectorize / vector generation via ComfyUI's Recraft partner nodes
- [x] Install ComfyUI (CPU) in the sandbox, confirm nodes load and the rig-only workflow runs headless
