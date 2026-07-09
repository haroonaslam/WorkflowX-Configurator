# Unified Autoprompter X Guide

`Unified Autoprompter X` is a WorkflowX prompting node for building model-targeted prompts from one UI. It can generate prompt text through Gemini, OpenAI-compatible, Ollama, or local GGUF backends, then writes the result into normal ComfyUI node outputs.

The node lives under:

```text
WorkflowX_Configurator/Prompting
```

## What It Does

Unified Autoprompter X helps convert a short idea, subject, image reference, or video intent into prompt output tailored for the selected target model.

It supports:

- image and video prompt profiles
- natural, tags, and JSON prompt formats
- optional negative prompt output
- optional connected image reference
- Gemini model generation
- Ollama model generation
- local GGUF generation
- editable model/profile instructions
- BBox Layout editing helpers for bbox-capable targets

## Node Inputs And Outputs

Inputs:

| Name | Type | Notes |
| --- | --- | --- |
| `target_model` | dropdown | Prompt profile target, such as `ideogram4` or `sdxl`. |
| `prompt_format` | dropdown | `natural`, `tags`, or `json`; unsupported choices are normalized for the selected profile. |
| `negative_enabled` | `BOOLEAN` | Enables separate negative prompt generation/output. |
| `enable_bbox_json_input` | `BOOLEAN` | UI-managed toggle for reading connected `bbox_json` during BBox Layout sync. |
| `enable_text_input` | `BOOLEAN` | UI-managed toggle for using connected `raw_prompt_text` during generation. |
| `refresh_vram` | `BOOLEAN` | UI-managed toggle to unload ComfyUI models and clear cache before prompt generation. |
| `generated_positive` | multiline `STRING` | UI-managed positive output. |
| `generated_negative` | multiline `STRING` | UI-managed negative output. |
| `final_prompt` | multiline `STRING` | UI-managed final prompt. |
| `image` | optional `IMAGE` | Optional visual reference. |
| `bbox_json` | optional connected `STRING` | Raw bbox layout JSON used only when `enable_bbox_json_input` is on and the user clicks BBox Layout `Sync`. |
| `raw_prompt_text` | optional connected `STRING` | Raw upstream prompt text or JSON used as the generation source when `enable_text_input` is on. |
| `ui_state` | optional multiline `STRING` | UI-managed editor/backend state. |

Outputs:

| Name | Type | Notes |
| --- | --- | --- |
| `prompt` | `STRING` | Final prompt ready for downstream nodes. |
| `positive` | `STRING` | Positive prompt text. |
| `negative` | `STRING` | Negative prompt text, or empty when negative output is disabled. |

For JSON prompt formats, the `prompt` output is the final JSON text. For natural and tag formats, `prompt` is assembled from positive and optional negative text.

## Built-In Profiles

Default profiles are stored in:

```text
unified_autoprompter/model_prompt_profiles.defaults.json
```

Current built-in targets:

| Profile | Key | Media | Default format |
| --- | --- | --- | --- |
| Ideogram 4 | `ideogram4` | image | `json` |
| SDXL | `sdxl` | image | `tags` |
| Qwen-Image | `qwen_image` | image | `natural` |
| FLUX.1 dev | `flux1_dev` | image | `natural` |
| FLUX.2 dev | `flux2_dev` | image | `natural` |
| Flux Klein | `flux_klein` | image | `natural` |
| Krea2 | `krea2` | image | `natural` |
| Z-Image | `z_image` | image | `natural` |
| WAN 2.2 | `wan2_2` | video | `natural` |
| LTX 2.3 | `ltx_2_3` | video | `natural` |

Profiles define:

- display label
- media type: image or video
- enabled prompt formats
- default format
- negative prompt support
- with-image and without-image instructions
- output contracts for negative on/off states

## Prompt Formats

