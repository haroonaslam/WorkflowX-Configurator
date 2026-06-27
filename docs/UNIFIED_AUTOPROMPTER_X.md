# Unified Autoprompter X Guide

`Unified Autoprompter X` is a WorkflowX prompting node for building model-targeted prompts from one UI. It can generate prompt text through Gemini, Ollama, or local GGUF backends, then writes the result into normal ComfyUI node outputs.

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
- Ideogram 4 layout editing helpers

## Node Inputs And Outputs

Inputs:

| Name | Type | Notes |
| --- | --- | --- |
| `target_model` | dropdown | Prompt profile target, such as `ideogram4` or `sdxl`. |
| `prompt_format` | dropdown | `natural`, `tags`, or `json`; unsupported choices are normalized for the selected profile. |
| `negative_enabled` | `BOOLEAN` | Enables separate negative prompt generation/output. |
| `generated_positive` | multiline `STRING` | UI-managed positive output. |
| `generated_negative` | multiline `STRING` | UI-managed negative output. |
| `final_prompt` | multiline `STRING` | UI-managed final prompt. |
| `image` | optional `IMAGE` | Optional visual reference. |
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

Unified Autoprompter X can generate through three backend modes.

### Gemini

Use Gemini when you want cloud model generation.

UI fields:

- Gemini API key
- Gemini model
- timeout
- fetch models

The API key is stored in the browser via the frontend helper, not in the node's visible prompt outputs.

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

## Video Prompt Fields

For video profiles, the UI exposes extra intent fields:

- video duration or frames
- motion / action
- temporal beats
- camera movement
- audio / dialogue
- reference or control notes

These fields are included only when the active profile is a video profile, such as `wan2_2` or `ltx_2_3`.

## Ideogram 4 Tools

When `target_model` is `ideogram4`, the UI exposes Ideogram-specific helpers.

Capabilities include:

- structured JSON prompt output
- bbox/layout JSON hints
- palette hints
- layout editor
- image overlay preview
- saved layout templates
- apply layout to output
- copy/sync layout JSON

The Ideogram tools are meant for spatial composition, text placement, object boxes, and color/layout control. They write back to the same node fields used by the normal prompt outputs.

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
6. Choose Gemini, Ollama, or Local GGUF.
7. Enter the idea, subject, image note, or video notes.
8. Click `Generate`.
9. Review positive, negative, and final prompt output.
10. Connect `prompt`, `positive`, or `negative` to downstream text-consuming nodes.

## Troubleshooting

### Gemini models do not load

Check that the API key is present, the timeout is high enough, and the network can reach Gemini.

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
