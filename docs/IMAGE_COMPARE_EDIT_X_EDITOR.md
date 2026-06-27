# Image Compare Edit X Editor Guide

`Image Compare Edit X` is a WorkflowX image comparison node with an expanded in-node editor. It accepts two image inputs, previews them as Image 1 and Image 2, and lets you create an edited in-node Image 3 without adding Image 3 as a graph output.

Image 3 can be compared, copied, downloaded, or saved to ComfyUI output from the node UI.

## Main Node View

The compact node view is for fast comparison and save/copy actions.

Source controls:

- `Source A`: choose Image 1, Image 2, or Image 3.
- `Source B`: choose Image 1, Image 2, or Image 3 for compare modes.
- `Swap A/B`: exchange the two selected sources.

View modes:

| Mode | Behavior |
| --- | --- |
| `Single` | Shows Source A only. |
| `Split` | Shows Source A and Source B in a wipe split. |
| `Overlay` | Draws Source A over Source B using the opacity slider. |
| `Difference` | Shows pixel difference between Source A and Source B. |

Split orientations:

- `Left/Right`
- `Right/Left`
- `Up/Down`

Save/copy behavior:

- In `Single`, save/copy targets Source A.
- In compare modes, save/copy defaults to Image 3.
- `Save O#` writes to ComfyUI output.
- `Save D#` downloads through the browser.
- `Copy #` copies to the clipboard.

## Image 3

Image 3 is the editor composite made from:

- current top/under source order
- top image opacity
- blend mask paint
- adjustment layers
- adjustment brush masks
- curves and other adjustment values

Image 3 is stored in browser-side node state and is not emitted as a downstream graph output. Use `Save O3`, `Save D3`, or `Copy 3` when you want to keep the edited result.

If Image 1 and Image 2 have different sizes, Image 3 uses the under layer's native canvas size. The top image is aspect-fit and centered.

## Expanded Editor

Click `Open Editor` to enter the large editor workspace.

The editor has four main areas:

- top bar: current/before preview, fast/quality preview, zoom, fit, undo, redo, close
- left panel: compare settings, adjustment controls, curves, image metadata
- center canvas: live Image 3 composite
- right panel: layers, brush controls, save/copy controls

## Preview Controls

Top bar controls:

| Control | Behavior |
| --- | --- |
| `Current` | Shows the edited Image 3 composite. |
| `Before` | Shows the base top/under composite without blend mask or adjustment layers. |
| `Fast` | Uses a capped preview canvas during interaction, then refreshes full quality when idle. |
| `Quality` | Keeps full-resolution preview behavior during interaction. |
| `Fit` | Fits Image 3 into the editor stage. |
| `100%` | Returns editor zoom to 100%. |
| `+` / `-` | Zoom in and out. |
| `Undo` / `Redo` | Document-level history for layer changes, brush strokes, masks, and adjustments. |

`Before` is preview-only. Save/copy always uses the current final Image 3, not the before preview.

## Layers Panel

The Layers panel controls source order, adjustment layers, mask preview, and top-layer opacity.

Layer rows:

| Row | Meaning |
| --- | --- |
| `Adjustments` | One or more adjustment layers above the image blend. |
| `Blend Mask` | The mask that reveals the under image through the top image. |
| `Top Image` | Current top image source and opacity. |
| `Under Image` | Current base image source. |

Layer buttons:

- `V`: layer visibility. For adjustment layers, this controls whether the layer affects Image 3.
- `M`: mask preview visibility. This only controls colored mask tint overlays in the editor.

The `V` and `M` buttons are intentionally separate:

- `V` changes final Image 3.
- `M` changes only what mask tint you see while editing.

## Mask Preview

Mask preview is view-only. It does not change mask data and never appears in saved/copied Image 3 output.

Controls:

| Control | Behavior |
| --- | --- |
| `Masks On` / `Masks Off` | Global show/hide switch for all mask tint overlays. |
| `Selected` | Show only the active mask context. |
| `All` | Show enabled blend and adjustment masks together using distinct colors. |

Selected mode:

- If `Blend Brush` is active, the editor shows the blend mask.
- If `Adjustment Brush` is active, the editor shows the selected brush adjustment layer mask.

All mode:

- Shows the blend mask if its `M` icon is enabled.
- Shows every brush adjustment layer mask whose `M` icon is enabled.
- Draws the selected adjustment layer mask brighter and last so it remains readable.

## Blend Mask

The blend mask controls how Image 1 and Image 2 are mixed.

Mask semantics:

- mask value `0`: normal top-over-under blend
- mask value `1`: reveal the under image fully at that pixel
- partial values: partially reveal the under image

Use `Blend Brush` to paint reveal areas. Use `Eraser` to remove reveal paint and restore normal top-over-under blending.

## Brush Panel

