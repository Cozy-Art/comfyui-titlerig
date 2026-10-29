# TitleRig demo: 75-second script and shot list

**Build it with:**

```bash
python examples/build_demo.py
```

It writes `examples/out/demo/titlerig_demo.mp4`. Fill `docs/demo/slots/` with build-night results first (see `slots/README.md`).

- **Music bed:** `examples/assets/titlerig_beat.wav`, 120 BPM, synthesised for TitleRig and looped. To use your own track, pass `--audio song.mp3`.
- **Cuts:** every cut is snapped to a kick in the bed, and the audio-react shot is driven by the exact bit of music it plays over.
- **Credits:** every shot names its tools and models in a lower-third, as the contest requires. The end card lists them all.
- **Voice-over:** about 150 words at a relaxed pace. Record it over the built video, or use the on-screen text alone; the cut works without VO.

## Script

| Time | Shot | On screen | VO | Source |
| --- | --- | --- | --- | --- |
| 0:00–0:06 | **Hook** | A FLUX title from a plain prompt, with letters mangled or misspelled. Lower third: *FLUX.1 [dev], plain prompt: "3D chrome title that says TITLERIG". No rig.* | "Ask an image model for a 3D title, and this is what you get." | slot `hook_mangled` |
| 0:06–0:08 | **Card** | "AI CAN'T SPELL." (TitleRig, Trailer Title look, letters flip in) | "AI can't spell…" | rendered |
| 0:08–0:12 | **Card** | "SO WE GAVE IT A RIG." (TitleRig, Chrome Slam) | "…so we gave it a rig." | rendered |
| 0:12–0:22 | **The rig** | ComfyUI canvas: Text → Look 3D → Shadow → Layout → Animate → Render, with the live preview widget scrubbing frames. Lower third: *TitleRig: 13 open-source ComfyUI nodes.* | "TitleRig is a ComfyUI node pack. You type the word and pick the look, the shadow and the layout: arcs, wraps, flags. Then you animate it, letter by letter." | slot `comfyui_canvas` |
| 0:22–0:30 | **The passes** | 3×2 grid of beauty, depth, edges, alpha, normals and letter IDs, live. Lower third: *TitleRig Render: beauty, depth, edges, alpha, normals, letter IDs.* | "Every frame comes out as passes: depth, edges, alpha, normals, the exact shape of every letter." | rendered |
| 0:30–0:32 | **Card** | "LTX-2" | "Feed the depth to LTX-2…" | rendered |
| 0:32–0:42 | **LTX result** | The Spell-Locked LTX-2 clip, Chrome Slam, with the track. Lower third: *LTX-2 19B + Depth Control IC-LoRA (Lightricks), guided by the rig's depth, then TitleRig Spell-Lock.* | "…and the AI paints the material while the rig holds every letter. Spell-Lock snaps each frame back to the rig, so it still spells TITLERIG." | slot `ltx_result` |
| 0:42–0:46 | **FLUX still** | FLUX.1 Depth still with its transparent cutout. Lower third: *FLUX.1 Depth [dev] (Black Forest Labs) on the rig's depth.* | "Stills too, with a transparent cut-out." | slot `flux_still` |
| 0:46–0:48 | **Card** | "PRESETS" (Holo Foil) | "Fifteen presets…" | rendered |
| 0:48–1:00 | **Three presets** | Three 4-second shots: Ben-Day Pop, a second preset and a third preset. Lower third: *Style Preset: <name>.* | "…from Ben-Day pop art to chrome to candy vinyl. Each one writes the prompt for FLUX and LTX-2, and sets a matching look." | slots `preset_1`–`3` (rig-only fallbacks) |
| 1:00–1:02 | **Card** | "AUDIO REACT" (Ben-Day Pop) | "And it listens." | rendered |
| 1:02–1:10 | **Audio react** | POW! pops on the kicks and hops on the hats. Kicks throw the halftone shadow. Lower third: *TitleRig Audio React: kicks pop the letters, hats make them hop, kicks throw the shadow.* | "Kicks punch the letters, hats bounce them, any part of the sound drives any part of the title." | rendered from the bed |
| 1:10–1:15 | **End** | "TITLERIG" / "OPEN SOURCE · MIT". Lower third: *github.com/Cozy-Art/comfyui-titlerig · ComfyUI · LTX-2 · FLUX.1 [dev] · Gemma 3 · fonts: Anton, Shrikhand (OFL).* | "TitleRig. Open source, MIT. AI can't spell. Now it doesn't have to." | rendered |

## Shot list for build night (what to capture)

1. **Hook (slot `hook_mangled`):** a FLUX.1 [dev] or FLUX.2 [dev] still from a plain prompt with **no rig**. Make 4 to 8 seeds and keep the worst-spelled. Use the same word (TITLERIG) so the before and after match.
2. **Canvas recording (slot `comfyui_canvas`):** 10–15 s. Open **Templates → comfyui-titlerig → titlerig_rig_only**. Change the text, switch the pass chips (Beauty → Depth → Edges), then scrub the Render Animation preview. Record at 1280×720 or larger.
3. **LTX hero (slot `ltx_result`):** `titlerig_ltx2_animated`, Chrome Slam, 5 s. Use the **Spell-Locked** output.
4. **FLUX still (slot `flux_still`):** `titlerig_flux_still`, Chrome Slam. The locked PNG, or the cutout on a brand colour.
5. **Presets (slots `preset_1`–`3`):** the same LTX or FLUX workflow with Style Preset set to Ben-Day Pop, Holo Foil and Candy Inflatable (or Fuzzy Grass). If GPU time runs short, the rig-only fallbacks stand in.
6. **Optional B-roll:** the Templates menu with thumbnails, and the Cutout workflow.

## Tools and models named (contest rule: name every tool used)

- **ComfyUI** (core nodes, LTX-2 nodes, templates) and the **ComfyUI frontend**
- **TitleRig** (this repo, MIT): Text, Look 3D, Shadow, Layout, Render, Animate, Audio React, Render Animation, Style Preset, Magnet, SVG Export, Spell-Lock, Cutout
- **LTX-2 19B dev fp8**, **LTX-2 Depth Control IC-LoRA**, the distilled LoRA, the x2 spatial upscaler (Lightricks, LTX-2 Community License)
- **Gemma 3 12B** text encoder (Google, Gemma Terms of Use)
- **FLUX.1 [dev]** with the **FLUX.1 Depth [dev] LoRA**, CLIP-L, T5-XXL and the FLUX VAE (Black Forest Labs, FLUX.1 [dev] Non-Commercial License). Also **FLUX.2 [dev]** if used.
- Prompting: the **super-skills** prompt guides by Jason Cozy (flux-2-prompts, ltx-2-3-prompts)
- **Fonts:** Anton (Vernon Adams) and Shrikhand (Jonny Pinhorn), SIL Open Font License
- **Editing:** ffmpeg (via `examples/build_demo.py`). Also name the GPU host: Comfy Cloud or Runpod.
- **Paid APIs: none** in the entry. The FLUX 3 and Recraft bonus workflows are not used in the video.
