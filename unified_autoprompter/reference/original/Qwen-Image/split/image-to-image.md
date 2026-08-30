# Qwen-Image Image to Image

## Generation type

- **Single-image editing:** modify, add, remove, replace, restyle, restore, inpaint, or outpaint one image.
- **Multi-image editing:** combine or transfer clearly assigned content among several images.
- **Identity-sensitive human editing:** change selected attributes while preserving the person’s defining visual identity.

## Direct image-editing principles

Editing prompts should be direct, specific, and operational. Name the source image when several images exist, identify the target, state the requested change, and preserve everything else that matters.

If an instruction is vague, add only the minimum sufficient category, color, size, orientation, position, or material detail. If it is contradictory or physically impossible, resolve it into one feasible operation while preserving the stronger intent.

## Add, delete, and replace

- **Add:** identify the new object, quantity, location, scale, orientation, and interaction with the scene.
- **Delete:** identify exactly what is removed and describe the surface or content revealed behind it.
- **Replace:** use direct wording such as “Replace Y with X,” then describe the defining visual properties of X and what surrounding content remains unchanged.
- Ignore meaningless operations such as adding zero objects rather than producing nonsensical prompt text.

Compact example:

```text
Replace the red plastic chair beside the desk with a low walnut reading chair upholstered in olive fabric; preserve the person, window light, camera position, and the rest of the room unchanged.
```

## Human identity editing

Preserve the person’s defining visual consistency unless the request explicitly changes it: apparent identity, facial structure, age presentation, hair, expression, body proportions, and clothing. When changing one attribute, name both the change and the important retained traits.

Expression, beauty, and makeup changes should be physically coherent with the source. Do not exaggerate them unless explicitly requested. Avoid allowing an added style reference to replace the source person’s identity.

## Inpainting and outpainting

For inpainting, state that the selected region is being filled and describe the intended content and its relationship to the original scene. For outpainting, describe the extension beyond the boundaries and preserve perspective, lighting, texture, and environmental continuity.

Keep the operation explicit rather than disguising it as ordinary generation.

## Multi-image editing

- Refer to each image consistently by number.
- State which image supplies the editable base.
- Give every other image one bounded role: subject, garment, object, pose, style, background, or composition.
- State which source attributes must not transfer.
- Never rely on “respectively”; map each target explicitly.
- For replacement, distinguish the source of the replacement from the image whose background or layout should remain.
- For stylization, extract style properties from the style image while preserving visual content from the base.

Compact example:

```text
In Picture 1, replace the seated woman’s jacket with the blue embroidered jacket from Picture 2; preserve the woman’s identity, pose, hands, Picture 1 background, and Picture 1 lighting.
```

## Image-edit method

1. Identify task type and base image.
2. Name the exact target and direct operation.
3. Bind each additional image to one role.
4. Specify necessary visual details and physical integration.
5. State preservation constraints.
6. Return only the direct edit instruction.
