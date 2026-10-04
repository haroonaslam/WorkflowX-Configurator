# DetailerX

Find **DetailerX** under **WorkflowX / Image**. Connect MODEL, VAE, CLIP, positive/negative CONDITIONING and IMAGE. Defaults reproduce the post-processing configuration in `Qwen2.1 Viggle Custom.json`.

Visible rows run top to bottom. Open toolbar **Node Settings** to select visible processors. Hiding disables a processor; showing it again starts it off, retaining its advanced settings. An unchanged visibility selection preserves toggles. Drag the row handle to reorder, or focus it and press Arrow Up/Down. Hidden processors retain their positions in the full order. Restore Default Order changes order only. Dialog drafts do not apply until Apply.

Nine IMAGE sockets expose cumulative results at the corresponding processor position, even when disabled. The realism output captures the last enabled realism operation (or last realism position if none is enabled). `final_image` always returns the completed chain, including operations placed after DLSS5.

The gear beside **Face detailer** contains **Shared SAM configuration**. It applies to every detailer even if the face row is disabled. Each detailer keeps its own detector, mask settings, crop settings, prompt, CFG and seed controls. The original local prompts replace positive conditioning by default; choose `incoming` or `concat` to change that behavior.

All controls serialize in the `settings` JSON input (schema version 3), including visibility, full order, shared SAM, seeds, model identifiers and the selected preset snapshot. Versions 1 and 2 migrate without changing effective processing values. A disabled former realism master turns its children off; former collapse state does not hide them. Backend validation disables hidden processors even for API calls. Internal identifiers start with `internal:`; selectors also expose `comfy:` model locations. API callers can omit fields to receive defaults. Unsupported versions and invalid values produce validation errors.

## Additional finishing processors

RGB, Gamma, Color Balance, Kelvin White Balance, Lens Optic Axis, Pixel Perturb, Neural Grain, LUT, Camera Simulator and Multi-Compression start hidden and disabled. Each has its own gear settings. LUTs can come from internal assets or installed LayerStyle LUT folders, without loading that node pack. Camera and compression perform JPEG roundtrips in memory; they do not save JPEG files. Original alpha is retained.

Kelvin White Balance corrects a specified source illuminant toward neutral 6500 K: low source temperatures cool the image. 6500 K is an exact no-op. It uses a Kang CCT white-point approximation and Bradford adaptation in linear-light RGB, relative to 6500 K; it is not automatic white balance or tint correction.

Ordinary queues, Resume, timeout resume and retained-input Rerun use the same ordered pipeline. Fixed-seed unchanged stages may reuse cached results; enabled randomized processors realize one seed per execution. Visibility changes to already-disabled processors do not invalidate processing caches. Existing time-based grain retains its realized result for downstream-only changes.

## Model presets

The first row selects family and variant together. Selection immediately applies model-related values to all five detailers, including disabled ones. It changes steps, CFG, embedded guidance, sampler/schedule, denoise, guide/max size and cycles. It leaves detectors, SAM, masks, prompts, seeds, toggles, VAE tiling, upscaling, realism and DLSS alone.

| Preset | Steps | Comfy CFG | Sampler / schedule |
|---|---:|---:|---|
| Qwen 2.1 | 15 | 2 face/breast, 2.5 others | DPM++ 2M / Beta |
| SDXL — Standard | 20 | 5 | DPM++ 2M / Karras |
| FLUX.1 — Dev | 20 | 1 | Euler / Simple, embedded guidance 3.5 |
| FLUX.1 — Schnell | 4 | 1 | Euler / Simple |
| FLUX.2 Klein — 4B/9B Base (separate entries) | 20 | 5 | Euler / Flux2 |
| FLUX.2 Klein — 4B/9B Distilled (separate entries) | 4 | 1 | Euler / Flux2 |
| Z-Image — Base | 25 | 4 | RES Multistep / Simple |
| Z-Image — Turbo | 8 | 1 | RES Multistep / Simple |
| Krea 2 — Raw | 52 | 4.5 | Euler / Krea2 |
| Krea 2 — Turbo | 8 | 1 | Euler / Simple |
| Custom | Current values | Current values | Current values |

All start with denoise 0.15 / 0.45 / 0.50 / 0.50 / 0.50, guide/max size 1024 and one cycle. These are editable starting points, not universally optimal settings. Match MODEL, CLIP and VAE yourself; preset selection does not install models, apply Turbo LoRAs or replace upstream attention/sampling patches. Detectable family mismatches produce warnings.

