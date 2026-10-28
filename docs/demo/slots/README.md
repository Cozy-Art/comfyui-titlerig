# Demo slots

Put build-night results here, then run `python examples/build_demo.py`. Name each file after its slot and use any common extension (`.mp4`, `.mov`, `.webm`, `.gif`, `.png`, `.jpg`). The files here are git-ignored except this README.

If a slot is empty, the video still builds. The **Fallback** column below says what plays instead: a labelled placeholder card, or a rig-only clip from `docs/media/`.

| Slot | Shot | What to put here | Fallback |
| --- | --- | --- | --- |
| `hook_mangled` | 0:00–0:06, the hook | Before rendering it, check it really is misspelled or mangled. | placeholder |
| `comfyui_canvas` | 0:12–0:22, the rig | A screen recording of the canvas: Text → Look → Animate → Render with the preview widget scrubbing, about 10 s. | `preview_widget_dark.png` |
| `ltx_result` | 0:32–0:42, LTX-2 | `ltx2_spell_locked_*.mp4` from `titlerig_ltx2_animated`, or the Spell-Locked Cloud result. | placeholder |
| `flux_still` | 0:42–0:46, FLUX | `flux1_depth_spell_locked_*.png`, or the cutout on a colour. | placeholder |
| `preset_1` | 0:48–0:52 | An LTX or FLUX result for a second preset, such as Ben-Day Pop. | `ben_day_beat.mp4` |
| `preset_2` | 0:52–0:56 | A third preset, such as Holo Foil or Vapor Sunset. | `sphere_ticker.mp4` |
| `preset_3` | 0:56–1:00 | A fourth preset, such as Candy Inflatable or Fuzzy Grass. | `magnet_snap_back.mp4` |

For `hook_mangled`, this is how to make it:
1. Run FLUX.1 [dev] (or FLUX.2 [dev]) with a plain prompt and no rig, for example "3D chrome title that says TITLERIG on a blue background".
2. Pick the most wrong one.

## Notes

- **Size and length:** clips are fitted into 1280×720 and letterboxed, never stretched. A clip shorter than its shot is looped.
- **Captions:** each slot's lower third names the models used. If you used something else, edit the caption in `TIMELINE` at the top of `examples/build_demo.py`.
- **Faster rebuilds:** after changing one slot, rebuild only that shot, then the final cut is reassembled. For example: `python examples/build_demo.py --only ltx`.
