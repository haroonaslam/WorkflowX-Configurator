# FLUX.2 dev Common Rules and Guide

FLUX.2 pays strong attention to prompt order. Introduce the most important subject and action first, then style and context, and only then secondary composition, camera, lighting, color, material, and finishing detail.
## Prompt-output hygiene

- FLUX.2 does not use a conventional negative prompt. Describe the desired result positively and state preservation constraints directly.
- Do not include generation controls, media metadata, or process commentary in the prompt.
- Do not rely on numbered images without assigning each one an explicit role.
- Keep every requested visible string exact and quoted.
- Resolve contradictory directions before producing the prompt.

## Core prompt structure

Use the priority order:

```text
Subject + action + style + context
```

Expand it with composition, camera, lighting, palette, materials, typography, and atmosphere only where they improve control. Word order matters: indispensable content belongs first.

## Prompt density and controlled expansion

Start ordinary scenes with a focused description. Expand when the request genuinely contains several subjects, exact typography, a structured design, or multiple bounded references. Additional capacity is not a reason to repeat quality language or restate the same attribute.

Revise iteratively: keep the subject/action anchor stable and change one control family at a time. When an unwanted feature appears, describe the positive replacement state rather than adding conventional negative-prompt prose. This makes the intended scene state explicit and reduces conflicting instructions.

## Subject, action, and relationships

State count, visible appearance, pose, action, expression, wardrobe, and object ownership. For multi-element scenes, name relationships and screen positions directly. Keep modifiers next to their owner and avoid ambiguous pronouns.

When several actions are requested, establish one dominant event and arrange secondary actions around it. A complex composition should still have a clear focal hierarchy.

## Composition and camera

Specify shot scale, viewpoint, camera height, lens character, focus, depth layers, crop, and negative space. Describe placements in ordinary spatial language. For product and design work, identify the hero object, supporting elements, and intentional empty areas.

For photorealism, use plausible camera and light behavior. Lens, aperture feel, depth of field, motion, and exposure should agree with the shot scale and environment.

## Style and material

Name the medium and describe its visible qualities. A style reference may control palette, texture, lighting, mark-making, graphic rhythm, or photographic finish, but it should not contribute its people, words, objects, or layout unless assigned those roles.

Describe materials specifically and physically: brushed aluminum, frosted glass, worn leather, translucent resin, wet stone, embroidered silk, printed paper, or textured plaster. State how light interacts with important surfaces.

## Lighting and precise color

Define source, direction, softness, contrast, temperature, and atmosphere. FLUX.2 can follow named colors and hexadecimal colors when exact brand or design matching matters. Bind every precise color to a specific object or region and describe gradients by direction and endpoints.

Do not flood an organic photographic request with unnecessary color codes. Use exact codes for design-critical work and ordinary color relationships elsewhere.

## Typography and graphic design

- Put every literal string in quotation marks.
- Preserve spelling, capitalization, punctuation, and language.
- State location, scale, alignment, hierarchy, font character, weight, color, and material treatment.
- Separate headline, subheading, label, and body copy.
- Keep copy length plausible for the available space.
- In edits, quote both the target and replacement and preserve surrounding design unless a redesign is requested.

Compact example:

```text
Replace the headline "SUMMER SALE" with "AUTUMN STUDY" in the same centered bold serif lettering; preserve the paper texture, letter size, alignment, shadows, and all other poster elements.
```

## Infographics and structured design

Organize complex design prompts around canvas purpose, hierarchy, grid, sections, data relationships, icons, palette, and exact text. Do not invent data. Keep visual hierarchy explicit and copy concise.

## Common failure repairs

- Move the main subject and action earlier when adherence is weak.
- Replace vague style labels with visible traits.
- Bind colors, garments, props, and actions to owners.
- Simplify overloaded scenes into one focal hierarchy.
- Use direct preservation language for edits.
- Separate reference roles and block incidental transfer.
- Remove conventional negative-prompt phrasing and describe the intended positive state.

## Validation checklist

- The central subject and action occur first.
- Every reference has one explicit role and boundary.
- Base content, edit targets, and preservation locks are clear.
- Composition, camera, lighting, palette, and materials agree.
- Exact text is quoted and positioned.
