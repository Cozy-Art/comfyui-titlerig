# Build Night runbook (LA, Oct 28)

Goal for the night: one real **LTX-2** hero clip and one **FLUX** still made from the TitleRig rig, recorded for the
demo video. Everything below is open weights. **Never run anything in `workflows/bonus/`** (paid APIs).

Node titles in quotes ("Kicks (bass)", "Rig depth guide", ...) are the titles shown on the canvas in the shipped
workflows.

---

## 0. Before you leave (Mac, 15 min)

1. Update the pack. You get 13 nodes and 7 templates.
   ```bash
   cd ~/Documents/ComfyUI/custom_nodes/comfyui-titlerig && git pull
   ```
2. Check you have ffmpeg (`ffmpeg -version`). If not, run `brew install ffmpeg`. The two Mac scripts below need it.
3. Make the Comfy Cloud fallback files now, while you're on good Wi-Fi. This takes about 1 minute on an M1 and needs no ComfyUI:
   ```bash
   cd ~/Documents/ComfyUI/custom_nodes/comfyui-titlerig
   ../../.venv/bin/python examples/export_for_cloud.py
   ```
   It writes `examples/out/cloud/`:

   | File | What it's for |
   | --- | --- |
   | `depth.mp4` | The rig depth with your track. This is what you upload. |
   | `edges.mp4` | The rig edges, for the Canny fallback. |
   | `beauty.mp4` | The rig render, for reference. |
   | `rig.npz` | The alpha and shadow masks per frame, for Spell-Lock afterwards. |
   | `prompt.txt` and `negative.txt` | The LTX prompts. |
   | `still_depth.png`, `still_alpha.png`, `still_shadow.png` and `flux_prompt.txt` | The FLUX still inputs and prompt. |
   | `track.wav` | The audio the motion was cut to. |

   Options: `--text "YOUR WORD" --preset "Ben-Day Pop" --audio song.mp3 --seconds 5`. Use 5 s, which is 121 frames, the LTX template's length.
4. Hugging Face, for the Runpod path:
   - Create a **read token** at <https://huggingface.co/settings/tokens>.
   - While logged in, open these pages and accept any licence prompt: <https://huggingface.co/Lightricks/LTX-2>, <https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Depth-Control>, <https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Canny-Control> and <https://huggingface.co/black-forest-labs/FLUX.2-small-decoder>. The `Comfy-Org/…` and `comfyanonymous/…` mirrors are not gated.
5. Put credit on Runpod, and sign in to Comfy Cloud, so the account is ready.
6. Charge the laptop. Have the screen recorder ready: QuickTime, File → New Screen Recording.

---

## a. Comfy Cloud path

### a1. Can TitleRig be installed?

1. Open Comfy Cloud and start a workflow.
2. Look for **Manager → Custom Nodes Manager → Install via Git URL**, or a "Custom nodes" settings page.
   - **If you can install from Git:** paste `https://github.com/Cozy-Art/comfyui-titlerig`, install, then restart or refresh. Open **Templates → Extensions → comfyui-titlerig → titlerig_ltx2_animated** and go to section c.
   - **If it only offers a curated list:** search it for "TitleRig". If it's missing, ask the Comfy team (question 2 in section d). Meanwhile, use the fallback below.

### a2. Fallback: rig on the Mac, LTX on Cloud (core nodes only)

`example_workflows/titlerig_cloud_ltx2.json` is the hero's LTX-2 graph with the rig replaced by **Load Video**. It uses only built-in ComfyUI nodes, so it runs on any ComfyUI, including Cloud.

1. Drag `titlerig_cloud_ltx2.json` from the repo onto the Cloud canvas.
2. **"Rig depth video"** (Load Video): upload `examples/out/cloud/depth.mp4`.
3. **"Prompt (paste prompt.txt)"**: it already holds the Chrome Slam / TITLERIG prompt. If you exported another word or preset, paste `prompt.txt` instead.
4. **Model loaders:** a red loader means Cloud names a model differently. Open Cloud's own template **"LTX-2 Depth to Video"**, copy the names from its loaders into ours, and close it. Ours uses the same files as that template.
5. Run it. The output is `titlerig/ltx2_cloud_*.mp4`, the LTX result with your track. Download it.
6. Back on the Mac, Spell-Lock it:
   ```bash
   ../../.venv/bin/python examples/spell_lock_video.py ~/Downloads/ltx2_cloud_00001_.mp4
   ```
   This writes `…_spell_locked.mp4` with the track and prints the drift before and after.