| Format | Typical use |
| --- | --- |
| `natural` | A polished paragraph or production prompt. |
| `tags` | Comma-separated diffusion-style tags. |
| `json` | Structured prompt JSON for models or workflows that benefit from schema-like control. |

The selected profile decides which formats are available. If a workflow stores an invalid format for the current target, the node normalizes to that profile's default enabled format.

## Generation Backends

Unified Autoprompter X can generate through four backend modes.

### Gemini

Use Gemini when you want cloud model generation.

UI fields:

- Gemini API key
- Gemini model
- timeout
- fetch models

The API key is stored in the browser via the frontend helper, not in the node's visible prompt outputs.

### OpenAI Compatible

Use OpenAI Compatible when you want generation through LM Studio, Open WebUI, LiteLLM, or another server that exposes an OpenAI-compatible API.

UI fields:

- base URL, default `http://localhost:1234/v1`
- optional API key
- model ID, typed manually or selected after fetching
- optional unload after
- timeout
- fetch models

The backend lists models from `{base_url}/models` and generates through `{base_url}/chat/completions`. Connected image previews are sent as Chat Completions `image_url` data URLs when available.

The API key is stored in the browser via the frontend helper, not in the node's visible prompt outputs. Leave it empty for local servers that do not require authentication.

When `unload after` is enabled, the compatible backend first generates through Chat Completions and then attempts LM Studio's unload endpoint, `POST /api/v1/models/unload`, using the selected model ID as `instance_id`. This unload request is best effort: if the endpoint is missing, rejects the request, or times out, generation output is still returned normally. Ollama keeps its separate `keep_alive: 0` unload behavior.

Common base URL examples:

- LM Studio: `http://localhost:1234/v1`
- Open WebUI: use the OpenAI-compatible base URL exposed by the instance, commonly ending in `/v1` or `/api` depending on setup.

### Ollama

Use Ollama when you have a local Ollama server running.

UI fields:

- Ollama host, default `http://localhost:11434`
- Ollama model
- optional think mode
- fetch models

The backend calls the configured Ollama host and can send the connected image when the selected model supports image input.

### Local GGUF

Use Local GGUF when you want generation through local llama.cpp-compatible files discovered by WorkflowX.

WorkflowX registers:

```text
ComfyUI/models/LLM/
ComfyUI/models/LLM/prompts/
```

Local model support uses:

- `.gguf` model files under `models/LLM`
- optional mmproj `.gguf` files under `models/LLM`
- optional system prompt `.txt` presets under `models/LLM/prompts`

UI fields include model selection, mmproj selection, system prompt preset, and local generation options.

## Connected Image Input

The optional `image` input lets the frontend capture an upstream image preview and send it as visual context during generation.

Use it for:

- image-to-prompt
- reference-based edits
- layout or identity preservation
- color, lighting, pose, or composition extraction

If the connected image has no preview yet, run or refresh the upstream image node first so the frontend can capture it.

## Connected JSON And Text Inputs

The optional `bbox_json` and `raw_prompt_text` inputs are raw `STRING` connections.

`bbox_json` is sync-only. When `Use connected bbox JSON` is enabled, the BBox Layout editor's `Sync` button first reads the connected JSON and renders its regions. Generation does not automatically use connected bbox JSON until you sync or apply the layout.

`raw_prompt_text` is generation-source only. When `Use connected text` is enabled and the connected text is readable, Unified Autoprompter X sends that raw text to the selected backend instead of the Idea, Subject, Style, Camera, and Text fields. The backend still refines it normally for the selected target model and format. The connected text can be plain text or arbitrary JSON.

If either enabled input is missing or unreadable, the UI shows a status warning and falls back to the current cached output or form fields.

## VRAM Refresh

Enable `refresh VRAM` before generation when existing ComfyUI image/video models are still resident and may compete with the prompt model for VRAM. When checked, Unified Autoprompter X asks ComfyUI to unload all loaded models and clear cache before calling the selected prompt backend. This may make generation start a little slower, but can prevent prompt LLM loading from spilling into system RAM.

