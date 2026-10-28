# flux-v2 skill (vendored reference)

`schema.json` is the output schema of the **flux-2-prompts** skill v1.0.0 (2026-02-25) from
[Cozy-Art/super-skills](https://github.com/Cozy-Art/super-skills) `skills/image/flux-v2`, by Jason Cozy @ Visual
Horizon Studio, MIT License. TitleRig's tests validate the Style Preset node's FLUX.2 `settings` output against it.

Rules TitleRig applies from the skill: front-load the subject and the quoted text in the first 5–10 words; keep
prompts short (≈25–60 words here); describe only what is wanted, with no negative prompt and no "no / without /
avoid"; bind hex colours to specific objects (letter faces, extrusion, background); add lighting last; refer to
reference images by index ("image 1"); for typography use Flex with 40–50 steps and guidance 7–8; JSON structured
prompts are pasted into the single prompt string.
