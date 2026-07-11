# Anything Swap Bridge

WorkflowX bundles two paired nodes under `WorkflowX_Configurator/Image/Anything Swap`:

- `Anything Crop (for Swap)` segments or masks an object and prepares a crop.
- `Anything Stitch` composites the edited crop back into the original image.

The nodes are model-agnostic. Put a local image model, LoRA workflow, inpaint chain, or remote API between them.

## Basic Wiring

```text
Load Image -> Anything Crop -> your edit model/API -> Anything Stitch -> Save Image
                  |                                  ^
                  +------------- stitch -------------+
```

Wire `crop` into the editing path, the edited result into `swapped`, and the opaque `stitch` output directly into the matching `stitch` input. Do not decode or modify the `SWAP_STITCH` payload.

## Segmentation Modes

`use_sam3` controls how the crop mask is obtained:

| `use_sam3` | Connected mask | Behavior |
| --- | --- | --- |
| on | either | Internally load SAM3 and segment `sam3_prompt`; the connected mask is ignored. |
| off | yes | Use the connected mask. |
| off | no | Stop with a readable error. |

Internal segmentation requires a recent ComfyUI version exposing `SAM3_Detect` and a SAM3 checkpoint under `models/checkpoints`. The checkpoint contains its own text encoder. Mask-driven operation does not load SAM3.

When several objects match, `select_mode` chooses the largest mask, the highest-confidence detection, or `object_index`.

## Crop Geometry

- `expand_factor` and `expand_pixels` grow the detected bounding box.
- `force_square` makes the crop square; it is useful for face models and required by `target_size` mode.
- `padding` rounds crop dimensions to a model-friendly multiple.
- `edge_handling=shift` keeps the crop inside the source where possible.
- `pad_replicate` extends source edges and records the padding for exact removal during stitching.
- `clamp` truncates the crop at the source boundary.
- `resize_mode=none` preserves native pixels. `target_size` and `max_dimension` prepare a fixed-size model input.

The crop node accepts one source image, not an image batch. SAM3 masks may contain multiple detected objects; that object dimension is handled through `select_mode`.

## Crop Outputs

| Output | Purpose |
| --- | --- |
| `crop` | Region passed to the editing model or API. |
| `crop_mask` | Object mask in crop coordinates, optionally blurred. |
| `swap_prompt` | Prompt with `{target}`, `{width}`, `{height}`, and `{caption}` tokens replaced. |
| `source_masked` | Preview or inpaint input with the selected object blanked. |
| `stitch` | Exact original image, geometry, mask, and resize metadata for `Anything Stitch`. |
| `detected` | False when segmentation or the supplied mask found nothing. |

If no object is detected, the stitch node passes the original image through unchanged and returns an empty changed mask.

## Stitch Controls

`size_mismatch` controls edited crops whose resolution differs from the crop sent out:

- `resize`: accept a different resolution when its aspect ratio still matches.
- `stretch`: accept an aspect-ratio change and resize with distortion.
- `error`: require the exact outgoing dimensions.

`mask_mode` controls the composite area:

- `payload_mask`: use the original detected object shape.
- `full_rect`: composite the complete crop rectangle.
- `override`: use a connected crop-space `mask_override`.

The override mask must be based on `crop` or `crop_mask`, not on the full source image. `feather` softens the final composite boundary. Colour matching always uses the original hard object mask so background pixels do not dominate its statistics.

The `changed_mask` output is in source-image coordinates. Pixels where that mask is zero remain bit-identical to the source.

## Common Recipes

- Face replacement: prompt `face`, enable `force_square`, and use the target resolution expected by the face model.
- Generic object replacement: leave `force_square` off and begin with `resize_mode=none`.
- Wider blend: grow `crop_mask`, connect it to `mask_override`, choose `override`, and let `feather` soften the edge.
- Manual selection: disable SAM3 and connect a mask drawn or generated elsewhere.
- Conditional execution: use `detected` to bypass the editing branch when no object is found.

## Troubleshooting

- `SAM3_Detect not found`: update ComfyUI or disable internal SAM3 and connect a mask.
- Checkpoint has no text encoder: select a SAM3 checkpoint rather than a diffusion checkpoint.
- Aspect mismatch: make the original crop square or set `size_mismatch=stretch` only if distortion is acceptable.
- Wrong override placement: build the override from crop-space outputs.
- Old sockets on an existing canvas node: restart ComfyUI, hard refresh, then recreate or use WorkflowX's node replacement action.

The bundled implementation preserves the original `AnythingCropForSwap`, `AnythingStitch`, and `SWAP_STITCH` identifiers so existing workflows continue to resolve them.
