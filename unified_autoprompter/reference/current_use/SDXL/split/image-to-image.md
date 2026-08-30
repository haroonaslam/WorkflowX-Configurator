# SDXL Image to Image

## Generation type

- **Image to image:** reinterpret an initial image while preserving an amount of its composition and structure determined by denoising strength.
- **Inpainting:** replace a masked region while keeping surrounding pixels and scene logic coherent.
- **Outpainting:** extend an image beyond its original boundary with compatible perspective, illumination, and content.

## Image-to-image method

The initial image supplies composition and visual structure in proportion to denoising strength. The prompt defines the desired denoised result.

- State which content must remain recognizable and which content should change.
- Describe the target image, not merely the editing process.
- For small changes, keep subject identity, layout, lighting direction, and perspective explicit.
- For large reinterpretations, restate the intended medium and scene while preserving only the requested structural anchors.
- Do not assume text alone can override a very low denoising strength or preserve a high-noise input exactly.

## Inpainting method

Describe the content that should occupy the mask and how it connects to its surroundings. Include scale, orientation, material, lighting, occlusion, contact shadow, and perspective. For removal, describe the background or surface that continues through the masked region. Avoid changing unmasked content in the prompt unless a local transition requires it.

## Outpainting method

Describe the continuation beyond the source boundary. Preserve horizon, vanishing point, light direction, depth, texture scale, and recurring scene elements. Add new content only when it follows naturally from the original image and requested framing.
