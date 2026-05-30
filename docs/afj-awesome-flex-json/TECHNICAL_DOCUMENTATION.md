# AFJ - Technical Documentation (Templates v2)

## 1. Purpose
This project provides AFJ nodes for JSON-prompt authoring and runtime randomization in ComfyUI:
1. `FluxVisualJsonBuilder` (display: `AFJ - Visual Builder`)
2. `FluxTemplateRandomizer` (display: `AFJ - Template Randomizer`)
3. `AFJPromptTemplateImporter` (display: `AFJ - Prompt Template Importer`)

## 2. Active Components
1. Package entry: `__init__.py`
2. Backend:
   1. `visual_builder/api.py`
   2. `visual_builder/node.py`
   3. `visual_builder/presets.json`
   4. `visual_builder/templates/` (one JSON file per template)
3. Frontend extensions:
   1. `web/flux_visual_builder.js`
   2. `web/flux_template_randomizer.js`
   3. `web/afj_prompt_template_importer.js`

## 3. Node Contracts
### 3.1 AFJ - Visual Builder
Node class: `FluxVisualJsonBuilderNode`
1. Input widget: `prompt_json` (multiline string, optional)
2. Output: `prompt_json` string
3. UI writes compiled JSON directly to node `prompt_json`.

### 3.2 AFJ - Template Randomizer
Node class: `FluxTemplateRandomizerNode`
1. Inputs:
   1. `template_name`
   2. `randomize_rules` (`path | mode | value` lines)
   3. `randomize_rules_help`
   4. `seed`
2. Outputs:
   1. `prompt_json`
   2. `run_log`

### 3.3 AFJ - Prompt Template Importer
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
2. Rejects AFJ metadata/template payloads (`tree`, `randomizer_checked`) with explicit error.
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
1. Add root key in `visual_builder/presets.json`
2. Add root in `buildStarterTree()` inside `web/flux_visual_builder.js`
3. Include in preset-library traversal used by attach-preset in `web/flux_visual_builder.js`
4. Optional: add backend validation in `visual_builder/api.py`

### Add subject subsection
1. Add under `subject` in `visual_builder/presets.json`
2. Add subsection in `buildSubjectItemTemplate()` in `web/flux_visual_builder.js`

## 10. Smoke Checklist
1. Save/load/delete templates and verify per-file creation/removal under `visual_builder/templates/`
2. Invalid filename save returns clear error
3. Visual Builder template list still works
4. Template Randomizer resolves preset options dynamically from current `presets.json` using field binding metadata
5. Importer Convert/Preview works with valid prompt JSON
6. Importer rejects AFJ metadata payload with explicit message
