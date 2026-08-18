# Load Diffusion Model X

Load Diffusion Model X keeps a reusable shortlist of diffusion models inside one workflow node. Add models from the searchable picker, then click a row's radio control to choose the single model used by the next execution.

The node returns one `MODEL` and delegates loading to ComfyUI's native `UNETLoader`. Its shared `weight_dtype` widget is derived from the installed native loader, so the active model receives the same dtype choice as the standard Load Diffusion Model node.

Rows are saved with the workflow. Adding a model makes it active, activating another row disables the previous row, and removing the active row promotes a remaining row. The picker can show LoRA Manager names, previews, tags, base-model information, and descriptions when that extension is installed. Without it, WorkflowX lists the same `diffusion_models` files known to ComfyUI and shows their folder, path, extension, and file size.

Use the row context menu to activate, replace, or remove a model. The node preserves its chosen width while its height grows and shrinks with the saved model list.
