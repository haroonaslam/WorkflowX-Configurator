# Image ProcessorX Guide

`Image ProcessorX` is a fully independent evolution of `Image Compare Edit X`. It keeps its own Python renderer, frontend editor, state namespace, styles, events, and HTTP routes. Changes to either node do not change the other node's implementation.

## Node Contract

The node is registered as `WorkflowX_ImageProcessorX`, displayed as `Image ProcessorX`, and found under `WorkflowX/Image Compare`.

Inputs:

| Input | Required | Default | Purpose |
| --- | --- | --- | --- |
| `image1` | yes | - | Primary source and O1. |
| `image2` | no | disconnected | Optional comparison/composition source and O2. |
| `operation_mode` | yes | `Continue` | Choose immediate execution or an interactive pause. |
| `output_image` | yes | `O1` | Choose O1, O2, or rendered O3 for the downstream output. |
| `processor_state` | internal | `{"schemaVersion":1}` | Serialized editor and renderer state. |

The single output is `image` (`IMAGE`). O1 and O2 are returned without re-rendering or changing their tensor or batch. Selecting O2 without a connected `image2` is an execution error; the saved selection remains visible so the workflow is not silently changed.

## One-Image Mode

With only `image1` connected, O1 is the original and O3 is the processed image. The compact compare UI can use O1 and O3 in Single, Split, Overlay, and Difference views.

The editor keeps adjustment layers, RGB curves, global and brush masks, histogram, processing controls, save, download, and copy. Controls that require a second source are unavailable:

- O2 as a usable source or output
- top/under source order
- inter-image opacity
- blend-mask painting

If an older workflow still selects O2, the selection is retained and marked unavailable. Compare-only references warn that O2 is missing; an O2 workflow output is blocked until `image2` is connected or another output is selected.

## Two-Image Mode

Connecting `image2` enables the full comparison and composition workflow. O3 uses the selected top/under order, bilinear aspect-fit placement, top opacity, blend mask, ordered adjustment layers, curves, and adjustment brush masks.

The browser renderer provides the live editor preview. The Python renderer is authoritative for the graph output and follows the same normalized state, layer order, clamp/rounding behavior, and deterministic grain seed.

A deterministic cross-engine fixture exercises every adjustment plus cubic RGB/channel curves. Identity and O1/O2 pass-through paths require exact equality; processed fixture pixels permit at most one 8-bit channel value of platform rounding difference.

## Continue Mode

Continue processes the snapshot serialized when the workflow is queued:

- O1 returns `image1` unchanged.
- O2 returns `image2` unchanged and errors if it is absent.
- O3 runs the backend renderer and sends the result downstream.

Continue mode needs no connected browser. Normal ComfyUI caching includes the upstream images, selected output, and serialized processor state.

## Pause Mode

Pause mode always executes instead of using a cached result. When the queue reaches the node:

1. The backend creates an unguessable request token and stores a pending asynchronous session.
2. The node emits a pause event containing the token, node ID, image availability, and fresh temporary previews.
3. The compact node is marked **Paused** and enables **Resume** and **Cancel**. The expanded editor also exposes the output selector, **Resume**, and **Cancel Run** in its top bar.
4. Open the editor only if you want to adjust the image.
5. Choose O1, O2, or O3 and press **Resume**. The latest editor state and output selection are submitted to the waiting execution.

The pause has no timeout and does not re-run upstream nodes. Reloading or reconnecting the browser restores pending state through the status route. **Cancel** releases the pending session and ends that node execution with a clear cancellation message.

## Processing Order

For O3, Image ProcessorX applies processing in this order:

1. Prepare the O1 base, or aspect-fit and composite O1/O2 using source order, opacity, and blend mask.
2. Apply enabled adjustment layers in their saved order.
3. For each layer, apply brightness, contrast, exposure, highlights, shadows, whites, blacks, saturation, vibrance, temperature, tint, hue, sharpness, clarity, grain, vignette, and fade.
4. Apply the layer's linear or cubic RGB/R/G/B curves.
5. Blend the layer globally or through its decoded brush mask and amount.

