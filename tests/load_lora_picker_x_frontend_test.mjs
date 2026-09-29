import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  compactPickerVersionLabel,
  normalizePickerPath,
  pickerRowFromInspection,
  pickerRowRestoreKey,
  sanitizePickerRow,
} from "../web/js/load_lora_picker_x_state.mjs";

const source = readFileSync(new URL("../web/js/load_lora_picker_x.js", import.meta.url), "utf8");

test("picker rows normalize and preserve independent strengths", () => {
  const row = sanitizePickerRow({
    enabled: true,
    path: "D:\\runs\\hero-000010.safetensors",
    model_strength: "0.75",
    clip_strength: "0.25",
  });
  assert.equal(row.load_name, "D:/runs/hero-000010.safetensors");
  assert.equal(row.strength_model, 0.75);
  assert.equal(row.strength_clip, 0.25);
  assert.equal(normalizePickerPath("A\\B"), "A/B");
});

test("inspection changes only the selected file identity", () => {
  const next = pickerRowFromInspection(
    { selected: { load_name: "hero-000020.safetensors", filename: "hero-000020.safetensors", source: "registered" } },
    { on: false, load_name: "hero-000010.safetensors", strength_model: 0.6, strength_clip: 0.2 },
  );
  assert.equal(next.on, false);
  assert.equal(next.load_name, "hero-000020.safetensors");
  assert.equal(next.strength_model, 0.6);
  assert.equal(next.strength_clip, 0.2);
  assert.equal(next.source, "registered");
});

test("restore keys include both strengths and selected epoch", () => {
  assert.notEqual(
    pickerRowRestoreKey({ load_name: "hero-001.safetensors", strength_clip: 1 }),
    pickerRowRestoreKey({ load_name: "hero-002.safetensors", strength_clip: 1 }),
  );
  assert.notEqual(
    pickerRowRestoreKey({ load_name: "hero-001.safetensors", strength_clip: 1 }),
    pickerRowRestoreKey({ load_name: "hero-001.safetensors", strength_clip: 0.5 }),
  );
});

test("selected versions use compact but unambiguous labels", () => {
  assert.equal(compactPickerVersionLabel({ label: "Checkpoint 000040", epoch_kind: "checkpoint" }), "#000040");
  assert.equal(compactPickerVersionLabel({ label: "Epoch 060", epoch_kind: "epoch" }), "E060");
  assert.equal(compactPickerVersionLabel({ label: "Step 005000", epoch_kind: "step" }), "S005000");
  assert.equal(compactPickerVersionLabel({ label: "Final", epoch_kind: "final" }), "Final");
});

test("frontend exposes native picker, inspection, epoch and strength controls", () => {
  assert.match(source, /const PICK_ROUTE = "\/workflowx_configurator\/load_lora_picker_x\/pick"/);
  assert.match(source, /const INSPECT_ROUTE = "\/workflowx_configurator\/load_lora_picker_x\/inspect"/);
  assert.match(source, /versionText = .*"Single"/s);
  assert.match(source, /"strength_model"/);
  assert.match(source, /"strength_clip"/);
  assert.match(source, /queueMicrotask\(\(\) => inspectRow/);
  assert.match(source, /function createAddButtonWidget\(\)/);
  assert.match(source, /addButton\?\.last_y/);
  assert.match(source, /pickForRow\(node\);\s*return true;/);
  assert.match(source, /ctx\.fillText\("Version"/);
  assert.doesNotMatch(source, /Epoch \/ step/);
});

test("every custom control handles ComfyUI widget pointer events directly", () => {
  assert.match(source, /function isWidgetPress\(event\)/);
  assert.match(source, /mouse\(event, pos, node\)[\s\S]*?pickForRow\(node\)/);
  assert.match(source, /mouse\(event, pos, node\)[\s\S]*?handleRowControlClick\(node, this, event/);
  assert.match(source, /layout\.versionX/);
  assert.match(source, /const VERSION_WIDTH = 124/);
  assert.match(source, /const STRENGTH_WIDTH = 68/);
});

test("adding and removing rows preserve width and adjust only the current height", () => {
  assert.match(source, /function adjustNodeHeight\(node, delta\)/);
  assert.match(source, /node\.size\[0\] = width/);
  assert.match(source, /node\.size\[1\] = Math\.max\(120, height \+ delta\)/);
  assert.match(source, /if \(adjustSize\) adjustNodeHeight\(node, ROW_HEIGHT\)/);
  assert.match(source, /adjustNodeHeight\(node, -ROW_HEIGHT\)/);
  assert.match(source, /addRow\(node, value, \[\], \{ adjustSize: false \}\)/);
});

test("workflow restore preserves the serialized node dimensions", () => {
  assert.match(source, /const savedSize = Array\.isArray\(info\?\.size\) \? \[\.\.\.info\.size\] : null/);
  assert.match(source, /setupNode\(this, values, savedSize\)/);
  assert.match(source, /node\.size\[0\] = savedWidth/);
  assert.match(source, /node\.size\[1\] = savedHeight/);
});
