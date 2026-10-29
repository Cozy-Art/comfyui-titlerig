# Submission checklist (Comfy "Open Source Higgsfield")

**Deadline: Oct 30, 2026, 9:00 am PT.** Aim to submit by **7:00 am PT** so two hours are left for upload problems.

I couldn't reach the contest page (comfy.org) from the build sandbox, so the form fields below are a best guess. Open <https://comfy.org/open-source-higgsfield>, compare it with this list, and fix anything that differs. Each draft answer is ready to paste.

---

## 1. Licence and rights

- [x] `LICENSE`: MIT, © 2026 Jason Cozy.
- [x] Fonts: only SIL OFL fonts are bundled (Anton and Shrikhand), each with its `OFL-*.txt` beside it in `fonts/`.
- [x] Music bed: `examples/assets/titlerig_beat.wav` is synthesised by `examples/audio_demo.py`, with no samples, so there's nothing to clear. If the video uses another track, make sure you have the rights to it.
- [x] Model licences are listed in `workflows/README.md`:
  - LTX-2 Community License (Lightricks)
  - Gemma Terms of Use
  - FLUX.1 [dev] and FLUX.2 [dev] Non-Commercial Licenses (BFL)
  - CLIP-L (MIT) and T5-XXL (Apache-2.0)

  The models are downloaded by the user, never redistributed in the repo.
- [x] **Open weights only:** the entry's workflows use open-weights models only. The paid-API workflows sit apart in `workflows/bonus/`, are marked **API (paid)**, are left out of the Templates menu, and were never run.
- [ ] **Check:** nothing in the video or the README uses Magnific, Recraft, MachGen or FLUX Pro output.

## 2. Repo and README

