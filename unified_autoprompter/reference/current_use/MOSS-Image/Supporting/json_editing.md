# MOSS-Image Editing Procedure

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

Identify which source is the base and which supplies an object, identity, style or layout. Use the actual source order. Express roles in plain language such as “the room in the second image” and “the vase in the first image”; use special reference tokens only if the user already establishes them. Do not invent adapter syntax.

Transfer only assigned traits. Fit transferred objects to the base scene's perspective, scale, light, shadows and contact points. Do not import an object source's background, unrelated people or lighting.

## Stage 6 — Masked editing

If a mask or selected region is supplied, write the change for that region and describe edge integration. The mask is an input constraint, not a new object in the picture.

Preserve visible boundaries and neighboring objects unless the edit requires their modification. If the requested target extends beyond the known selected region and cannot be represented faithfully, identify the mismatch before promising a complete edit.

Do not create mask coordinates or embed mask data in the image prompt. If the user separately requests a mask specification, keep that deliverable outside the prompt.

## Stage 7 — Render the layout edit prompt

Read [canvas.md](canvas.md) completely. Resolve the actual intended canvas and the target's placement from supplied evidence or a confirmed existing layout. If precise placement cannot be determined, ask for the missing image/layout or target bounds rather than inventing coordinates for an unseen source. A known source canvas alone does not establish the target rectangle.

Keep the normal MOSS structure: summary, items, bbox_coord_space and bbox_format. In summary.caption state the bounded edit and compatible scene-preservation constraints. In items describe the target's intended result, exact replacement text where applicable, and its box on the intended output canvas. Do not add an edit_instruction, source_image, mask, strength, adapter or API wrapper field.

When revising existing layout JSON, retain unchanged items, captions and boxes. Change only affected attributes unless repositioning, resizing, crop or another requested transformation requires related updates. When starting from an image rather than layout JSON, describe only reliably known content and the target; do not invent a full inventory of unseen surroundings. For removal, describe the revealed continuation in the affected region; do not leave the removed object as a visible item or retain its dependent shadow. Do not force an item for an object that no longer exists.

Apply the coordinate semantics from the JSON authoring block. Recalculate bounds on explicit resize/crop; preserve existing bounds on recoloring or text-only changes. Do not infer z-order from array order. Keep masks outside the caption. Multi-reference ownership belongs in descriptive strings, not invented control keys.

## Stage 8 — Validate the edit

Confirm the request is still I2I, the target is identifiable, the intended new state and compatible preservation requirements are explicit, no obsolete target remains, source roles are correct, and boxes use the resolved canvas. Text must be exact and JSON must parse. Keep setup notes and findings outside the prompt value.

## Example: color-only layout revision

For a user-supplied 1024-square layout with one bag box [-200,-160,240,160], recoloring to red changes the bag caption and summary but retains the box. The summary can state “Change only the bag to red; retain its material texture, shape, position and the surrounding scene.” Do not assume these example dimensions or coordinates for another source.
