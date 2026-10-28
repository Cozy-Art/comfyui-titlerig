# TitleRig PRD (summary)

Living doc: https://claude.ai/artifact/2qzTkJzmj6nwPUjcdNAad4

**Pitch:** AI can't spell. So we gave it a rig. TitleRig draws exact title geometry and hands Flux/LTX control passes; the AI only paints material and world.

## Nodes
| Node | Key inputs | Output | Priority |
| --- | --- | --- | --- |
| Text | text, font, size, bulk tracking, per-pair kerning, per-letter spacing/overrides | GLYPHS | P0 ✅ |
| Look 3D | extrude depth/angle, side colour, bevel size+profile, face colour/gradient, light angle/height, gloss, rim | LOOK | P0 ✅ |
| Shadow | angle, length, softness, colour, texture (solid/halftone/stripes/checker/noise/pixel/gradient), scale, angle | SHADOW | P0 ✅ |
| Layout | flat, arc, circle, sphere, cube, ticker; tilt, vanishing point, warp | LAYOUT | P0 flat+arc, P2 rest |
| Animate | flip X, spin Y, roll Z, pop, drop, slide; per letter; stagger/order; easing; duration; fps | ANIM | P1 |
| Audio React | AUDIO, sensitivity, attack, release, band | keyframes / curves | P1 (hero demo) |
| Magnet | second GLYPHS, polarity (attract/repel), strength, range, lag, spring, overshoot, squash/stretch | ANIM | P2 |
| Render | all of the above, width, height | beauty, alpha, depth, edges, normals, face, sides, highlight, shadow, letter_ids, guides | P0 ✅ |
| Style Preset | preset, colour words | positive/negative prompt, suggested LOOK | P2 |
| Spell-Lock | AI frames, rig alpha + edges, strength | corrected frames, drift score | P2 |

## Style presets (bright, ad-ready)
Chrome Slam · Fuzzy Grass · Liquid Glass · Aero Bubble · Ben-Day Pop · Holo Foil · ChromaDepth · Candy Inflatable · Op Art Stripe · Vapor Sunset · Low Poly · Cel Toon · Trailer Title

## Workflows to ship
1. Still (FLUX, depth/canny) → composite with alpha → PNG
2. Animated (LTX-2 + Depth IC-LoRA) → Spell-Lock → MP4 (hero)
3. Rig only (no AI) — safety net

## UI (Glyph Bench 2.0 + ComfyUI preview widget)
Clean, modern, dark default with an equally designed light theme (tokens, follows system). Stage centre, layers/fonts rail left, inspector right (Type · 3D · Shadow · Motion · Audio), timeline docked bottom. Dashed type guides (baseline, x-height, cap, ascender, descender), scrubbable numbers, preset chips that render your own word.
