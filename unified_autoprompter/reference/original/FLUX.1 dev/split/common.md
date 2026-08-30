# FLUX.1 dev Common Rules and Guide

## Purpose and model scope

Write FLUX.1 dev prompts for text-to-image generation. Do not write reference-editing operations as though they were text-to-image instructions.

FLUX responds well to structured natural language, strong concept ordering, clear spatial relationships, and concrete visual detail. A prompt should establish the subject and action first, then style and context, followed by composition, camera, lighting, color, material, and finishing detail.

## Prompt-output hygiene

- Put the most important subject and action early.
- Do not use unexplained tag soup, weighting syntax, sampler settings, dimensions, or generation details as visual prose.
- Do not produce a negative prompt as the primary control method; describe what should appear positively and concretely.
- Preserve exact requested visible text in quotation marks.
- Avoid mutually incompatible styles, camera descriptions, lighting systems, and time periods.

## Canonical prompt structure

Use this conceptual order:

```text
Subject + action + style or medium + environment and context + composition and camera + lighting and color + materials and finishing detail
```

The structure is a priority guide, not a rigid sentence template.

## Prompt density and iteration

Use enough focused detail to establish subject, setting, composition, light, and medium without burying the intent. Complex typography or multi-element designs may need more development; simple concepts may need less.

Build from the focal subject and action, then add one layer at a time. When revising after a generation, change one meaningful variable—composition, light, palette, material, or style—rather than rewriting every clause. Express exclusions as positive scene states such as “an empty pedestrian street,” “clear blue sky,” or “tack-sharp focus.”

## Subject and action

Name the central subject, count, defining visible traits, pose, expression, gaze, wardrobe, and action. Use active, observable language. For several subjects, make ownership and interaction explicit so attributes do not migrate between them.

Start with a clear focal event. Supporting details should reinforce the main image rather than create competing actions.

## Environment and context

Describe location, time, weather, surrounding objects, surfaces, and background activity. Establish whether the setting is intimate, expansive, crowded, sparse, natural, industrial, domestic, editorial, or fantastical through visible evidence.

## Composition and spatial control

State framing, viewpoint, focal hierarchy, relative scale, depth layers, and placement. Use clear terms such as foreground, middle ground, background, left, right, centered, behind, facing, cropped, isolated against, or occupying the upper third.

For complex layouts, introduce elements in visual-priority order and state their relationships directly. Avoid dense coordinate-like instructions unless the target format explicitly requires them.

## Camera and photographic language

For photographic results, specify shot scale, camera height, angle, lens character, depth of field, and capture treatment. Use compatible combinations: close portrait with shallow focus, wide architectural view with strong perspective, telephoto compression across a landscape, macro product detail, or handheld documentary framing.

Camera language must serve the composition. Do not stack incompatible lenses or viewpoints merely as quality tags.

## Style, medium, and production design

Name the visual medium or aesthetic directly: editorial photography, documentary still, cinematic frame, analog snapshot, ink illustration, oil painting, screen print, 3D product render, architectural visualization, or another defined form.

Describe style through visible decisions such as line quality, brushwork, grain, print texture, set design, costume, era, material finish, and color process. Avoid relying only on broad labels.

## Lighting and color

Describe light source, direction, softness, contrast, temperature, and interaction with surfaces. Keep time of day and practical sources coherent. State palette using ordinary color names and relationships such as muted earth tones, cool cyan shadows with warm highlights, monochrome red, or complementary orange and teal.

## Materials and physical detail

Name important materials and how they behave under light: brushed metal, translucent glass, wet asphalt, woven cotton, rough plaster, glossy ceramic, skin texture, haze, dust, smoke, or condensation. Use detail to clarify physical reality, not to inflate the prompt.

## Typography and visible graphics

Place required visible text inside quotation marks and describe its location, hierarchy, style, color, and material context. Keep copy concise enough for the composition. Distinguish headline, label, subtitle, and decorative graphic elements. Do not invent additional text.

## Photorealism

For realistic images, specify plausible capture conditions, lighting, material response, and small physical imperfections. Use coherent lens and depth cues. Avoid contradictory requests such as raw phone footage combined with elaborate studio crane cinematography and flawless commercial retouching.

## Illustration and stylization

State the medium early and describe its mark-making, palette, texture, shape language, and edge treatment. Keep the scene readable after stylization by preserving subject hierarchy and spatial relationships.

## Common failure repairs

- **Too vague:** add subject, action, setting, framing, light, and medium.
- **Attribute leakage:** bind each color, garment, object, and action to its owner.
- **Flat composition:** state foreground/background order, camera position, and focal hierarchy.
- **Contradictory lighting:** choose one primary source and compatible secondary light.
- **Style overload:** keep one dominant medium and a small number of compatible influences.
- **Unwanted content:** state the desired clean result positively, such as an empty background or unbranded packaging.
- **Text ambiguity:** quote the exact string and state its placement.

## Validation checklist

- The main subject and action appear first.
- Subject count and ownership are stable.
- Spatial relationships and crop are explicit where important.
- Medium, camera, lighting, palette, and materials are compatible.
- Exact visible text is quoted and positioned.
- The prompt is self-contained.
- No reference-editing instructions appear.
