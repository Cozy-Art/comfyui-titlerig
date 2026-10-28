"""Build the example workflows in ComfyUI API format (workflows/api/*.json, workflows/api/bonus/*.json).

The UI-format files (workflows/*.json, drag-and-drop into ComfyUI) are made from these by workflows/to_ui.js, which
loads each one into the real ComfyUI frontend and saves the graph it builds. The AI workflows reproduce the wiring of
ComfyUI's official templates (video_ltx2_depth_to_video, flux_depth_lora_example, image_flux2), flattened, with the
TitleRig rig in place of the depth estimator. Run: python workflows/build_workflows.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

TEXT = {"text": "TITLERIG", "font": "Anton-Regular", "size": 200, "tracking": 4.0,
        "kerning_json": "{}", "letters_json": "{}"}
LOOK = {"face": "#ff8fd8", "face_gradient_to": "#ffd400", "side": "#7c3aed", "extrude": 30, "extrude_angle": 55.0,
        "bevel": 12.0, "bevel_profile": "round", "light_angle": 225.0, "light_height": 0.6, "gloss": 0.9, "rim": 0.4}
SHADOW = {"texture": "halftone", "color": "#0f172a", "angle": 45.0, "length": 36.0, "softness": 0.0,
          "texture_scale": 10.0, "texture_angle": 45.0, "opacity": 1.0}
LAYOUT = {"mode": "arc", "bend": 0.22, "align": 0.5, "bulge": 0.0, "tilt_x": 0.0, "tilt_y": 0.0, "fov": 50.0,
          "vanish": False, "vp_x": 0.5, "vp_y": 1.4, "flag_amp": 0.0, "flag_wavelength": 420.0, "flag_phase": 0.0,
          "flag_shade": 0.5, "curve_json": ""}
ANIM = {"effect": "pop", "target": "letters", "direction": "in", "easing": "back", "duration": 0.6, "stagger": 0.06,
        "order": "center_out", "amount": 0.0, "start": 0.0, "fps": 24.0, "hold": 0.8, "shuffle_seed": 0,
        "letters": "all", "influence": 1.0, "response": "follow", "retrigger": "restart"}


# Every model file the AI workflows load: (filename, ComfyUI models/ folder, download URL, licence).
# URLs and folders are the ones ComfyUI's own templates use.
MODELS = {
    "ltx2_ckpt": ("ltx-2-19b-dev-fp8.safetensors", "checkpoints",
                  "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-dev-fp8.safetensors",
                  "LTX-2 Community License"),
    "ltx2_depth_iclora": ("ltx-2-19b-ic-lora-depth-control.safetensors", "loras",
                          "https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Depth-Control/resolve/main/"
                          "ltx-2-19b-ic-lora-depth-control.safetensors", "LTX-2 Community License"),
    "ltx2_distilled_lora": ("ltx-2-19b-distilled-lora-384.safetensors", "loras",
                            "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-lora-384.safetensors",
                            "LTX-2 Community License"),
    "ltx2_upscaler": ("ltx-2-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models",
                      "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors",
                      "LTX-2 Community License"),
    "gemma3": ("gemma_3_12B_it_fp4_mixed.safetensors", "text_encoders",
               "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/"
               "gemma_3_12B_it_fp4_mixed.safetensors", "Gemma Terms of Use"),
    "flux1_dev": ("flux1-dev-fp8.safetensors", "diffusion_models",
                  "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors",
                  "FLUX.1 [dev] Non-Commercial License"),
    "flux1_depth_lora": ("flux1-depth-dev-lora.safetensors", "loras",
                         "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/split_files/loras/"
                         "flux1-depth-dev-lora.safetensors", "FLUX.1 [dev] Non-Commercial License"),
    "clip_l": ("clip_l.safetensors", "text_encoders",
               "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors", "MIT"),
    "t5xxl": ("t5xxl_fp16.safetensors", "text_encoders",
              "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors",
              "Apache-2.0"),
    "flux_ae": ("ae.safetensors", "vae",
                "https://huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors",
                "FLUX.1 [schnell] VAE, Apache-2.0"),
    "flux2_dev": ("flux2_dev_fp8mixed.safetensors", "diffusion_models",
                  "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/diffusion_models/"
                  "flux2_dev_fp8mixed.safetensors", "FLUX.2 [dev] Non-Commercial License"),
    "mistral_flux2": ("mistral_3_small_flux2_bf16.safetensors", "text_encoders",
                      "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/text_encoders/"
                      "mistral_3_small_flux2_bf16.safetensors", "Apache-2.0"),
    "flux2_vae": ("full_encoder_small_decoder.safetensors", "vae",
                  "https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/"
                  "full_encoder_small_decoder.safetensors", "see model card"),
}


def mfile(key):
    return MODELS[key][0]


def node(cls, inputs, title=None):
    n = {"class_type": cls, "inputs": inputs}
    if title:
        n["_meta"] = {"title": title}
    return n


def rig(width=1280, height=720):
    """Shared Text -> Look -> Shadow -> Layout nodes (ids 1-4)."""
    return {
        "1": node("TitleRigText", dict(TEXT)),
        "2": node("TitleRigLook3D", dict(LOOK)),
        "3": node("TitleRigShadow", dict(SHADOW)),
        "4": node("TitleRigLayout", dict(LAYOUT)),
    }


def rig_only():
    """No AI, no models: a still with every pass + an animated title saved as WEBP (beauty and depth)."""
    g = rig()
    g["5"] = node("TitleRigRender", {"glyphs": ["1", 0], "width": 1280, "height": 720, "look": ["2", 0],
                                     "shadow": ["3", 0], "layout": ["4", 0], "guide_lines": "all"}, "Render still")
    g["6"] = node("SaveImage", {"images": ["5", 0], "filename_prefix": "titlerig/still_beauty"})
    g["7"] = node("SaveImage", {"images": ["5", 2], "filename_prefix": "titlerig/still_depth"})
    g["8"] = node("PreviewImage", {"images": ["5", 10]}, "Guides")
    g["9"] = node("TitleRigAnimate", dict(ANIM), "Pop in (back, centre out)")
    g["10"] = node("TitleRigAnimate", {**ANIM, "effect": "roll_z", "easing": "elastic", "duration": 0.8,
                                       "order": "forward", "amount": 25.0, "anim": ["9", 0]}, "Roll in (elastic)")
    g["11"] = node("TitleRigRenderAnimation", {"glyphs": ["1", 0], "anim": ["10", 0], "width": 960, "height": 540,
                                               "look": ["2", 0], "shadow": ["3", 0], "layout": ["4", 0]})
    g["12"] = node("SaveAnimatedWEBP", {"images": ["11", 0], "filename_prefix": "titlerig/anim_beauty", "fps": 24.0,
                                        "lossless": False, "quality": 85, "method": "default"})
    g["13"] = node("SaveAnimatedWEBP", {"images": ["11", 2], "filename_prefix": "titlerig/anim_depth", "fps": 24.0,
                                        "lossless": False, "quality": 85, "method": "default"})
    return g


def audio_react():
    """Hero, still no AI: kicks pump BASS, hats bounce TREBLE, kicks throw the shadow -> MP4 with the sound."""
    g = rig()
    g["1"]["inputs"].update(text="BASS TREBLE", size=150)
    g["20"] = node("LoadAudio", {"audio": "titlerig_beat.wav"})
    react = {"fps": 24.0, "mode": "beats", "sensitivity": 0.5, "attack": 0.0, "release": 0.18, "start": 0.0,
             "max_seconds": 0.0, "spectrum_bands": 12}
    g["21"] = node("TitleRigAudioReact", {**react, "audio": ["20", 0], "band": "bass"}, "Kicks (bass)")
    g["22"] = node("TitleRigAudioReact", {**react, "audio": ["20", 0], "band": "highs", "sensitivity": 0.15,
                                          "release": 0.12}, "Hats (highs)")
    g["23"] = node("TitleRigAnimate", {**ANIM, "effect": "pop", "amount": -40.0, "stagger": 0.042, "letters": "word:1",
                                       "drive": ["21", 0]}, "BASS pops on kicks")
    g["24"] = node("TitleRigAnimate", {**ANIM, "effect": "drop", "amount": 40.0, "stagger": 0.042, "letters": "word:2",
                                       "response": "trigger", "easing": "bounce", "duration": 0.3,
                                       "retrigger": "finish", "drive": ["22", 0], "anim": ["23", 0]},
                   "TREBLE bounces on hats")
    g["25"] = node("TitleRigAnimate", {**ANIM, "effect": "shadow_length", "amount": 50.0, "drive": ["21", 0],
                                       "anim": ["24", 0]}, "Kicks throw the shadow")
    g["26"] = node("TitleRigRenderAnimation", {"glyphs": ["1", 0], "anim": ["25", 0], "width": 960, "height": 540,
                                               "look": ["2", 0], "shadow": ["3", 0], "layout": ["4", 0]})
    g["27"] = node("CreateVideo", {"images": ["26", 0], "fps": ["26", 6], "audio": ["20", 0]})
    g["28"] = node("SaveVideo", {"video": ["27", 0], "filename_prefix": "titlerig/audio_react", "format": "mp4",
                                 "codec": "h264"})
    g["29"] = node("PreviewImage", {"images": ["21", 1]}, "Kick curve")
    return g


def audio_drive():
    """Shared audio-reactive motion (ids 20-25): kicks pop the letters, hats bounce them, kicks throw the shadow."""
    react = {"fps": 24.0, "mode": "beats", "sensitivity": 0.5, "attack": 0.0, "release": 0.18, "start": 0.0,
             "max_seconds": 5.0, "spectrum_bands": 12}  # 5 s -> 120 frames -> 121 with pad_ltx (LTX-2 template length)
    return {
        "20": node("LoadAudio", {"audio": "titlerig_beat.wav"}),
        "21": node("TitleRigAudioReact", {**react, "audio": ["20", 0], "band": "bass"}, "Kicks (bass)"),
        "22": node("TitleRigAudioReact", {**react, "audio": ["20", 0], "band": "highs", "sensitivity": 0.15,
                                          "release": 0.12}, "Hats (highs)"),
        "23": node("TitleRigAnimate", {**ANIM, "effect": "pop", "amount": -35.0, "stagger": 0.042, "drive": ["21", 0]},
                   "Letters pop on kicks"),
        "24": node("TitleRigAnimate", {**ANIM, "effect": "drop", "amount": 28.0, "stagger": 0.042, "response": "trigger",
                                       "easing": "bounce", "duration": 0.3, "retrigger": "finish", "drive": ["22", 0],
                                       "anim": ["23", 0]}, "Letters hop on hats"),
        "25": node("TitleRigAnimate", {**ANIM, "effect": "shadow_length", "amount": 40.0, "drive": ["21", 0],
                                       "anim": ["24", 0]}, "Kicks throw the shadow"),
    }


def preset(name, target, **extra):
    return node("TitleRigStylePreset", {"preset": name, "target": target, "colour_words": "", "text": "TITLE",
                                        "format": "prose", "audio": "own_track", "glyphs": ["1", 0], **extra},
                f"Style Preset ({name})")


LTX_NEGATIVE = "blurry, low quality, still frame, frames, watermark, overlay, has blurbox, has subtitles"


def ltx2_animated():
    """Hero: audio-reactive rig -> depth frames -> LTX-2 19B + Depth Control IC-LoRA (two-stage, as ComfyUI's
    video_ltx2_depth_to_video template) -> Spell-Lock -> MP4 with the original track."""
    g = {"1": node("TitleRigText", dict(TEXT)), "4": node("TitleRigLayout", {**LAYOUT, "bend": 0.15}),
         "5": preset("Chrome Slam", "ltx23_video")}
    g.update(audio_drive())
    g["26"] = node("TitleRigRenderAnimation", {"glyphs": ["1", 0], "anim": ["25", 0], "width": 1280, "height": 720,
                                               "look": ["5", 2], "shadow": ["5", 3], "layout": ["4", 0],
                                               "pad_ltx": True}, "Rig: depth + edges + alpha frames")
    g["30"] = node("ImageScaleBy", {"image": ["26", 2], "upscale_method": "lanczos", "scale_by": 0.5},
                   "Depth guide at half res (stage 1)")
    g["31"] = node("ImageFromBatch", {"image": ["26", 0], "batch_index": 0, "length": 1}, "First frame (bypassed)")
    g["40"] = node("CheckpointLoaderSimple", {"ckpt_name": mfile("ltx2_ckpt")})
    g["41"] = node("LoraLoaderModelOnly", {"model": ["40", 0], "lora_name": mfile("ltx2_depth_iclora"),
                                           "strength_model": 1.0}, "Depth Control IC-LoRA (strength 1.0)")
    g["42"] = node("LoraLoaderModelOnly", {"model": ["41", 0], "lora_name": mfile("ltx2_distilled_lora"),
                                           "strength_model": 1.0}, "Distilled LoRA (stage 2)")
    g["43"] = node("LTXVAudioVAELoader", {"ckpt_name": mfile("ltx2_ckpt")})
    g["44"] = node("LTXAVTextEncoderLoader", {"text_encoder": mfile("gemma3"), "ckpt_name": mfile("ltx2_ckpt"),
                                              "device": "default"})
    g["45"] = node("LatentUpscaleModelLoader", {"model_name": mfile("ltx2_upscaler")})
    g["46"] = node("CLIPTextEncode", {"text": ["5", 0], "clip": ["44", 0]}, "Prompt (from Style Preset)")
    g["47"] = node("CLIPTextEncode", {"text": LTX_NEGATIVE, "clip": ["44", 0]}, "Negative (template, minus 'titles')")
    g["48"] = node("LTXVConditioning", {"positive": ["46", 0], "negative": ["47", 0], "frame_rate": 24.0})
    g["49"] = node("GetImageSize", {"image": ["30", 0]})
    g["50"] = node("EmptyLTXVLatentVideo", {"width": ["49", 0], "height": ["49", 1], "length": ["49", 2],
                                            "batch_size": 1})
    g["51"] = node("LTXVImgToVideoInplace", {"vae": ["40", 2], "image": ["31", 0], "latent": ["50", 0],
                                             "strength": 1.0, "bypass": True})
    g["52"] = node("LTXVAddGuide", {"positive": ["48", 0], "negative": ["48", 1], "vae": ["40", 2],
                                    "latent": ["51", 0], "image": ["30", 0], "frame_idx": 0, "strength": 1.0},
                   "Rig depth guide")
    g["53"] = node("LTXVEmptyLatentAudio", {"frames_number": ["49", 2], "frame_rate": 24, "batch_size": 1,
                                            "audio_vae": ["43", 0]})
    g["54"] = node("LTXVConcatAVLatent", {"video_latent": ["52", 2], "audio_latent": ["53", 0]})
    g["55"] = node("LTXVScheduler", {"steps": 20, "max_shift": 2.05, "base_shift": 0.95, "stretch": True,
                                     "terminal": 0.1, "latent": ["54", 0]})
    g["56"] = node("RandomNoise", {"noise_seed": 42})
    g["57"] = node("CFGGuider", {"model": ["41", 0], "positive": ["52", 0], "negative": ["52", 1], "cfg": 3.0})
    g["58"] = node("KSamplerSelect", {"sampler_name": "euler"})
    g["59"] = node("SamplerCustomAdvanced", {"noise": ["56", 0], "guider": ["57", 0], "sampler": ["58", 0],
                                             "sigmas": ["55", 0], "latent_image": ["54", 0]}, "Stage 1 (dev, half res)")
    g["60"] = node("LTXVSeparateAVLatent", {"av_latent": ["59", 0]})
    g["61"] = node("LTXVCropGuides", {"positive": ["52", 0], "negative": ["52", 1], "latent": ["60", 0]})
    g["62"] = node("LTXVLatentUpsampler", {"samples": ["61", 2], "upscale_model": ["45", 0], "vae": ["40", 2]})
    g["63"] = node("LTXVImgToVideoInplace", {"vae": ["40", 2], "image": ["31", 0], "latent": ["62", 0],
                                             "strength": 1.0, "bypass": True})
    g["64"] = node("LTXVConcatAVLatent", {"video_latent": ["63", 0], "audio_latent": ["60", 1]})
    g["65"] = node("CFGGuider", {"model": ["42", 0], "positive": ["61", 0], "negative": ["61", 1], "cfg": 1.0})
    g["66"] = node("KSamplerSelect", {"sampler_name": "gradient_estimation"})
    g["67"] = node("ManualSigmas", {"sigmas": "0.909375, 0.725, 0.421875, 0.0"})
    g["68"] = node("RandomNoise", {"noise_seed": 42})
    g["69"] = node("SamplerCustomAdvanced", {"noise": ["68", 0], "guider": ["65", 0], "sampler": ["66", 0],
                                             "sigmas": ["67", 0], "latent_image": ["64", 0]},
                   "Stage 2 (distilled, x2 upscale)")
    g["70"] = node("LTXVSeparateAVLatent", {"av_latent": ["69", 1]})
    g["71"] = node("VAEDecodeTiled", {"samples": ["70", 0], "vae": ["40", 2], "tile_size": 512, "overlap": 64,
                                      "temporal_size": 4096, "temporal_overlap": 8}, "LTX frames")
    g["80"] = node("TitleRigSpellLock", {"images": ["71", 0], "alpha": ["26", 1], "strength": 1.0, "tolerance": 2,
                                         "ring": 24, "edges": ["26", 3]})
    out = {"82": ("80", "titlerig/ltx2_spell_locked", "Spell-Locked + original track"),
           "84": ("71", "titlerig/ltx2_raw", "LTX raw (before Spell-Lock)"),
           "86": ("26:2", "titlerig/control_depth", "Control: rig depth"),
           "88": ("26:3", "titlerig/control_edges", "Control: rig edges (for a Canny IC-LoRA)")}
    for sid, (src, prefix, title) in out.items():
        nid, slot = (src.split(":") + ["0"])[:2]
        cid = str(int(sid) - 1)
        g[cid] = node("CreateVideo", {"images": [nid, int(slot)], "fps": ["26", 6], "audio": ["20", 0]})
        g[sid] = node("SaveVideo", {"video": [cid, 0], "filename_prefix": prefix, "format": "mp4",
                                    "format.codec": "h264"}, title)
    return g


def still_rig(target, preset_name="Chrome Slam", w=1344, h=768):
    return {"1": node("TitleRigText", dict(TEXT)), "4": node("TitleRigLayout", {**LAYOUT, "bend": 0.15}),
            "5": preset(preset_name, target),
            "6": node("TitleRigRender", {"glyphs": ["1", 0], "width": w, "height": h, "look": ["5", 2],
                                         "shadow": ["5", 3], "layout": ["4", 0], "guide_lines": "none"},
                      "Rig: depth + alpha")}


def still_outputs(g, image_ref, prefix):
    """Spell-Lock the AI still, then save raw / locked / transparent cut-out (rig alpha) / control depth."""
    g["90"] = node("TitleRigSpellLock", {"images": image_ref, "alpha": ["6", 1], "strength": 1.0, "tolerance": 2,
                                         "ring": 24, "edges": ["6", 3], "shadow": ["6", 8]})
    g["91"] = node("InvertMask", {"mask": ["6", 1]})  # JoinImageWithAlpha treats the mask as transparency
    g["92"] = node("JoinImageWithAlpha", {"image": ["90", 0], "alpha": ["91", 0]}, "Title cut-out (alpha)")
    g["93"] = node("SaveImage", {"images": image_ref, "filename_prefix": f"titlerig/{prefix}_raw"}, "AI raw")
    g["94"] = node("SaveImage", {"images": ["90", 0], "filename_prefix": f"titlerig/{prefix}_spell_locked"},
                   "Spell-Locked")
    g["95"] = node("SaveImage", {"images": ["92", 0], "filename_prefix": f"titlerig/{prefix}_cutout"},
                   "Transparent PNG")
    g["96"] = node("SaveImage", {"images": ["6", 2], "filename_prefix": f"titlerig/{prefix}_control_depth"},
                   "Control: rig depth")
    return g


def flux_still():
    """FLUX.1 Depth [dev] (flux1-dev + BFL depth LoRA, as ComfyUI's flux_depth_lora_example) on the rig depth."""
    g = still_rig("flux1_depth")
    g["10"] = node("UNETLoader", {"unet_name": mfile("flux1_dev"), "weight_dtype": "default"})
    g["11"] = node("LoraLoaderModelOnly", {"model": ["10", 0], "lora_name": mfile("flux1_depth_lora"),
                                           "strength_model": 1.0}, "FLUX.1 Depth [dev] LoRA")
    g["12"] = node("DualCLIPLoader", {"clip_name1": mfile("clip_l"), "clip_name2": mfile("t5xxl"), "type": "flux",
                                      "device": "default"})
    g["13"] = node("VAELoader", {"vae_name": mfile("flux_ae")})
    g["14"] = node("CLIPTextEncode", {"text": ["5", 0], "clip": ["12", 0]}, "Prompt (from Style Preset)")
    g["15"] = node("FluxGuidance", {"conditioning": ["14", 0], "guidance": 10.0})
    g["16"] = node("ConditioningZeroOut", {"conditioning": ["14", 0]})
    g["17"] = node("InstructPixToPixConditioning", {"positive": ["15", 0], "negative": ["16", 0], "vae": ["13", 0],
                                                    "pixels": ["6", 2]}, "Depth conditioning (rig depth)")
    g["18"] = node("KSampler", {"model": ["11", 0], "seed": 42, "steps": 20, "cfg": 1.0, "sampler_name": "euler",
                                "scheduler": "normal", "positive": ["17", 0], "negative": ["17", 1],
                                "latent_image": ["17", 2], "denoise": 1.0})
    g["19"] = node("VAEDecode", {"samples": ["18", 0], "vae": ["13", 0]})
    return still_outputs(g, ["19", 0], "flux1_depth")


def flux2_still():
    """FLUX.2 [dev] with the rig beauty as reference image 1 (ReferenceLatent, as ComfyUI's image_flux2)."""
    g = still_rig("flux2_dev")
    g["10"] = node("UNETLoader", {"unet_name": mfile("flux2_dev"), "weight_dtype": "default"})
    g["11"] = node("CLIPLoader", {"clip_name": mfile("mistral_flux2"), "type": "flux2", "device": "default"})
    g["12"] = node("VAELoader", {"vae_name": mfile("flux2_vae")})
    g["13"] = node("CLIPTextEncode", {"text": ["5", 0], "clip": ["11", 0]}, "Prompt (from Style Preset)")
    g["14"] = node("FluxGuidance", {"conditioning": ["13", 0], "guidance": 4.0})
    g["15"] = node("VAEEncode", {"pixels": ["6", 0], "vae": ["12", 0]}, "Rig beauty = image 1")
    g["16"] = node("ReferenceLatent", {"conditioning": ["14", 0], "latent": ["15", 0]})
    g["17"] = node("BasicGuider", {"model": ["10", 0], "conditioning": ["16", 0]})
    g["18"] = node("GetImageSize", {"image": ["6", 0]})
    g["19"] = node("EmptyFlux2LatentImage", {"width": ["18", 0], "height": ["18", 1], "batch_size": 1})
    g["20"] = node("Flux2Scheduler", {"steps": 20, "width": ["18", 0], "height": ["18", 1]})
    g["21"] = node("RandomNoise", {"noise_seed": 42})
    g["22"] = node("KSamplerSelect", {"sampler_name": "euler"})
    g["23"] = node("SamplerCustomAdvanced", {"noise": ["21", 0], "guider": ["17", 0], "sampler": ["22", 0],
                                             "sigmas": ["20", 0], "latent_image": ["19", 0]})
    g["24"] = node("VAEDecode", {"samples": ["23", 0], "vae": ["12", 0]})
    return still_outputs(g, ["24", 0], "flux2_dev")


API_NOTE = "API (paid) — NOT part of the open-weights entry. Never run from tests or CI."


def bonus_flux3():
    """FLUX 3 Image (BFL partner node): rig beauty as image 1, prompt per docs/FLUX3.md / the flux-v3 skill."""
    g = still_rig("flux3")
    g["10"] = node("Flux3ImageNode", {"prompt": ["5", 0], "aspect_ratio": "auto", "resolution": "2K",
                                      "grounding": False, "safety_tolerance": 2, "seed": 42,
                                      "images.image_1": ["6", 0]}, f"FLUX 3 Image — {API_NOTE}")
    return still_outputs(g, ["10", 0], "flux3")


def bonus_recraft_vector():
    """Recraft (partner nodes): route 1 vectorizes the rig render (keeps exact letterforms); route 2 generates
    V4 vector art from the MODEL-SKILLS prompt. TitleRig's own open SVG export sits alongside for comparison."""
    g = still_rig("recraft_v4_vector", "Ben-Day Pop")
    g["10"] = node("RecraftVectorizeImageNode", {"image": ["6", 0]}, f"Recraft vectorize — {API_NOTE}")
    g["11"] = node("SaveSVGNode", {"svg": ["10", 0], "filename_prefix": "titlerig/recraft_vectorized"})
    cols = [(255, 212, 0), (225, 29, 72), (253, 224, 71)]  # Ben-Day Pop faces, extrusion, ground
    g["12"] = node("RecraftColorRGB", {"r": cols[0][0], "g": cols[0][1], "b": cols[0][2]})
    g["13"] = node("RecraftColorRGB", {"r": cols[1][0], "g": cols[1][1], "b": cols[1][2], "recraft_color": ["12", 0]})
    g["14"] = node("RecraftColorRGB", {"r": cols[2][0], "g": cols[2][1], "b": cols[2][2]})
    g["15"] = node("RecraftControls", {"colors": ["13", 0], "background_color": ["14", 0]})
    g["16"] = node("RecraftV4TextToVectorNode", {"prompt": ["5", 0], "negative_prompt": "", "model": "recraftv4_1_vector",
                                                 "model.size": "1536x768", "n": 1, "seed": 42, "style_id": "",
                                                 "style_match": "precise", "recraft_controls": ["15", 0]},
                   f"Recraft V4 vector — {API_NOTE}")
    g["17"] = node("SaveSVGNode", {"svg": ["16", 0], "filename_prefix": "titlerig/recraft_v4_vector"})
    g["18"] = node("TitleRigSVGExport", {"glyphs": ["1", 0], "width": 1344, "height": 768,
                                         "filename_prefix": "titlerig/rig_vector", "supersample": 2, "side_tones": 4,
                                         "background": "", "look": ["5", 2], "shadow": ["5", 3], "layout": ["4", 0]},
                   "Open alternative: TitleRig SVG Export (free)")
    return g


WORKFLOWS = {"titlerig_rig_only": rig_only, "titlerig_audio_react": audio_react,
             "titlerig_ltx2_animated": ltx2_animated, "titlerig_flux_still": flux_still,
             "titlerig_flux2_still": flux2_still}
BONUS = {"titlerig_flux3": bonus_flux3, "titlerig_recraft_vector": bonus_recraft_vector}
RUNNABLE_ON_CPU = ("titlerig_rig_only", "titlerig_audio_react")  # no models, no API: safe to execute anywhere
# CPU dry runs of the AI workflows: the AI output node is replaced by the rig beauty pass, model nodes are pruned,
# so everything TitleRig does around the model (rig, audio, Spell-Lock, cut-out, saves) runs end to end.
DRYRUN = {"titlerig_ltx2_animated": ("71", ["26", 0]), "titlerig_flux_still": ("19", ["6", 0]),
          "titlerig_flux2_still": ("24", ["6", 0])}
OUTPUT_CLASSES = ("SaveImage", "SaveVideo", "SaveAnimatedWEBP", "PreviewImage", "SaveSVGNode", "TitleRigSVGExport")


def dryrun(prompt: dict, ai_node: str, replacement: list) -> dict:
    g = json.loads(json.dumps(prompt))
    for n in g.values():
        for k, v in n["inputs"].items():
            if isinstance(v, list) and len(v) == 2 and v[0] == ai_node:
                n["inputs"][k] = list(replacement)
    keep, stack = set(), [k for k, n in g.items() if n["class_type"] in OUTPUT_CLASSES]
    while stack:  # everything an output still needs
        k = stack.pop()
        if k in keep or k not in g:
            continue
        keep.add(k)
        stack += [v[0] for v in g[k]["inputs"].values() if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)]
    for k in [k for k in g if k not in keep]:
        del g[k]
    for n in g.values():
        if n["class_type"] in ("TitleRigRenderAnimation", "TitleRigRender"):  # fit a 16 GB CPU box
            n["inputs"]["width"], n["inputs"]["height"] = n["inputs"]["width"] // 2, n["inputs"]["height"] // 2
        if n["class_type"] == "SaveVideo" or n["class_type"] == "SaveImage":
            n["inputs"]["filename_prefix"] = n["inputs"]["filename_prefix"].replace("titlerig/", "titlerig/dryrun_")
    return g

if __name__ == "__main__":
    for sub, table in (("api", WORKFLOWS), (os.path.join("api", "bonus"), BONUS)):
        os.makedirs(os.path.join(HERE, sub), exist_ok=True)
        for name, fn in table.items():
            with open(os.path.join(HERE, sub, f"{name}.json"), "w") as f:
                json.dump(fn(), f, indent=2)
            print("wrote", f"workflows/{sub}/{name}.json")
    os.makedirs(os.path.join(HERE, "api", "dryrun"), exist_ok=True)
    for name, (ai, repl) in DRYRUN.items():
        with open(os.path.join(HERE, "api", "dryrun", f"{name}.json"), "w") as f:
            json.dump(dryrun(WORKFLOWS[name](), ai, repl), f, indent=2)
        print("wrote", f"workflows/api/dryrun/{name}.json")
