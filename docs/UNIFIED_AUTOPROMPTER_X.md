# Unified PrompterX Guide

> [Node contract](../README.md#prompting-and-jsonx) · [Example workflow](../examples/02-local-generation-and-model-management.json)

The source-to-field and reverse-payload review is recorded in the [Canonical Guide Audit](UNIFIED_CANONICAL_GUIDE_AUDIT.md).

`Unified Autoprompter X` builds model-specific image, video, and JsonX prompts through one compact ComfyUI node. It lives under `WorkflowX/Prompting` and keeps its existing node ID and three `STRING` outputs: `prompt`, `positive`, and `negative`.

## Node workflow

1. Select a target profile.
2. Select one of that profile's supported generation types.
3. Select an output format.
4. Enter the request in **Prompt instructions**, or enable a connected `raw_prompt_text` input. Type `@` to insert a saved character or scene preset.
5. Keep **Detail level** as a separate explicit instruction.
6. Optionally connect images as prompt-authoring evidence. The selected generation type determines how their role is described.
7. Choose **On Generate** for manual authoring or **On Queue** to author a fresh prompt whenever this node is included in a queued graph.
8. Optionally select **Add audit pass** or **Audit only**.
9. Choose a provider from the **Provider** dropdown, expand **Model settings**, and generate or queue.

The NSFW checkbox adds exactly one shared Markdown block selected by output medium: Image or Video. It does not change Gemini or provider safety settings.

Prompt instructions, detail level, generation type, NSFW state, generated outputs, and functional UI state travel with the workflow. Credentials, provider URLs, provider model choices, tuning parameters, and additional local-model folders remain in engine-specific browser storage.

## Generation types

Images belong to prompt authoring and do not choose or change the downstream generation type. Unified applies this four-state resolver:

| Downstream path | Image connected | Model-facing image block | Authoring image sent |
| --- | --- | --- | ---: |
| Supports image input | Yes | Supported with image connected | Yes |
| Supports image input | No | Supported with image not connected | No |
| Reference-unsupported | Yes | `without_reference_unsupported.md` | Yes |
| Reference-unsupported | No | `without_reference_unsupported.md` | No |

Image-capable paths therefore remain usable when the user describes an assumed reference without attaching it. Text-to-Image and Text-to-Video can use connected images as visual evidence, but their final contracts remain self-contained text and never imply that the downstream generator receives those images. Unified enforces only its nine-image authoring limit and the selected provider/model's vision capability; it does not enforce downstream reference counts.

Built-in support:

| Profiles | Supported generation types | Default |
| --- | --- | --- |
| Image profiles | Text to Image, Image to Image | Text to Image |
| Qwen Image 2.1 | Text to Image, Image to Image; Natural output only; no negative channel | Text to Image |
| JsonX | Text to Image, Image to Image | Text to Image |
| WAN 2.2, LTX 2.3 | Text to Video, First Frame, First–Last Frame | Text to Video |
| MiniMax H3 Official | Text to Video, First Frame, First–Last Frame, Last Frame, Reference to Video | Text to Video |
| MiniMax H3 Alternate | Text to Video, First Frame, First–Last Frame, Reference to Video | Text to Video |

Connected images are sent to the authoring LLM in socket order. A path's editable canonical reference-usage block defines their role: for example, First–Last Frame treats the first two as boundary frames, while Reference to Video assigns bounded authority. If no image is attached, the corresponding no-image block tells the LLM to derive only the reference assumptions explicitly present in the user's description. For text-only downstream paths, connected media remains authoring guidance: the LLM combines visible evidence with the user's description to infer intent without emitting reference commentary or implying that the downstream generator receives the media.

## Minimal prompt assembly

For standard profiles, Unified sends only exact Markdown file contents, in this order:

1. `split/common.md`.
2. The selected generation-type file from `split/`, when it is non-empty.
3. `nsfw-image.md` or `nsfw-video.md`, only when NSFW is enabled.
4. Exactly one profile-level reference-processing file from `Supporting/`.
5. Exactly one profile-wide output-contract file from `Supporting/`, selected by output format and negative state.

File contents are not trimmed, interpolated, summarized, converted, or reformatted. Unified inserts only a fixed blank-line separator between selected blocks. An enabled generation type may have a blank file, in which case that optional block is skipped.

It does not send Unified identity text, target keys, display labels, profile notes, editor commentary, unrelated generation paths, or generic metadata headings.

The user input contains only:

- effective manual or connected prompt instructions;
- detail level.

Actual images are transmitted separately in the provider's multimodal payload. The **Preview** page separates the exact system text, exact user text, and submitted authoring media from **Local routing only** data such as activated relative filenames and sanitized provider parameters. Local routing metadata is never inserted into the model prompt. Preview and generation call the same Markdown payload builder.

## Working modes

**On Generate** updates the saved outputs only when you press **Generate**. Ordinary workflow queues reuse that saved prompt, which is useful when prompt authoring and image/video generation should be separate operations.

**On Queue** requests a fresh authored prompt whenever a queued graph includes Unified Autoprompter X. The queue waits for that request to finish before downstream nodes run. If the node is not part of the queued execution path, no prompt request is made.

## Audit modes

**None** returns the generated or saved text without an audit request. **Add audit pass** generates normally, then sends the result through an independent second provider call; if that call fails, Unified retains the newly generated prompt. **Audit only** skips generation and audits the visible **Prompt instructions** exactly as the source text. It ignores connected prompt text and authoring images; if the audit fails, the visible text is retained.

The audit instruction is an independently editable global Markdown block in `unified_autoprompter/reference/current_use/audit.md`, with its packaged default under `reference/original`. Audit validation preserves the selected output contract: JSON must remain valid JSON, required headings and reference tokens remain intact, shot markers are preserved, and quoted text is not silently rewritten into a different structure. Cancellation still preserves the previous successful output.

## Prompt presets

Open **Presets** to create reusable character or scene records. Each preset stores a name, `@tag`, type, optional target profile, and adaptation guidance. Typing `@` in **Prompt instructions** opens autocomplete; choosing a tag expands the matching preset into the authoring request.

Packaged presets live under `unified_autoprompter/prompt_presets/original`, and the editable runtime catalog lives under `prompt_presets/current_use`. Built-in presets can be edited and reset to their packaged form but not deleted. Custom presets can be edited or deleted.

## Providers

Use the single **Provider** dropdown. The expandable **Model settings** panel changes to the selected provider and the node refits its height when the panel, provider, model list, or profile changes.

### Gemini

Gemini exposes API key, model discovery, timeout, and harassment, hate-speech, sexually-explicit, and dangerous-content thresholds. Optional generation parameters are left to the provider unless the interface explicitly supplies them.

### Grok API

Grok uses xAI's first-party Responses API at `https://api.x.ai/v1` with `store: false`. Settings include:

- xAI API key;
- language-model discovery and manual fallback;
- timeout and maximum output tokens;
- temperature and top-p;
- model-supported reasoning effort;
- prompt caching Auto/Off.

Model discovery combines `/language-models` capability data with `/models` context metadata. Image-assisted generation is blocked for a discovered text-only model. JSON contracts request structured JSON output; natural contracts request text. Unified does not enable search, tools, citations, conversation persistence, code execution, or encrypted reasoning.

Auto caching derives a stable non-sensitive key from engine, profile, generation type, format, stage, and the selected system-instruction checksum. User text, images, and credentials are excluded. Diagnostics may report sanitized model, context, input, output, reasoning, cached-token, and total-token statistics.

### DeepSeek API

DeepSeek is a dedicated first-party provider path using the official Chat Completions API at `https://api.deepseek.com`. It is separate from the generic OpenAI-compatible provider and exposes:

- DeepSeek API key;
- live `/models` discovery with manual model fallback;
- timeout and maximum output tokens;
- thinking mode and supported reasoning effort;
- temperature and top-p for non-thinking generation;
- capability-aware image input and image-detail selection for `deepseek-v4-flash-vision-exp`.

DeepSeek text-only models work for any path when no authoring image is connected. If an image is connected—even as Text-to-Image or Text-to-Video guidance—the selected model must support vision. The vision model accepts ordered ComfyUI images using inline OpenAI-compatible `image_url` blocks. Non-vision models reject submitted images before dispatch. Image detail supports Provider Default, Auto, Low, High, and Original; inline requests enforce DeepSeek's 32 MiB per-image and 48 MiB request-body limits.

Thinking output is never merged into the generated prompt; only final response content is parsed, while sanitized reasoning-token and automatic context-cache statistics may appear in diagnostics. Optional sampling values are omitted in thinking mode because the provider documents them as ineffective there.

### OpenAI Compatible

The generic OpenAI-compatible path supports arbitrary servers with base URL/key, discovery or manual model ID, timeout, reasoning where supported, and server-managed/keep-loaded/unload-after lifecycle behavior. It uses Chat Completions and does not assume LM Studio- or Unsloth-specific request fields.

### LM Studio

The dedicated LM Studio path uses the native `/api/v1/chat` interface with storage disabled. It supports multimodal image payloads, native model discovery, model instance lifecycle, maximum output tokens, context length, temperature, top-p, top-k, min-p, repeat penalty, and supported reasoning controls. When returned by the server, diagnostics include token counts, tokens per second, time to first token, and model-load time.

Unload failures are non-blocking. The generated result is retained and a sanitized warning is printed to the ComfyUI console.

### Unsloth Studio

The dedicated Unsloth path exposes server URL/key, discovery, timeout, maximum new tokens, temperature, top-p, top-k, min-p, repetition penalty, presence penalty, enable-thinking mode, reasoning effort, and preserve-thinking when advertised.

Discovery reports active/native/maximum context information. Unified does not send an unsupported per-request context override. Image calls are blocked when the active model reports that it lacks vision support. Unload failures remain non-blocking console warnings.

### Ollama

Ollama exposes host, model discovery, timeout, think, unload, maximum output tokens, context length, temperature, top-p, top-k, min-p, repeat penalty, and seed. Empty optional values are omitted so Ollama retains its own defaults.

### Local GGUF

Local GGUF keeps the existing recursive `ComfyUI/models/LLM` discovery plus optional semicolon-separated additional folders. It exposes model, mmproj, prompt preset, context, output length, sampling, memory/offload, reasoning, GPU/CPU layers, seed, and speculative MTP settings.

The standard Unified runtime is pinned under `vendor/llama.cpp`; the isolated Unified JsonX profile uses `vendor/unified-jsonx-llama.cpp`. MTP Auto detects compatible embedded metadata, Off disables it, and forced MTP enables the configured draft-token count. Long system prompts use short temporary UTF-8 files that are cleaned on success, failure, cancellation, and process-start errors.

## JsonX profile

JsonX uses the common Provider and Model settings UI but dispatches only through its private routes, providers, reference store, validation engine, cancellation registry, and llama.cpp cache. Its reference subtree is managed independently under `reference/original/JsonX` and `reference/current_use/JsonX`; standard profile operations ignore and preserve that subtree. The only shared prompt content is `nsfw-image.md`.

The JsonX profile action opens an isolated Markdown-backed editor with Overview, Path Settings, Templates, Presets, Output Contracts, and Preview. Overview controls Adaptive/Template Fill, Fast/Refined, Ranked/Full Adaptive context, hierarchy depth, Template Fill presets, framing, default format, and enabled/default generation route. Path Settings exposes every stage, repair, conditional, reference, and user-message template as an exact file-backed editor.

Templates exposes the ranked and full Adaptive context carriers plus both Template Fill hierarchy variants. Presets exposes the complete raw JSON catalog and validates it before Save. Output Contracts exposes the exact Stage 1, refined JSON, natural prose, JSON repair, and natural repair contracts. Unknown or missing template tokens, malformed presets, missing required blocks, and unsafe paths fail explicitly instead of falling back to hidden constants.

Natural output always follows the validated two-call path. Stage 1 remains in memory, Stage 2 receives no preset catalog, and Unified derives its `negative` output locally from the validated Stage 1 `negative` branch. Preview and generation use the same private payload builder. Duplicate, Import, Export, Save, Reset Profile, Reset All, and Revert operate on exact JsonX Markdown bundles, while the node serializes only behavior selections and JsonX provider choices remain isolated in browser storage.

## Markdown-backed profile settings

Standard profiles use a dedicated reference schema independently from the existing Unified/JsonX schema. Packaged defaults are immutable under `unified_autoprompter/reference/original`; runtime and UI always load `unified_autoprompter/reference/current_use`. On upgrade, newly packaged profiles and files are copied into `current_use` only when missing, so existing edits are not overwritten. Direct filesystem edits become active on the next Preview or Generate request without restarting ComfyUI.

The standard editor has two modes. **Profiles** provides Overview, Common Profile Rules, Generation Paths, Reference Usage, Output Contracts, and Preview. **Global Rules** provides Audit, Image NSFW, and Video NSFW editors. Every textarea contains the exact corresponding Markdown string, including headings, lists, tags, blank lines, and line endings.

- **Common Profile Rules** edits `split/common.md`.
- **Generation Paths** edits the selected enabled generation type's mapped file. Enabling a type without a file exposes a blank editor, and Save creates it.
- **Reference Usage** edits the three profile-level conditional files.
- **Output Contracts** selects one profile-wide contract by Natural/JSON/Tags and negative on/off; it is not duplicated per generation path.
- **Preview** reads the last saved `current_use`, which is also the generation source. Save draft edits before previewing them.

Save transactionally replaces only `current_use`. Revert discards unsaved modal edits. Reset Profile restores one built-in profile from `original`; Reset All restores all built-ins and the global Audit/Image/Video files while preserving custom profiles. Duplicate copies exact current Markdown into a custom profile. Import creates an unsaved draft, while Export downloads the last saved versioned bundle.

The standard manifest stores routing metadata only: profile keys and labels, folder mappings, media type, enabled/default formats and generation types, negative support, reference capability, filename mappings, and the reference schema version. It contains no model-facing instructions. JsonX has a separate manifest and reference-schema handshake; legacy profile JSON is not a JsonX prompt source.

The frontend/backend Unified handshake is version 8. Standard Markdown references use schema version 2; JsonX Markdown references and prompt presets each use their own version-1 handshake. If any browser/backend pair is stale, generation stops and asks you to restart ComfyUI and hard-refresh instead of sending an incompatible payload.

## Preserved controls

- `raw_prompt_text`, when enabled and readable, replaces only the manual Prompt instructions; Detail level still applies.
- BBox JSON sync, BBox Layout, palettes, layout application, image ordering, negative output, saved output widgets, node ID, and output indices remain compatible.
- **Cancel** marks the active request cancelled and preserves the previous output. Local llama.cpp processes are terminated through their cancellation event; remote results that arrive after cancellation are discarded.
- **Refresh VRAM** requests ComfyUI model unloading/cache cleanup before generation.

## Troubleshooting

### Schema mismatch after updating

Restart ComfyUI and hard-refresh the browser. The node deliberately refuses to mix v8 JavaScript with an older Python route or the reverse.

### Image guidance error

Unified accepts at most nine authoring images. If any image is connected, the selected provider model must accept vision input; Local GGUF also requires a compatible vision `mmproj`. Run or refresh upstream image nodes so their previews are readable before generating.

### Models do not appear

Use the active provider's discovery action. Generic OpenAI-compatible servers may require a manual model ID. For Local GGUF, add the existing model folder to **Additional model folders** and refresh instead of duplicating the file under ComfyUI.

### Provider Default

Leave an optional number empty to omit it from the request. Unified does not manufacture a sampling value for empty Grok, Studio, generic OpenAI, Gemini, or Ollama controls.

### Previous output remains after an error

This is intentional. Provider, validation, repair, context, image-capability, and cancellation failures do not replace the last successful output.
