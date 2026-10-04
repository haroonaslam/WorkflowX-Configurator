# DetailerX source and local assets

The processing compatibility layer follows algorithms from these installed projects:

- ComfyUI-Impact-Pack, ltdrdata: detector/SAM hint handling, crop sizing, feathering and truncated-schedule sampling behavior. GPL-3.0; license in `licenses/Impact-GPL-3.0.txt`. The adapted processing module is distributed under GPL-3.0.
- ComfyUI_LayerStyle, chflame163: image adjustments and grain algorithm. MIT; `licenses/LayerStyle-MIT.txt`.
- Allor, Nourepide: radial lens behavior, adapted with finite-center and rectangular-size corrections. MIT; `licenses/Allor-MIT.txt`.
- ComfyUI-Image-Effects: color balance behavior, extended to all batch images with alpha preservation. Apache-2.0; `licenses/Image-Effects-Apache-2.0.txt`.
- WAS Node Suite, Jordan Thompson: Lucy sharpening algorithm. MIT; `licenses/WAS-MIT.txt`.
- ComfyUI_Comfyroll_CustomNodes, RockOfFire and Akatsuzi: upscale resize behavior, based on ComfyUI core and WAS image resize. Used as a behavior reference; model execution uses ComfyUI core and Spandrel.
- ComfyUI-RH-DLSS5: isolated backend source snapshot in `vendor/dlss`, including native bridge build sources. MIT; `licenses/RH-DLSS5-MIT.txt`. The callback honors ComfyUI cancellation, and the host transport supports native Windows execution with bounded, interruptible I/O and teardown. Its original public node registrations are not exported by WorkflowX.

Installed Python libraries retain their own licenses. NVIDIA runtime binaries and model weights are user-supplied local assets, not included in source releases. `assets/manifest.json` records the exact local source paths, file sizes and SHA-256 hashes. Provisioning copies existing files; it does not download or publish them.
