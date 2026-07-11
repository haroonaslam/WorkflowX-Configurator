# NanoBanana Full API

`NanoBanana Full API` is registered under `WorkflowX_Configurator/Image/NanoBanana`. It keeps the workflow ID `NanoBanana_Gemini_2_5_Flash_V2` while updating the original node to Google's current Gemini image endpoints.

The WorkflowX implementation is derived from [`haroonaslam/ComfyUI_NanoBanana_Full_API` commit `a1a21b9`](https://github.com/haroonaslam/ComfyUI_NanoBanana_Full_API/commit/a1a21b936229fc6d37421d8c78d8622498378c9e).

## API Key

The key is resolved in this order:

1. Nonblank `api_key` password widget.
2. `GEMINI_API_KEY` environment variable.
3. `GOOGLE_API_KEY` environment variable.

The key is sent in the `x-goog-api-key` header. It is not placed in the URL, JSON body, logs, or node error text. Keys entered in a node widget can still be serialized into a workflow; use an environment variable when workflows may be shared.

## Models

| Model ID | Position | Notes |
| --- | --- | --- |
| `gemini-3.1-flash-image` | Default | Current general-purpose Nano Banana image model. |
| `gemini-3-pro-image` | Premium | Intended for complex instructions and professional asset work. |

Legacy Gemini 2.5 and preview model IDs are not exposed.

Both choices call:

```text
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
```

Google's current references are the [Gemini 3.1 Flash Image model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-image), [Gemini 3 Pro Image model page](https://ai.google.dev/gemini-api/docs/models/gemini-3-pro-image), [GenerateContent image guide](https://ai.google.dev/gemini-api/docs/generate-content/image-generation), and [safety-settings guide](https://ai.google.dev/gemini-api/docs/safety-settings).

The direct REST body follows the wire format emitted by Google's `google-genai` SDK for these stable model IDs: `v1beta` GenerateContent with `responseModalities`, `imageConfig`, and model-compatible `thinkingConfig`. This retains the original node's aspect-ratio shape while carrying every supported generation, resolution, thinking, and safety control.

## Inputs

- `prompt`: the user instruction.
- `system_prompt`: preserves the source node's behavior. A nondefault value is prepended to the user prompt as `system prompt`, a blank line, then `User: prompt`. The unchanged default system prompt is not added.
- `image_1` through `image_5`: optional labeled PNG reference images.
- `edit_mode_enabled`: when `yes`, an optional mask is labeled as the mask for image 1.
- `aspect_ratio`: requested output ratio.
- `resolution`: requested image size: `1K`, `2K`, or `4K`; defaults to `4K`.
- `timeout_seconds`: maximum time to wait for the Google request, from 1 to 3600 seconds; defaults to 120.
- `show_thoughts`: requests thought summaries and returns their text in `text_output`.
- `thinking_level`: Gemini 3.1 Flash Image only, with `minimal` and `high`; WorkflowX defaults to `high`. Gemini 3 Pro Image uses its model-managed thinking level, so this field is deliberately omitted for Pro.
- `seed`, `temperature`, and `top_p`: forwarded to generation configuration.
- `candidate_count`: requested number of response candidates, from 1 to 10.
- Four safety controls: harassment, hate speech, sexually explicit content, and dangerous content.

Every connected image and mask is encoded as PNG. The original natural-language labels (`image 1` through `image 5` and `mask for image 1`) are preserved in the request parts.

## Exact Request Mapping

All supported models receive the same controls:

| Node control | REST field |
| --- | --- |
| `system_prompt` | Prepended to `contents[0].parts[0].text` when nondefault |
| `temperature` | `generationConfig.temperature` |
| `top_p` | `generationConfig.topP` |
| `seed` | `generationConfig.seed` |
| `candidate_count` | `generationConfig.candidateCount` |
| `aspect_ratio` | `generationConfig.imageConfig.aspectRatio` |
| `resolution` | `generationConfig.imageConfig.imageSize` |
| `show_thoughts` | `generationConfig.thinkingConfig.includeThoughts = true` when enabled |
| Flash `thinking_level` | `generationConfig.thinkingConfig.thinkingLevel` as `MINIMAL` or `HIGH` |
| Output modalities | `generationConfig.responseModalities = ["TEXT", "IMAGE"]` |
| Images and mask | `contents[0].parts[].inlineData` |
| Safety overrides | Top-level `safetySettings[]` |

The node sends one content object containing the source node's combined prompt and all labeled image parts. No model path silently drops an original control.

## Safety Overrides

The four node widgets map to:

| Widget | API category |
| --- | --- |
| `safety_harassment` | `HARM_CATEGORY_HARASSMENT` |
| `safety_hate_speech` | `HARM_CATEGORY_HATE_SPEECH` |
| `safety_sexual` | `HARM_CATEGORY_SEXUALLY_EXPLICIT` |
| `safety_dangerous` | `HARM_CATEGORY_DANGEROUS_CONTENT` |

`BLOCK_NONE`, `BLOCK_LOW_AND_ABOVE`, `BLOCK_MEDIUM_AND_ABOVE`, and `BLOCK_ONLY_HIGH` are sent verbatim as the API threshold. `BLOCK_DEFAULT` is a local sentinel: that category is omitted so Google applies the model default.

These request-level filters cannot override Google's non-configurable core protections or post-generation model filtering.

## Generation and Editing

For text-to-image, leave all image inputs disconnected. For reference-guided generation, connect any of the five image inputs. For the source node's mask-guided editing convention, connect the primary image to `image_1`, connect a crop-space mask, and set `edit_mode_enabled=yes`. Select `1K`, `2K`, or `4K` resolution; both exposed Gemini 3 image models receive the selected value through `imageConfig.imageSize`.

The API may return thought summaries, answer text, thought images, final images, multiple candidates, safety feedback, or a mixture. The node:

- reports thought text under `=== CANDIDATE N THINKING ===`;
- reports non-thought answer text under `=== CANDIDATE N ANSWER ===`;
- excludes interim Gemini thought images from the ComfyUI image batch while reporting their presence;
- decodes every final image from every successful candidate;
- concatenates successful images into one ComfyUI batch;
- reports final-image counts under `=== CANDIDATE N RESULT ===`;
- keeps partial-success warnings, decode errors, finish reasons, and safety details in `text_output`;
- returns a 1x1 black placeholder plus error text when no image succeeds.

Gemini 3.1 Flash Image supports `minimal` and `high` thinking levels. Gemini 3 Pro Image supports thinking and thought inclusion, but its image API does not expose those Flash levels. Setting `show_thoughts=false` hides thought summaries; it does not disable internal model thinking or avoid thinking-token charges.

## Candidate Count and Cost

`candidate_count` is forwarded as `generationConfig.candidateCount`. Higher values can increase API usage and cost. Resolution also affects output usage: `4K` costs more than `2K` or `1K`. Keep the resolution tokens uppercase exactly as shown. The model may return fewer usable images because candidates can finish without images or be blocked independently. The output text reports those partial results.

No test in WorkflowX calls the live Google API. Request behavior is validated with mocked responses so development checks do not incur charges.

## Errors

- Missing key: set the widget or one of the supported environment variables.
- HTTP error: the output includes the status code and Google response body, without the submitted key.
- Timeout: `timeout_seconds` controls the request limit, and the selected value is reported in timeout errors.
- Prompt block: `promptFeedback` reason and safety ratings are returned in text.
- Candidate safety block: other candidates continue to be processed.
- Text-only response: the text is returned with the placeholder if no candidate produced an image.
- Decode failure: the affected image is skipped and reported while other successful images remain available.
