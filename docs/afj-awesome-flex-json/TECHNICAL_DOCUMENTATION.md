# JsonX Visual and Template Tools — Technical Documentation

## 1. Purpose

This package supplies three local JsonX authoring and template nodes:

1. `FluxVisualJsonBuilder` — `JsonX - Visual Builder`
2. `FluxTemplateRandomizer` — `JsonX - Template Randomizer`
3. `AFJPromptTemplateImporter` — `JsonX - Prompt Template Importer`

LLM-backed JsonX generation is provided by the independently implemented JsonX profile in `UnifiedAutoprompterX`; see [Unified Autoprompter X](../UNIFIED_AUTOPROMPTER_X.md).

## 2. Active Components

1. Package entry: `afj_awesome_flex_json_v2/__init__.py`
2. Backend:
   1. `visual_builder/api.py`
   2. `visual_builder/node.py`
   3. `visual_builder/presets.json`
   4. `visual_builder/templates/`
3. Frontend:
   1. `web/js/flux_visual_builder.js`
   2. `web/js/flux_template_randomizer.js`
   3. `web/js/afj_prompt_template_importer.js`

There is no provider, model-discovery, or llama.cpp runtime in this visual/template subsystem.

## 3. Node Contracts

### 3.1 JsonX - Visual Builder

- Class: `FluxVisualJsonBuilderNode`
- Input: optional multiline `prompt_json`
- Output: validated `prompt_json`
- The frontend writes compiled JSON directly to the node widget.

### 3.2 JsonX - Template Randomizer

- Class: `FluxTemplateRandomizerNode`
- Inputs: `template_name`, `randomize_rules`, `randomize_rules_help`, and `seed`
- Outputs: `prompt_json` and `run_log`

### 3.3 JsonX - Prompt Template Importer

- Class: `AFJPromptTemplateImporterNode`
- Inputs: `template_name`, `source_prompt_json`, and `import_report`
- Output: `template_payload_json`
- The frontend supports conversion preview and saving to template storage.

## 4. Template Storage

Templates use one file per template:

`visual_builder/templates/<template_name>.json`

The strict payload is:

```json
{
  "tree": { "...": "..." },
  "randomizer_checked": []
}
```

Preset `options` are not stored in template files; they are rehydrated from the current `presets.json`. Legacy files embedding option catalogs are rejected.

Template names are rejected when they are empty, contain control or Windows-invalid filename characters, start or end with whitespace, end with a dot or space, use a reserved Windows filename, or resolve outside the templates directory.

## 5. API Layer

`register_visual_builder_routes()` exposes only the local visual/template API:

1. `GET /fluxvisual/presets`
2. `GET /fluxvisual/templates`
3. `POST /fluxvisual/templates/save`
4. `POST /fluxvisual/templates/delete`
5. `POST /fluxvisual/validate`
6. `POST /fluxvisual/import/convert`

Unified JsonX owns its separate `/workflowx/unified_autoprompter/jsonx/*` routes.

### Import conversion

`POST /fluxvisual/import/convert` accepts:

```json
{ "source_prompt_json": "{...}" }
```

It returns an `ok` flag, conversion report, warnings, field summary, and a strict template payload containing `tree` and `randomizer_checked`.

## 6. Importer Conversion

1. Accepts a final prompt JSON object only.
2. Rejects template metadata payloads containing `tree` or `randomizer_checked`.
3. Builds a minimal tree without unrelated starter sections.
4. Keeps unknown keys as custom fields, groups, or arrays.
5. Supports object and primitive array items.
6. Uses path-first preset binding from `presets.json`.
7. Strips option catalogs before saving.

## 7. Visual Builder Persistence and Validation

Applied editor state is stored under `properties.flux_visual_state` with version, prompt signature, tree, and `randomizer_checked`. State persists only after `Validate & Apply`.

`validate_prompt_payload()` verifies that the payload is an object, `subjects` is an array when present, subject items are objects, duplicate subject IDs are reported, and malformed `interactions` values are reported.

## 8. Extension Notes

- Add preset options or new paths in `visual_builder/presets.json`; the visual tools traverse the catalog dynamically.
- Add structural backend validation only when a new category requires more than the generic prompt contract.
- Add subject subsections below `subject`; repeatable subject templates discover them automatically.
- Do not import Unified JsonX provider or reference-store modules into this subsystem.

## 9. Smoke Checklist

1. Save, load, and delete individual templates.
2. Reject invalid and traversal-style template names.
3. Load preset options dynamically from `presets.json`.
4. Convert valid final prompt JSON into a template.
5. Reject template metadata passed as final prompt JSON.
6. Apply Visual Builder edits and confirm persisted state.
7. Randomize the same template and rules reproducibly for a fixed seed.
