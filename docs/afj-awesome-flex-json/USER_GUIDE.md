# JsonX User Guide

> [Documentation and node contracts](../../README.md#prompting-and-jsonx) · [Connected JsonX example](../../examples/06-jsonx-prompt-toolchain.json)

## 1. What You Can Do
JsonX provides four nodes under `WorkflowX/Prompting/JsonX`:

1. `LLM to JsonX`: preset-aware generation from instructions and an optional image.
2. `JsonX - Visual Builder`: visual tree editor for prompt JSON.
3. `JsonX - Template Randomizer`: runtime randomization from saved templates.
4. `JsonX - Prompt Template Importer`: convert final prompt JSON into JsonX template format and save it.

## 2. LLM to JsonX Quick Start

1. Add `LLM to JsonX`.
2. Enter instructions and optionally connect one `IMAGE`.
3. Choose a provider and model in the embedded JsonX panel.
4. Keep `fast` for one generation call, or select `refined` for a preset-aware first pass plus a preset-agnostic coherence pass.
5. Keep `optimized` to send every live schema path plus a bounded, deterministically ranked set of relevant preset values. Select `full` only when the model can accept the complete preset catalog; JsonX shows an estimated size warning and never silently falls back.
6. Click `Generate`. The validated result is saved in the node, displayed in the read-only output box, and returned from the generic `prompt` output when queued; the prior result is retained if generation or validation fails.

The Settings modal offers **Adaptive** and **Template Fill** profiles. Adaptive is the existing default and continues to follow the node's Optimized/Full selector. Template Fill instead supplies the complete blank JsonX hierarchy with `null` leaves. Enable **Use Presets** to append the full preset catalog verbatim; suitable catalog values are preferred, while missing concepts receive a custom value written in the same style. Leave it disabled to send only the blank hierarchy. The model retains `null` where a leaf genuinely does not apply, and the backend removes those leaves and empty containers before validation. Refined Template Fill improves coherence and wording without replacing or restructuring the populated Stage 1 tree.

**Output format** is saved per node and defaults to **JsonX JSON**. Choose **Natural language** to automatically use Refined and run two passes for either profile. Stage 1 produces the same validated canonical JsonX in memory; Stage 2 uses the same provider to improve coherence while converting every non-null detail into prose. It may use top-level headings, expresses `negative` as avoidance guidance, preserves multiple subjects and interactions, and includes all nine framing regions when enabled. Only the final prose is saved and returned from `prompt`.

Enable **Framing & placement (3x3 rule-of-thirds map)** to add an explicit nine-region composition map in Adaptive or Template Fill. Each top/middle/bottom and left/center/right region receives a concrete description of the visible image content. Background and negative space are described rather than left blank, and a subject or object spanning regions is described in every affected region. This checkbox is saved on the individual node and travels with the workflow; Reset defaults turns it off.

JsonX defaults to **Deep** hierarchy generation. It asks the model to decompose visible concepts into atomic leaves and use the catalog's deepest compatible paths—for example nested clothing, pose, appearance, lens, and exposure branches—while omitting details unsupported by framing. Click `Settings` to select **Exhaustive** when you want still broader visible-detail coverage.

Neither mode uses a numerical leaf range or maximum. Deep maximizes all relevant tree and subtree coverage; Exhaustive makes a broader branch-by-branch relevance pass. The model must not stop because it has reached a count, and it must not create unsupported filler simply to increase that count.

The preset catalog is not an exhaustive vocabulary. JsonX chooses a preset only when it faithfully matches the intended detail. If no supplied value fits, it reasons out a concise custom value on the appropriate catalog path; if no path fits either, it adds a small descriptive subtree under the nearest logical parent. Custom keys use readable `lower_snake_case`, custom values use natural visual wording, and independent attributes stay as separate atomic leaves. Missing preset coverage never causes a requested or visible concept to be silently dropped.

The Settings modal also exposes the editable Adaptive Stage 1, Template Fill Stage 1, JSON refinement, and Natural Language Stage 2 system instructions. `Refresh effective preview` shows the exact selected backend prompts, output format, blank hierarchy, framing-map state, and preset context. `Reset defaults` restores JsonX JSON, Fast mode, and the packaged instructions. Saved custom instructions remain only in JsonX browser storage and are not embedded in workflow JSON.

After Generate, the status line reports the resulting atomic leaf count, maximum hierarchy depth, and number of root groups. These measurements are diagnostic only and are never generation targets or stopping conditions; visibility, relevance, and evidence govern the content.

Provider settings and credentials are stored in JsonX-specific browser storage. API keys are not saved in workflow JSON or returned through the node output. Queueing emits the saved JSON or natural-language `prompt`; it does not invoke the provider again.

For Gemini, expand `Gemini safety settings` to configure harassment, hate-speech, sexually-explicit, and dangerous-content blocking thresholds. These match Unified Autoprompter X and default to `BLOCK_NONE`.

If Gemini returns no candidates, JsonX does not retry. `Generation diagnostics` shows the provider's sanitized prompt feedback or blocking reason without exposing the API key, and the previous JSON or natural-language output remains saved.

Fetched provider models appear in full-list pickers. OpenAI-compatible and Ollama panels expose unload controls, Ollama also exposes think mode, and `Refresh VRAM` can unload active ComfyUI models before generation. Timeout values are remembered separately per backend.

Preset IDs such as `env_indoor_home` are lookup metadata and never belong in final output. JsonX automatically converts recognized ID-key objects into canonical scalar path/value fields and normalizes a singular generated `subject` into `subjects`. If generation and its one repair call both fail, expand `Generation diagnostics` to inspect the transient raw responses; the previously saved prompt remains intact.

When using Local GGUF, expand `Local generation settings` for context size, maximum output length, sampling, memory/offload, reasoning, speculative decoding, and seed controls. New JsonX settings default to reasoning off and an 8192-token output ceiling; this leaves the model's generation budget available for the deep JSON tree. `full` mode commonly needs more context than `optimized`. JsonX uses its own llama.cpp runtime cache. Long system instructions are supplied through short temporary UTF-8 files and removed when the call finishes, fails, or is cancelled, so they do not hit the Windows command-line length limit or accumulate during normal use.

To reuse models already downloaded by LM Studio or another application, enter their containing directories in `Additional model folders`, separated by semicolons, and refresh the model list. JsonX scans those directories recursively alongside `ComfyUI/models/LLM`, deduplicates identical resolved files, and labels external GGUF/mmproj choices. Paths remain in JsonX browser storage, are not serialized into workflows, and are separate from Unified Autoprompter settings.

For GGUFs with an embedded multi-token-prediction head, leave `Speculative decoding` on `Auto`. JsonX detects the MTP metadata and launches its isolated llama.cpp runtime with `draft-mtp`; `MTP draft tokens` defaults to 2. Use `Off` only for ordinary decoding or troubleshooting.

## 3. Visual Builder Quick Start

1. Add `JsonX - Visual Builder` node.
2. Click `Open Visual Builder`.
3. Build/edit your prompt tree.
4. Click `Validate & Apply` to write JSON into `prompt_json`.

Important behavior:
1. All tags are optional.
2. Empty values are omitted from output.
3. `Close` discards in-session unsaved edits.
4. `Validate & Apply` is the save boundary for editor state.

## 4. Templates (Per-File Storage)
Templates are stored as separate files:
1. `visual_builder/templates/<template_name>.json`

Template file rules:
1. Field `options` are not stored.
2. Legacy template files that embed `options` are not supported and will be skipped.

Template operations in Visual Builder:
1. `Save`
2. `Load` (explicit, selection is non-destructive)
3. `Delete`

### Filename rules
Template names are rejected if they:
1. are empty
2. contain invalid filename chars (`< > : " / \ | ? *`)
3. end with dot/space
4. are reserved Windows names (like `CON`, `PRN`, `AUX`, `NUL`, `COM1`...)

## 5. Prompt Template Importer (JSON -> Template)
Use `JsonX - Prompt Template Importer` when you have JSON prompt text from another source.

### Steps
1. Add node and click `Open Prompt Template Importer UI`.
2. Enter `template_name`.
3. Paste **final prompt JSON object** into source box.
4. Click `Convert/Preview`.
5. Check preview and report.
6. Click `Save Template`.

### Input constraint
Importer accepts final prompt JSON object only.
If JSON looks like JsonX metadata payload (`tree` / `randomizer_checked`), conversion is rejected with a clear error.

### Conversion behavior
1. Builds a minimal tree from your prompt JSON only (no extra blank starter sections).
2. Matching paths get preset bindings.
3. Unknown keys become custom fields/groups/arrays.
4. Arrays support object items and primitive items.
5. Saved templates strip `options`; live options are rehydrated from current `presets.json`.

## 6. Template Randomizer Quick Start
1. Add `JsonX - Template Randomizer` node.
2. Click `Open Template Randomizer UI`.
3. Select template and fields.
4. Apply writes `randomize_rules` back to node.
5. Run graph; node outputs randomized `prompt_json` plus `run_log`.
6. Preset randomization uses current `presets.json` dynamically (not frozen template option blobs).

## 7. Update the Authoritative `presets.json`
File: `visual_builder/presets.json`

This file is the authoritative JsonX schema and value catalog. Its root categories, nested branches, field paths, preset IDs, and values are discovered dynamically by the backend starter tree, Visual Builder, importer, saved-template hydration, randomizer, and LLM preset context. Preserve valid UTF-8 JSON and reload the ComfyUI frontend after replacing or editing it.

### Add options to existing field
```json
{
  "camera": {
    "angle": {
      "angle_eye": "eye-level camera angle",
      "angle_topdown": "top-down overhead angle"
    }
  }
}
```

### Add new preset-backed field
```json
{
  "scene": {
    "subject_position": {
      "pos_center": "subject centered in frame",
      "pos_left": "subject on left third"
    }
  }
}
```

### Add free-text field
```json
{
  "scene": {
    "notes": ""
  }
}
```

After editing presets:
1. Reload ComfyUI frontend.
2. Reopen builder/importer UI.

### Add a root category
```json
{
  "story": {
    "arc": {
      "arc_setup": "story setup phase"
    },
    "additional_information": ""
  }
}
```

No code change is required for a new root category. The reserved mappings remain:

1. Catalog `subject` becomes the repeatable output `subjects` array; every branch below it is discovered dynamically.
2. `interaction_suggestions` provides choices for the editable output `interactions` group.
3. `negative` remains an editable free-form output branch.

### Add a subject subsection

Add it anywhere under `subject` in `visual_builder/presets.json`. New subject cards and importer bindings discover the subsection automatically.

## 8. Troubleshooting

1. Template not visible:
   1. Check save response/status message.
   2. Verify file exists under `visual_builder/templates/`.
2. Importer says metadata payload:
   1. Paste final prompt object JSON, not JsonX template JSON.
3. Preset dropdown missing for a field:
   1. Use `Attach Preset Options` in Visual Builder.
4. Apply blocked in Visual Builder:
   1. Check validation panel or use `Force apply` if intentional.
