# Kie and Atlas Image API Nodes

`Kie Image API X` and `Atlas Image API X` provide a single-generation ComfyUI interface to the image models supported by GemMobi's Kie and Atlas engines. Both nodes live under `WorkflowX_Configurator/Image/API` and return one ComfyUI `IMAGE`.

## Credentials

The masked `api_key` widget overrides environment configuration. When it is blank:

- Kie reads `KIE_API_KEY`.
- Atlas reads `ATLAS_API_KEY`, then `ATLASCLOUD_API_KEY`.

API keys are used only for the live request. Pending-task records never contain credentials, prompts, reference bytes, or provider payloads. Remember that workflow JSON can contain a key entered directly in a widget; use environment variables when sharing workflows.

## Generation Mode and References

With no image connected, the selected model's text-to-image route is used. Connecting any `IMAGE` switches automatically to image-to-image/edit mode. `image_1` is present initially; connecting the last available image socket adds the next socket until `image_14`. Redundant empty sockets are removed from the end when connections are disconnected.

Each connected batch frame counts as one reference. The node validates the selected model's real reference maximum before uploading anything. It never silently drops extra references.

## Dynamic Model Panel

Both nodes use a rich in-node panel. Changing `model` rebuilds the generation card from WorkflowX's packaged copy of GemMobi's canonical Kie/Atlas model contracts. The panel distinguishes aspect ratio, named `1K`/`2K`/`4K` tiers, explicit `W×H` provider sizes, output quality, and output type instead of presenting one generic size control. Unsupported controls disappear and stale workflow values normalize to that model's documented defaults.

The header reports `T2I` or `I2I`, the connected reference count, and the selected model's maximum. Models with documented custom dimensions expose width and height controls with the provider's exact edge and step limits. `Reference Resize Max Edge` resizes oversized inputs while preserving aspect ratio before upload; it defaults to 5120px and supports 512–8192px.

Kie includes Wan 2.7/Pro, Grok Imagine, GPT Image 1.5, GPT2, Seedream 4.5/5 Lite/5 Pro, Nano Banana 2/Pro, Qwen2, and Flux2 Pro. Atlas includes Wan 2.7/Pro, GPT Image 1.5, GPT2, Seedream 4.5/5 Lite/5 Pro, Nano Banana 2/Pro, Qwen2, Qwen Image 2 Pro, and Kontext. Kie Topaz Upscale is intentionally excluded because these nodes are generation/edit nodes.

Model-dependent controls include:

- Kie: quality, NSFW checker, thinking, watermark, fixed seed, sequential generation, output format, and Grok Pro mode.
- Atlas: quality, thinking, fixed seed, output format, input fidelity, web/image search, media resolution, guidance scale, inference steps, and safety checker.

`timeout_seconds` controls the total polling window from 30 to 3600 seconds. `poll_interval_seconds` controls status-query spacing from 2 to 60 seconds. `Log Request Payload` adds a redacted payload view to the session log; reference URLs and credentials are not shown.

## Live Status and Actions

The lower panel shows a bounded, session-only log for validation, reference preparation and upload, submission, task ID, each polling attempt, timeout, cancellation, download, decode, and completion. Logs are not saved into workflow JSON or pending-task storage.

- **Queue Generation** queues the workflow in normal generation mode.
- **Stop & Continue** stops local work, removes local pending tracking, and returns a black placeholder image so downstream nodes can continue. The placeholder follows the requested explicit/custom dimensions or the selected aspect/tier where possible.
- **Stop & Retrieve Later** stops the current execution but preserves an accepted task for **Force Retrieve**.
- **Force Retrieve** queues a retrieval-only execution for the stored task ID.
- **Forget Pending** deliberately removes only the local task record.

Kie and Atlas do not expose a cancellation endpoint in the canonical contracts. A request already accepted by the provider may continue and incur charges after either Stop action or Forget Pending. Network calls already in flight may also finish before the local stop signal is observed.

## Pending Tasks and Force Retrieve

The remote task ID is persisted under ComfyUI user data immediately after a successful create response and before polling begins. A timeout, interruption, restart, temporary status error, or output-download error therefore does not lose the paid task.

Use **Force Retrieve** to queue the workflow in retrieval mode. The node polls the stored task ID and never calls the generation endpoint. If the result is ready, it downloads and returns the image and clears the local pending record. If it times out again, the same task remains retrievable. A timed-out ComfyUI execution cannot later receive an asynchronous output, so retrieval necessarily runs as a new queue execution.

A normal run is blocked while that node has a pending task, preventing an accidental replacement paid submission. Use **Forget Pending** only when you intentionally want to abandon local tracking. Forgetting a record does not cancel the provider-side task and cannot reverse its charges.

## Failure Behavior

Validation, authentication, provider failure, timeout, upload, status, download, and decode problems stop the workflow with an actionable error. API keys are redacted from errors. Definitive provider failures remove the pending record; retriable timeouts and transport/download failures retain it. Timeout therefore parks the paid task and requires **Force Retrieve**; it does not return an empty image automatically.

Result download is retried once against the same result URL. Generation creation is never retried after a task ID is issued.

## Contract Maintenance

Runtime code reads only `remote_image_api/model_contracts.json`; it never imports the separate GemMobi checkout. When GemMobi contracts change, refresh the packaged Kie/Atlas subset and run:

```powershell
python remote_image_api\validate_contract_drift.py C:\path\to\GemMobi\docs\model_contracts\canonical_models.json
```
