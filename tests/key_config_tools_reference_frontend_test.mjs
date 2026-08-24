import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = fs.readFileSync(path.join(root, "web", "js", "key_config_tools.js"), "utf8");

test("reference routing is registered alongside relay routing", () => {
  assert.match(source, /const SET_REFERENCE_TYPE = "KVGC_SetReference"/);
  assert.match(source, /const GET_REFERENCE_TYPE = "KVGC_GetReference"/);
  assert.match(source, /function resolveReferenceSource\(getNode, promptOutput = null\)/);
  assert.match(source, /getOutput\.inputs\.value = \[String\(source\.node\.id\), 0\]/);
});

test("dimensions routing materializes width and height from separate output slots", () => {
  assert.match(source, /const SET_DIMENSIONS_TYPE = "KVGC_SetDimensions"/);
  assert.match(source, /const GET_DIMENSIONS_TYPE = "KVGC_GetDimensions"/);
  assert.match(source, /function resolveDimensionsSource\(getNode, promptOutput\)/);
  assert.match(source, /getOutput\.inputs\.width = \[String\(source\.node\.id\), 0\]/);
  assert.match(source, /getOutput\.inputs\.height = \[String\(source\.node\.id\), 1\]/);
  assert.match(source, /nodeData\.name === GET_DIMENSIONS_TYPE/);
});

test("reference mute temporarily uses ComfyUI native mute mode during serialization", () => {
  assert.match(source, /function applyReferenceMuteModesBeforeQueue\(\)/);
  assert.match(source, /setWidgetValueSilently\(getNode, "set_mute", setMute\)/);
  assert.match(source, /getNode\.mode = MODES\.Mute/);
  assert.match(source, /function restoreReferenceModes\(originalModes\)/);
  assert.match(source, /node\.mode = mode/);
  assert.match(
    source,
    /applySelectedConfigAndAdvancedOverrides\(\);\s+referenceModes = applyReferenceMuteModesBeforeQueue\(\);/,
  );
  assert.match(source, /finally \{\s+restoreReferenceModes\(referenceModes\)/);
});

test("set and get reference mute widgets both activate queue-time native muting", () => {
  assert.match(source, /nodeData\.name === GET_REFERENCE_TYPE/);
  assert.match(source, /nodeData\.name === SET_REFERENCE_TYPE/);
  assert.match(source, /const mute = findWidget\(this, "mute"\)/);
  assert.match(source, /mute\.beforeQueued = \(\) => \{\s+app\.__workflowXRelayQueueing = true/);
});

test("a manually muted or bypassed set reference cannot control related gets", () => {
  const resolver = source.slice(
    source.indexOf("function resolveReferenceSource"),
    source.indexOf("function resolveDimensionsSource"),
  );
  assert.match(
    resolver,
    /if \(node\.mode === MODES\.Mute \|\| node\.mode === MODES\.Bypass\) continue/,
  );
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