Sources checked 2026-10-03: [official ComfyUI templates](https://github.com/Comfy-Org/workflow_templates/tree/main/templates) (`flux_dev_full_text_to_image`, `flux_schnell`, `image_flux2_klein_text_to_image`, `image_z_image`, `image_z_image_turbo`, `image_krea2_turbo_t2i`), [Krea Raw model card](https://huggingface.co/krea/Krea-2-Raw), and [Krea guidance/schedule conventions](https://huggingface.co/docs/diffusers/api/pipelines/krea2). Krea Raw's published 3.5 guidance equals Comfy CFG 4.5. SDXL 20/5 is a proposed conservative detailing baseline; Qwen values are the user's existing workflow, not a substituted generation recommendation.

**Steps mean actual crop sampling iterations**, preserving the original detailer behavior: build `floor(steps / denoise)` intervals and use the last `steps` intervals. Thus low-denoise sampling differs from a model card's full-noise generation schedule. Distilled presets especially require visual evaluation at your chosen denoise. Flux2 schedules use the encoded latent grid; Krea Raw uses latent 2×2 patch count and resolution-aware exponential shift (0.5 at 256 tokens, 1.15 at 6400). Both end at zero and avoid applying the model shift a second time. Other schedules continue using the supplied model's sampling configuration.

CFG is separate from embedded FLUX guidance. CFG 1 disables the negative branch; negative conditioning remains connected for later changes. Embedded guidance is set after local prompt encoding. Incoming mode preserves unambiguous incoming guidance on prompt replacement without copying incompatible text-encoder metadata.

The preset gear provides shared edits and individual detailer values. **Save and Apply** updates the current node and reusable local library; **Save As** creates an independent preset. Detailer-gear/inline edits are node-local and show **Modified** until explicitly saved. **Restore Built-in Defaults** restores the selected preset's model-related values in the draft, then Save and Apply persists them. Custom presets reset to their embedded saved baseline. Cancel discards the draft.

The library lives at `detailer_x/local/presets.json` (Git-ignored). Writes are validated, atomic and revision-checked. Other nodes keep their snapshots until they explicitly reselect a preset. Workflows/API requests embed all effective values and the snapshot; they execute without the library. Overrides are the difference between effective detailer fields and the snapshot, not a second conflicting settings source. Runtime cache keys ignore preset labels/revisions and depend on effective stage settings.

Controls provide mouseover and keyboard-focus help. Searchable selectors support long names, dialogs stay within the viewport and scroll internally. RGB or RGBA VAE decoding is normalized to RGB before compositing; the original input alpha is restored at outputs rather than replaced with generated alpha.

Intermediate results are held as immutable CPU snapshots in a 2 GiB process-wide LRU cache. Editing Levels reuses earlier realism/detailer results. Model patches, conditioning, asset changes and earlier stage edits invalidate dependent results. Unknown mutable dependencies deliberately cause recomputation. **Clear cache** starts a new cache generation for that node on the next queue. Caches are never saved into workflows.

Grain defaults to the original time-based randomness; its gear supports a fixed seed. A cached grain realization remains stable while editing later stages. Detailer seed mode can be fixed or random; randomized seeds are resolved per execution.

## Live status and terminal updates

The node footer and terminal show matching, human-readable stage updates, for example `[2/12] Face detailer — Running · Image 1/2 · region 1/3 · pass 1/1 · Sampling step 6/15`. The running row is highlighted; a collapsed realism section highlights its master row. The stage counter includes disabled stages, which are explicitly marked skipped; it is not a time estimate.

Updates identify prompt encoding, detection, SAM masking, crop VAE encode/decode, sampling checkpoints, compositing and DLSS runtime preparation. No-detection and empty-mask pass-throughs are explicit. Terminal lines include the node ID, per-stage elapsed seconds and output size, cached reuse, failures/cancellation, and total completion time. Sampling emits approximately five checkpoints per pass to avoid per-step terminal spam. All status is execution-local and excluded from workflow serialization and cache keys. ComfyUI's native sampler progress remains available for detailed per-step feedback.

## Entry controls and reruns

The toolbar operates **only before the first stage**. Pause and Skip are saved, persistent toggles that remain enabled until disabled. Skip takes priority over Pause and bypasses detailing on every run, including reruns; enabling it while paused releases the input immediately. Cancel releases only the current paused run without changing either toggle. Bypass returns independent copies of the original input through all nine outputs so downstream nodes can continue.

Resume applies the latest acknowledged settings. While paused, toggle/inline changes and applied gear dialogs synchronize to the server; look for **Changes saved**. Unapplied dialog drafts are excluded. The gear sets minutes from the original entry time (default five), or indefinite waiting. Expiry automatically processes the latest acknowledged settings. An invalid update blocks expiry until corrected. Pause does not stop an already running stage. The current ComfyUI queue job stays open while paused; native interruption remains available.

The entry area contains only the compact toolbar. A single bottom status beside Clear cache shows entry state/countdown, settings acknowledgements, stage progress, completion, and errors. No incoming-image display expands the node. Inspect images using upstream preview nodes. Runtime controls are isolated by browser/workflow/node owner and session token; stale commands are rejected. Refresh/reconnect recovers a retained session when the same browser/workflow identity is available.

**Rerun** queues only DetailerX and its downstream branch, using retained model/CLIP/VAE, image and conditioning inputs. It skips the Pause gate but honors Skip, uses current settings, and preserves stage-cache reuse. Connected savers execute again and may write additional files. It does not pick up upstream generator changes. Clear cache remains the explicit force-recompute action.

Submission injects internal transparent capture nodes at downstream external-input boundaries. Rerun replaces those connections with process-local snapshot sources; it never mutates ComfyUI executor caches. Resolved subgraph IDs work; unavailable/new boundaries or unresolved dynamic mappings produce an ordinary-queue-required error. Use tensor batches, not list-mapped DetailerX inputs. Rerun is unavailable until the originating workflow job finishes, avoiding overlapping GPU work.

Retained tensors have a separate shared **2 GiB CPU limit**, with up to 32 idle sessions and idle eviction; active/queued sessions are pinned. Model weights are referenced, not copied. Oversized entry batches fail with an actionable message. Unsupported/missing external snapshots reject replay rather than regenerate upstream. Runtime snapshots, timers, and tokens are not saved in workflow files and disappear on restart; Pause and Skip settings are saved. Effective resumed settings are included in prompt/PNG metadata under `detailer_x_effective`.

Tests include real ComfyUI executor validation/replay with synthetic inputs (proving upstream generation is not repeated), gate transitions, timers, pass-through RGB/RGBA batches, snapshots, and cache/preset regressions. The isolated browser harness simulates entry states for visual checks; it does not execute real diffusion or save user outputs.

## Local assets

The local installation contains copies of five detectors, SAM, SkinDiffDetail, three NVIDIA runtimes, the caller shim and bridge/host binaries. These files are ignored by Git. A fresh source installation needs the Python requirements and its own supplied assets. From the WorkflowX folder, with normal Python:

```powershell
python -m pip install -r detailer_x/requirements.txt
python -m detailer_x.provision --comfy-root /path/to/ComfyUI
```

For isolated embedded Python, insert the WorkflowX directory into `sys.path` before invoking the provisioning module. The provisioning command verifies hashes and rejects different existing internal assets. External node packs are needed only as sources for the initial native-file copy, never during DetailerX execution.

Windows DLSS5 uses the internal D3D12 bridge in a task-owned native host process and requires a compatible NVIDIA GPU/driver. This isolates NVIDIA runtimes that hang on shutdown; after delivering frames, teardown is bounded and releases the host. Native frame I/O has a 180-second timeout and supports queue cancellation. Linux additionally needs the Wine/DXVK environment required by the bundled backend. Disabling DLSS5 avoids loading its native runtime. No video/audio outputs are included.

## Checks

```powershell
python -m pytest tests/test_detailer_x.py tests/test_detailer_x_presets.py --rootdir=tests --confcutdir=tests --import-mode=importlib -q
node --test tests/detailer_x_frontend_test.mjs
python tests/detailer_x_gpu_smoke.py
```

The optional `--sampling-checkpoint` argument performs real diffusion detailing with a supplied ComfyUI-compatible checkpoint. GPU tests use the bundled scikit-image astronaut portrait and do not modify workflows or start a ComfyUI server.

Use `--preset sdxl` to exercise its full sampling step count and `--rgba-vae PATH` for a real Qwen 2.1 RGB/RGBA VAE roundtrip. `python tests/detailer_x_ui_preview.py` serves the real frontend with an isolated graph and temporary preset library at `http://127.0.0.1:8766`; stop with Ctrl+C. This harness does not load or modify user workflows.

Preset update verification: backend RGB/RGBA regressions include ordinary, tiled and OOM-fallback decode; library conflicts, migration and resolution schedules have automated coverage. GPU checks passed SDXL 20-step detailing at 512px crop and the installed Qwen 2.1 RGBA VAE with RGB and RGBA inputs. Other family presets have configuration/schedule tests, **not full-model visual quality validation**. The live ComfyUI process must be restarted, followed by a browser refresh, to load this backend/schema update; do not hot-mix the new frontend with the old backend.

Add `--compare-reference` to compare the face result against a locally installed Impact Pack using the same inputs and seed. This optional test imports reference packs; DetailerX itself does not.

Validated locally on an RTX 5090: SkinDiffDetail upscaling, detector + SAM, diffusion face detailing (SDXL smoke checkpoint), and DLSS5 native/1.5×. The controlled face comparison was pixel-identical to Impact Pack. The five realism operations also match the original functions at workflow defaults with a fixed grain seed. Full-resolution Qwen generation plus the complete original chain has not been run as a parity benchmark.
