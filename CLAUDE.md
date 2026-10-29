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
- [ ] Build night (GPU on Comfy Cloud / Runpod; validate structure here, run the TitleRig half on CPU):
  - [x] `example_workflows/titlerig_ltx2_animated.json`: Animate / Audio React → rig depth (+ edges) frames → LTX-2 + Depth Control IC-LoRA (strength 1.0) + Style Preset prompt → Spell-Lock → video
  - [x] `example_workflows/titlerig_flux_still.json`: rig depth / edges → FLUX.2-dev or FLUX.1 Depth [dev] → composite with alpha → PNG
  - [x] `workflows/README.md`: exact model files, Hugging Face links, target folders, licences, custom node packs (e.g. ComfyUI-LTXVideo)
  - [x] Bonus API workflows, built but never run: `workflows/bonus/titlerig_flux3.json`, `workflows/bonus/titlerig_recraft_vector.json`
  - [x] Demo assets in `docs/media/`: Chrome Slam flip-in, Ben-Day Pop halftone on the beat, ticker on a spinning sphere, Magnet repel-and-snap-back, preview widget dark + light
  - [x] README polish: hero GIF, pitch, node list, install, workflows table (open vs API), credits
  - [x] `docs/BUILD_NIGHT.md` runbook: Comfy Cloud path + Mac fallback (`examples/export_for_cloud.py`, `titlerig_cloud_ltx2`, `examples/spell_lock_video.py`), Runpod one-paste `scripts/runpod_setup.sh`, first-run checklists, questions for Comfy
  - [x] Flip X / spin Y edge-on: letters turn as solid cards (extrusion wall), Chrome Slam re-rendered
  - [x] Demo kit: `docs/demo/SCRIPT.md` (75 s script + shot list) and `examples/build_demo.py` (TitleRig cards, cut to the beat, slots)
  - [x] Fresh-install test as a judge (README steps only); example inputs auto-seeded; README install check
  - [x] `docs/SUBMIT.md` submission checklist (confirm form fields on the contest page)
  - [x] `example_workflows/titlerig_ltx2_duo.json`: fur title flies in + dances to the beat, cloud line streams under it with a beat-driven Magnet; one LTX-2 pass + prompt per layer, Spell-Lock + Cutout; Shaggy Fur and Cloud Puff presets; `examples/duo_preview.py`
  - [x] `example_workflows/titlerig_ltx2_scene.json`: the title rendered into your own image (image = frame 0, rig edges over the image's Canny edges, Canny IC-LoRA, your prompt, plate restored outside letters + shadow)
  - [ ] First real GPU run of both AI workflows (by the user on build night); try Spell-Lock on real output
  - [ ] Fill `docs/demo/slots/`, build the video, upload, submit by Oct 30 7am PT (docs/SUBMIT.md)
- [x] Cutout text node: an `inside` image / video masked to the letters (rig alpha, per frame), an `outside` image / video everywhere else; mask from faces / faces + extrusion / silhouette + shadow; fit cover / contain / stretch; feather; optional outline stroke; optional rig shading on top
- [ ] Nice to have, after build night — P3 (optional, separate workflow, API — never in the open-weights entry): Recraft vectorize / vector generation via ComfyUI's Recraft partner nodes
- [x] Install ComfyUI (CPU) in the sandbox, confirm nodes load and the rig-only workflow runs headless
