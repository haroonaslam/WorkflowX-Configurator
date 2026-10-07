# DetailerX

Find **DetailerX** under **WorkflowX / Image**. Connect MODEL, VAE, CLIP, positive/negative CONDITIONING and IMAGE. Defaults reproduce the post-processing configuration in `Qwen2.1 Viggle Custom.json`.

Visible rows run top to bottom. Open toolbar **Node Settings** to select visible processors. Hiding disables a processor; showing it again starts it off, retaining its advanced settings. Every processor gear also has **Hide processor**. Repeatable custom detailers additionally have a confirmed **Delete custom** action; built-in processors cannot be deleted. An unchanged visibility selection preserves toggles. Drag the row handle to reorder, or focus it and press Arrow Up/Down. Hidden processors retain their positions in the full order. Restore Default Order changes order only. Dialog drafts do not apply until Apply, and Hide deliberately ignores an open draft.

DetailerX has three outputs. `final_image` is the completed chain, including processors placed after DLSS5. `processor_images` is an ordered, named snapshot bundle containing the untouched original and one cumulative image batch for every enabled processor. `detailer_masks` is a diagnostic bundle for **DetailerX Masks**. Disabled and hidden processors are omitted.

Connect `processor_images` to **DetailerX Preview**. Its arrow controls browse enabled processor stages in actual execution order, and its batch arrows browse images within each stage. Compare mode can be Off, Original, or Previous processor, with wipe and side-by-side layouts. Fit/100% and an enlarged overlay are available without adding image sockets to DetailerX. The fullscreen inspector retains stage, batch, and comparison controls and adds Fit, 100%, zoom-in, zoom-out, keyboard navigation, and Ctrl+wheel zoom. Its comparison split follows the mouse across the image instead of using the compact node's slider. The bundle is process-local workflow data, not an ordinary IMAGE; connect `final_image` to standard image nodes.

Connect `detailer_masks` to **DetailerX Masks**. It browses enabled detailers in execution order and overlays diagnostics on the exact cumulative image entering each detailer. Choose **Detector proposal**, **SAM-refined mask**, or **Final blend mask**. For SAM3, the refined view is the raw SAM result before its post-constraint; the final blend view is the constrained and feathered mask actually allowed to change. Overlay color and opacity are adjustable. Batch navigation, fit/100%, enlargement, detector/class/backend information, region counts, and explicit no-detection/zero-denoise states are included. When SAM is disabled, the refined view represents the detector-only mask. Files created by this viewer are temporary previews, not saved outputs.

The toolbar gear opens tabbed node-wide settings: **Flow**, **Seed**, **Detailers**, and **SAM**. The SAM tab is the inherited default. Each detailer gear selects **Inherit global SAM**, **Detector only**, or **Override SAM**. A complete override owns its backend, checkpoint, device and loading preference while retaining that detailer's independent thresholds, mode and concept. Select SAM1 (ViT-B/L/H), SAM2.1 (Tiny/Small/Base+/Large), or a registered native ComfyUI SAM3.1 checkpoint. The original local prompts replace positive conditioning by default; choose `incoming` or `concat` to change that behavior.

Hair and Anything are built-in rows and start disabled. **Additional Detailers** in Node Settings opens the concept catalog and can create unlimited UUID-backed custom detailers. A new custom row asks for a display name, copies the current Anything settings, appears visible and starts disabled. Duplicate names and concepts are supported because identity is independent of the label. Hidden custom rows remain available for re-showing; deletion permanently removes only that custom instance. A catalog concept appears once even when several compatible checkpoints exist; choose the checkpoint in its gear. Multi-class YOLO results are filtered by saved class IDs and labels, keeping segmentation masks aligned with their detections. Detector selectors show companion TXT information on hover; uncatalogued ComfyUI models are inspected only when selected.

Every detailer gear includes **Detector proposal**. **Native** preserves the shaped mask from a SEGM checkpoint and uses a rectangle for ordinary BBOX checkpoints. **Bounding box** forces a solid rectangle from every detection before `bbox_dilation`, including detections from SEGM checkpoints. This gives small targets more editable context without changing the detector checkpoint; the effective rectangle is also shown in DetailerX Masks. Fully text-guided SAM3 ignores this setting because it bypasses Ultralytics.

With SAM3.1, each detailer offers **Refine detector**, **Hybrid**, **BBox controlled**, and **Fully text-guided**. Refine uses the full image with one detector-box prompt at a time and no semantic text. Hybrid uses the full image with the detector box plus the editable mask concept; the box is still a soft SAM3 prompt. BBox controlled crops the source to each detector box, runs concept-guided SAM3 only on that crop, pastes the result back into full-image coordinates, and hard-clips every pixel to the original detector box. Fully text-guided bypasses Ultralytics and searches the full image. Other detector-assisted modes default to **Bounding box** post-constraint, so a SEGM proposal localizes SAM3 without preventing it from replacing an inaccurate shaped mask. **Detector mask** restores strict intersection; **No post-constraint** accepts the complete SAM3 result while retaining the box prompt. The post-constraint selector is hidden for BBox controlled because its hard boundary is mandatory. Catalog concepts provide canonical initial text, and **Use selected class concept** can restore it. The mask concept remains separate from the diffusion enhancement prompt.

