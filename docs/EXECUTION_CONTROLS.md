# Execution controls and image handoffs

[WorkflowX README](../README.md#segment-runx-and-run-targetx) · [Image loaders](IMAGE_LOADERS.md)

These controls live under **WorkflowX** in the node menu. They select existing nodes through dropdowns instead of adding canvas wires. Choices travel with the saved workflow. Node names and containing subgraph paths identify selections; choose a replacement if a selected node is deleted. The panels support growing and shrinking in the classic and Vue renderers.

Restart ComfyUI and refresh the browser after installing these changes. StopX and automatic image transfers need the WorkflowX backend scheduler integration as well as its frontend. The private execution helpers are managed automatically and are not nodes to configure by hand.

## Segment RunX and Run TargetX

1. Add **Run TargetX** and select an output node, such as Preview Image or Save Image.
2. Add **Segment RunX**. It lists Run TargetX entries from the workflow and reachable subgraphs.
3. Press **▶** beside the desired entry. Its status reports preparation, queueing, execution, and completion or failure.

The submitted prompt contains the selected output's upstream closure. Muted and bypassed nodes needed by that path can execute in this submitted prompt while their canvas modes remain unchanged. A normal queue submitted alongside it therefore uses its own configured modes. There is no visual activation or subsequent canvas-state restoration window.

WorkflowX Set/Get relays and the selected ToggleX input are resolved when the path is compiled. A branch with another consumer can still run for that consumer. Missing dependencies and cycles must be resolved before queueing.

Only one Segment RunX job is monitored at a time in the open workflow. Opening another workflow abandons monitoring, without removing or interrupting the queued job. Use ComfyUI's queue controls to manage submitted jobs.

## StopX

Add **StopX** and select a node in **Stop after**. In a normal queue, once that node finishes successfully, WorkflowX completes the configured image copies and prevents the scheduler from advancing to further pending nodes. The stop is intentional and is recorded separately from an execution failure. Pending async work belonging to that job is cancelled and awaited as part of stopping.

- Cached completion at the selected point counts as reaching it.
- StopX does not enable a muted, bypassed, or unreachable path. An inactive StopX control is ignored.
- Multiple StopX controls are allowed; the first applicable point reached stops the job.
- Segment RunX, ComfyUI queues carrying selected-output targets, and rgthree's selected-output queue ignore StopX.

A stop point prevents subsequent scheduling. It cannot undo output files or other effects from nodes that already ran. Independent async work may have started before the stop point was reached.

## Image SourceX and Image TargetX

1. Add **Image SourceX** and select the producer in **Image from**.
2. Add **Image TargetX**, select that SourceX entry, then choose the destination in **Copy to**.
3. Choose the transfer timing and queue the relevant path.

| Role | Supported node types |
|---|---|
| Source | Native Save Image (`SaveImage`), Preview Image (`PreviewImage`), Load Image (`LoadImage`), Load ImageX (`WorkflowX_LoadImageX`), Load ImageX Adv (`WorkflowX_LoadImageXAdv`) |
| Destination | Native Load Image, Load ImageX, Load ImageX Adv |

The transfer uses the first image of the first produced batch. Save/preview sources use their first saved image; loader sources use their actual image output, including advanced-loader transformations. The copied PNG preserves dimensions and alpha where supplied by the source. A separate temporary file is created, leaving the destination's previous image file intact.

### Transfer timing

| Mode | Current job | Destination selection after copying |
|---|---|---|
| **Prepare next run** (default) | Keeps the destination's originally submitted input | Selects the copied image for a later queue |
| **Use in this run** | Runs the needed source before an executing destination and supplies its new image | Also selects the copy for later queues |

**A muted or bypassed destination still receives the copy.** Its mode stays unchanged. Use in this run does not force an inactive destination to execute during a normal run; it still receives the image for future use. The selected source must be executable in the queued path. Inactive SourceX or TargetX controls do not request a transfer.

Load ImageX Adv automatically selects **Direct** mode and retains its other processing settings. Native Load Image and basic Load ImageX select the copied temporary image without an additional mode switch.

### Ordering and selective runs

Required source captures and copies finish before an applicable StopX ends the run. In a selective queue, transfers apply to included source paths; a same-run destination can also bring in the source dependencies it requires. StopX remains disabled for that selective queue.

Do not create a same-run dependency from a loader back into a source that already depends on that loader. Also avoid choosing a source downstream of a required stop point. Such ordering cycles are rejected before queueing. Use **Prepare next run** for a staged feedback workflow. Only one active Image TargetX may write to a particular loader in one queued run; independent pairs can coexist.

If capture or copying fails, the job reports an execution error and that failed transfer does not replace the destination's existing selection. Successful transfers are retained in job history so the open workflow can recover a missed update after reconnecting. Older recovered transfers do not replace a newer received copy.

### Persistence and temporary files

Save the workflow to keep the control selections, transfer mode, and received loader selection. Copied images live in ComfyUI's temporary directory. If those files are cleared, rerun the source transfer or choose a persistent image before queueing that loader.

**Image SourceX** is separate from the existing wired **ImageX Source** node. ImageX Source continues to support the advanced loader's manual **From Node → Refresh Image** workflow; see [From Node](IMAGE_LOADERS.md#from-node).
