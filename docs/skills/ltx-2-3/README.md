# ltx-2-3 skill (reference)

TitleRig's `ltx23_video` Style Preset target follows the **ltx-2-3-prompts** skill v1.0 (built 2026-10-18) from
[Cozy-Art/super-skills](https://github.com/Cozy-Art/super-skills) (Jason Cozy @ Visual Horizon Studio, MIT License).

Rules applied: one shot as one chronological present-tense paragraph (~60–180 words), every sentence with a verb;
for structure-driven video (rig depth via IC-LoRA, like I2V) spend the words on motion, light and sound, since the
control supplies the letterforms; prose and settings agree (resolution, fps, duration, camera preset are never in the
text; a locked camera is stated because the rig control fixes the geometry); audio is written as layered ambience →
synced effects → music, or, when the deliverable carries its own track, `generate_audio: false` instead of prompting
for silence. Local open weights: `ltx-2.3-22b-distilled`, 8 steps, CFG 1.0, width/height divisible by 32, frames
`8n + 1`; the local negative prompt is the shipped default, edited only for observed failures. LTX-2 LoRAs do not
transfer to 2.3: use a 2.3 IC-LoRA for depth control.

Per the skill's build notes, the ComfyUI two-stage template sizes and the default local negative prompt come from
research and were not re-verified; the `settings` output says so. Ben-Day Pop and Cel Toon drop "cartoon, childish"
from the negative because that is their intended look.
