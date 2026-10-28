# flux-v3 skill (reference)

TitleRig's `flux3` Style Preset target follows the **flux-3-image-prompts** skill from
[Cozy-Art/super-skills](https://github.com/Cozy-Art/super-skills) `skills/image/flux-v3` (Jason Cozy @ Visual Horizon
Studio, MIT License).

Rules applied: describe the finished image in sentences, in layer order (image type → subject → setting → lighting →
framing/camera → style/palette → exact text); say what IS there (no `negative_prompt`); continuity lives in images,
so the TitleRig beauty pass is **image 1** (1-based in prose) with an explicit preserve list; quote visible text
exactly with placement and type character; hex is allowed bound to objects; no "8K / best quality" filler.
Settings carry only valid native fields: `images`, `aspect_ratio` (`auto` follows image 1), `resolution`
(draft `1k`, final `2k`), `grounding: false`, `safety_tolerance`, `version`. Never `seed`, `guidance`, `steps`,
`width`, `height`, `negative_prompt` or `mode` (HTTP 422).