Brush panel controls apply to the active brush target.

Targets:

| Target | Behavior |
| --- | --- |
| `Blend Brush` | Paints or erases the blend/reveal mask. |
| `Adjustment Brush` | Paints or erases the selected brush adjustment layer area. |

Tools:

| Tool | Behavior |
| --- | --- |
| `Brush` | Adds paint to the active mask. |
| `Eraser` | Removes paint from the active mask. |
| `Pan` | Moves the canvas view. |

Brush sliders:

| Slider | Range | Meaning |
| --- | --- | --- |
| `Size` | 1-300 | Brush diameter in image pixels. |
| `Hardness` | 0-100 | Full-strength core size. Lower values soften the center. |
| `Feather` | 0-100 | Edge falloff width. Higher values create a wider fade to the edge. |
| `Opacity` | 0-100 | Maximum alpha applied by a stroke. |
| `Flow` | 1-100 | Paint buildup rate while stroking. |

The editor cursor shows the brush size ring and full-opacity core ring.

Brush actions:

| Action | Behavior |
| --- | --- |
| `Reset Area` | Clears the active mask target. |
| `Invert Area` | Inverts the active mask target. |

Reset and invert affect only the active target: the blend mask or the selected adjustment layer mask.

## Adjustment Layers

Adjustment layers sit above the blended image composite.

Layer actions:

| Action | Behavior |
| --- | --- |
| `Add Global` | Adds an adjustment layer that affects all of Image 3. |
| `Add Brush` | Adds an adjustment layer that affects only painted brush areas. |
| `Duplicate` | Copies the selected adjustment layer. |
| `Delete` | Deletes the selected adjustment layer. |
| `Reset Layer` | Resets selected layer adjustments, curves, amount, preset, and mask. |
| `Clear All` | Removes all adjustment layers. |

Adjustment mode:

| Mode | Behavior |
| --- | --- |
| `Global` | Layer adjustments apply across the entire Image 3 composite. |
| `Brush` | Layer adjustments apply only where that layer's adjustment mask is painted. |

Switching a layer between `Global` and `Brush` changes that selected layer only. A brush mask is preserved when switching to `Global`; it is simply ignored until the layer returns to `Brush`.

Adjustment controls include:

- preset chips
- layer amount
- brightness
- contrast
- exposure
- highlights
- shadows
- whites
- blacks
- saturation
- vibrance
- temperature
- tint
- hue
- sharpness
- clarity
- grain
- vignette
- fade

## Curves

Curves are part of the selected adjustment layer.

Channels:

- `RGB`
- `Red`
- `Green`
- `Blue`

Curve behavior:

- Click or drag the curve line to add a point.
- Drag points to reshape the curve.
- Right-click an inner point to delete it.
- Endpoints remain constrained.
- `Reset Channel` resets the current channel.
- `Reset All` resets RGB, Red, Green, and Blue.

Options:

| Control | Meaning |
| --- | --- |
| `Type` | Curve interpolation mode. |
| `Strength` | How strongly the curve affects the selected layer. |
| point text field | Direct point list for the active channel. |

Curves follow the selected adjustment layer's mode:

- Global adjustment layer: curve applies globally.
- Brush adjustment layer: curve applies only where the layer's adjustment mask is painted.

## Save / Copy

Save and copy actions use the final Image 3 composite:

- source order
- top opacity
- blend mask
- adjustment layers
- adjustment masks
- curves

Mask preview tint overlays are never included.

Actions:

| Action | Behavior |
| --- | --- |
| `Save O3` | Save Image 3 to ComfyUI output with workflow metadata. |
| `Save D3` | Download Image 3 through the browser. |
| `Copy 3` | Copy Image 3 to the clipboard. |
| `Clear Editor Cache` | Clear browser-side preview/render caches without removing masks, layers, or workflow state. |

## Cache And Persistence

The editor reuses browser-side canvases for performance. It does not create numbered Image 3 files while you paint or adjust. Image 3 becomes a file only when you explicitly save/download it.

Persisted workflow state includes:

- compare sources and mode
- layer order
- top opacity
- blend mask data
- brush settings
- adjustment layers
- adjustment brush masks
- curve state
- mask preview preferences
- editor zoom and pan
- performance mode

`Clear Editor Cache` only clears transient render caches. It does not delete masks, adjustment layers, or saved workflow state.

## Practical Workflow

1. Connect `image1` and `image2`.
2. Run the graph so the node receives both source images.
3. Use the compact node view for quick compare modes.
4. Open the editor.
5. Choose which image is on top in the Layers panel.
6. Paint with `Blend Brush` to reveal the under image.
7. Add global or brush adjustment layers as needed.
8. Use `Current` / `Before` to compare the edit against the base composite.
9. Use `Save O3`, `Save D3`, or `Copy 3` when the Image 3 result is ready.
