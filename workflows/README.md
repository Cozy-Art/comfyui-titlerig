# TitleRig workflows

**Open weights** workflows are the contest entry. They live in `../example_workflows/`, so ComfyUI lists them under **Templates → Extensions → comfyui-titlerig**; you can also drag a `.json` onto the canvas. **API** workflows live in `workflows/bonus/`, out of the Templates menu. They call paid partner services and are never part of the open-weights entry. This folder (`workflows/`) holds the API-format graphs, the builders and the validators.

| Workflow | Kind | Needs | What it makes |
| --- | --- | --- | --- |
| `titlerig_rig_only.json` | open · no models | CPU | still + animated title (beauty and depth), WEBP |
| `titlerig_audio_react.json` | open · no models | CPU | the hero motion on its own: words react to the track, MP4 with sound |
| `titlerig_cutout.json` | open · no models | CPU | Cutout text: an image inside the popping letters, a colour outside (swap either for Load Video), MP4 |
| `titlerig_ltx2_animated.json` | **open weights · hero** | GPU (LTX-2 19B) | audio-reactive rig → depth frames → **LTX-2 + Depth Control IC-LoRA** → Spell-Lock → MP4 with the original track |
| `titlerig_flux_still.json` | open weights | GPU (FLUX.1 [dev]) | rig depth → **FLUX.1 Depth [dev]** → Spell-Lock → raw, locked and transparent title PNGs |
| `titlerig_flux2_still.json` | open weights | GPU (FLUX.2 [dev]) | rig beauty as **reference image 1** → FLUX.2 [dev] → Spell-Lock → same PNG set |
| `bonus/titlerig_flux3.json` | **API (paid)** | BFL partner node | rig beauty as image 1 → FLUX 3 Image (prompt per `docs/FLUX3.md`) → Spell-Lock → PNGs |
| `bonus/titlerig_recraft_vector.json` | **API (paid)** | Recraft partner nodes | Recraft vectorize of the rig + Recraft V4 vector, next to TitleRig's own free SVG export |

Drag a `.json` onto ComfyUI. The audio workflows expect `examples/assets/titlerig_beat.wav` in `ComfyUI/input/`. You can pick your own track in Load Audio.

## What the AI workflows do

**Hero, `titlerig_ltx2_animated.json`:** this reproduces ComfyUI's official *Depth to Video (LTX 2.0)* template, flattened, with the TitleRig rig in place of the Lotus depth estimator.
- **Motion:**
  - Two Audio React nodes split the track into kicks (bass) and hats (highs).
  - Letters pop on kicks, hop on hats (trigger + bounce, retrigger *finish*), and kicks throw the shadow.
- **Prompt:** the Style Preset (Chrome Slam, `ltx23_video`) supplies it, along with the matching Look and Shadow.
- **Rig render:** TitleRig Render Animation renders depth, edges and alpha at 1280×720. `pad_ltx` holds the last frame to LTX's 8n + 1 rule (121 frames = 5 s at 24 fps).
- **Stage 1:** LTX-2 19B dev + **Depth Control IC-LoRA at strength 1.0**, guided by the rig depth at half resolution (`LTXVAddGuide`), 20 steps at CFG 3.
- **Stage 2:** the distilled LoRA plus the x2 spatial upscaler, 3 steps at CFG 1. This is the template's two-stage schedule.
- **Spell-Lock:** snaps every LTX frame back to the rig alpha.
- **Audio:** the video is rebuilt with **your original track**. LTX's generated audio is discarded.
- **Saved outputs:** the Spell-Locked video, the raw LTX video, and the depth and edges control clips. The edges clip is ready for the Canny IC-LoRA (`ltx-2-19b-ic-lora-canny-control`): swap the LoRA and feed edges to `LTXVAddGuide`.
- **Two template changes:**
  - The negative prompt drops the template's word "titles", which would fight the title.
  - The first-frame input is bypassed, so LTX isn't forced to start from the rig's flat colours. Feed a FLUX still there and set `bypass` to false to lock the look.

**Still, `titlerig_flux_still.json`:** this reproduces ComfyUI's *flux_depth_lora_example*.
- FLUX.1 [dev] + BFL's **FLUX.1 Depth [dev]** LoRA, conditioned on the rig depth via `InstructPixToPixConditioning`.
- Settings: guidance 10, 20 steps, CFG 1. The prompt is the Style Preset's `flux1_depth` target.
- Outputs: the raw still, the Spell-Locked still, a **transparent PNG of the title** (rig alpha via `JoinImageWithAlpha`), and the depth control image.

**Still, `titlerig_flux2_still.json`:** this reproduces ComfyUI's *image_flux2*. The rig beauty pass is reference image 1 (`ReferenceLatent`), matching the Style Preset's FLUX.2 prompts ("follow image 1"). The outputs are the same.

## Models

### LTX-2 hero

