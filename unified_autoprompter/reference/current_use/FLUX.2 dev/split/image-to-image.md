# FLUX.2 dev Image to Image

## Shared style, identity, and visible-text capabilities

- **Style transfer:** use a reference for visual treatment without importing incidental content.
- **Identity or character continuity:** retain defining subject identity across a new scene or edit.
- **Text editing and design generation:** render or replace exact visible copy.

## Style reference and transfer

Extract only assigned style traits: palette, contrast, texture, brushwork, lighting, grain, typography character, or layout rhythm. Keep the target subject and scene content from the base prompt or base image. If the reference style conflicts with required readability or identity, preserve the explicit content requirement first.

## Identity continuity

Bind the reference to the person or character whose identity must remain stable. Describe new pose, expression, wardrobe, setting, and camera independently. Prevent face, body, clothing, or accessory leakage between multiple people by naming ownership and placement.

## Single-reference editing

Treat the input image as the base. Describe the requested change directly and preserve unmentioned content.

- Identify the target precisely.
- State the new content or state.
- Preserve identity, composition, perspective, lighting, material, and background where relevant.
- For local edits, avoid unnecessarily redescribing the entire image.
- For broad transformations, describe the complete target while naming the source features that remain anchors.
- For text edits, use exact replacement wording and quote both strings.

## Multi-reference editing

Give each input one bounded role and state the final composition explicitly.

- Name which image supplies the base scene.
- Map each additional image to a subject, garment, object, style, background, or layout role.
- State what must not transfer from each reference.
- Describe final screen position, scale, interaction, occlusion, and lighting integration.
- Never rely on “respectively.”
- Preserve identity and ownership when several people or objects are combined.
- Prefer fewer, higher-quality references when roles begin to overlap. If several views represent the same identity, say so explicitly; otherwise treat each image as a separate source.
- Reconcile light direction and color response in the final scene rather than allowing every reference to preserve incompatible illumination.

Compact pattern:

```text
Use Image 1 as the room and camera composition. Place the chair from Image 2 beside the window and dress the woman from Image 1 in the coat from Image 3. Preserve the woman’s identity, Image 1 lighting, and Image 1 background; do not transfer the models or backgrounds from Images 2 and 3.
```