## Video Prompt Fields

For video profiles, the UI exposes extra intent fields:

- video duration or frames
- motion / action
- temporal beats
- camera movement
- audio / dialogue
- reference or control notes

These fields are included only when the active profile is a video profile, such as `wan2_2` or `ltx_2_3`.

## BBox Layout Tools

When `target_model` is bbox-capable, the UI exposes BBox Layout helpers.

Initial bbox-capable targets:

| Target | Key | BBox order |
| --- | --- | --- |
| Ideogram 4 | `ideogram4` | `[y_min,x_min,y_max,x_max]` |
| Krea2 | `krea2` | `[x_min,y_min,x_max,y_max]` |

Capabilities include:

- structured JSON prompt output
- bbox/layout JSON hints
- palette hints
- layout editor
- image overlay preview
- saved layout templates
- apply layout to output
- copy/sync layout JSON
- keyboard delete/backspace for the selected unlocked region

The BBox Layout editor stores boxes internally as normalized canvas rectangles, then imports and exports the correct bbox order for the active target model. `Apply layout to output` writes the current layout JSON to the node output and selects JSON format for the active bbox-capable target.

## Model Settings

Click `Model settings` in the UI to edit target profiles.

Profile settings include:

- key
- label
- media type
- default format
- negative support
- JSON support
- notes
- per-format enablement
- common format instructions
- with-image instructions
- without-image instructions
- output contract when negative is off
- output contract when negative is on

Built-in profiles can be reset to WorkflowX defaults. Custom profiles can be added, duplicated, edited, and deleted.

Use `Export JSON` to write the current model settings, default profiles, custom profiles, and profile metadata to one JSON file. Use `Import JSON` to load a previously exported file back into the settings draft, then review it and click `Save` to apply it.

User profile settings are saved to:

```text
unified_autoprompter/model_prompt_profiles.json
```

When saving over an existing file, WorkflowX creates a `.bak` backup.

## Output Behavior

The backend generation route returns parsed fields:

- `prompt`
- `positive`
- `negative`
- raw backend response
- target model
- prompt format
- negative enabled state

The frontend writes generated values back into node widgets. The Python node then returns those widget values as ComfyUI outputs at execution time.

Important details:

- If `final_prompt` is populated, it wins as the `prompt` output.
- If `negative_enabled` is off, the negative output is empty.
- For tag format, generated text is normalized into comma-separated tags.
- For JSON format, the parser extracts the JSON object from fenced or plain responses when possible.

## Practical Workflow

1. Add `Unified Autoprompter X`.
2. Choose `target_model`.
3. Choose `prompt_format`.
4. Enable negative output only if the downstream workflow needs it.
5. Optionally connect an image input.
6. Choose Gemini, OpenAI Compatible, Ollama, or Local GGUF.
7. Enter the idea, subject, image note, or video notes.
8. Click `Generate`.
9. Review positive, negative, and final prompt output.
10. Connect `prompt`, `positive`, or `negative` to downstream text-consuming nodes.

## Troubleshooting

### Gemini models do not load

Check that the API key is present, the timeout is high enough, and the network can reach Gemini.

### OpenAI Compatible models do not load

Check that the base URL is correct, the timeout is high enough, and the API key is present if the server requires one. Some compatible servers do not expose model discovery; type the model ID manually and generate through chat completions.

### Ollama models do not load

Check that Ollama is running and the host field points to the correct server, usually:

```text
http://localhost:11434
```

### Local GGUF list is empty

Place `.gguf` files under:

```text
ComfyUI/models/LLM/
```

Then click `Refresh local GGUF list`.

### Connected image is ignored

Run or refresh the upstream image node first. Unified Autoprompter X needs a frontend image preview to convert the connected image into generation context.

### Output format looks wrong

Open `Model settings` and check the selected profile's enabled formats and output contracts. The parser expects backend responses to follow the active profile's contract.