| File | Folder (`ComfyUI/models/…`) | Licence | Download |
| --- | --- | --- | --- |
| `ltx-2-19b-dev-fp8.safetensors` | `checkpoints/` | LTX-2 Community License | [Hugging Face](https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-dev-fp8.safetensors) |
| `ltx-2-19b-ic-lora-depth-control.safetensors` | `loras/` | LTX-2 Community License | [Hugging Face](https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Depth-Control/resolve/main/ltx-2-19b-ic-lora-depth-control.safetensors) |
| `ltx-2-19b-ic-lora-canny-control.safetensors` (optional: swap in for Depth with the rig edges if LTX drifts) | `loras/` | LTX-2 Community License | [Hugging Face](https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Canny-Control/resolve/main/ltx-2-19b-ic-lora-canny-control.safetensors) |
| `ltx-2-19b-distilled-lora-384.safetensors` | `loras/` | LTX-2 Community License | [Hugging Face](https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-lora-384.safetensors) |
| `ltx-2-spatial-upscaler-x2-1.0.safetensors` | `latent_upscale_models/` | LTX-2 Community License | [Hugging Face](https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors) |
| `gemma_3_12B_it_fp4_mixed.safetensors` | `text_encoders/` | Gemma Terms of Use | [Hugging Face](https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors) |

### FLUX.1 Depth [dev] still

| File | Folder (`ComfyUI/models/…`) | Licence | Download |
| --- | --- | --- | --- |
| `flux1-dev-fp8.safetensors` | `diffusion_models/` | FLUX.1 [dev] Non-Commercial License | [Hugging Face](https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors) |
| `flux1-depth-dev-lora.safetensors` | `loras/` | FLUX.1 [dev] Non-Commercial License | [Hugging Face](https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/split_files/loras/flux1-depth-dev-lora.safetensors) |
| `clip_l.safetensors` | `text_encoders/` | MIT | [Hugging Face](https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors) |
| `t5xxl_fp16.safetensors` | `text_encoders/` | Apache-2.0 | [Hugging Face](https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors) |
| `ae.safetensors` | `vae/` | FLUX.1 [schnell] VAE, Apache-2.0 | [Hugging Face](https://huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors) |

### FLUX.2 [dev] still

| File | Folder (`ComfyUI/models/…`) | Licence | Download |
| --- | --- | --- | --- |
| `flux2_dev_fp8mixed.safetensors` | `diffusion_models/` | FLUX.2 [dev] Non-Commercial License | [Hugging Face](https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/diffusion_models/flux2_dev_fp8mixed.safetensors) |
| `mistral_3_small_flux2_bf16.safetensors` | `text_encoders/` | Apache-2.0 | [Hugging Face](https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/text_encoders/mistral_3_small_flux2_bf16.safetensors) |
| `full_encoder_small_decoder.safetensors` | `vae/` | see model card | [Hugging Face](https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors) |

Folders and URLs are the ones ComfyUI's own templates use (`comfyui-workflow-templates` 0.11.98). Read each model's licence before commercial use. The FLUX [dev] models are non-commercial.

## Custom nodes

- **TitleRig**: this repo, in `ComfyUI/custom_nodes/`.
- **Nothing else.** The LTX-2 nodes (`LTXVAddGuide`, `LTXVImgToVideoInplace`, `LTXVLatentUpsampler`, …) are built into ComfyUI. These workflows were validated against ComfyUI **0.43.0** (frontend 1.57.6). On an older ComfyUI without the LTX-2 nodes, update ComfyUI. Installing **ComfyUI-LTXVideo** (Lightricks) is optional; these graphs don't use it.
- The API bonus workflows use ComfyUI's built-in partner nodes (BFL, Recraft) and need a Comfy account with credits.
- Recraft: the recraft-v4 prompting skill names `recraftv4_vector` at `16:9`; ComfyUI 0.43's partner node offers `recraftv4_1_vector` with pixel sizes, so the workflow uses `recraftv4_1_vector` at `1536x768` (the closest wide size). Check the combo on your ComfyUI before running.

## Hardware

- **LTX-2 19B (fp8):** a 24 GB+ GPU; the template defaults target 48 GB-class cards for 1280×720. Comfy Cloud or Runpod work.
- **System RAM:** about 10 GB for TitleRig's 121 rig frames at 1280×720. The rig renders on CPU at roughly 0.5 s per frame, so the TitleRig half of the hero takes about a minute before LTX starts.
- **FLUX.1 / FLUX.2 [dev] fp8:** 16–24 GB GPUs.

## How these were checked (no GPU here)

- `python workflows/validate.py`: a structural check of every workflow against `/object_info`. It checks node types, input names, link types and combo values. It never queues, so it's safe for the bonus API workflows.
- `python workflows/comfy_validate.py <ComfyUI dir>`: puts empty placeholder files with the exact model names in place, then lets **ComfyUI's own validator** accept each AI workflow. The run is cancelled immediately and the placeholders removed. All three were accepted.
- `workflows/api/dryrun/*.json`: the AI workflows with the model replaced by the rig beauty pass. Everything TitleRig does around the model (rig, audio, Spell-Lock, cut-out, saves) **ran end to end on CPU**. The hero dry run gives 121 frames, with video and audio both 5.04 s.
- `node workflows/to_ui.js <url> --verify`: makes the UI files through the real frontend. Each AI and bonus UI file converts back to its source prompt with every value intact. Only the model-free workflows are ever queued.

**Not yet run:** the models themselves. The first real GPU run happens on build night. Spell-Lock has only been tested on simulated AI damage so far; check its `drift` report on real frames.

## Files

- `build_workflows.py`: builds `api/*.json`, `api/bonus/*.json` and `api/dryrun/*.json`. `MODELS` is the one list of model files.
- `to_ui.js`: rebuilds the UI files (`example_workflows/`, `workflows/bonus/`) from the API graphs through the real ComfyUI frontend.
- `validate.py`, `comfy_validate.py`: the checks above.
- `run_headless.py`: queues an API workflow on a running server and lists its outputs. Never use it on `bonus/`.
