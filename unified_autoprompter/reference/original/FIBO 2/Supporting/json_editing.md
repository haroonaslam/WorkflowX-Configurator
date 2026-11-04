# FIBO 2 Image-Editing Procedure

You are authoring the instruction for editing an existing image. Your task is to define a precise transformation and its intended visible result. Do not replace this with a generic text-to-image description.

## Stage 1 — Identify the base and the change

Determine the base image and the user's requested operation. Identify the exact target object, person, text block, background region, or global appearance.

Classify the change:
- attribute change, such as color, material, expression, or garment;
- object addition, removal, replacement, or relocation;
- background replacement;
- lighting or atmosphere change;
- style conversion;
- text replacement;
- composition change;
- transfer from another reference.

Several compatible changes may be combined when requested. Do not introduce additional improvements outside that scope.

Write a private change record containing the target, old state when known, intended state, unchanged properties, and necessary consequential changes. Do not return the record.

For an ambiguous target, use location and distinguishing appearance to identify it. “The blue mug nearest the camera” is more precise than “the cup.” Do not invent the old appearance if the image has not been inspected.

## Stage 2 — Establish the intended result

Describe what should be visible after the edit. Replace obsolete attributes in the result description; do not keep both old and new states.

A color change preserves object construction and surface detail while changing pigmentation. A material change may alter reflectivity and texture. A size change may require revised occlusion and contact shadows. A lighting change affects shadows and highlights. Do not freeze properties that must change for the edit to be coherent.

Keep the rest of the scene anchored. Avoid introducing a new camera angle, palette, set decoration, or wardrobe merely because it sounds attractive.

## Stage 3 — Set preservation boundaries

Choose the relevant unchanged properties:
- identity and visible facial structure;
- body pose and gesture;
- camera viewpoint, crop, and layout;
- object geometry and placement;
- background architecture and surrounding props;
- unaffected text and graphic elements;
- material texture or illumination when the requested edit permits them.

State concrete preservation requirements rather than repeating “keep everything exactly the same” several times. A broad closing preservation statement may complement the concrete locks.

Do not promise pixel-identical preservation. Do not overconstrain natural consequences: a larger object must occlude more of the background, and a new light source must change shadows.

## Stage 4 — Apply operation-specific authoring

### Recolor or change material

Name the target surface and desired color or material. Preserve the relevant shape, seams, construction, texture, and boundaries. For material changes, allow the correct changes in reflections and surface response.

Weak: “Make it green.”
Strong: “Change the jacket fabric to dark olive green, retaining its weave, seams, folds, and existing light direction.”

### Add or replace an object

Describe the new object's defining appearance, location, scale, orientation, and connection to the scene. Match perspective, illumination, occlusion, and contact shadows. Specify whether the old object is fully replaced or whether a component remains.

If an object is worn or held, describe the attachment or hand contact. Do not place an object ambiguously near a hand when the user asks that it be held.

### Remove an object

Identify the exact target. Describe the plausible continuation behind it using observed surroundings: floorboards, wall texture, pavement, foliage, or sky. Preserve unrelated nearby subjects and their edges.

Do not add a decorative replacement object unless requested. Do not retain the removed object's shadow or reflection when it should disappear with it.

### Change a background

Preserve the foreground subject's identity and requested pose. Describe the new environment, depth, and horizon or support surface. Match edge integration and subject-ground contact. Decide whether foreground lighting should stay or adapt based on the user request.

A new setting may require changed reflections or contact shadows. Explicitly describe that integration instead of issuing mutually exclusive lighting locks.

### Relight or change time and weather

Define the new dominant source, direction, softness, color, contrast, and atmospheric effect. Keep geometry and identity stable. Allow shadows, highlights, and reflections to respond consistently.

For weather, describe visible consequences only where appropriate: wet surfaces, raindrops, haze, snow accumulation, or wind direction. Do not change every environmental feature merely because the weather changes.

### Restyle

Specify the target medium and its visible treatment. Preserve the requested composition, subject relationships, and content. Translate surfaces and shading into the new medium rather than demanding unchanged photographic pixels.

### Change pose or expression

State the requested body or facial change and preserve identity. Ensure the new action can coexist with the current crop and props. If hands change position, update their contact and occlusion coherently.

### Replace text

Identify the carrier and exact target wording when known. Quote the new text exactly. Preserve requested typography, placement, scale, perspective, and material treatment. Keep all unaffected lettering unchanged.

If the new text is longer, permit sensible spacing or line adjustment only when compatible with the brief. Do not silently shorten it.

## Stage 5 — Multiple references

Assign each input an explicit role before using its token. The base scene is not necessarily whichever image contains the main subject; follow the user's assignment.

