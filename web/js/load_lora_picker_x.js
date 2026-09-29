import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { compactPickerVersionLabel, normalizePickerPath, pickerRowFromInspection, pickerRowRestoreKey, sanitizePickerRow } from "./load_lora_picker_x_state.mjs";

const NODE_TYPE = "KVGC_LoadLoraPickerX";
const PICK_ROUTE = "/workflowx_configurator/load_lora_picker_x/pick";
const INSPECT_ROUTE = "/workflowx_configurator/load_lora_picker_x/inspect";
const MIN_WIDTH = 820;
const ROW_HEIGHT = 27;
const HEADER_HEIGHT = 22;
const VERSION_WIDTH = 124;
const STRENGTH_WIDTH = 68;
const REMOVE_WIDTH = 28;
const GAP = 6;

function markDirty(node) {
  node?.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

async function postJson(path, payload) {
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  };
  const response = api?.fetchApi ? await api.fetchApi(path, options) : await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.error || `${response.status} ${response.statusText}`);
  return data;
}

function reportError(error) {
  const message = error?.message || String(error);
  console.error("[WorkflowX Load Lora PickerX]", error);
  window.alert?.(`Load Lora PickerX: ${message}`);
}

function fitText(ctx, value, width) {
  const text = String(value || "Select LoRA...");
  if (ctx.measureText(text).width <= width) return text;
  let shortened = text;
  while (shortened.length > 4 && ctx.measureText(`${shortened}...`).width > width) shortened = shortened.slice(0, -1);
  return `${shortened}...`;
}

function drawBox(ctx, x, y, width, text, { disabled = false, missing = false, align = "center" } = {}) {
  ctx.beginPath();
  ctx.roundRect?.(x, y + 3, width, ROW_HEIGHT - 6, 6);
  if (!ctx.roundRect) ctx.rect(x, y + 3, width, ROW_HEIGHT - 6);
  ctx.fillStyle = disabled ? "#202329" : "#2b3038";
  ctx.strokeStyle = missing ? "#b85b5b" : disabled ? "#454a52" : "#707782";
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = missing ? "#ffb2b2" : disabled ? "#777f89" : "#edf1f5";
  ctx.textAlign = align;
  ctx.textBaseline = "middle";
  const textX = align === "left" ? x + 8 : x + width / 2;
  ctx.fillText(fitText(ctx, text, width - 14), textX, y + ROW_HEIGHT / 2);
}

function rowLayout(width) {
  const removeX = width - 10 - REMOVE_WIDTH;
  const clipX = removeX - GAP - STRENGTH_WIDTH;
  const modelX = clipX - GAP - STRENGTH_WIDTH;
  const versionX = modelX - GAP - VERSION_WIDTH;
  return { removeX, clipX, modelX, versionX, fileX: 48, fileWidth: Math.max(150, versionX - 48 - GAP) };
}

function isWidgetPress(event) {
  return !event?.type || event.type === "pointerdown" || event.type === "mousedown";
}

function drawToggle(ctx, x, y, enabled) {
  ctx.beginPath();
  ctx.arc(x + 9, y + ROW_HEIGHT / 2, 8, 0, Math.PI * 2);
  ctx.fillStyle = enabled ? "#8fa8e8" : "#555b64";
  ctx.fill();
}

function serializeRow(widget) {
  return sanitizePickerRow(widget.value);
}

function rowWidgets(node) {
  return (node.widgets || []).filter((widget) => widget.__loadLoraPickerRow);
}

function nextRowName(node) {
  node.__loadLoraPickerCounter = Number(node.__loadLoraPickerCounter || 0) + 1;
  return `lora_${node.__loadLoraPickerCounter}`;
}

function resizeNode(node, preservedWidth = null) {
  const requested = Number(preservedWidth);
  const width = Number.isFinite(requested) && requested > 0 ? Math.max(MIN_WIDTH, requested) : Math.max(MIN_WIDTH, Number(node.size?.[0] || 0));
  node.size = node.size || [width, 120];
  node.size[0] = width;
  const computed = node.computeSize?.() || node.size;
  node.size[1] = Math.max(120, Number(computed?.[1] || node.size[1]));
  markDirty(node);
}

function adjustNodeHeight(node, delta) {
  const width = Number(node.size?.[0]);
  const height = Number(node.size?.[1]);
  if (!Number.isFinite(width) || width <= 0 || !Number.isFinite(height) || height <= 0) {
    resizeNode(node);
    return;
  }
  node.size[0] = width;
  node.size[1] = Math.max(120, height + delta);
  markDirty(node);
}

