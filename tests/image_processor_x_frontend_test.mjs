import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";


const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = fs.readFileSync(path.join(root, "web", "js", "image_processor_x.js"), "utf8");
const compareSource = fs.readFileSync(path.join(root, "web", "js", "image_compare_edit_x.js"), "utf8");


test("Image ProcessorX frontend is independently namespaced", () => {
  for (const token of [
    'const NODE_TYPE = "WorkflowX_ImageProcessorX"',
    'const STATE_KEY = "workflowxImageProcessorX"',
    'workflowx.image_processor_x.canvas',
    'workflowx.image_processor_x.pause',
    '/workflowx_configurator/image_processor_x/continue',
    '/workflowx_configurator/image_processor_x/cancel',
    '/workflowx_configurator/image_processor_x/status',
    'wfx-ipx-overlay',
  ]) assert.ok(source.includes(token), `missing ${token}`);
  assert.ok(!source.includes("KVGC_ImageCompareEditX"));
  assert.ok(!source.includes("workflowxImageCompareEditX"));
  assert.ok(!source.includes("wfx-ice-"));
  assert.ok(!source.includes('from "./image_compare_edit_x'));
});


test("workflow controls and single-image handling are present", () => {
  for (const token of [
    "function drawWorkflowRow",
    "continuePausedWorkflow",
    "cancelPausedWorkflow",
    "restorePendingSession",
    'makeButton("Resume", () => continuePausedWorkflow(node)',
    'makeButton("Cancel Run", () => cancelPausedWorkflow(node)',
    'setNativeWidget(node, "operation_mode", value)',
    'setNativeWidget(node, "output_image", value)',
    "Single-image mode: compare O1 with processed O3.",
    "if (!s.hasImage2) return;",
  ]) assert.ok(source.includes(token), `missing ${token}`);
});


test("internal native state widgets cannot leak into the node layout", () => {
  for (const token of [
    'for (const name of ["operation_mode", "output_image", "processor_state"])',
    "widget.hidden = true",
    'widget.type = "hidden"',
    "widget.draw = () => {}",
    "widget.computeSize = () => [0, -4]",
    "widget.computeLayoutSize = () => ({ minHeight: 0, maxHeight: 0, minWidth: 0 })",
    'element.style.display = "none"',
  ]) assert.ok(source.includes(token), `missing ${token}`);
});


test("custom controls reserve a strip for native image sockets", () => {
  for (const token of [
    "const PORT_STRIP_H = ROW_H * 2 + GAP",
    "const toolbarY = PAD + PORT_STRIP_H",
    "drawWorkflowRow(ctx, node, toolbarY)",
    "return PAD + PORT_STRIP_H + rows * ROW_H",
  ]) assert.ok(source.includes(token), `missing ${token}`);
  assert.ok(!source.includes("drawWorkflowRow(ctx, node, PAD)"));
});


test("canvas toolbar uses aligned control rows and stacked resolution badges", () => {
  for (const token of [
    "fillAvailable = false",
    "fillAvailable ? available / Math.max(1, naturalTotal)",
    "const selectW = Math.max(1, Math.floor((controlW - editorW - swapW - GAP * 3) / 2))",
    "{ label: \"Continue\", action: \"operationMode\", value: \"Continue\", width: 58",
    "{ label: \"Pause\", action: \"operationMode\", value: \"Pause\", width: 58",
    "{ label: \"Resume\", action: \"continueWorkflow\", width: 58",
    "{ label: \"Cancel\", action: \"cancelWorkflow\", width: 58",
    "width: 60",
    "const modeColumnW = Math.max(1, Math.floor((controlW - GAP * 3) / 4))",
    "const saveRowW = modeColumnW * saveItems.length + GAP * (saveItems.length - 1)",
    "const saveRowX = CONTROL_X + Math.floor((controlW - saveRowW) / 2)",
    "const chipW = visibleChips.reduce",
    "box.y + 8 + index * (ROW_H + GAP)",
  ]) assert.ok(source.includes(token), `missing ${token}`);
  assert.ok(!source.includes("Math.min(148, Math.floor((controlW - editorW"));
  assert.ok(!source.includes('width: value === "difference"'));
});