- [ ] The repo is **public**: <https://github.com/Cozy-Art/comfyui-titlerig>.
- [ ] Every PR is merged to `main`, and `main` installs cleanly. Re-run the fresh-install check in §4.
- [x] The README has the hero GIF, the pitch ("AI can't spell. So we gave it a rig."), the node list, install steps (Desktop, portable, manual), the workflows table (open vs API), demos, and credits for the models and super-skills.
- [ ] **Replace the hero GIF** with one that includes a real LTX-2 frame, once tonight's result exists. Put it in `docs/media/` and update the first image in the README.
- [ ] Add the **video link** at the top of the README, under the pitch.
- [ ] Add one real **LTX result** and one **FLUX still** to `docs/media/`, and show them in the README's Workflows section.
- [ ] Bump `version` in `pyproject.toml` to `1.0.0`, then tag a release:
  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```
  On GitHub, create a release from the tag and attach the demo MP4.

## 3. Setup detail (for judges who run it)

- [x] Install steps are in the README, and a fresh install was tested: ComfyUI 0.43.0 (latest `main` on Oct 28), CPU, README steps only. All 13 nodes loaded, all 7 templates opened from the Templates menu, and the three model-free workflows ran.
- [x] Every model file, Hugging Face link, target folder and licence is in `workflows/README.md`. Runpod gets a one-paste setup (`scripts/runpod_setup.sh`), and `docs/BUILD_NIGHT.md` covers Comfy Cloud.
- [x] Hardware notes: LTX-2 19B needs 48 GB+ for 1280×720 (H100/A100 80 GB recommended), FLUX [dev] fp8 needs 16–24 GB, and the rig itself runs on CPU.
- [ ] Record the GPU and host actually used tonight (Comfy Cloud or Runpod, card) in `workflows/README.md` → Hardware, with the real run times.

## 4. Final checks (run on the morning of the 30th)

```bash
git pull
python -m pytest -q                          # all pass
python workflows/build_workflows.py          # API graphs current
python workflows/validate.py                 # needs a running ComfyUI: every workflow OK
python workflows/make_setup.py && git diff --exit-code scripts/  # setup script current
```

Then do the fresh-install check:
1. Clone ComfyUI fresh and follow the README's **Manual install**.
2. Start ComfyUI and open **Templates → comfyui-titlerig**.
3. Run `titlerig_rig_only`.

## 5. Video

- [ ] Fill `docs/demo/slots/` and run `python examples/build_demo.py`. The output is `examples/out/demo/titlerig_demo.mp4` (1280×720, 24 fps, 75 s).
- [ ] Watch it once with sound:
  - Every lower third is readable and names the tools and models.
  - No placeholder card is left, unless you decide one is fine.
- [ ] Upload it as YouTube **unlisted** (or the platform the form asks for). Paste the link into the README and the form.
- [ ] Check the form's length and format rules. If it caps below 75 s, trim in `TIMELINE` in `examples/build_demo.py`: the presets section has 12 s to give.

## 6. The form (draft answers; confirm the fields on the contest page)

**Project name:** TitleRig

**One-liner (≤ 140 characters):**
> AI can't spell. So we gave it a rig: exact, animated 3D titles in ComfyUI that drive LTX-2 and FLUX with depth.

**Short description (≈ 280 characters):**
> TitleRig is an open-source ComfyUI node pack that renders exact, animated 3D title text and outputs every pass: depth, edges, alpha, normals, letter IDs. Feed them to LTX-2 or FLUX and the AI paints the material while the rig keeps every letter spelled right. MIT.

**Long description:**
> Image and video models can't spell. TitleRig fixes that by building the title first: 13 ComfyUI nodes for text, a 3D look (bevel, extrusion, lighting, textured shadows) and a layout (arcs, perspective, flags, ticker, sphere and cube wraps). Titles animate per letter with flips, spins, pops and easings, react to audio (kicks and hats drive any property), and can be pushed around by a magnet. Each frame is rendered on CPU into passes: depth, edges, alpha, normals and letter IDs.
>
> The hero workflow feeds the rig's depth to **LTX-2 with the Depth Control IC-LoRA**. LTX paints chrome, fur or glass while the letters stay locked to the rig, and **Spell-Lock** snaps every frame back to the rig's silhouette. **FLUX.1 Depth [dev]** makes stills with a transparent cut-out.
>
> **Style Presets** (Chrome Slam, Ben-Day Pop, Holo Foil and 12 more) write model-specific prompts and set a matching look. Also included: **Cutout** (video inside the letters), **SVG export**, and a live preview widget on the canvas.
>
> Everything is open source (MIT) and runs on open-weights models.

**Categories:** confirm which are entered automatically.
- Best Overall
- Most Innovative (a novel custom node pack)
- **Open Weights Only**
- **LTX VFX bonus**

Before choosing, ask the Comfy team the question in BUILD_NIGHT.md §d: can one entry win a main prize and a bonus prize?

**Models used (open weights):**
- LTX-2 19B dev (fp8), with the LTX-2 Depth Control IC-LoRA, distilled LoRA and spatial upscaler x2 (Lightricks)
- Gemma 3 12B text encoder (Google)
- FLUX.1 [dev] with the FLUX.1 Depth [dev] LoRA, CLIP-L, T5-XXL and the FLUX VAE (Black Forest Labs)
- FLUX.2 [dev], if used

**Tools used:**
- ComfyUI and its frontend
- TitleRig (this repo)
- the GPU host: Comfy Cloud or Runpod (say which)
- ffmpeg for editing
- the super-skills prompt guides (Jason Cozy)
- Anton and Shrikhand fonts (OFL)
- Claude Code, used to build the node pack

**Links:**
- Repo: <https://github.com/Cozy-Art/comfyui-titlerig>
- Video: *(paste)*
- Workflows: `example_workflows/titlerig_ltx2_animated.json` (hero), `example_workflows/titlerig_flux_still.json`

**Team or contact:** Jason Cozy *(add the email and handles the form asks for)*

**Thumbnail or screenshot:** use `docs/media/hero.gif` frame, a real LTX frame, or `example_workflows/titlerig_ltx2_animated.jpg`.

## 7. After submitting

- [ ] Save a copy of the submitted answers in this file (`docs/SUBMIT.md`) and commit it.
- [ ] Post the video. Credit Comfy, Lightricks (LTX-2) and BFL (FLUX).
- [ ] Optional: publish to the ComfyUI registry. `pyproject.toml` already has the `[tool.comfy]` block. See the registry docs for `comfy node publish`.