function addCustomWidget(node, widget) {
  if (typeof node.addCustomWidget === "function") return node.addCustomWidget(widget);
  node.widgets = node.widgets || [];
  node.widgets.push(widget);
  return widget;
}

function moveBeforeAddButton(node, widget) {
  const widgets = node.widgets || [];
  const buttonIndex = widgets.findIndex((item) => item.__loadLoraPickerAddButton);
  const currentIndex = widgets.indexOf(widget);
  if (buttonIndex < 0 || currentIndex < 0 || currentIndex < buttonIndex) return;
  widgets.splice(currentIndex, 1);
  widgets.splice(buttonIndex, 0, widget);
}

async function inspectRow(node, row, { quiet = false } = {}) {
  const loadName = normalizePickerPath(row?.value?.load_name);
  if (!loadName || row.__pickerBusy) return null;
  row.__pickerBusy = true;
  markDirty(node);
  try {
    const inspection = await postJson(INSPECT_ROUTE, { load_name: loadName });
    row.value = pickerRowFromInspection(inspection, row.value);
    row.__epochOptions = Array.isArray(inspection.options) ? inspection.options : [];
    row.__missing = false;
    return inspection;
  } catch (error) {
    row.__epochOptions = [];
    row.__missing = true;
    if (!quiet) reportError(error);
    return null;
  } finally {
    row.__pickerBusy = false;
    markDirty(node);
  }
}

function applyInspection(row, inspection) {
  row.value = pickerRowFromInspection(inspection, row.value);
  row.__epochOptions = Array.isArray(inspection?.options) ? inspection.options : [];
  row.__missing = false;
}

async function pickForRow(node, row = null) {
  if (node.__loadLoraPickerSelecting) return;
  node.__loadLoraPickerSelecting = true;
  markDirty(node);
  try {
    const inspection = await postJson(PICK_ROUTE, { load_name: row?.value?.load_name || "" });
    if (inspection.cancelled) return;
    if (row) {
      applyInspection(row, inspection);
    } else {
      addRow(node, pickerRowFromInspection(inspection), inspection.options);
    }
    markDirty(node);
  } catch (error) {
    reportError(error);
  } finally {
    node.__loadLoraPickerSelecting = false;
    markDirty(node);
  }
}

async function openEpochMenu(node, row, event) {
  const inspection = await inspectRow(node, row);
  if (!inspection || !inspection.has_epochs || !window.LiteGraph?.ContextMenu) return;
  new LiteGraph.ContextMenu(
    inspection.options.map((option) => ({
      content: `${option.label} — ${option.filename}`,
      callback: () => {
        const old = sanitizePickerRow(row.value);
        row.value = {
          ...old,
          load_name: option.load_name,
          display_name: option.display_name || option.filename,
          filename: option.filename,
          source: option.source,
        };
        row.__missing = false;
        markDirty(node);
      },
    })),
    { event, title: "Select training checkpoint" },
  );
}

function promptStrength(node, row, key, title, event) {
  const current = Number(row.value[key] ?? 1);
  const finish = (value) => {
    const next = Number(value);
    if (!Number.isFinite(next)) return;
    row.value[key] = next;
    markDirty(node);
  };
  if (app.canvas?.prompt) app.canvas.prompt(title, current, finish, event);
  else {
    const value = window.prompt(title, String(current));
    if (value != null) finish(value);
  }
}

function removeRow(node, row) {
  node.widgets = (node.widgets || []).filter((widget) => widget !== row);
  adjustNodeHeight(node, -ROW_HEIGHT);
}

function moveRow(node, row, direction) {
  const widgets = node.widgets || [];
  const rows = rowWidgets(node);
  const index = rows.indexOf(row);
  const target = rows[index + direction];
  if (!target) return;
  const first = widgets.indexOf(row);
  const second = widgets.indexOf(target);
  widgets[first] = target;
  widgets[second] = row;
  markDirty(node);
}

function rowMenu(node, row, event) {
  if (!window.LiteGraph?.ContextMenu) return;
  new LiteGraph.ContextMenu(
    [
      { content: row.value.on ? "Disable" : "Enable", callback: () => { row.value.on = !row.value.on; markDirty(node); } },
      { content: "Choose another file", callback: () => pickForRow(node, row) },
      { content: "Refresh epochs", callback: () => inspectRow(node, row) },
      null,
      { content: "Move Up", callback: () => moveRow(node, row, -1) },
      { content: "Move Down", callback: () => moveRow(node, row, 1) },
      { content: "Remove", callback: () => removeRow(node, row) },
    ],
    { event, title: "Load Lora PickerX" },
  );
}

