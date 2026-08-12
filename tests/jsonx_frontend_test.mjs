import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../web/js/llm_to_jsonx.js", import.meta.url), "utf8");
const builder = fs.readFileSync(new URL("../web/js/flux_visual_builder.js", import.meta.url), "utf8");

test("JsonX frontend keeps credentials separate and exposes both preset modes", () => {
  assert.match(source, /workflowx_jsonx_gemini_api_key/);
  assert.match(source, /workflowx_jsonx_openai_api_key/);
  assert.match(source, /preset_context_mode/);
  assert.match(source, /Full preset mode/);
  assert.match(source, /Previous output kept/);
  assert.doesNotMatch(source, /setWidgetValue\(node, "ui_state"/);
});

test("LLM to JsonX stays compact and Generate feeds the prompt_json output", () => {
  assert.match(source, /height:26px;min-height:26px/);
  assert.match(source, /height:27px;min-height:27px/);
  assert.match(source, /align-content:start/);
  assert.match(source, /getMinHeight:\(\) => Math\.max\(118, root\.scrollHeight \+ 2\)/);
  assert.match(source, /setWidgetValue\(node, "generated_prompt_json", promptJson\)/);
  assert.match(source, /Saved to prompt_json/);
  assert.match(source, /makePicker\(localPanel, "Local GGUF model"/);
  assert.match(source, /makePicker\(geminiPanel, "Gemini model"/);
  assert.match(source, /makePicker\(openaiPanel, "Fetched model"/);
  assert.match(source, /makePicker\(ollamaPanel, "Ollama model"/);
  assert.doesNotMatch(source, /function fillModels/);
  assert.doesNotMatch(source, /datalist/);
  assert.match(source, /localModel\.setOptions\(data\.models/);
  assert.match(source, /jsonx-picker-menu/);
  assert.match(source, /jsonx-picker-open/);
  assert.match(source, /for \(const item of options\)/);
  assert.doesNotMatch(source, /makeModelInput\(localPanel, "Local GGUF model"/);
  assert.match(source, /Refresh to load GGUF models/);
  assert.match(source, /No GGUF models found/);
  assert.doesNotMatch(source, /Math\.max\(680/);
  for (const setting of ["local_ctx_size", "local_max_tokens", "local_temperature", "local_top_p", "local_top_k", "local_repeat_penalty", "local_memory_mode", "local_reasoning", "local_seed"]) {
    assert.match(source, new RegExp(setting));
  }
  assert.match(source, /Local generation settings/);
  assert.match(source, /Gemini safety settings/);
  assert.match(source, /GEMINI_SAFETY_OPTIONS/);
  for (const setting of ["safety_harassment", "safety_hate_speech", "safety_sexual", "safety_dangerous"]) {
    assert.match(source, new RegExp(setting));
  }
  assert.match(source, /payload\.gemini_safety\[key\]/);
  assert.match(source, /Generated JsonX output/);
  assert.match(source, /outputPreview\.readOnly = true/);
  assert.match(source, /outputPreview\.value = promptJson/);
  assert.match(source, /Generation diagnostics/);
  assert.match(source, /Prompt feedback/);
  assert.match(source, /Candidate details/);
  assert.match(source, /error\.data = data/);
  assert.match(source, /showDiagnostics\(error\.data\?\.diagnostics\)/);
  assert.match(source, /openaiUnload\.checked/);
  assert.match(source, /ollamaThink\.checked/);
  assert.match(source, /ollamaUnload\.checked/);
  assert.match(source, /refresh_vram: refreshVram\.checked/);
  assert.match(source, /settings\[`\$\{activeBackend\}_timeout`\]/);
  assert.match(source, /host:ollamaHost\.value, timeout:Number\(timeout\.value \|\| 180\)/);
  assert.match(source, /repeat_penalty: settings\.local_repeat_penalty/);
  assert.match(source, /JsonX Backend Instructions/);
  assert.match(source, /Hierarchy coverage/);
  assert.match(source, /Deep \(maximize relevant hierarchy\)/);
  assert.match(source, /Exhaustive \(maximum relevant branch coverage\)/);
  assert.match(source, /Stage 1 preset-aware system instructions/);
  assert.match(source, /Refined Stage 2 system instructions/);
  assert.match(source, /Effective instructions preview/);
  assert.match(source, /Reset defaults/);
  assert.match(source, /stage_one_instructions: settings\.stage_one_instructions/);
  assert.match(source, /refinement_instructions: settings\.refinement_instructions/);
  assert.match(source, /detail_level: settings\.detail_level/);
  assert.match(source, /instructions\/preview/);
  assert.match(source, /hierarchy_metrics/);
  assert.match(source, /leaves · depth/);
});

test("JsonX visual builder discovers preset roots and subject branches dynamically", () => {
  assert.match(builder, /Object\.entries\(subjectPreset \|\| \{\}\)/);
  assert.match(builder, /Object\.entries\(presets \|\| \{\}\)/);
  assert.match(builder, /interaction_suggestions/);
  assert.match(builder, /flattenPresetLibrary\(presets \|\| \{\}\)/);
  assert.match(builder, /function hydrateStateFromTemplate[\s\S]*enrichPresetBindingsFromTree\(tree\)/);
});