Grain uses a deterministic seed, so the same images and serialized state produce the same result.

## Batches and Dimensions

The compact preview uses the first item in each still-image batch. O3 applies the same state to every output item.

- Equal batch sizes pair item by item.
- A one-item input broadcasts across the other batch.
- Other batch-size mismatches raise a clear error.
- O1 and O2 pass-through retain the original batch exactly.

When source dimensions differ, the top image is bilinearly resized to fit within the base canvas while preserving aspect ratio and is centered on that canvas.

## State and Validation

`processor_state` is a JSON object with `schemaVersion: 1`. It stores compose settings, compare state, editor preferences, masks, brush state, adjustment layers, and curves. The backend:

- rejects malformed JSON and unsupported schema versions
- supplies defaults for missing supported fields
- clamps numeric fields to supported ranges
- ignores unknown fields for forward compatibility

The browser maintains one authoritative state snapshot for the node. Committed editor changes are written to the hidden state widget and workflow properties automatically. Live mask canvases are flushed before image replacement, workflow serialization, editor close, Save, and Pause Resume, so changing an upstream image or reopening a workflow applies the same editor recipe to the new image.

If replacement images use different dimensions, blend masks and adjustment-brush masks are proportionally resampled to the new O3 canvas. Removing `image2` does not delete its blend opacity, order, mask, or source selections; those settings remain dormant until a second image is connected again.

## Reset and Editor Presets

The expanded editor top bar provides **Reset** and **Presets**:

- **Reset** restores every editor setting to its default after confirmation. It retains connected images, Continue/Pause mode, selected node output, and any pending Pause session. Reset is one undoable editor action.
- **Presets** opens the named preset library. **Save As** captures the complete editor recipe, **Load** replaces the current recipe as one undoable action, and **Delete** removes the selected preset. Overwrite and delete require confirmation.

Named presets are stored in the current ComfyUI user's userdata and are reusable across Image ProcessorX nodes and workflows. Browser local storage is used only when the ComfyUI userdata API is unavailable. The active state of each node is still embedded in its workflow independently of the preset library.

Preset files include composition order and opacity, blend masks, comparison controls, brush settings, every global/brush adjustment layer, curves, layer masks, preview preferences, and editor viewport settings. They deliberately exclude connected image references, image availability, Continue/Pause mode, output routing, pending sessions, undo history, and render caches. Loading a two-image preset in single-image mode retains the unavailable image-2 settings until `image2` is connected.

## Save and Session Routes

All routes are private to Image ProcessorX under `/workflowx_configurator/image_processor_x/`:

- `save` writes a PNG to ComfyUI output with available workflow metadata.
- `prepare` returns a metadata-bearing PNG for browser download.
- `continue` submits the latest output and processor state to a pending session.
- `cancel` terminates a pending session.
- `status` reports outstanding sessions for refresh/reconnection.

Tokens are checked together with the node ID. Stale, unknown, already-completed, and invalid requests are rejected.

## Troubleshooting

**O2 is marked unavailable**

Connect `image2`, or select O1/O3. The node intentionally does not rewrite a saved O2 choice.

**The queue is still running**

If the node says Paused, press Resume or Cancel. Pauses intentionally have no timeout.

**A replacement image does not use the previous edit**

Editor state is serialized automatically. Hard-refresh the ComfyUI frontend if this behavior follows an extension update; the saved workflow state and masks will then be restored and proportionally applied to the replacement image.

**A named preset is not visible in another browser**

Presets normally use ComfyUI userdata. If userdata was unavailable when the preset was saved, it falls back to that browser's local storage and is available only in that browser profile.

**A batch fails**

Use equal batch sizes, or make one input a one-item batch so it can broadcast.