function createHeaderWidget() {
  return {
    name: "load_lora_picker_header",
    type: "custom",
    __loadLoraPicker: true,
    value: { type: "header" },
    computeSize: () => [MIN_WIDTH, HEADER_HEIGHT],
    serializeValue: () => ({ type: "header" }),
    draw(ctx, node, width, y) {
      this.last_y = y;
      const layout = rowLayout(width);
      ctx.save();
      ctx.fillStyle = "#aeb6c1";
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";
      ctx.fillText("On", 17, y + HEADER_HEIGHT / 2);
      ctx.fillText("LoRA file", layout.fileX, y + HEADER_HEIGHT / 2);
      ctx.textAlign = "center";
      ctx.fillText("Version", layout.versionX + VERSION_WIDTH / 2, y + HEADER_HEIGHT / 2);
      ctx.fillText("Model", layout.modelX + STRENGTH_WIDTH / 2, y + HEADER_HEIGHT / 2);
      ctx.fillText("CLIP", layout.clipX + STRENGTH_WIDTH / 2, y + HEADER_HEIGHT / 2);
      ctx.fillText("Remove", layout.removeX + REMOVE_WIDTH / 2, y + HEADER_HEIGHT / 2);
      ctx.restore();
    },
  };
}

function createAddButtonWidget() {
  return {
    name: "load_lora_picker_add",
    type: "custom",
    __loadLoraPicker: true,
    __loadLoraPickerAddButton: true,
    value: { type: "add" },
    computeSize: () => [MIN_WIDTH, ROW_HEIGHT],
    serializeValue: () => ({ type: "add" }),
    mouse(event, pos, node) {
      if (!isWidgetPress(event) || event.button === 2) return false;
      pickForRow(node);
      return true;
    },
    draw(ctx, node, width, y) {
      this.last_y = y;
      ctx.save();
      ctx.globalAlpha = app.canvas?.editor_alpha ?? 1;
      drawBox(
        ctx,
        10,
        y,
        Math.max(80, width - 20),
        node.__loadLoraPickerSelecting ? "Opening file picker..." : "+ Pick LoRA",
        { disabled: Boolean(node.__loadLoraPickerSelecting) },
      );
      ctx.restore();
    },
  };
}

function createRowWidget(name, value, options = []) {
  return {
    name,
    type: "custom",
    __loadLoraPicker: true,
    __loadLoraPickerRow: true,
    value: sanitizePickerRow(value),
    __epochOptions: Array.isArray(options) ? options : [],
    __missing: false,
    computeSize: () => [MIN_WIDTH, ROW_HEIGHT],
    serializeValue() { return serializeRow(this); },
    mouse(event, pos, node) {
      if (!isWidgetPress(event)) return false;
      return handleRowControlClick(node, this, event, Number(pos?.[0] || 0));
    },
    draw(ctx, node, width, y) {
      this.last_y = y;
      const layout = rowLayout(width);
      const optionsCount = this.__epochOptions?.length || 0;
      const selectedOption = this.__epochOptions?.find((item) => item.load_name === this.value.load_name);
      const versionText = this.__pickerBusy ? "Scanning..." : optionsCount > 1 ? `${compactPickerVersionLabel(selectedOption)} ▾` : "Single";
      ctx.save();
      ctx.globalAlpha = app.canvas?.editor_alpha ?? 1;
      drawToggle(ctx, 18, y, this.value.on);
      drawBox(ctx, layout.fileX, y, layout.fileWidth, this.value.filename || this.value.display_name || "Select LoRA...", { missing: this.__missing, align: "left" });
      drawBox(ctx, layout.versionX, y, VERSION_WIDTH, versionText, { disabled: optionsCount < 2 || this.__pickerBusy });
      drawBox(ctx, layout.modelX, y, STRENGTH_WIDTH, Number(this.value.strength_model).toFixed(2));
      drawBox(ctx, layout.clipX, y, STRENGTH_WIDTH, Number(this.value.strength_clip).toFixed(2));
      drawBox(ctx, layout.removeX, y, REMOVE_WIDTH, "x");
      ctx.restore();
    },
  };
}

function addRow(node, value, options = [], { adjustSize = true } = {}) {
  const widget = addCustomWidget(node, createRowWidget(nextRowName(node), value, options));
  moveBeforeAddButton(node, widget);
  if (adjustSize) adjustNodeHeight(node, ROW_HEIGHT);
  return widget;
}

