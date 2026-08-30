# SDXL Common Rules and Guide

Use clear concept ordering, compatible descriptive modifiers, and an explicit negative prompt. Prefer ordinary visual description over densely constrained typography, complicated spatial logic, or overloaded multi-subject arrangements.
## Prompt-output hygiene

- Keep generation parameters out of the visual description.
- Preserve trigger tokens, embedding names, LoRA activation phrases, and exact user terminology when supplied.
- Prefer one coherent visual direction over mutually exclusive styles, lenses, times of day, or lighting systems.
- Do not claim exact text rendering when the request depends on typography SDXL cannot reliably reproduce.
- Do not use excessive generic quality tags as a substitute for scene content.

## Positive prompt construction

### Concept priority and ordering

Put the defining subject and action first. Follow with environment, composition, medium, lighting, color, materials, mood, and finishing detail. Early concepts usually carry stronger semantic importance, so do not bury the essential subject behind a long style preamble.

For multiple subjects, state count, identity, action, position, and interaction in connected prose. Keep modifiers near the noun they modify. Avoid ambiguous pronouns when attributes could transfer between people or objects.

### Subject and action

Describe visible identity, silhouette, clothing, pose, expression, gaze, and action. Replace abstract labels with observable cues. If anatomy or hands are prominent, describe the hand action and contact point rather than relying only on negative terms.

### Environment and depth

Specify location, time, weather, background elements, surfaces, and depth layers. Establish foreground, middle ground, and background when spatial clarity matters. State relative placement such as left, right, centered, behind, in front of, above, or partially occluding.

### Composition and camera

Use photographic language when appropriate: wide establishing shot, medium portrait, close-up, macro, low angle, overhead, eye level, shallow depth of field, telephoto compression, wide-angle perspective, leading lines, symmetry, negative space, or off-center framing. Do not combine incompatible lens or viewpoint descriptions.

### Medium and style

Name the intended medium and treatment directly: editorial photograph, cinematic still, watercolor, oil painting, screen print, concept art, 3D render, anime illustration, charcoal drawing, or another coherent form. Add a limited set of compatible art-direction cues such as brushwork, film stock character, paper texture, color process, or production era.

### Lighting and color

Describe source, direction, quality, contrast, and temperature: soft window light from camera left, hard noon sunlight, warm practical lamps, cool overcast skylight, neon rim lighting, or diffused studio illumination. Use a coherent palette and avoid contradictory temperature or shadow descriptions.

### Detail and finish

Add materials, surface texture, atmospheric effects, and fidelity-critical details last. Specific visual detail is more useful than repeated words such as masterpiece, best quality, ultra detailed, or award winning.

## Prompt weighting and multiple prompts

SDXL can blend separately weighted text prompts. Use weighting only when a concept needs intentional emphasis or suppression; do not weight every phrase. Keep weighted concepts semantically compatible. A negative weight or negative prompt should describe what to avoid, while the positive prompt states the desired content.

When explicit weighting syntax is selected, keep nesting shallow and ensure literal punctuation is not mistaken for weighting. Do not invent a weighting grammar when none is specified.

Use modest emphasis when `(phrase:weight)` syntax is selected. Values around `1.1` to `1.3` are a practical starting range rather than a universal contract; weights around or above `1.5` can distort composition or image quality. Omit numeric weighting when no weighting syntax is specified.

## Prompt clarity and priority

Place indispensable subject, action, and composition information early. Prefer precise visual language over inherited SD 1.5 tag boilerplate. Organize additional detail by priority and avoid repeating the same quality or style language.

## Known prompt limitations

- Complex object-on-object relationships can drift; simplify and state relations explicitly.
- Dense crowds, many simultaneous actions, and exact counts are harder than one clear focal event.
- Faces and hands benefit from explicit action, framing, and relevant negative guidance.
- The model is not a factual renderer; prompts should describe the intended image rather than assert documentary truth.

## Validation checklist

- The subject and action are unmistakable.
- Modifiers attach to the correct subject.
- Composition, viewpoint, lens feel, and depth agree.
- Lighting direction, temperature, shadows, and palette are coherent.
- Positive and negative prompts do not contradict one another.
- Image-conditioned modes identify preservation and change targets.
- Trigger tokens and exact user terms remain intact.
- Generation settings are not presented as visible content.
