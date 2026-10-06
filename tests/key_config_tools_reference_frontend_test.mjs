import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = fs.readFileSync(path.join(root, "web", "js", "key_config_tools.js"), "utf8");
const selectorUiSource = fs.readFileSync(
  path.join(root, "web", "js", "config_selector_x_ui.js"),
  "utf8",
);

test("all Set/Get families use the recursive runtime resolver", () => {
  for (const type of [
    "KVGC_SetInt",
    "KVGC_SetFloat",
    "KVGC_SetString",
    "KVGC_SetText",
    "KVGC_SetBoolean",
    "KVGC_SetSampler",
    "KVGC_SetScheduler",
    "KVGC_SetRelay",
    "KVGC_SetDimensions",
    "KVGC_SetReference",
  ]) {
    assert.ok(source.includes(type), `${type} should be registered`);
  }
  assert.match(source, /function materializeRecursiveSetGets\(promptResult, inventory\)/);
  assert.match(source, /for \(const record of inventory\.instances\)/);
  assert.match(source, /resolveCandidates\(candidates, family, key\)/);
});

test("Scopes and Configs display breadcrumbs without changing stored group names", () => {
  assert.match(source, /groupLabel: groupDisplayLabel/);
  assert.match(selectorUiSource, /function groupNameElement\(groupName\)/);
  assert.match(selectorUiSource, /element\.title = displayName/);
  assert.match(selectorUiSource, /element\.setAttribute\("aria-label", displayName\)/);
  assert.match(selectorUiSource, /grid-template-columns:minmax\(260px,1\.35fr\) minmax\(460px,1\.65fr\)/);
  assert.match(selectorUiSource, /draft\.scopes\[groupName\]/);
  assert.match(selectorUiSource, /config\.modes\[groupName\]/);
});

test("relay, dimensions, and reference links use full execution IDs", () => {
  assert.match(source, /getPrompt\.inputs\.value = \[source\.executionId, 0\]/);
  assert.match(source, /getPrompt\.inputs\.width = \[source\.executionId, 0\]/);
  assert.match(source, /getPrompt\.inputs\.height = \[source\.executionId, 1\]/);
});

test("typed values and provenance bind to the winning runtime source", () => {
  assert.match(source, /getPrompt\.inputs\.resolved_value = value/);
  assert.match(source, /getPrompt\.inputs\.resolved_config = selectedConfig/);
  assert.match(source, /digestResolvedValue\([\s\S]*?source\.executionId,[\s\S]*?value/);
});

test("reference mute removes routed Gets and dangling prompt inputs", () => {
  assert.match(source, /removedReferences\.add\(executionId\)/);
  assert.match(source, /for \(const executionId of removedReferences\) delete output\[executionId\]/);
  assert.match(
    source,
    /Array\.isArray\(input\) && removedReferences\.has\(String\(input\[0\]\)\)/,
  );
});

test("Set/Get queue hooks validate and apply the root selector", () => {
  assert.match(source, /const inventory = assertQueueGraphValid\(\)/);
  assert.match(source, /applySelectedConfigAndAdvancedOverrides\(\)/);
  assert.doesNotMatch(source, /__workflowXRelayQueueing/);
});

test("internal set mute state is hidden while independent get mute remains visible", () => {
  assert.match(source, /function hideReferenceBackingWidgets\(node\)/);
  assert.match(source, /const setMute = findWidget\(node, "set_mute"\)/);
  const helper = source.slice(
    source.indexOf("function hideReferenceBackingWidgets"),
    source.indexOf("function ensureRefreshButton"),
  );
  assert.doesNotMatch(helper, /findWidget\(node, "mute"\)/);
});
