# JsonX Technical Documentation

## 1. Purpose
This project provides JsonX nodes for JSON-prompt generation, authoring, and runtime randomization in ComfyUI:
1. `LLMToJsonX` (display: `LLM to JsonX`)
2. `FluxVisualJsonBuilder` (display: `JsonX - Visual Builder`)
3. `FluxTemplateRandomizer` (display: `JsonX - Template Randomizer`)
4. legacy internal `AFJPromptTemplateImporter` (display: `JsonX - Prompt Template Importer`)

## 2. Active Components
1. Package entry: `__init__.py`
2. Backend:
   1. `visual_builder/api.py`
   2. `visual_builder/node.py`
   3. `visual_builder/jsonx_llm.py`
   4. `visual_builder/jsonx_backends/` (isolated provider and local-runtime implementations)
   5. `visual_builder/presets.json`
   6. `visual_builder/templates/` (one JSON file per template)
3. Frontend extensions:
   1. `web/js/flux_visual_builder.js`
   2. `web/js/flux_template_randomizer.js`
   3. `web/js/afj_prompt_template_importer.js`
   4. `web/js/llm_to_jsonx.js`

## 3. Node Contracts
### 3.1 LLM to JsonX

Node class: `LLMToJsonXNode`

1. Inputs: multiline `user_instructions`, `generation_mode`, `preset_context_mode`, UI-managed `generated_prompt_json`, optional `IMAGE`, and a reserved UI state string.
2. Output: validated `prompt_json` string only.
3. Provider calls happen only through the Generate action. Queue execution validates and returns the saved JSON without calling a provider.
4. Browser provider configuration and credentials use JsonX-specific local-storage keys; the UI never writes them into node widgets or workflow properties.
5. The read-only output preview mirrors `generated_prompt_json`; it is display-only and adds no serialized field.
6. Response extraction accepts exactly one unambiguous JSON object, including a sole fence or common reasoning/preamble wrappers. Multiple object candidates are rejected before validation or repair. An unfinished local reasoning channel remains transient input to the single repair pass and never enters `prompt_json`.
7. Canonicalization keeps catalog leaves scalar while preserving open-world nested expansions in deterministic sibling `<leaf>_details` branches. Scalar lists at catalog leaves are joined without dropping entries, which supports negative-prompt lists from local models.
8. Adaptive is the default generation profile and retains the existing Optimized/Full context behavior. Template Fill dynamically converts every live catalog leaf to `null`, maps `subject` to the repeatable `subjects` array, and maps `interaction_suggestions` to `interactions`. Its independent preset checkbox sends either no catalog or the complete raw catalog verbatim.
9. Template Fill null pruning is deterministic backend work. Refined Template Fill overlays Stage 2 scalar changes only at Stage 1 paths, preserves omitted Stage 1 paths, honors explicit null removal, and discards structural additions.
10. Gemini safety thresholds mirror Unified Autoprompter X and are transported in the transient `gemini_safety` request object.
11. Canonicalization resolves recognized preset-ID keys to catalog paths/values, rebases misplaced known siblings, flattens leaf objects, and maps singular `subject` to `subjects` before final validation.
12. A failed initial response and failed repair response are returned only as transient route diagnostics; neither is written to a widget, workflow, or `prompt_json`.
13. Provider parity state includes full-list model pickers, per-backend timeouts, OpenAI unload, Ollama think/unload, and a JsonX-owned VRAM refresh helper.
14. JsonX provider modules do not import Unified Autoprompter X. Local model discovery reads `ComfyUI/models/LLM` independently, and local inference uses only `vendor/jsonx-llama.cpp`.
15. An empty Gemini candidates response is not retried. Sanitized prompt feedback is returned as transient diagnostics while the saved output remains unchanged.
16. Stage 1 defaults require atomic parent/child/sub-child expansion to the deepest coherent catalog or custom paths. Deep maximizes relevant hierarchy; Exhaustive performs a broader branch-by-branch relevance pass. Neither mode has a numerical leaf target, depth ceiling, or maximum, and leaf count never acts as a stopping condition.
17. `/workflowx/jsonx/instructions` returns packaged instruction templates. `/workflowx/jsonx/instructions/preview` returns exact effective Stage 1 and Stage 2 prompts without invoking a provider. Browser-local custom templates and detail level are sent transiently only during Generate.
18. Generation route metadata includes hierarchy leaf, branch, depth, and root counts for UI troubleshooting; these metrics are not inserted into `prompt_json`.
19. The always-appended open-world preset contract treats catalog entries as canonical guidance rather than an allow-list. Meaning-preserving matches are canonicalized, while unmatched known-path values and unknown nested branches remain custom prompt content. This invariant also applies when browser-local custom instruction templates replace the packaged editable text.
20. Local discovery accepts up to 16 transient additional roots from JsonX browser storage. Recursive `.gguf` results are deduplicated by resolved path; external selections use a root-hash plus relative-path token and are revalidated inside the supplied root before generation. The setting and absolute roots are never serialized into workflow JSON.
21. JsonX pins its isolated CUDA llama.cpp runtime to `b10252`. Local command construction reads the GGUF metadata needed to detect an embedded Qwen MTP head and applies `--spec-type draft-mtp` plus the configured draft-token depth without importing or executing LM Studio or Unified runtime files.

