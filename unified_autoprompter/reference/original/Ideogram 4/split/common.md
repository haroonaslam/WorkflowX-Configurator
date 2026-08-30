# Ideogram 4 Common Rules and Guide

Turn each image request into a precise Ideogram 4 structured caption. Use the relevant instructions for direct JSON captioning, text-to-image creation, remixing an existing image, character and style references, masked edits, extension, and composition-guided generation. Keep aspect ratio, render speed, seed, and reference strength out of the caption unless their visual consequence must be expressed.

Expand a plain-language brief into the structured JSON caption schema. Identify the primary subject first, establish the medium and scene, make spatial relationships explicit, give visible text exact treatment, and avoid incompatible alternatives.

These modes describe where the visual intent comes from. Their final direct-model representation is the same structured JSON caption.
## Canonical JSON caption schema

The caption is one JSON object with three top-level keys in this order:

1. `high_level_description` — optional but strongly recommended; one or two sentences summarizing the complete image.
2. `style_description` — optional; describes aesthetics, lighting, medium, photographic or artistic treatment, and palette.
3. `compositional_deconstruction` — required; contains `background` followed by `elements`.

No wrapper key is part of the native caption. Return the caption object itself.

### `style_description`

When `style_description` is present, it contains exactly one of `photo` and `art_style`.

- Photographic key order: `aesthetics`, `lighting`, `photo`, `medium`, then optional `color_palette`.
- Non-photographic key order: `aesthetics`, `lighting`, `medium`, `art_style`, then optional `color_palette`.
- `aesthetics`, `lighting`, and `medium` are required whenever the block is present.
- `photo` carries camera and lens treatment for photographic captions.
- `art_style` carries visible rendering treatment for illustration, painting, graphic design, 3D work, and other non-photographic media.
- The overall `color_palette` accepts up to sixteen uppercase `#RRGGBB` strings and remains last.

Do not include both `photo` and `art_style`, do not lowercase or shorten hex colors, and do not change the trained key order.

### `compositional_deconstruction`

`compositional_deconstruction` is required even when the composition is simple. It contains:

- `background`: a string describing the environment or scene shell;
- `elements`: an ordered array of visible objects, subjects, and text.

`background` comes before `elements`. Every non-text subject or object uses `"type": "obj"`; visible lettering uses `"type": "text"`. The exact descriptive field name is `desc`, not `description`.

Object element key order:

```text
type, bbox, desc, color_palette
```

Text element key order:

```text
type, bbox, text, desc, color_palette
```

`bbox` and `color_palette` are optional. When present, they stay in the positions shown. A per-element palette accepts up to five uppercase hex colors.

### Bounding boxes

Bounding boxes use normalized coordinates from 0 to 1000 with the origin at the top-left. Ideogram 4 uses this exact order:

```text
[y_min, x_min, y_max, x_max]
```

`y` measures vertical position from top to bottom; `x` measures horizontal position from left to right. The first pair is the top-left corner and the second pair is the bottom-right corner. Require `0 <= y_min < y_max <= 1000` and `0 <= x_min < x_max <= 1000`.

Boxes should describe the intended occupied region, not trace an irregular silhouette. Include them when layout control matters; omit them when precise placement would add false certainty. List elements in a stable visual order, such as dominant subject first followed by supporting objects and text.

### Complete blank caption template

```json
{
  "high_level_description": "one- or two-sentence summary of the complete image",
  "style_description": {
    "aesthetics": "coherent aesthetic keywords",
    "lighting": "source, direction, quality, contrast, and color",
    "photo": "camera and lens treatment for a photograph",
    "medium": "photograph",
    "color_palette": ["#RRGGBB"]
  },
  "compositional_deconstruction": {
    "background": "complete background and environment description",
    "elements": [
      {
        "type": "obj",
        "bbox": [0, 0, 1000, 1000],
        "desc": "subject or object description",
        "color_palette": ["#RRGGBB"]
      },
      {
        "type": "text",
        "bbox": [0, 0, 1000, 1000],
        "text": "EXACT VISIBLE TEXT",
        "desc": "typography, hierarchy, color, and placement",
        "color_palette": ["#RRGGBB"]
      }
    ]
  }
}
```

For a non-photographic caption, replace the `photo` form with the required non-photo order: `aesthetics`, `lighting`, `medium`, `art_style`, then optional `color_palette`. The full-frame boxes above demonstrate coordinate order only; replace or omit them rather than using them indiscriminately.

## Prompt-output hygiene

- Return one definitive structured caption, not alternatives or a discussion of the process.
- Use natural sentences and concrete visible language. Do not use weighting syntax, hidden flags, parameter notation, or unexplained tag soup.
- Preserve the user's requested subject, count, relationships, composition, medium, and visible strings.
- Do not insert model settings into the prompt unless the setting itself is intended to be visible content.
- Do not mention references, masks, canvases, upload order, or editing tools in the final caption unless the selected mode requires an explicit edit instruction.
- Do not add slogans, captions, labels, signatures, or watermarks the user did not request.