All controls serialize in the `settings` JSON input (schema version 5), including dynamic detailers, per-detailer SAM policy/overrides, class filters, visibility, full order, seeds, model identifiers and the selected preset snapshot. Versions 1–4 migrate to inherited SAM and Bounding-box SAM3 constraints; Hair and Anything remain visibly available but disabled when introduced. A disabled former realism master turns its children off; former collapse state does not hide them. Backend validation disables hidden processors even for API calls. Internal identifiers start with `internal:`; selectors also expose `comfy:` model locations. API callers can omit fields to receive defaults. Unsupported versions and invalid values produce validation errors.

## Additional finishing processors

RGB, Gamma, Color Balance, Kelvin White Balance, Lens Optic Axis, Pixel Perturb, Neural Grain, LUT, Camera Simulator and Multi-Compression start hidden and disabled. Each has its own gear settings. LUTs can come from internal assets or installed LayerStyle LUT folders, without loading that node pack. Camera and compression perform JPEG roundtrips in memory; they do not save JPEG files. Original alpha is retained.

Kelvin White Balance corrects a specified source illuminant toward neutral 6500 K: low source temperatures cool the image. 6500 K is an exact no-op. It uses a Kang CCT white-point approximation and Bradford adaptation in linear-light RGB, relative to 6500 K; it is not automatic white balance or tint correction.

Ordinary queues, Resume, timeout resume and retained-input Rerun use the same ordered pipeline. Fixed-seed unchanged stages may reuse cached results; enabled randomized processors realize one seed per execution. Visibility changes to already-disabled processors do not invalidate processing caches. Existing time-based grain retains its realized result for downstream-only changes.

## Model presets

The first row selects family and variant together. Selection immediately applies model-related values to all built-in and currently added detailers, including disabled ones. It changes steps, CFG, embedded guidance, sampler/schedule, denoise, guide/max size and cycles. It leaves detectors, SAM, masks, prompts, seeds, toggles, VAE tiling, upscaling, realism and DLSS alone.

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

Mixed SAM overrides use a separate two-model process-wide LRU. Opted-in checkpoints are retained offloaded on CPU, only the active spatial SAM moves to GPU, and the least-recently-used checkpoint is evicted when a third is needed. Turning off `keep_model_loaded` prevents retention for that configuration. Clear cache does not unload model weights.

Grain defaults to the original time-based randomness; its gear supports a fixed seed. A cached grain realization remains stable while editing later stages. Detailer seed mode can be fixed or random; randomized seeds are resolved per execution. Node Settings can override every seeded processor with one fixed seed or one execution-wide randomized seed. Local values remain saved but inactive while the override is enabled, and the realized seed appears in execution status.

## Live status and terminal updates

The node footer and terminal show matching, human-readable stage updates, for example `[2/12] Face detailer — Running · Image 1/2 · region 1/3 · pass 1/1 · Sampling step 6/15`. The running row is highlighted; a collapsed realism section highlights its master row. The stage counter includes disabled stages, which are explicitly marked skipped; it is not a time estimate.

Updates identify prompt encoding, detection, SAM masking, crop VAE encode/decode, sampling checkpoints, compositing and DLSS runtime preparation. No-detection and empty-mask pass-throughs are explicit. Terminal lines include the node ID, per-stage elapsed seconds and output size, cached reuse, failures/cancellation, and total completion time. Sampling emits approximately five checkpoints per pass to avoid per-step terminal spam. All status is execution-local and excluded from workflow serialization and cache keys. ComfyUI's native sampler progress remains available for detailed per-step feedback.

## Entry controls and reruns

The toolbar operates **only before the first stage**. Pause and Skip are saved, persistent toggles that remain enabled until disabled. Skip takes priority over Pause during ordinary queues and Resume; enabling it while paused releases the input immediately. Cancel releases only the current paused run without changing either toggle. Bypass returns the original input through `final_image` and an original-only preview bundle through `processor_images`, so downstream nodes can continue.

Resume applies the latest acknowledged settings. While paused, toggle/inline changes and applied gear dialogs synchronize to the server; look for **Changes saved**. Unapplied dialog drafts are excluded. The gear sets minutes from the original entry time (default five), or indefinite waiting. Expiry automatically processes the latest acknowledged settings. An invalid update blocks expiry until corrected. Pause does not stop an already running stage. The current ComfyUI queue job stays open while paused; native interruption remains available.

The entry area contains only the compact toolbar. A single bottom status beside Clear cache shows entry state/countdown, settings acknowledgements, stage progress, completion, and errors. No incoming-image display expands the node. Inspect images using upstream preview nodes or inspect masks with DetailerX Masks. Runtime controls are isolated by browser/workflow/node owner and session token; stale commands are rejected. Refresh/reconnect recovers a retained session when the same browser/workflow identity is available.