**FLUX still on Cloud (fallback):**
1. Open Cloud's template **"Flux Depth LoRA"** (or similar).
2. Load `still_depth.png` as its control image.
3. Paste `flux_prompt.txt`.
4. Run it and download the PNG.
5. On the Mac, lock it:
   ```bash
   ../../.venv/bin/python examples/spell_lock_video.py ~/Downloads/flux.png
   ```
   This locks the still against `still_alpha.png`.

---

## b. Runpod path (full TitleRig, everything in one place)

### b1. Pod

| Setting | Value |
| --- | --- |
| GPU | **H100 80 GB** or **A100 80 GB**. L40S or RTX 6000 Ada 48 GB also work for 1280×720. Avoid 24 GB cards for the LTX hero. |
| Template | **Runpod PyTorch 2.x** (official, CUDA 12.x). Any image with Python 3.10+ and a working CUDA torch is fine. |
| Container disk | 50 GB |
| Volume disk | **200 GB** at `/workspace` (all models are about 150 GB; `ltx` alone is much less) |
| Expose HTTP ports | **8188** |

Deploy, then **Connect → Web Terminal** (or the Jupyter terminal).

### b1b. Already running Runpod's official ComfyUI template?

`runpod/comfyui` (for example `runpod/comfyui:1.5.0-comfyuiv0.35.0-cuda12.8`) works as it is:
- **ComfyUI location:** the script finds it at `/workspace/runpod-slim/ComfyUI` and installs TitleRig there. There's no second ComfyUI and no ComfyUI update.
- **Compatibility:** every open-weights workflow was validated against ComfyUI **0.35.0** with frontend 1.51.10, the template's versions. ComfyUI's own validator accepted all four AI workflows.
- **ComfyUI-LTXVideo:** add `SKIP_LTXVIDEO=1`. It isn't needed, and its requirements could change the template's packages.
- **Disk:** if `/workspace` is too small for the models, the script puts them on the container disk and links them into `ComfyUI/models`. The container disk is wiped if the pod is reset.
- **After the script:** restart ComfyUI from **Manager → Restart** in the ComfyUI page. The template starts ComfyUI itself.

### b2. One paste

```bash
export HF_TOKEN=hf_your_token_here
curl -fsSL https://raw.githubusercontent.com/Cozy-Art/comfyui-titlerig/main/scripts/runpod_setup.sh | bash -s -- ltx flux1
```

The script does the following:
1. Clones ComfyUI into `/workspace/ComfyUI`.
2. Clones TitleRig and ComfyUI-LTXVideo into `custom_nodes/`.
3. Runs `pip install` for all three.
4. Copies the beat track into `input/`.
5. Downloads every model into the right folder.
6. Prints the torch and GPU check, plus anything that failed.

Notes:
- **Groups:** `ltx` (the hero, plus the Canny fallback LoRA), `flux1` (FLUX.1 Depth still) and `flux2` (FLUX.2-dev still). Leave the arguments off to get all three.
- **Re-runs:** files already downloaded are skipped.
- **If a download 401s or 403s:** accept that repo's licence on Hugging Face, then run the same command again.
- **ComfyUI-LTXVideo is optional.** TitleRig's graphs use the LTX-2 nodes built into ComfyUI. If its `pip install` fails, the script carries on.

Then start ComfyUI:

```bash
cd /workspace/ComfyUI && python main.py --listen 0.0.0.0 --port 8188
```

Open the pod's **port 8188** link, then go to **Templates → Extensions → comfyui-titlerig**.

### b3. The exact downloads (if you'd rather paste them one by one)

From `/workspace/ComfyUI`, run each line. Each one downloads into `/workspace/hf` and then moves the file into place. If `huggingface-cli` isn't installed, `hf download` takes the same arguments.

