# AFJ - User Guide (Templates v2)

## 1. What You Can Do
AFJ provides three nodes:
1. `AFJ - Visual Builder`: visual tree editor for prompt JSON.
2. `AFJ - Template Randomizer`: runtime randomization from saved templates.
3. `AFJ - Prompt Template Importer`: convert final prompt JSON into AFJ template format and save it.

## 2. Visual Builder Quick Start
1. Add `AFJ - Visual Builder` node.
2. Click `Open Visual Builder`.
3. Build/edit your prompt tree.
4. Click `Validate & Apply` to write JSON into `prompt_json`.

Important behavior:
1. All tags are optional.
2. Empty values are omitted from output.
3. `Close` discards in-session unsaved edits.
4. `Validate & Apply` is the save boundary for editor state.

## 3. Templates (Per-File Storage)
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

## 4. Prompt Template Importer (JSON -> Template)
Use `AFJ - Prompt Template Importer` when you have JSON prompt text from another source.

### Steps
1. Add node and click `Open Prompt Template Importer UI`.
2. Enter `template_name`.
3. Paste **final prompt JSON object** into source box.
4. Click `Convert/Preview`.
5. Check preview and report.
6. Click `Save Template`.

### Input constraint
Importer accepts final prompt JSON object only.
If JSON looks like AFJ metadata payload (`tree` / `randomizer_checked`), conversion is rejected with a clear error.

### Conversion behavior
1. Builds a minimal tree from your prompt JSON only (no extra blank starter sections).
2. Matching paths get preset bindings.
3. Unknown keys become custom fields/groups/arrays.
4. Arrays support object items and primitive items.
5. Saved templates strip `options`; live options are rehydrated from current `presets.json`.

## 5. Template Randomizer Quick Start
1. Add `AFJ - Template Randomizer` node.
2. Click `Open Template Randomizer UI`.
3. Select template and fields.
4. Apply writes `randomize_rules` back to node.
5. Run graph; node outputs randomized `prompt_json` plus `run_log`.
6. Preset randomization uses current `presets.json` dynamically (not frozen template option blobs).

## 6. Add a New Leaf/Field in `presets.json`
File: `visual_builder/presets.json`

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

## 7. Add a New Category in `presets.json` (and required code updates)
If you add a brand-new root category, update both presets and code.

### Step 1: Add root category in presets
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

### Step 2: Add starter section in builder code
File: `web/flux_visual_builder.js`
Function: `buildStarterTree()`

Add a root child entry like:
```js
buildNodesFromPresetObject("story", presets.story || {}, "story", false, "story")
```

### Step 3: Include category in preset attach library
File: `web/flux_visual_builder.js`
Ensure the preset library traversal includes `story` root.

### Step 4 (optional): validation logic
File: `visual_builder/api.py`
Function: `validate_prompt_payload()`
Add checks only if new category needs constraints.

## 8. Add a Subject Subsection
To add a subsection under `subject`:
1. Add it in `visual_builder/presets.json` under `subject`.
2. Update `buildSubjectItemTemplate()` in `web/flux_visual_builder.js` to include that subsection.

Without step 2, new subject subsection will not appear by default in each subject card.

## 9. Troubleshooting
1. Template not visible:
   1. Check save response/status message.
   2. Verify file exists under `visual_builder/templates/`.
2. Importer says metadata payload:
   1. Paste final prompt object JSON, not AFJ template JSON.
3. Preset dropdown missing for a field:
   1. Use `Attach Preset Options` in Visual Builder.
4. Apply blocked in Visual Builder:
   1. Check validation panel or use `Force apply` if intentional.