## Core prompt construction

### 1. Lead with the visual priority

Begin with the main subject or the dominant design goal. State what it is, what it is doing, and its defining visible traits before secondary decoration. When multiple subjects matter, name their count and relationships rather than listing them independently.

### 2. Establish the medium and rendering intent

Name the intended visual form: photograph, editorial image, poster, screen print, watercolor, ink drawing, collage, 3D render, packaging design, logo, infographic, comic panel, or another specific medium. Add production qualities that genuinely alter the result, such as paper grain, halftone dots, soft studio diffusion, glossy product reflections, or hand-painted edges.

### 3. Describe the scene and action

Specify environment, time, weather, surfaces, props, and background activity. Use direct action verbs and observable poses. Replace abstract emotion with visible expression, posture, gesture, gaze, and interaction.

### 4. Define composition and spatial relationships

State framing, camera angle, foreground/background order, relative scale, overlap, crop, symmetry, balance, negative space, and the position of important elements. Use plain relationships such as left of, behind, centered beneath, filling the upper third, cropped at the waist, or receding into the distance.

When exact layout matters, distinguish the dominant element, supporting elements, and empty areas. Describe what should remain visually separated and what may overlap.

### 5. Add lighting, color, material, and atmosphere

Name the light source and quality where relevant: overcast daylight, warm practical lamps, hard noon sun, diffused studio light, neon spill, rim light, or soft window light. Define a coherent palette in ordinary color names and material descriptions. Do not rely on hexadecimal or RGB values as the only color instruction.

### 6. Finish with fidelity-critical details

Close with exact typography, surface detail, production finish, or exclusions. Detail should reinforce the core image rather than compete with it.

## Text and typography

Ideogram is especially capable with visible text, but the prompt must remove ambiguity.

- Put every literal visible string in quotation marks.
- Preserve spelling, capitalization, punctuation, numerals, and language exactly.
- State where the text appears and what role it serves: headline, subheading, label, button, packaging copy, sign, or body text.
- Describe alignment, hierarchy, font character, weight, color, spacing, and its relationship to surrounding graphics.
- Distinguish separate text blocks rather than combining them into one quoted string.
- If the request names a category but not the actual wording, either choose one definitive phrase consistent with the intent or leave the area intentionally without readable copy; do not output placeholders such as “name here.”
- Avoid asking for more exact copy than the available area can plausibly contain.

Compact syntax example:

```text
A restrained museum poster with the headline "NIGHT BLOOM" centered in tall white condensed lettering, a smaller line "Botanical Studies 2026" directly beneath it, and no other readable text.
```

## Prompt clarity and prioritization

Ideogram gives more reliable results when the caption has a clear hierarchy. Put indispensable content early. Group related attributes together. Avoid long chains of mutually incompatible styles, lighting setups, viewpoints, or eras. If the request contains a contradiction, preserve the stronger explicit intent and resolve the weaker detail into a compatible form.

Use descriptive specificity rather than generic quality words. “Brushed aluminum housing with fine horizontal grain and soft edge highlights” is more actionable than “high quality metal.” Use mood language only when it is supported by visible choices in light, palette, posture, weather, or composition.

## Shared style and composition capabilities

- **Style reference:** derive visual treatment from an image without importing its incidental subjects or layout.
- **Composition-guided generation:** use a drawing or arranged canvas as evidence for placement, scale, color zones, and hierarchy.

## Style reference method

Use the reference for visual treatment: palette, texture, medium, lighting logic, mark-making, graphic rhythm, or photographic finish. Do not import its people, objects, words, or composition unless requested.

Translate the style into visible characteristics rather than relying solely on an artist or brand name. State which content is new and which stylistic properties should carry over.

## Composition-guided generation

Treat an uploaded drawing or assembled canvas as evidence for arrangement and relative scale. Describe the intended finished medium and the semantic identity of each major shape or region. Preserve important placement while allowing rough marks to become coherent forms. If a sketch includes placeholder lettering, provide the exact finished copy in quotation marks.

## Validation checklist

- The principal subject and action appear first.
- Subject count, ownership, and relationships are unambiguous.
- Medium, environment, composition, lighting, and palette are mutually compatible.
- Important elements have explicit placement and scale.
- Every requested visible string is quoted exactly and assigned a location and hierarchy.
- The root is the caption object itself, with no wrapper or commentary.
- `compositional_deconstruction` contains `background` followed by `elements`.
- `style_description` uses exactly one of `photo` and `art_style` in the correct key order.
- Object elements use `type`, optional `bbox`, `desc`, then optional `color_palette`; text elements insert exact `text` before `desc`.
- Every bbox uses `[y_min,x_min,y_max,x_max]`, normalized to 0–1000 with valid increasing bounds.
- Hex colors are uppercase `#RRGGBB`; the overall palette has at most sixteen entries and each element palette at most five.
- Reference modes state what to preserve and what to change without importing incidental content.
- The prompt contains one definitive visual outcome rather than alternatives.
- No unwanted tool, setting, upload, or process commentary appears in the final prompt.
