# Krea 2 Common Rules and Guide

## Purpose and model scope

Write Krea 2 prompts as detailed natural-language visual descriptions. Preserve the user’s intent, enrich it with coherent subject, scene, composition, camera, lighting, color, material, and aesthetic detail, and keep visible text exact.

For natural output, use one expanded paragraph. For structured output, express the same semantic prompt as one JSON object with an explicit compositional decomposition and normalized bounding boxes.

## Prompt-output hygiene

- Preserve the user’s central idea, subject, and requested style.
- Do not return analysis, alternatives, or generation parameters.
- Avoid keyword soup, weighting syntax, and contradictory style stacks.
- Put visible text in quotation marks and preserve it exactly.
- Add detail to complete the image, not to replace the user’s idea with a different concept.

## Prompt expansion philosophy

Expansion should make a sparse request production-ready while retaining its semantic center. Infer missing details only when they support visual coherence. Do not invent named characters, brands, stories, text, or culturally specific claims without evidence.

Keep the description organized. Each sentence or clause should clarify subject, action, environment, composition, light, color, texture, atmosphere, or finish.

## Subject definition

Describe subject count, visible appearance, action, pose, expression, clothing, and distinguishing features. For several subjects, define relationships, screen positions, gaze, contact, and object ownership.

Use observable behavior instead of abstract emotion. Describe posture, face, gesture, tension, gaze, and movement.

## Scene and production design

Specify location, time, weather, architecture, landscape, props, surfaces, and background activity. Keep the setting causally and aesthetically compatible with the subject.

For stylized imagery, extend production design through shape language, recurring motifs, set dressing, costume, and material choices rather than relying only on a genre label.

## Composition and camera

Describe shot scale, camera height, viewpoint, lens character, crop, focal hierarchy, depth layers, and negative space. State important placements and relationships directly.

For photography, use plausible capture language. For illustration or design, translate camera concepts into viewpoint, framing, hierarchy, and spatial organization.

## Style and medium

Name the medium or aesthetic, then explain its visible properties: mark-making, surface, grain, color process, edge treatment, contrast, era, or production finish. Keep one dominant visual language with compatible supporting influences.

Krea 2 is built for aesthetic range, so prompts may be expressive, but poetic language should still resolve into visible choices.

## Lighting, color, and atmosphere

State light source, direction, quality, contrast, and temperature. Define a deliberate palette and how it distributes across subject and environment. Add atmosphere through haze, rain, dust, reflections, smoke, bloom, or practical light only when physically coherent.

## Materials and texture

Describe important surfaces and their response to light: polished chrome, chalky plaster, translucent fabric, glossy lacquer, coarse paper, worn leather, wet pavement, or soft skin texture. Material detail should reinforce scale and realism or clarify the chosen medium.

## Typography

Place exact visible strings inside quotation marks. State location, scale, hierarchy, alignment, font character, color, and material relationship. Do not invent additional wording. Keep copy length appropriate for the composition.

## Structured JSON layout

The structured representation preserves the same Krea 2 visual semantics while separating scene-wide and spatial information. Return the JSON object itself with these keys in order:

1. `description`: complete final visual description;
2. `style`: medium and coherent aesthetic direction;
3. `composition`: framing, viewpoint, depth, balance, and focal hierarchy;
4. `compositional_deconstruction`: background and ordered elements;
5. `lighting`: source, direction, quality, color, contrast, and shadow behavior;
6. `color_and_materials`: palette, surfaces, textures, and material response.

Inside `compositional_deconstruction`, put `background` before `elements`. Use `"type": "obj"` for every subject or non-text object and `"type": "text"` only for visible lettering. Text elements preserve the literal string in `text`; both types use `description` for their visual description.

### Krea 2 bounding boxes

Krea 2 layout boxes use normalized coordinates from 0 to 1000 with the origin at the top-left. The coordinate order differs from the Ideogram 4 structured caption:

```text
[x_min, y_min, x_max, y_max]
```

`x` measures horizontal position from left to right and `y` measures vertical position from top to bottom. Require `0 <= x_min < x_max <= 1000` and `0 <= y_min < y_max <= 1000`.

Use a box for the intended occupied rectangular region. Do not swap the axes, use pixel coordinates, or place normalized values outside 0–1000. Omit a text element when no visible text is requested.

### Complete structured template

```json
{
  "description": "complete final Krea 2 visual description",
  "style": "medium and coherent aesthetic direction",
  "composition": "framing, viewpoint, depth, balance, and focal hierarchy",
  "compositional_deconstruction": {
    "background": "setting, foreground, background, and atmosphere",
    "elements": [
      {
        "type": "obj",
        "bbox": [0, 0, 1000, 1000],
        "description": "subject or object"
      },
      {
        "type": "text",
        "bbox": [0, 0, 1000, 1000],
        "text": "EXACT VISIBLE TEXT",
        "description": "typography and placement"
      }
    ]
  },
  "lighting": "source, direction, quality, color, contrast, and shadow behavior",
  "color_and_materials": "palette, surfaces, textures, and material response"
}
```

The full-frame boxes demonstrate coordinate order only. Replace them with composition-specific boxes or omit them when exact placement is not requested.

## Detail scaling

Match detail to framing:

- close views benefit from skin, eyes, material weave, edge detail, and subtle light transitions;
- medium views benefit from posture, wardrobe, props, and nearby environment;
- wide views benefit from layout, architecture, landscape, atmosphere, and background motion.

Do not add microscopic detail to a distant subject or omit composition from a large scene.

## Failure repairs

- **Too short:** add scene, framing, light, material, and atmosphere while preserving intent.
- **Too generic:** replace quality adjectives with specific visual properties.
- **Overloaded:** select one focal subject, one dominant action, and one coherent style.
- **Attribute leakage:** attach every color, garment, prop, and action to its owner.
- **Flat image:** strengthen viewpoint, depth, hierarchy, and light direction.
- **Typography drift:** use one exact quoted string and precise placement.
- **Style contradiction:** retain the dominant requested medium and remove incompatible treatments.