### 3.2 JsonX - Visual Builder
Node class: `FluxVisualJsonBuilderNode`
1. Input widget: `prompt_json` (multiline string, optional)
2. Output: `prompt_json` string
3. UI writes compiled JSON directly to node `prompt_json`.

### 3.3 JsonX - Template Randomizer
Node class: `FluxTemplateRandomizerNode`
1. Inputs:
   1. `template_name`
   2. `randomize_rules` (`path | mode | value` lines)
   3. `randomize_rules_help`
   4. `seed`
2. Outputs:
   1. `prompt_json`
   2. `run_log`

### 3.4 JsonX - Prompt Template Importer
Node class: `AFJPromptTemplateImporterNode`
1. Inputs:
   1. `template_name`
   2. `source_prompt_json`
   3. `import_report`
2. Output:
   1. `template_payload_json`
3. UI supports Convert/Preview and Save to template storage.

## 4. Template Storage v2
Storage is now **folder-based**.

Path:
1. `visual_builder/templates/<template_name>.json`

File payload (strict):
```json
{
  "tree": { "...": "..." },
  "randomizer_checked": []
}
```

Rules:
1. `options` are not stored in template files.
2. Legacy template files embedding `options` are rejected at load time.

`templates.json` is no longer used.

### Name validation rules
Template save rejects names that:
1. Are empty/whitespace
2. Start/end with whitespace
3. End with `.` or space
4. Contain control chars or any of `< > : " / \ | ? *`
5. Use reserved Windows names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`...`COM9`, `LPT1`...`LPT9`)
6. Resolve outside template directory

## 5. API Layer
`register_visual_builder_routes()` exposes:
1. `GET /fluxvisual/presets`
2. `GET /fluxvisual/templates`
3. `POST /fluxvisual/templates/save`
4. `POST /fluxvisual/templates/delete`
5. `POST /fluxvisual/validate`
6. `POST /fluxvisual/import/convert`

Legacy `/fluxvisual` routes remain unchanged. JsonX generation additionally exposes:

1. `GET /workflowx/jsonx/presets/info`
2. `GET /workflowx/jsonx/local/models`
3. `POST /workflowx/jsonx/gemini/models`
4. `POST /workflowx/jsonx/openai/models`
5. `POST /workflowx/jsonx/ollama/models`
6. `POST /workflowx/jsonx/generate`

### `/fluxvisual/import/convert`
Input:
```json
{ "source_prompt_json": "{...}" }
```

Output:
```json
{
  "ok": true,
  "report": "...",
  "warnings": [],
  "summary": {
    "total_fields": 0,
    "non_empty_fields": 0,
    "non_empty_preset_fields": 0,
    "non_empty_custom_fields": 0
  },
  "data": {
    "tree": { "...": "..." },
    "randomizer_checked": []
  }
}
```

## 6. Importer Conversion Behavior
1. Accepts **final prompt JSON object only**.
2. Rejects JsonX metadata/template payloads (`tree`, `randomizer_checked`) with explicit error.
3. Builds a minimal tree from the prompt object only (no starter blank sections).
4. Unknown keys become custom fields/groups/arrays.
5. Arrays support object items and primitive items (`value` field mapping for primitives).
6. Preset binding is path-first from `presets.json`; unmatched fields remain custom.
7. Converted/saved template payload strips `options` (dynamic rehydration on load).

## 7. Visual Builder Persistence
Applied editor state is stored in node hidden props:
1. `properties.flux_visual_state`

Payload:
1. `version`
2. `prompt_signature`
3. `tree`
4. `randomizer_checked`

State persists only on `Validate & Apply`.

## 8. Validation Rules (Current)
`validate_prompt_payload()` checks:
1. Payload is object
2. `subjects` is array when present
3. Subject items are objects
4. Duplicate `subject.id` warns
5. `interactions` non-object warns

## 9. Extension Notes
### Add new preset options to existing field
Edit `visual_builder/presets.json` leaf object values. UI picks up after reload.

### Add a new root category

Add the root key in `visual_builder/presets.json`. Backend/frontend starter trees, preset attachment, importer hydration, randomizer lookup, and LLM schema generation traverse the catalog dynamically. Add bespoke backend validation only when the new category requires a structural rule beyond the generic prompt contract.

### Add subject subsection
Add it under `subject` in `visual_builder/presets.json`; repeatable subject templates discover it dynamically.

## 10. Smoke Checklist
1. Save/load/delete templates and verify per-file creation/removal under `visual_builder/templates/`
2. Invalid filename save returns clear error
3. Visual Builder template list still works
4. Template Randomizer resolves preset options dynamically from current `presets.json` using field binding metadata
5. Importer Convert/Preview works with valid prompt JSON
6. Importer rejects JsonX metadata payload with explicit message
7. Optimized context contains every schema path and only a bounded ranked value subset
8. Full context ends with the exact raw `presets.json` text and never falls back to Optimized
9. Fast, Refined, malformed-JSON repair, optional-image, and context-limit failures preserve the node contract