**Rerun** always checks that the image socket is connected. If evaluated inputs are retained, it queues only DetailerX and its downstream branch using the retained model/CLIP/VAE, image and conditioning values; the upstream generator is not repeated. If no retained run exists, or the image connection/leaf loader selection changed, it queues the current DetailerX branch: only the ancestors required to evaluate DetailerX plus its downstream consumers. A Load Image → DetailerX iteration therefore does not run an unrelated generation branch. A direct generator → DetailerX connection must evaluate that generator when no matching retained image exists. Missing image connections are reported in the node status.

Rerun explicitly overrides both Pause and Skip for that execution without changing either persistent toggle, uses current applied settings, and preserves stage-cache reuse. Connected savers execute again and may write additional files. This supports iterative output → Load Image → DetailerX passes. Clear cache remains the explicit force-recompute action.

Every visible processor row also has a compact **Play** button for selective refinement. This queues only that processor plus the connected downstream branch; it does not run the other DetailerX processors. **Refine Original** applies the chosen processor to the retained image that originally entered DetailerX. When no retained tensor exists but the IMAGE socket is connected, it instead evaluates only the connected ancestors required to supply that image, then runs the selected processor and downstream consumers. Consequently, a connected Load Image is inexpensive, while a directly connected generator must run if it has not yet produced a retained input. **Refine Output** applies a non-detailer processor to the latest completed result, including the result of an earlier selective refinement, and remains unavailable until such an output exists.

Detailer rows add two output choices. **Refine Output — Reuse Mask** reuses that detailer's most recently retained final blend mask, preserving the selected region while resampling it; if no compatible mask is retained, it reports the fallback and performs fresh detection automatically. **Refine Output — Remask** deliberately reruns Ultralytics/SAM on the latest image before sampling. Reused masks are resized to the current image when necessary and separated into connected regions so unrelated detections remain independent. Each successful selective run becomes the new latest output, making repeated local repairs cumulative. A process restart or retained-session eviction removes the source and masks, after which an ordinary DetailerX run is required.

Submission injects internal transparent capture nodes at downstream external-input boundaries. A retained rerun replaces those connections with process-local snapshot sources; it never mutates ComfyUI executor caches. A connected-input run constructs and validates a pruned ComfyUI prompt rather than queueing every output in the canvas. Resolved subgraph IDs work; unavailable/new boundaries or unresolved dynamic mappings produce an actionable error. Use tensor batches, not list-mapped DetailerX inputs. Rerun is disabled while this node is already processing or queued, avoiding overlapping GPU work.

Retained tensors have a separate shared **2 GiB CPU limit**, with up to 32 idle sessions and idle eviction; active/queued sessions are pinned. Model weights are referenced, not copied. Oversized entry batches fail with an actionable message. Unsupported/missing external snapshots reject retained replay; the user can then run the current connected branch. Runtime snapshots, timers, and tokens are not saved in workflow files and disappear on restart; Pause and Skip settings are saved. Effective resumed/rerun settings are included in prompt/PNG metadata under `detailer_x_effective`.

Tests include real ComfyUI executor validation/replay with synthetic inputs (proving retained upstream generation is not repeated), connected-branch pruning, changed Load Image detection, gate transitions, timers, pass-through RGB/RGBA batches, snapshots, and cache/preset regressions. The isolated browser harness simulates entry states for visual checks; it does not execute real diffusion or save user outputs.

## Local assets

The local installation contains the verified 40-pair Ultralytics catalog, legacy detectors, SAM1 B/L/H, SAM2.1 Tiny/Small/Base+/Large, SkinDiffDetail, three NVIDIA runtimes, the caller shim and bridge/host binaries. These model/runtime files are ignored by Git; the SAM2.1 inference implementation and configurations are vendored under Apache-2.0. SAM3.1 is selected from ComfyUI checkpoints and uses core's native `SAM3_Detect`. A fresh source installation needs the Python requirements and its own supplied assets. From the WorkflowX folder, with normal Python:

```powershell
python -m pip install -r detailer_x/requirements.txt
python -m detailer_x.provision --comfy-root /path/to/ComfyUI --ultralytics-source /path/to/ultralytics --download-official-sams
```

For isolated embedded Python, insert the WorkflowX directory into `sys.path` before invoking the provisioning module. The optional SAM flag downloads the seven official SAM1/SAM2.1 checkpoints from Meta's public endpoints, verifies pinned SHA-256 values before atomic installation, and records URL provenance. The provisioning command verifies copied assets and rejects different existing internal assets. External node packs are needed only as sources for the initial native-file copy, never during DetailerX execution.

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

Validated locally on an RTX 5090: all three SAM1 variants, all four SAM2.1 variants, and the original three native SAM3 interaction modes, plus SkinDiffDetail upscaling, detector + SAM, diffusion face detailing (SDXL smoke checkpoint), and DLSS5 native/1.5×. BBox controlled has automated crop, coordinate, alignment and hard-boundary coverage and still requires a post-restart live GPU smoke test. The controlled face comparison was pixel-identical to Impact Pack. The five realism operations also match the original functions at workflow defaults with a fixed grain seed. Full-resolution Qwen generation plus the complete original chain has not been run as a parity benchmark.
