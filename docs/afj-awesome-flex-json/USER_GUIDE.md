# JsonX Visual and Template Tools

> [Documentation and node contracts](../../README.md#prompting-and-jsonx) · [Connected JsonX example](../../examples/06-jsonx-prompt-toolchain.json)

## 1. What You Can Do

The JsonX toolset provides three nodes under `WorkflowX/Prompting/JsonX`:

1. `JsonX - Visual Builder`: visually edit and validate prompt JSON.
2. `JsonX - Template Randomizer`: generate reproducible prompt variants from saved templates.
3. `JsonX - Prompt Template Importer`: convert final prompt JSON into template format.

Use the **JsonX profile in Unified Autoprompter X** when you want LLM-backed JsonX generation. Its isolated generation engine, providers, Markdown settings, templates, presets, validation, repair, and output contracts are documented in the [Unified Autoprompter X guide](../UNIFIED_AUTOPROMPTER_X.md).

## 2. Generate JsonX with Unified Autoprompter X

1. Add `Unified Autoprompter X`.
2. Select the `JsonX` target profile.
3. Select Text to Image or Image to Image and choose JsonX JSON or Natural language output.
4. Enter Prompt instructions and optionally connect authoring images.
5. Configure the isolated JsonX provider under Model settings.
6. Use Profile settings for Adaptive or Template Fill behavior, editable instruction paths, templates, presets, and output contracts.
7. Click Generate. The node retains its previous successful output when generation, validation, repair, or cancellation fails.

Unified JsonX returns the final result from `prompt` and `positive`. Its `negative` output is derived locally from the validated Stage 1 JsonX negative branch.

## 3. Visual Builder Quick Start

1. Add `JsonX - Visual Builder`.
2. Click `Open Visual Builder`.
3. Build or edit the prompt tree.
4. Click `Validate & Apply` to write JSON into `prompt_json`.

Important behavior:

1. All fields are optional.
2. Empty values are omitted from output.
3. `Close` discards unsaved in-session edits.
4. `Validate & Apply` is the save boundary for editor state.

## 4. Templates

Templates are stored as separate files under:

`visual_builder/templates/<template_name>.json`

Template files contain structure, values, and randomizer metadata. Preset option catalogs are loaded dynamically from `presets.json` and are not embedded in each template.

The Visual Builder supports Save, explicit Load, and Delete. Template names cannot be empty, contain Windows-invalid filename characters, end with a dot or space, use a reserved Windows name, or resolve outside the templates directory.

## 5. Prompt Template Importer

Use `JsonX - Prompt Template Importer` when you have a final prompt JSON object from Unified JsonX or another source.

1. Add the importer and open its UI.
2. Enter a template name.
3. Paste the final prompt JSON object.
4. Click Convert/Preview.
5. Review the conversion report.
6. Save the template.

The importer rejects JsonX template metadata payloads containing `tree` or `randomizer_checked`. It builds a minimal tree from the supplied prompt, binds recognized paths to current presets, and retains unknown fields as custom groups, fields, or arrays.

## 6. Template Randomizer

1. Add `JsonX - Template Randomizer`.
2. Open its UI and select a template.
3. Choose fields and randomization rules.
4. Apply the rules to the node.
5. Queue the graph to receive randomized `prompt_json` and a `run_log`.

Randomization is deterministic for a given template, ruleset, and seed. Preset-backed choices always use the current `presets.json` catalog.

## 7. Authoritative Visual-Tool Presets

`visual_builder/presets.json` remains the authoritative schema and option catalog for the Visual Builder, importer, saved-template hydration, and Template Randomizer.

The reserved mappings are:

1. Catalog `subject` becomes the repeatable output `subjects` array.
2. `interaction_suggestions` provides choices for the editable output `interactions` group.
3. `negative` remains an editable free-form output branch.

New root categories and subject subsections are discovered dynamically. Reload the ComfyUI frontend after changing the catalog.

Unified JsonX uses its own independently editable preset catalog under `unified_autoprompter/reference/current_use/JsonX`; changing one catalog does not silently change the other.

## 8. Troubleshooting

1. Template not visible: verify that saving succeeded and the file exists under `visual_builder/templates/`.
2. Importer reports a metadata payload: paste the final prompt object, not a JsonX template file.
3. Preset selector missing for a field: use `Attach Preset Options` in Visual Builder.
4. Apply blocked in Visual Builder: inspect the validation panel or use Force apply when intentional.
5. LLM-backed generation needed: use the JsonX profile in Unified Autoprompter X.
