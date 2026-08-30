# Qwen-Image Common Rules and Guide

Write Qwen-Image prompts with explicit subject, scene, camera, style, spatial relationships, and visible text while preserving the user’s core intention. Use descriptive expansion for text-to-image and direct operation instructions for image editing.
## Prompt-output hygiene

- Preserve the user’s central subject and requested operation.
- Resolve vague or contradictory details with the smallest visually plausible inference.
- Do not emit reasoning, alternatives, confidence statements, or a description of the enhancement process.
- Do not include model invocation, sampling, resolution, or generation instructions as scene content.
- Keep exact trigger phrases and exact visible text unchanged.
- For edits, state the operation and target clearly rather than rewriting the request as a new unrelated scene.

## Shared style-reference and visible-text capabilities

- **Text editing:** add or replace visible text while preserving exact spelling and case.
- **Style conversion and style reference:** apply a specified or referenced visual treatment while keeping requested content stable.

## Text editing

Use direct replacement syntax and straight double quotes:

```text
Replace "OPEN DAILY" with "OPEN FRIDAY"; preserve the sign layout, letter size, color, weathering, perspective, and surrounding storefront.
```

Keep the new text’s exact language and capitalization. Add position, color, alignment, or font character only when requested or necessary to disambiguate the target.

## Style conversion and enhancement

Describe a named style through its visible characteristics: palette, line quality, medium, texture, contrast, lighting, and composition. When another image supplies the style, identify the content image and style image separately. Apply style without importing incidental people, objects, text, or layout from the style source.

For restoration and colorization, use the direct intent “Restore and colorize the photo,” then add only requested preservation or repair details. Do not invent a historically unsupported palette when accuracy is important.

## Validation checklist

- The original intent and requested operation remain unchanged.
- All subjects, images, and transferred attributes have unambiguous ownership.
- Added details are visually compatible with the base scene.
- Every visible string is quoted exactly.
- Text replacement names the target and replacement precisely.
- Human edits preserve identity except where explicitly changed.
- Multi-image prompts state the base, source roles, and non-transfer boundaries.
- The result is direct prompt text with no process commentary.