```bash
# LTX-2 hero
huggingface-cli download Lightricks/LTX-2 ltx-2-19b-dev-fp8.safetensors --local-dir /workspace/hf && mv /workspace/hf/ltx-2-19b-dev-fp8.safetensors models/checkpoints/
huggingface-cli download Lightricks/LTX-2-19b-IC-LoRA-Depth-Control ltx-2-19b-ic-lora-depth-control.safetensors --local-dir /workspace/hf && mv /workspace/hf/ltx-2-19b-ic-lora-depth-control.safetensors models/loras/
huggingface-cli download Lightricks/LTX-2-19b-IC-LoRA-Canny-Control ltx-2-19b-ic-lora-canny-control.safetensors --local-dir /workspace/hf && mv /workspace/hf/ltx-2-19b-ic-lora-canny-control.safetensors models/loras/
huggingface-cli download Lightricks/LTX-2 ltx-2-19b-distilled-lora-384.safetensors --local-dir /workspace/hf && mv /workspace/hf/ltx-2-19b-distilled-lora-384.safetensors models/loras/
huggingface-cli download Lightricks/LTX-2 ltx-2-spatial-upscaler-x2-1.0.safetensors --local-dir /workspace/hf && mkdir -p models/latent_upscale_models && mv /workspace/hf/ltx-2-spatial-upscaler-x2-1.0.safetensors models/latent_upscale_models/
huggingface-cli download Comfy-Org/ltx-2 split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors --local-dir /workspace/hf && mv /workspace/hf/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors models/text_encoders/
# FLUX.1 Depth [dev] still
huggingface-cli download Comfy-Org/flux1-dev flux1-dev-fp8.safetensors --local-dir /workspace/hf && mv /workspace/hf/flux1-dev-fp8.safetensors models/diffusion_models/
huggingface-cli download Comfy-Org/flux1-dev split_files/loras/flux1-depth-dev-lora.safetensors --local-dir /workspace/hf && mv /workspace/hf/split_files/loras/flux1-depth-dev-lora.safetensors models/loras/
huggingface-cli download comfyanonymous/flux_text_encoders clip_l.safetensors --local-dir /workspace/hf && mv /workspace/hf/clip_l.safetensors models/text_encoders/
huggingface-cli download comfyanonymous/flux_text_encoders t5xxl_fp16.safetensors --local-dir /workspace/hf && mv /workspace/hf/t5xxl_fp16.safetensors models/text_encoders/
huggingface-cli download Comfy-Org/Lumina_Image_2.0_Repackaged split_files/vae/ae.safetensors --local-dir /workspace/hf && mv /workspace/hf/split_files/vae/ae.safetensors models/vae/
# FLUX.2 [dev] still (optional)
huggingface-cli download Comfy-Org/flux2-dev split_files/diffusion_models/flux2_dev_fp8mixed.safetensors --local-dir /workspace/hf && mv /workspace/hf/split_files/diffusion_models/flux2_dev_fp8mixed.safetensors models/diffusion_models/
huggingface-cli download Comfy-Org/flux2-dev split_files/text_encoders/mistral_3_small_flux2_bf16.safetensors --local-dir /workspace/hf && mv /workspace/hf/split_files/text_encoders/mistral_3_small_flux2_bf16.safetensors models/text_encoders/
huggingface-cli download black-forest-labs/FLUX.2-small-decoder full_encoder_small_decoder.safetensors --local-dir /workspace/hf && mv /workspace/hf/full_encoder_small_decoder.safetensors models/vae/
```

The licences are listed in `workflows/README.md`. The FLUX [dev] models are non-commercial.

---

## c. First-run checklists

### c1. LTX-2 hero (`titlerig_ltx2_animated`)

**Smoke test first, about 2 s:**
1. Set `max_seconds` to **2** in both **"Kicks (bass)"** and **"Hats (highs)"**. That gives 48 frames, padded to 49.
2. Run it. The rig half takes about 30 s on the pod's CPU, then LTX starts.
3. Check the four outputs in `output/titlerig/`:
   - `control_depth`: the rig, moving to the beat. If it's empty or black, the problem is in TitleRig, not LTX.
   - `ltx2_raw`: what LTX made.
   - `ltx2_spell_locked`: the same, snapped to the rig's letters, with your track.
   - `control_edges`: for the Canny fallback.
4. Open the Spell-Lock node's **drift** output (or the `report` JSON):
   - **Under 0.05:** letters match. Ship it.
   - **0.05 to 0.15:** Spell-Lock fixes it. Compare raw and locked.
   - **Over 0.15:** the letters are wrong. Use the ladder below.

**Then the full 5 s:** set `max_seconds` back to **5** (121 frames).

**Settings to try first (as shipped):**

| Setting | Value |
| --- | --- |
| Depth Control IC-LoRA | strength **1.0** |
| "Rig depth guide" (LTXVAddGuide) | strength **1.0** |
| Stage 1 | 20 steps, CFG **3**, seed 42, half res (640×360) |
| Stage 2 | distilled, x2 upscale, 3 steps, CFG 1 |
| Preset | **Chrome Slam** (`ltx23_video` prompt) |
| First frame | bypassed |

