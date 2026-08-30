# Z-Image Common Rules and Guide

Write Z-Image prompts for strong instruction adherence, photorealism, bilingual English and Chinese text rendering, and aesthetic diversity. Use text-to-image instructions for generation variants and direct transformation instructions for the image-editing variant.
## Prompt-output hygiene

- Preserve the user’s subject, count, action, relationships, composition, and exact visible text.
- Put the primary intent first.
- Avoid tag soup, unexplained weighting syntax, generation settings, and process commentary.
- Use editing instructions only with the image-editing variant.
- Do not invent translation of visible text unless requested.

## Language choice

Z-Image supports Chinese and English instructions and visible text. Keep the user’s requested language. For bilingual images, distinguish which string uses which language and where each appears. Preserve native characters, capitalization, punctuation, and numerals exactly.

## Shared family capabilities

- **Bilingual visible-text generation and editing.**
- **Style, composition, identity, pose, and layout transformation where supported by the selected family variant.**

## Subject and semantic completeness

Describe subject count, visible identity, action, pose, expression, wardrobe, and relationships. Bind attributes and objects to owners. When several subjects appear, make their positions, gaze, contact, and interaction explicit.

Do not add generic beauty or quality wording that changes the requested age, identity, body type, or visual premise.

## Scene, composition, and layout

Specify environment, time, weather, foreground/background order, shot scale, viewpoint, crop, focal hierarchy, and important placements. For designs or posters, define canvas hierarchy, text zones, graphic elements, and negative space.

Use direct spatial language. Avoid requiring the model to infer which person, object, or text block occupies a region.

## Photography and realism

For photorealism, describe plausible camera position, lens character, depth of field, lighting, material response, and small natural imperfections. Use coherent skin, hair, fabric, metal, glass, water, architecture, and atmospheric detail. Do not combine incompatible camera or lighting setups.

## Artistic style and diversity

Name the medium and describe its visible treatment: line work, brushwork, surface texture, palette, contrast, shape language, edge quality, or print process. Because variant behavior may favor realism differently, state stylization early and reinforce it through concrete visual choices rather than repeating a style label.

## Lighting, color, and material

Describe source, direction, softness, contrast, temperature, and reflections. Bind colors to named elements. Use material terms that clarify physical appearance and light interaction.

## Visible text

- Quote every required string.
- Preserve exact Chinese or English characters.
- State location, hierarchy, alignment, font character, color, and material.
- Keep copy length compatible with the design.
- Do not add translations, slogans, signatures, or watermarks unless requested.

## Failure repairs

- Strengthen early subject and action wording when adherence is weak.
- Replace vague quality terms with concrete visual detail.
- Bind every attribute and edit to an owner.
- Simplify crowded scenes and clarify depth.
- Reinforce stylization with palette, texture, line, and medium cues.
- Shorten and quote exact text when typography drifts.
- For edits, strengthen preservation locks rather than redescribing an unrelated final scene.

## Validation checklist

- The selected family variant supports the requested mode.
- Prompt density and negative behavior match Base or Turbo rather than mixing their conventions.
- Subject count, ownership, and relationships are stable.
- Composition, camera, lighting, palette, and style agree.
- Chinese and English text is exact, quoted, and positioned.
- Edit targets and preservation constraints are explicit.
- No generation-setting or process commentary appears.
