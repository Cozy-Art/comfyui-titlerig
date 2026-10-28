# TitleRig example workflows

Both run on CPU with **no models and no API calls**, using only TitleRig and core ComfyUI nodes.

| Workflow | What it makes |
| --- | --- |
| `titlerig_rig_only.json` | A still (beauty, depth and guides) plus an animated title: letters pop in (back easing, centre out), then roll in (elastic). Saved as animated WEBP, beauty and depth. |
| `titlerig_audio_react.json` | The hero. Load Audio → two Audio React nodes (bass kicks, high hats) → BASS pops on kicks, TREBLE bounces on hats (trigger + bounce, retrigger *finish*), kicks throw the shadow → Create Video with the sound → MP4. |

Drag a `.json` into ComfyUI. For the audio workflow, put `examples/assets/titlerig_beat.wav` into `ComfyUI/input/` (or pick your own track in Load Audio).

The depth and edges outputs are the control passes for FLUX depth/canny and LTX-2 IC-LoRAs. The AI workflows build on these graphs.

## Files

- `api/*.json`: the same graphs in API format, made by `build_workflows.py`
- `run_headless.py`: queues an API workflow on a running server and lists its outputs
  ```bash
  python workflows/run_headless.py workflows/api/titlerig_rig_only.json
  ```
- `to_ui.js`: rebuilds the UI files by loading the API graphs into the real ComfyUI frontend (Node + Playwright)

![rig-only workflow output: beauty above, depth below](../docs/media/rig_only_workflow.gif)

## Verified headless on CPU

Both workflows were run on a CPU-only ComfyUI (no GPU, no models): `run_headless.py` on the API files, and `to_ui.js --verify` on the UI files (each is loaded into the frontend, turned into a prompt and executed).

In a sandbox where `download.pytorch.org` is blocked, the CPU PyTorch build comes from conda-forge:

```bash
micromamba create -p /opt/comfyenv -c conda-forge python=3.13 "pytorch=*=cpu*" torchvision
/opt/comfyenv/bin/python -m pip install -r ComfyUI/requirements.txt   # torch is already satisfied
/opt/comfyenv/bin/python ComfyUI/main.py --cpu
```