**If LTX drifts off the letters, change one thing at a time, in this order:**
1. **Calm the motion.**
   - Lower the `amount` on "Letters pop on kicks" (-35 → -20) and "Letters hop on hats" (28 → 15).
   - Fast jumps between frames are the most common cause of drift.
2. **Lock the look on frame 0.**
   - Make a FLUX still (c2) and feed it to the first **LTXVImgToVideoInplace** "image" input.
   - Set `bypass` to **false** on both LTXVImgToVideoInplace nodes.
   - LTX then starts from correctly spelled letters.
3. **Lighter stage 2.**
   - Set the ManualSigmas in "Stage 2" to `0.725, 0.421875, 0.0` (drop the first value).
   - Stage 2 then refines rather than repaints.
4. **Canny instead of Depth.**
   - Change the "Depth Control IC-LoRA" loader to `ltx-2-19b-ic-lora-canny-control.safetensors`.
   - Point the "Depth guide at half res" input at the Render Animation **edges** output.
   - Edges hold letter outlines more tightly than depth does.
5. **Shorter prompt.** If the prompt's scene description wins over the guide, remove the background sentence.
6. **Stronger Spell-Lock.** Raise `tolerance` (2 → 4) for slightly wobbly edges. In `spell_lock_video.py` that's `--tolerance 4 --max-shift 10`.
7. **Try another seed** (42 → 7, 123) before changing anything else.

Keep the IC-LoRA and guide strengths at 1.0. Lowering them lets LTX invent its own letters.

**Spell-Lock caveat:** it reads the AI frame's colours. Dark letter sides on a dark background (or a dark shadow on dark) measure as drift even when the frame is fine. Judge by eye on dark presets.

### c2. FLUX.1 Depth still (`titlerig_flux_still`)

1. Run it as shipped:
   - FLUX.1 [dev] fp8 plus the **Depth LoRA at 1.0**
   - FluxGuidance **10**
   - KSampler **20 steps**, CFG 1, euler / normal, seed 42
   - 1344×768
2. Check the four PNGs in `output/titlerig/`: `flux1_depth_raw`, `_spell_locked`, `_cutout` (the transparent title) and `_control_depth`.
3. If it's too literal or plastic, lower guidance (10 → 6). If the letters soften, raise steps (20 → 28) or guidance (10 → 12).
4. If the material is wrong, try another preset in **Style Preset**: Chrome Slam, Ben-Day Pop or Holo Foil.
5. Save the best one as the LTX first frame for c1 step 2 of the drift ladder.

**FLUX.2 dev** (`titlerig_flux2_still`) uses the rig beauty as reference image 1, with Flux2Scheduler and guidance 4. Try it if FLUX.1's look is too plain.

### c3. Record while it runs

- Screen-record the canvas with the preview widget scrubbing.
- Record the Templates menu.
- Record one full run.
- Save every output. `examples/build_demo.py` (see `docs/demo/`) slots them into the video.

---

## d. Questions for the Comfy team

From the PRD's open questions, plus tonight's practical ones:

1. Can one entry win a main prize **and** a bonus prize (for example Open Weights Only **and** the LTX VFX bonus)?
2. **Does Comfy Cloud allow installing a custom node pack from GitHub?** If not, can TitleRig be added to the allowed list?
3. Can an entry include a separate **FLUX 3 (API)** workflow for the FLUX bonus and still qualify for **Open Weights Only** with its main workflow? If not, which counts more: the FLUX bonus or Open Weights Only?
4. How many free credits do the first 200 signups get, and is this account in?
5. **Demo video:** length limit, format, and where it's hosted (YouTube, upload)? Our cut is 75 s.
6. Do judges run the workflows? If so, on which ComfyUI version and GPU? We validated against ComfyUI 0.43.0 with frontend 1.57.6.
7. Do the Cloud's LTX-2 models use the same file names as the official "LTX-2 Depth to Video" template?
8. What exactly does the submission form ask for (fields, repo link, workflow JSON upload)? Fill in `docs/SUBMIT.md`.

---

## e. If time is short (priority order)

1. One locked LTX clip of Chrome Slam, 5 s, with the track.
2. One FLUX still and its transparent cutout.
3. A screen recording of the rig and its passes in ComfyUI.

Everything else in the demo is already rendered: the hero clips in `docs/media/`.
