# Load Lora PickerX

Load Lora PickerX applies an ordered stack of LoRAs selected directly from the Windows filesystem. Files are loaded in place; they are not copied or uploaded to ComfyUI's LoRA directory.

Use **Pick LoRA** to add a row. Each row has an enable toggle, selected file, epoch selector, model strength, CLIP strength, and remove button. Right-click a row to replace or refresh it, move it up or down, or remove it. LoRAs are applied from top to bottom.

## Epoch discovery

The node scans only the selected file's immediate directory and only files with the same extension. It recognizes names containing `epoch`, `ep`, `step`, `checkpoint`, or `ckpt`, plus trailing checkpoint numbers containing at least three digits. For example:

- `hero-epoch-2.safetensors`
- `hero-epoch-10.safetensors`
- `hero.safetensors` (shown as **Final**)

Ordinary short version names such as `hero-v2.safetensors` are not treated as epochs. When no related files are found, the epoch selector is disabled and displays **Single**. The directory is scanned again when the workflow is restored and whenever the epoch selector is opened.

## Paths and portability

Files inside a registered ComfyUI LoRA directory are saved using their normal ComfyUI load name. Files elsewhere are saved using an absolute path, so workflows containing them are machine-specific. If a selected checkpoint is moved or deleted, the row remains selected and execution reports the missing path instead of silently choosing another epoch.

The native picker is Windows-only and can be opened only from a browser running on the ComfyUI computer. A saved workflow can still execute without opening the picker when all stored paths are available.

Overwriting a checkpoint at the same path changes the node's cache fingerprint using its file size and modification time, ensuring the updated weights are loaded on the next run.
