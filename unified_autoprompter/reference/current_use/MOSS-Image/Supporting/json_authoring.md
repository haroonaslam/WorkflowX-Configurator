# MOSS-Image JSON — Model Authoring Rules

You turn the user's description or reference image into a finished MOSS-Image layout JSON prompt. Expand the scene, arrange the elements, calculate their bounding boxes, and write the complete JSON yourself.

## Scene construction

Plan the composition around the principal subject and its relationship to other elements. Put the overall medium, setting, light, palette, and mood in `summary.caption`. Give independently positioned subjects and text their own `items` entries. Describe continuous scenery in the overall caption rather than creating a box for every minor detail.

Expand missing details with compatible visual choices. Keep each subject's appearance, action, and location consistent across the prompt. Distinguish multiple subjects clearly. Describe one visible moment. Use exact counts when requested, and leave enough space for important limbs, objects, and lettering.

## JSON structure

Use these fields:

- `summary.meta`: an array of short medium descriptors, such as `"photograph"` or `"poster"`.
- `summary.canvas`: `"single"`.
- `summary.caption`: a complete description of the overall image.
- `items`: an array of individually placed elements.
- `items[].label`: `"object"` for pictorial elements or `"text"` for lettering.
- `items[].caption`: the element's appearance, action, material, or typography.
- `items[].text`: the exact lettering for text elements; omit for ordinary objects.
- `items[].bbox`: four numbers in `[y_min, x_min, y_max, x_max]` order.
- `bbox_coord_space`: `"abs_centralized"`.
- `bbox_format`: `"yxyx"`.

Use this structure directly. Do not add generation settings, image paths, extra metadata, or fields from another model's JSON format.

## Canvas and coordinates

Use the validated width W and height H resolved by [canvas.md](canvas.md). Use that same canvas for every box; the formulas below define only coordinate conversion, not canvas selection.

Coordinates are absolute pixels measured from the canvas center. X increases rightward and Y downward. Valid X bounds run from `-W/2` to `W/2`; Y bounds run from `-H/2` to `H/2`.

For a conventional top-left-origin box `[left, top, right, bottom]`, calculate:

```text
[top - H/2, left - W/2, bottom - H/2, right - W/2]
```

For example, on a 1024 by 1024 canvas, `[128, 64, 896, 224]` becomes `[-448, -384, -288, 384]`. On a 1536 by 1024 canvas, `[160, 256, 704, 896]` becomes `[-256, -608, 384, -64]`.

Use width and height independently. Recalculate all boxes when dimensions change. Ensure every box has positive width and height and fits the canvas unless intentional clipping is requested. Overlap boxes only when the visual elements should overlap; describe the intended front-to-back relationship in their captions.

## Text and object descriptions

Describe subjects with enough detail to preserve their identity, pose, materials, orientation, and relationship to nearby elements. Keep global lighting consistent with local descriptions. Do not repeat the whole scene in every caption.

For text, preserve wording exactly in `text`. Use the item's `caption` for font appearance, alignment, color, contrast, and scale. Use separate items for independently placed text. Encode intended line breaks with `\n`. Allocate sufficient box space for the wording without silently shortening it.

Use valid JSON with double-quoted keys and strings. Escape embedded quotation marks. Keep all required subjects and text consistent within the object.
