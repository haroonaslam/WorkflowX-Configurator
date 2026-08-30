# FLUX.2 Klein Common Rules and Guide

Write FLUX.2 Klein prompts with ordered natural language, explicit relationships, direct edit operations, and bounded references. Keep prompts concise and high-signal so ornamental detail does not bury the main request.
## Prompt-output hygiene

- Put the subject, action, or edit operation first.
- Do not use a conventional negative prompt; describe the intended result and preservation state positively.
- Remove repetition, generic quality filler, parameter notation, and process commentary.
- Preserve exact quoted text and explicit reference ownership.
- Prefer a few precise visual details over exhaustive lists that compete for attention.

## High-signal prompt structure

```text
Primary subject or edit + action/change + style + scene + composition + lighting/color + fidelity locks
```

Every phrase should perform a clear visual job. Keep modifiers close to their owner. If a detail does not alter content, composition, style, light, color, material, or preservation, omit it.

## Klein prompt density

Klein benefits from focused narrative prose rather than a tag inventory. Put the subject first, describe the scene as a coherent visual moment, and give lighting unusually clear treatment because it strongly shapes the result. Expand as needed for exact text, several subjects, or reference-role complexity without adding repetitive filler.

## Subject and scene

Name subject count, visible identity traits, action, pose, expression, wardrobe, and owned objects. Establish the environment with only the details needed to anchor location, depth, time, and atmosphere.

For multiple subjects, state left/right placement, interaction, gaze, contact, and object ownership. Avoid ambiguous pronouns.

## Composition and camera

Describe shot scale, viewpoint, crop, focal point, depth, and major placements. Use one coherent lens or capture treatment. A compact prompt can still specify foreground, background, negative space, symmetry, or off-center balance when those choices matter.

## Style, lighting, and material

Name one dominant medium or style and describe its visible traits. State the primary light source, direction, softness, and color logic. Add only important materials and surface reactions.

## Typography

Quote exact visible text. State its role, location, hierarchy, and style. Keep copy short and avoid inventing additional lettering.

## Shared style, identity, and visible-text capabilities

- **Style transfer and identity-guided generation.**
- **Visible-text generation and replacement.**

## Style and identity references

A style reference contributes visual treatment but not its incidental content. An identity reference contributes the named person or character but not its original pose, wardrobe, background, or camera unless requested. State the new scene and action independently.

## Text replacement

Quote the original and replacement. Preserve font character, size, color, perspective, material, and layout unless changing them is part of the request.

## Repair rules

- If the result ignores the main intent, move it to the first phrase.
- If attributes leak, bind each one to a named subject or image.
- If the scene drifts, shorten secondary details and strengthen preservation locks.
- If the composition is unclear, state placement and crop directly.
- If text is incorrect, shorten the copy and specify one exact quoted string.
- If references blend, narrow each reference to one job and state non-transfer boundaries.

## Validation checklist

- The prompt has one obvious priority.
- Every phrase adds actionable visual control.
- Subject and reference ownership are explicit.
- Edit target and preserved content are clear.
- Camera, light, palette, and style are compatible.
- Visible text is exact and quoted.
- No generation metadata appears.