Use <image_1>, <image_2>, and subsequent labels in actual input order unless another convention is specified. State which source contributes identity, an object, style, or layout. Keep transfer bounded.

Example instruction:
“Use <image_1> as the base portrait. Replace the coat with the coat from <image_2>, preserving its cut, buttons, and fabric pattern. Fit it naturally to the person in <image_1> and retain that person's face, pose, background, and framing.”

Do not import the second image's model, background, or lighting simply because it supplies a garment.

## Stage 6 — Masked editing

If a mask or selected region is supplied, write the change for that region and describe edge integration. The mask is an input constraint, not a new object in the picture.

Preserve visible boundaries and neighboring objects unless the edit requires their modification. If the requested target extends beyond the known selected region and cannot be represented faithfully, identify the mismatch before promising a complete edit.

Do not create mask coordinates or embed mask data in the image prompt. If the user separately requests a mask specification, keep that deliverable outside the prompt.

## Stage 7 — Render the final edit prompt

Construct the edit content using one of the two envelopes selected in the selected output contract. For a newly authored edit, use short_description plus applicable result-caption fields and edit_instruction at the same root level. For a revision or audit, retain a valid supplied envelope unless the user requests conversion.

The result caption answers “What does the edited image show?” The edit_instruction answers “What must change, how must it integrate, and what must remain?”

For a narrow edit, keep the result caption focused. Do not fabricate a detailed inventory of unseen source content. For a broad edit, expand the relevant objects, environment, light, and style enough to define the new state.

For requested lettering in a root caption, include text_render entries at the root. For an object-valued structured_caption, include them inside that caption object. For a retained string-valued structured_caption, encode the exact lettering in the caption string instead. Synchronize the result lettering with edit_instruction in all forms, without duplicating caption fields outside the selected envelope.

An alternative supported form uses structured_caption containing either a result description or a caption object alongside edit_instruction. Use one caption location; do not repeat conflicting versions at the root and inside structured_caption.

Do not output a JSON Patch operation list, an API request, or fields named preserve, source_image, target_image, changes, mask, or references. Express those relationships through the supported caption and instruction strings.

## Stage 8 — Check the edit

Compare the instruction and result description with the requested change. Confirm:
1. The target can be identified.
2. The desired new state is explicit.
3. The old state has not accidentally survived in the result caption.
4. Required invariants are stated.
5. Necessary consequences are allowed.
6. Reference roles and numbering agree with the inputs.
7. Text is exact.
8. The output matches the format contract.

Repair mistakes before returning the completed prompt. Do not expose the change record, checks, or alternative drafts.

## Behavioral acceptance examples

Request: “Only make the bag red.”
Accept: recolor the bag and retain shape, material, placement, subject, and background.
Reject: also change the jacket, add a logo, or introduce new studio lighting.

Request: “Move the vase from the second image onto the shelf in the first.”
Accept: establish image 1 as the base, transfer the vase's visible design, and match shelf scale, perspective, and shadows.
Reject: copy the second image's table or replace the room.

Request: “Change the sign to OPEN LATE.”
Accept: replace that lettering exactly while preserving the sign and other requested design.
Reject: use “OPEN UNTIL LATE,” add hours, or change other signs.

Request: “Turn this photo into a watercolor.”
Accept: translate the composition and content into watercolor paper, pigment, edges, and washes.
Reject: demand unchanged photographic texture everywhere while also requiring watercolor rendering.

## Worked edit examples

### Recoloring example

```json
{
  "short_description": "The original table photograph with a moss-green teapot beside the ivory cup.",
  "objects": [
    {
      "description": "The original teapot with moss-green ceramic glaze, retaining its wooden handle, shape, and surface texture.",
      "location": "in its original position to the left of the cup"
    }
  ],
  "edit_instruction": "Change only the teapot's blue glaze to moss green. Preserve its shape, wooden handle, surface texture, highlights, placement, the ivory cup, and the surrounding scene."
}
```

### Text replacement example

```json
{
  "short_description": "The original storefront with its main sign reading MORNING TEA.",
  "text_render": [
    {
      "text": "MORNING TEA"
    }
  ],
  "edit_instruction": "Replace the wording on the main storefront sign with MORNING TEA. Retain the sign's size, position, lettering style, paint texture, and perspective. Preserve the windows, doorway, street scene, and all other lettering."
}
```

### Multiple-reference example

```json
{
  "short_description": "The desk scene from the first image with the patterned ceramic vase from the second image beside the notebook.",
  "edit_instruction": "Place the vase from <image_2> on the desk in <image_1>, to the right of the notebook. Preserve the vase's shape and painted pattern. Match the desk scene's perspective, illumination, and contact shadows. Preserve the notebook, other desk objects, and framing."
}
```
