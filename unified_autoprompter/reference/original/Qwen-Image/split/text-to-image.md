# Qwen-Image Text to Image

## Generation type

- **Text to image:** generate a complete image from text.

## Text-to-image prompt enhancement

### Preserve intent while completing the image

Retain the original main content, including subject, action, setting, and requested style. When the input is short, add coherent details that make the image visually complete without changing its premise.

### Complete subject definition

Specify count, visible appearance, pose, expression, clothing, distinguishing features, and relationships where relevant. Avoid adding demographic, identity, or narrative details that are not visually necessary. Keep attributes attached to the correct subject.

For people, make pose physically legible: head direction, torso orientation, weight distribution, arm position, hand action, gaze, and expression. Describe hands through what they are doing or touching rather than adding generic anatomy-quality language. When clothing matters, bind garment type, material, color, pattern, fit, and layer to the correct person.

### Scene and background

Describe location, time, weather, surfaces, props, depth layers, and background activity. The environment should support the subject rather than introduce a competing story.

### Composition and camera

State shot scale, viewpoint, camera angle, focal hierarchy, crop, depth of field, and major placements. Use explicit spatial language for multi-subject scenes: left/right, foreground/background, facing, overlapping, holding, behind, above, or centered beneath.

### Style, lighting, and material

Name the medium or visual treatment, lighting source and direction, palette, texture, and atmosphere. Added details must remain compatible with the requested scene and style.

### Visible text

- Put every requested visible string inside straight double quotation marks.
- Keep its original language, capitalization, punctuation, and numerals.
- Preserve requested line breaks, horizontal or vertical writing direction, and reading order.
- State its carrier and rendering method—such as printed on paper, embroidered on fabric, painted on a wall, shown on an LED display, or formed as neon.
- State its position and design role: headline, subtitle, label, logo, slogan, caption, or decoration.
- Describe font character, weight, size hierarchy, color, alignment, outline, stroke, and shadow when those properties matter.
- Explain its spatial relationship to nearby people and objects when the text is held, worn, projected, attached, or partially occluded.
- When the user asks for generic information such as a name and date without specifying the actual strings, choose concrete text only when doing so preserves intent; otherwise request clarification rather than producing placeholder copy.
- Do not rewrite the quoted content during enhancement.

## Text-to-image method

1. Preserve the central intent and quoted text.
2. Complete subject appearance, action, and relationships.
3. Establish environment, composition, camera, and depth.
4. Add compatible style, lighting, color, texture, and atmosphere.
5. Remove ambiguity and contradictions.
6. Return only the enhanced prompt.