test("both independent image editors use a complete blue UI accent", () => {
  for (const [name, editorSource, namespace] of [
    ["Image ProcessorX", source, "wfx-ipx"],
    ["Image Compare Edit X", compareSource, "wfx-ice"],
  ]) {
    for (const token of [
      'const BRAND = "#3b82f6"',
      'const BUTTON_ACTIVE = "#3b82f6"',
      'active ? BUTTON_ACTIVE : "#202429"',
      `.${namespace}-btn.active,.${namespace}-chip.active{background:\${BUTTON_ACTIVE};border-color:\${BUTTON_ACTIVE};color:#fff}`,
      `.${namespace}-btn.primary{background:\${BUTTON_ACTIVE};border-color:\${BUTTON_ACTIVE};color:#fff}`,
      `.${namespace}-icon-btn.active{background:\${BUTTON_ACTIVE};border-color:\${BUTTON_ACTIVE};color:#fff}`,
      `.${namespace}-icon-btn.mask.active{background:\${BUTTON_ACTIVE};border-color:\${BUTTON_ACTIVE};color:#fff}`,
      "accent-color:${BRAND}",
      "border-color:#27466f;background:#131b27",
    ]) assert.ok(editorSource.includes(token), `${name} missing ${token}`);
    assert.ok(!editorSource.includes('#ff6847'), `${name} retains the old orange brand accent`);
    assert.ok(!editorSource.includes('rgba(255,104,71'), `${name} retains the old orange translucent accent`);
  }
});


test("complete editor state is canonical, image-independent for presets, and runtime-safe on restore", () => {
  let stateSource = source.replace(/^import .*;\r?\n/gm, "");
  stateSource = stateSource.slice(0, stateSource.indexOf("app.registerExtension({"));
  stateSource += `
    globalThis.__state = {
      normalizeSerializedEditorState,
      serializeEditorState,
      restoreSerializedEditorState,
      cloneDefaults,
      parseEditorPreset,
      readSavedEditorState,
    };
  `;
  const context = { console, Float32Array, Math, Uint8Array };
  context.globalThis = context;
  vm.runInNewContext(stateSource, context, { filename: "image_processor_x.js" });

  const saved = {
    schemaVersion: 1,
    sourceA: "2",
    sourceB: "3",
    viewMode: "split",
    splitMode: "upDown",
    splitX: 0.27,
    splitY: 0.73,
    layerOrder: "1over2",
    topOpacity: 0.42,
    tool: "eraser",
    brushTarget: "adjustment",
    brush: { size: 145, hardness: 0.4, softness: 0.3, feather: 0.6, opacity: 0.8, flow: 0.55 },
    maskPreviewEnabled: false,
    maskPreviewMode: "all",
    blendMaskVisible: false,
    maskData: "data:image/png;base64,blend",
    adjustmentLayers: [{
      id: "layer_one",
      name: "Brush Grade",
      visible: true,
      maskVisible: false,
      mode: "brush",
      amount: 0.81,
      preset: "Custom",
      adjustments: { brightness: 17, contrast: -8, hue: 12 },
      curve: { enabled: true, channel: "RGB", interpolation: "linear", strength: 80, channels: { RGB: [[0, 4], [255, 248]] } },
      maskData: "data:image/png;base64,adjustment",
    }],
    selectedAdjustmentLayerId: "layer_one",
    editorZoom: 2.4,
    editorPanX: 33,
    editorPanY: -19,
    performanceMode: "quality",
    beforePreview: true,
    images: [{ filename: "base.png", type: "temp", subfolder: "" }],
    hasImage2: true,
  };
  const normalized = context.__state.normalizeSerializedEditorState(saved);
  const workflowState = context.__state.serializeEditorState(normalized, { includeImages: true, captureMasks: false });
  const presetState = context.__state.serializeEditorState(normalized, { includeImages: false, captureMasks: false });

  for (const key of ["sourceA", "sourceB", "viewMode", "splitMode", "layerOrder", "topOpacity", "tool", "brushTarget", "maskData", "adjustmentLayers", "editorZoom", "editorPanX", "editorPanY", "performanceMode", "beforePreview"]) {
    assert.ok(key in workflowState, `workflow state missing ${key}`);
    assert.ok(key in presetState, `preset state missing ${key}`);
  }
  assert.equal(workflowState.images[0].filename, "base.png");
  assert.equal(workflowState.hasImage2, true);
  assert.equal("images" in presetState, false);
  assert.equal("hasImage2" in presetState, false);
  assert.equal(presetState.adjustmentLayers[0].maskData, "data:image/png;base64,adjustment");
  assert.equal(presetState.maskData, "data:image/png;base64,blend");

  const live = context.__state.normalizeSerializedEditorState(saved);
  live.images = [{ filename: "replacement.png", type: "temp", subfolder: "" }];
  live.hasImage2 = false;
  live.pendingRequest = { request_id: "keep-me" };
  context.__state.restoreSerializedEditorState(live, context.__state.cloneDefaults());
  assert.equal(live.images[0].filename, "replacement.png");
  assert.equal(live.hasImage2, false);
  assert.equal(live.pendingRequest.request_id, "keep-me");
  assert.equal(live.topOpacity, 0.65);
  assert.equal(live.adjustmentLayers.length, 0);
  assert.equal(live.maskData, "");

  const configuredNode = {
    widgets: [{ name: "processor_state", value: '{"schemaVersion":1}' }],
    properties: { workflowxImageProcessorX: { schemaVersion: 1, topOpacity: 0.22, adjustmentLayers: saved.adjustmentLayers } },
  };
  assert.equal(context.__state.readSavedEditorState(configuredNode).topOpacity, 0.22);
  configuredNode.widgets[0].value = JSON.stringify({ schemaVersion: 1, topOpacity: 0.37 });
  assert.equal(context.__state.readSavedEditorState(configuredNode).topOpacity, 0.37);
});


