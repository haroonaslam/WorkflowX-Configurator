# FIBO 2 JSON — Model Authoring Rules

Use this shared field vocabulary and visual semantics when writing FIBO 2 captions. The selected generation or editing procedure determines the task; the selected output contract determines the response presentation and permitted edit envelope.

## Expand the brief

Establish the central scene and its medium. Identify the important subjects and give each one a distinct appearance, pose, action, and location. Resolve their relative scale, contact, gaze, and front-to-back order. Choose compatible environmental details, composition, light, palette, texture, and mood.

Fill missing details with coherent choices that serve the brief. Avoid adding unrelated people, signs, brands, or events. Preserve intentional simplicity. Use enough detail to make the scene clear without padding to a fixed length.

Every field must describe the same final image. Attach each attribute to its correct subject. Keep crop, viewpoint, focus, illumination, and shadows compatible. Describe one visible moment unless the user asks for a multi-panel composition.

## Shared caption structure

Use the following fields, omitting optional fields that do not serve the image:

| Field | Content |
| --- | --- |
| `short_description` | One or two sentences summarizing the final scene |
| `objects` | Array of important subjects or individually controlled elements |
| `objects[].description` | Appearance, identity, pose, action, clothing, material, and texture |
| `objects[].location` | Position and relationships in plain language |
| `objects[].relative_size` | Scale within the frame or relative to another subject |
| `background_setting` | Environment and supporting scenery |
| `lighting.conditions` | Light type, softness, intensity, and color |
| `lighting.direction` | Where the illumination comes from |
| `lighting.shadows` | Consistent shadow character |
| `aesthetics.composition` | Framing, crop, balance, hierarchy, and negative space |
| `aesthetics.color_scheme` | Palette and color relationships |
| `aesthetics.mood_atmosphere` | Mood and atmosphere |
| `photographic_characteristics.camera_angle` | Viewing position |
| `photographic_characteristics.depth_of_field` | Focus-depth treatment |
| `photographic_characteristics.focus` | Focus target and sharpness |
| `style_medium` | Photograph, watercolor, vector illustration, or other medium |
| `context` | Intended visual genre or use, when relevant |
| `artistic_style` | Rendering character |
| `text_render` | Array of objects containing exact visible lettering in a `text` string |

The dotted names indicate nested fields. Write descriptive values as strings. Use separate object entries for subjects whose attributes or placement must remain distinct. Include fine material and appearance details in their descriptions. Do not force camera and focus fields into an image style that does not need them.

Keep generation settings, image paths, masks, and unrelated metadata out of the caption. Use descriptive positions rather than bounding-box coordinates. Do not add arbitrary control fields or numerical quality scores.

## Typography

For object-form captions, put literal visible words in `text_render`, preserving language, spelling, capitalization, and punctuation. Describe the supporting sign or surface and its typography in the relevant object description. Ensure repeated references to the text agree. For an edit that retains a string-valued `structured_caption`, encode exact lettering directly in that result-description string and in `edit_instruction`; do not add a parallel root `text_render` field or change the caption type just to carry lettering.

Use separate entries for independent text elements. Escape quotation marks and line breaks inside strings. A compact text-focused prompt may contain only `short_description` and `text_render`. For that compact form, use an empty `text_render` array when the intended image has no lettering.