function restoredRows(widgetValues) {
  if (!Array.isArray(widgetValues)) return [];
  const rows = widgetValues.filter((value) => value && typeof value === "object" && normalizePickerPath(value.load_name || value.lora));
  const normalized = rows.map(sanitizePickerRow);
  while (normalized.length > 1 && pickerRowRestoreKey(normalized.at(-1)) === pickerRowRestoreKey(normalized[0])) normalized.pop();
  return normalized;
}

function setupNode(node, values = [], preservedSize = null) {
  const width = Math.max(MIN_WIDTH, Number(node.size?.[0] || 0));
  node.widgets = (node.widgets || []).filter((widget) => !widget.__loadLoraPicker);
  node.serialize_widgets = true;
  node.__loadLoraPickerCounter = 0;
  addCustomWidget(node, createHeaderWidget());
  for (const value of values) {
    const row = addRow(node, value, [], { adjustSize: false });
    queueMicrotask(() => inspectRow(node, row, { quiet: true }));
  }
  addCustomWidget(node, createAddButtonWidget());
  if (Array.isArray(preservedSize) && preservedSize.length >= 2) {
    const savedWidth = Number(preservedSize[0]);
    const savedHeight = Number(preservedSize[1]);
    node.size = node.size || [width, 120];
    if (Number.isFinite(savedWidth) && savedWidth > 0) node.size[0] = savedWidth;
    if (Number.isFinite(savedHeight) && savedHeight > 0) node.size[1] = savedHeight;
    markDirty(node);
  } else {
    resizeNode(node, width);
  }
}

function nodeLocalPosition(node, pos) {
  let x = Number(pos?.[0] || 0);
  let y = Number(pos?.[1] || 0);
  if (node.pos && (x > Number(node.size?.[0] || 0) || y > Number(node.size?.[1] || 0))) {
    x -= node.pos[0];
    y -= node.pos[1];
  }
  return [x, y];
}

function handleRowControlClick(node, row, event, x) {
  const width = Number(node.size?.[0] || MIN_WIDTH);
  const layout = rowLayout(width);
  if (event.button === 2) { rowMenu(node, row, event); return true; }
  if (x < 44) { row.value.on = !row.value.on; markDirty(node); return true; }
  if (x >= layout.fileX && x <= layout.fileX + layout.fileWidth) { pickForRow(node, row); return true; }
  if (x >= layout.versionX && x <= layout.versionX + VERSION_WIDTH) { openEpochMenu(node, row, event); return true; }
  if (x >= layout.modelX && x <= layout.modelX + STRENGTH_WIDTH) { promptStrength(node, row, "strength_model", "Model strength", event); return true; }
  if (x >= layout.clipX && x <= layout.clipX + STRENGTH_WIDTH) { promptStrength(node, row, "strength_clip", "CLIP strength", event); return true; }
  if (x >= layout.removeX) { removeRow(node, row); return true; }
  return false;
}

function handleRowClick(node, event, pos) {
  const [x, localY] = nodeLocalPosition(node, pos);
  const width = Number(node.size?.[0] || MIN_WIDTH);
  const addButton = (node.widgets || []).find((widget) => widget.__loadLoraPickerAddButton);
  if (
    event.button !== 2
    && addButton?.last_y != null
    && localY >= addButton.last_y
    && localY <= addButton.last_y + ROW_HEIGHT
    && x >= 10
    && x <= width - 10
  ) {
    pickForRow(node);
    return true;
  }
  for (const row of rowWidgets(node)) {
    if (row.last_y == null || localY < row.last_y || localY > row.last_y + ROW_HEIGHT) continue;
    return handleRowControlClick(node, row, event, x);
  }
  return false;
}

app.registerExtension({
  name: "workflowx.load_lora_picker_x",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_TYPE) return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function loadLoraPickerXCreated() {
      originalCreated?.apply(this, arguments);
      setupNode(this);
    };
    const originalConfigure = nodeType.prototype.configure;
    nodeType.prototype.configure = function loadLoraPickerXConfigure(info) {
      const values = restoredRows(info?.widgets_values);
      const savedSize = Array.isArray(info?.size) ? [...info.size] : null;
      const configureInfo = info && Array.isArray(info.widgets_values) ? { ...info, widgets_values: [] } : info;
      const args = [...arguments];
      args[0] = configureInfo;
      const result = originalConfigure?.apply(this, args);
      setupNode(this, values, savedSize);
      return result;
    };
    const originalMouseDown = nodeType.prototype.onMouseDown;
    nodeType.prototype.onMouseDown = function loadLoraPickerXMouseDown(event, pos) {
      if (handleRowClick(this, event, pos || app.canvas?.graph_mouse || [0, 0])) return true;
      return originalMouseDown?.apply(this, arguments);
    };
  },
});