test("preset contract rejects malformed data and strips base images", () => {
  let stateSource = source.replace(/^import .*;\r?\n/gm, "");
  stateSource = stateSource.slice(0, stateSource.indexOf("app.registerExtension({"));
  stateSource += "\nglobalThis.__parsePreset = parseEditorPreset;";
  const context = { console, Float32Array, Math, Uint8Array };
  context.globalThis = context;
  vm.runInNewContext(stateSource, context, { filename: "image_processor_x.js" });
  assert.throws(() => context.__parsePreset("{}"), /Unsupported preset version/);
  assert.throws(() => context.__parsePreset('{"presetSchemaVersion":1}'), /editor state is missing/);
  const parsed = context.__parsePreset(JSON.stringify({
    presetSchemaVersion: 1,
    name: "Reusable Grade",
    editorState: { schemaVersion: 1, images: [{ filename: "must-not-survive.png" }], hasImage2: true, topOpacity: 0.2 },
  }));
  assert.equal(parsed.name, "Reusable Grade");
  assert.equal(parsed.editorState.topOpacity, 0.2);
  assert.equal("images" in parsed.editorState, false);
  assert.equal("hasImage2" in parsed.editorState, false);
});


test("editor lifecycle, reset, and user-library preset UI force complete persistence", () => {
  for (const token of [
    "function serializeEditorState",
    "function restoreSerializedEditorState",
    "function captureLiveMaskData",
    "persist(this, true);",
    "nodeType.prototype.onSerialize = function (serialized)",
    "function readSavedEditorState",
    "this.__wfxIpx = null;",
    "const closeEditor = () => {",
    "persist(node, true);",
    'makeButton("Presets"',
    'makeButton("Reset"',
    "listUserDataFullInfo(PRESET_USERDATA_DIR)",
    "storeUserData(presetUserDataFile(safeName)",
    "deleteUserData(presetUserDataFile(safeName))",
    "PRESET_LOCAL_STORAGE_KEY",
    "restoreSerializedEditorState(s, preset.editorState)",
    "restoreSerializedEditorState(s, cloneDefaults())",
  ]) assert.ok(source.includes(token), `missing ${token}`);
  assert.ok(!source.includes('if (!s.hasImage2 && s.brushTarget === "blend") s.brushTarget = "adjustment"'));
});


test("browser renderer matches the deterministic Python parity fixture", () => {
  const fixture = JSON.parse(fs.readFileSync(path.join(root, "tests", "fixtures", "image_processor_x_cross_engine.json"), "utf8"));
  let engineSource = source.replace(/^import .*;\r?\n/gm, "");
  engineSource = engineSource.slice(0, engineSource.indexOf("app.registerExtension({"));
  engineSource += "\nglobalThis.__engine = { applyFx, applyCurves };";
  const context = { console, Float32Array, Math, Uint8Array };
  context.globalThis = context;
  vm.runInNewContext(engineSource, context, { filename: "image_processor_x.js" });

  const rgba = new Uint8Array(fixture.rgba);
  context.__engine.applyFx(rgba, fixture.width, fixture.height, fixture.adjustments, fixture.amount, fixture.seed);
  context.__engine.applyCurves(rgba, fixture.width, fixture.height, fixture.curve, fixture.amount);
  const maximumDifference = rgba.reduce(
    (maximum, value, index) => Math.max(maximum, Math.abs(value - fixture.expectedRgba[index])),
    0,
  );
  assert.ok(maximumDifference <= fixture.pixelTolerance, `maximum pixel difference ${maximumDifference}`);
});
