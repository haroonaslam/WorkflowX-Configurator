import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { $el } from "../../scripts/ui.js";

const ROUTE = "/xflows/library";
const TRANSFER_ROUTE = "/xflows/export-import";
const SETTINGS_PREFIX = "workflowx.setting";
const STORAGE_PREFIX = "workflowx.library";
const WORKFLOWX_FEATURE_ROW_CATEGORY = ["WorkflowX", "Features", "Modules"];
const WORKFLOWX_IMPORT_EXPORT_ROW_CATEGORY = ["WorkflowX", "Import / Export", "Backup and Restore"];
const TRANSFER_PARTS = [
  { key: "workflows", label: "Workflows", file: "workflowx_workflows.zip", accept: ".zip,application/zip" },
  { key: "metadata", label: "XFlows metadata", file: "workflowx_xflows_metadata.json", accept: ".json,application/json" },
  { key: "prompts", label: "XPrompts", file: "workflowx_xprompts.json", accept: ".json,application/json" },
  { key: "presets", label: "Presets", file: "workflowx_presets.json", accept: ".json,application/json" },
  { key: "node_snips", label: "XNodes", file: "workflowx_xnodes.json", accept: ".json,application/json" },
];

const FEATURE_SETTINGS = {
  xflows: {
    id: "WorkflowX.XFlows.Enabled",
    name: "Enable XFlows",
    defaultValue: true,
    tooltip: "Show the WorkflowX workflow manager side panel.",
  },
  xprompts: {
    id: "WorkflowX.XPrompts.Enabled",
    name: "Enable XPrompts",
    defaultValue: true,
    tooltip: "Show the WorkflowX prompt and preset side panel button.",
  },
  xnodes: {
    id: "WorkflowX.XNodes.Enabled",
    name: "Enable XNodes",
    defaultValue: true,
    tooltip: "Show the WorkflowX node snips side panel button.",
  },
};

const XLIB = {
  prompts: [],
  presets: [],
  snips: [],
  activePanel: null,
  promptTab: "prompts",
  promptQuery: "",
  presetQuery: "",
  snipQuery: "",
  promptSort: "updated",
  presetFavorites: false,
  presetSort: "updated",
  snipSort: "updated",
  promptFavorites: false,
  snipFavorites: false,
  snipType: "all",
  dialog: null,
  transferDialog: null,
  message: "",
  lastTextTarget: null,
  panels: {},
  buttons: {},
  collapsedPresetCategories: new Set(JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}.collapsedPresetCategories`) || "[]")),
  collapsedSnipSections: new Set(JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}.collapsedSnipSections`) || "[]")),
};

const style = `
.xlib-panel {
  --xlib-bg: color-mix(in srgb, var(--comfy-menu-bg, #181a20) 94%, #1d4ed8 6%);
  --xlib-panel: color-mix(in srgb, var(--comfy-menu-bg, #181a20) 84%, #ffffff 7%);
  --xlib-panel-2: color-mix(in srgb, var(--comfy-input-bg, #101217) 88%, #38bdf8 6%);
  --xlib-border: color-mix(in srgb, var(--border-color, #3c3f45) 78%, #38bdf8 22%);
  --xlib-accent: #38bdf8;
  --xlib-warn: #f59e0b;
  --xlib-danger: #ef4444;
  --xlib-muted: color-mix(in srgb, var(--fg-color, #e7e9ee) 64%, transparent);
  background: var(--xlib-bg);
  border-left: 1px solid var(--xlib-border);
  bottom: 0;
  box-shadow: -24px 0 70px rgba(0,0,0,.46);
  color: var(--fg-color);
  display: none;
  flex-direction: column;
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  max-width: calc(100vw - 16px);
  min-width: min(360px, calc(100vw - 16px));
  position: fixed;
  right: 0;
  top: 0;
  width: clamp(380px, 28vw, 520px);
  z-index: 9998;
}
.xlib-panel * { box-sizing: border-box; letter-spacing: 0; }
.xlib-header {
  border-bottom: 1px solid var(--xlib-border);
  display: grid;
  gap: 8px;
  padding: 10px;
}
.xlib-title-row, .xlib-toolbar, .xlib-card-top, .xlib-actions, .xlib-dialog-title {
  align-items: center;
  display: flex;
  gap: 8px;
  min-width: 0;
}
.xlib-title {
  flex: 1;
  font-size: 15px;
  font-weight: 760;
  min-width: 0;
}
.xlib-toolbar {
  flex-wrap: wrap;
}
.xlib-subtle, .xlib-meta {
  color: var(--xlib-muted);
  font-size: 11px;
}
.xlib-status {
  color: var(--xlib-muted);
  font-size: 11px;
  min-height: 16px;
}
.xlib-content {
  align-content: start;
  display: grid;
  flex: 1;
  gap: 8px;
  grid-auto-rows: max-content;
  min-height: 0;
  overflow: auto;
  padding: 8px 10px 12px;
}
.xlib-input, .xlib-text, .xlib-select {
  background: var(--comfy-input-bg, #111318);
  border: 1px solid var(--xlib-border);
  border-radius: 7px;
  color: var(--fg-color);
  font: inherit;
  min-height: 34px;
  outline: none;
  padding: 7px 9px;
  width: 100%;
}
.xlib-text {
  min-height: 120px;
  resize: vertical;
  white-space: pre-wrap;
}
.xlib-input:focus, .xlib-text:focus, .xlib-select:focus {
  border-color: var(--xlib-accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--xlib-accent) 24%, transparent);
}
.xlib-btn {
  align-items: center;
  background: var(--xlib-panel-2);
  border: 1px solid var(--xlib-border);
  border-radius: 7px;
  color: var(--fg-color);
  cursor: pointer;
  display: inline-flex;
  font: inherit;
  font-size: 12px;
  font-weight: 650;
  gap: 6px;
  justify-content: center;
  min-height: 32px;
  padding: 6px 9px;
  white-space: nowrap;
}
.xlib-btn:hover { border-color: var(--xlib-accent); filter: brightness(1.08); }
.xlib-btn.active, .xlib-btn[aria-pressed="true"] {
  background: color-mix(in srgb, var(--xlib-accent) 28%, var(--xlib-panel-2));
  border-color: var(--xlib-accent);
}
.xlib-icon-btn {
  aspect-ratio: 1 / 1;
  min-width: 34px;
  padding: 0;
}
.xlib-danger:hover { border-color: var(--xlib-danger); color: #fecaca; }
.xlib-star {
  background: transparent;
  border-color: transparent;
  color: var(--xlib-muted);
}
.xlib-star.active { color: var(--xlib-warn); }
.xlib-segment {
  background: color-mix(in srgb, var(--xlib-panel-2) 70%, transparent);
  border: 1px solid var(--xlib-border);
  border-radius: 8px;
  display: inline-flex;
  padding: 2px;
}
.xlib-segment .xlib-btn {
  background: transparent;
  border-color: transparent;
  min-height: 28px;
}
.xlib-card {
  align-content: start;
  background: linear-gradient(180deg, var(--xlib-panel), color-mix(in srgb, var(--xlib-panel) 86%, #000 14%));
  border: 1px solid var(--xlib-border);
  border-radius: 8px;
  display: grid;
  gap: 7px;
  grid-auto-rows: max-content;
  min-height: 0;
  min-width: 0;
  padding: 10px;
}
.xlib-card-title {
  flex: 1;
  font-size: 13px;
  font-weight: 740;
  line-height: 1.25;
  min-width: 0;
  overflow-wrap: anywhere;
}
.xlib-preview {
  color: color-mix(in srgb, var(--fg-color, #e7e9ee) 82%, transparent);
  display: -webkit-box;
  font-size: 12px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-height: 1.35;
  overflow: hidden;
  white-space: pre-wrap;
}
.xlib-card-top .xlib-preview {
  flex: 1;
  min-width: 0;
}
.xlib-tags {
  align-content: start;
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  min-height: 0;
}
.xlib-pill {
  align-items: center;
  background: color-mix(in srgb, var(--xlib-accent) 18%, transparent);
  border: 1px solid color-mix(in srgb, var(--xlib-accent) 45%, transparent);
  border-radius: 999px;
  display: inline-flex;
  font-size: 10.5px;
  line-height: 1.15;
  max-height: 26px;
  max-width: 100%;
  min-height: 21px;
  overflow: hidden;
  overflow-wrap: anywhere;
  padding: 3px 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.xlib-section {
  border: 1px solid color-mix(in srgb, var(--xlib-border) 78%, transparent);
  border-radius: 8px;
  display: grid;
  min-width: 0;
  overflow: hidden;
}
.xlib-section > summary {
  align-items: center;
  background: color-mix(in srgb, var(--xlib-panel-2) 82%, transparent);
  cursor: pointer;
  display: grid;
  gap: 8px;
  grid-template-columns: auto 1fr auto;
  list-style: none;
  min-height: 34px;
  padding: 6px 8px;
}
.xlib-section > summary::-webkit-details-marker { display: none; }
.xlib-section > summary::before {
  color: var(--xlib-accent);
  content: ">";
  display: inline-block;
  font-size: 13px;
  transition: transform 120ms ease;
}
.xlib-section[open] > summary::before { transform: rotate(90deg); }
.xlib-section-body {
  display: grid;
  gap: 7px;
  padding: 8px;
}
.xlib-row-card {
  background: color-mix(in srgb, var(--xlib-panel) 82%, transparent);
  border: 1px solid color-mix(in srgb, var(--xlib-border) 66%, transparent);
  border-radius: 7px;
  display: grid;
  gap: 7px;
  min-width: 0;
  padding: 8px;
}
.xlib-empty {
  border: 1px dashed var(--xlib-border);
  border-radius: 8px;
  color: var(--xlib-muted);
  font-size: 12px;
  padding: 18px;
  text-align: center;
}
.xlib-dialog-backdrop {
  align-items: center;
  background: rgba(0, 0, 0, .48);
  display: flex;
  inset: 0;
  justify-content: center;
  padding: 14px;
  position: absolute;
  z-index: 4;
}
.xlib-dialog-backdrop.xlib-global {
  position: fixed;
  z-index: 10002;
}
.xlib-dialog {
  background: color-mix(in srgb, var(--comfy-menu-bg, #181a20) 94%, #111 6%);
  border: 1px solid var(--xlib-border);
  border-radius: 10px;
  box-shadow: 0 18px 60px rgba(0,0,0,.48);
  display: grid;
  gap: 10px;
  max-height: min(660px, 92%);
  overflow: auto;
  padding: 12px;
  width: min(500px, 100%);
}
.xlib-dialog.wide {
  width: min(620px, 100%);
}
.workflowx-settings-controls {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-start;
  width: 100%;
}
.workflowx-settings-row > td {
  padding-left: 0;
}
.workflowx-settings-row label:empty,
.workflowx-settings-row td:first-child:empty {
  display: none;
}
.workflowx-settings-toggle {
  align-items: center;
  background: color-mix(in srgb, var(--comfy-input-bg, #101217) 84%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color, #3c3f45) 72%, transparent);
  border-radius: 9px;
  color: var(--fg-color, #eef2f7);
  cursor: pointer;
  display: inline-flex;
  gap: 8px;
  min-height: 34px;
  padding: 0 10px;
  user-select: none;
}
.workflowx-settings-toggle input {
  accent-color: #38bdf8;
}
.workflowx-settings-action.xlib-btn {
  align-items: center;
  background: color-mix(in srgb, var(--comfy-input-bg, #101217) 84%, #38bdf8 10%);
  border: 1px solid color-mix(in srgb, var(--border-color, #3c3f45) 70%, #38bdf8 30%);
  border-radius: 8px;
  color: var(--fg-color, #eef2f7);
  display: inline-flex;
  font-size: 12px;
  font-weight: 760;
  gap: 7px;
  min-height: 34px;
  padding: 0 12px;
}
.workflowx-settings-action.xlib-btn:hover {
  background: color-mix(in srgb, var(--comfy-input-bg, #101217) 72%, #38bdf8 18%);
  border-color: #38bdf8;
}
.xlib-dialog-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}
.xlib-check-list {
  display: grid;
  gap: 6px;
}
.xlib-check-row {
  align-items: center;
  background: color-mix(in srgb, var(--xlib-panel-2) 68%, transparent);
  border: 1px solid color-mix(in srgb, var(--xlib-border) 72%, transparent);
  border-radius: 7px;
  cursor: pointer;
  display: grid;
  gap: 8px;
  grid-template-columns: auto 1fr auto;
  min-height: 34px;
  padding: 7px 8px;
}
.xlib-check-row input {
  accent-color: var(--xlib-accent);
}
.xlib-check-row.disabled {
  cursor: default;
  opacity: .55;
}
.xlib-file-list {
  border: 1px solid var(--xlib-border);
  border-radius: 8px;
  display: grid;
  gap: 4px;
  max-height: 170px;
  overflow: auto;
  padding: 8px;
}
.xlib-file-row {
  align-items: center;
  color: var(--xlib-muted);
  display: flex;
  font-size: 11px;
  gap: 6px;
  justify-content: space-between;
  min-width: 0;
}
.xlib-file-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
`;

function icon(name) {
  return $el("i", { className: `pi ${name}` });
}

function button({ label, iconName, title, className = "", pressed = false, onClick }) {
  const element = $el("button.xlib-btn", {
    type: "button",
    title: title || label || "",
    "aria-label": title || label || "",
    "aria-pressed": pressed ? "true" : "false",
    onclick: onClick,
  });
  for (const cls of className.split(/\s+/).filter(Boolean)) element.classList.add(cls);
  if (iconName) element.append(icon(iconName));
  if (label) element.append($el("span", { textContent: label }));
  return element;
}

function iconButton(iconName, title, onClick, className = "") {
  return button({ iconName, title, onClick, className: `xlib-icon-btn ${className}` });
}

function containComfyKeys(event) {
  event.stopPropagation();
}

function protectField(element, focusId = "") {
  if (!element) return element;
  if (focusId) element.dataset.xlibFocusId = focusId;
  for (const eventName of ["keydown", "keypress", "keyup", "beforeinput", "input", "compositionstart", "compositionupdate", "compositionend", "paste", "cut"]) {
    element.addEventListener(eventName, containComfyKeys);
  }
  return element;
}

function inputField(attrs = {}, focusId = "") {
  return protectField($el("input.xlib-input", attrs), focusId);
}

function textField(attrs = {}, focusId = "") {
  return protectField($el("textarea.xlib-text", attrs), focusId);
}

function selectField(attrs = {}, children = [], focusId = "") {
  return protectField($el("select.xlib-select", attrs, children), focusId);
}

function captureFocusState(element) {
  if (!element?.dataset?.xlibFocusId) return null;
  const panelName = XLIB.activePanel;
  const panel = panelName ? XLIB.panels[panelName] : null;
  return {
    panelName,
    focusId: element.dataset.xlibFocusId,
    start: Number.isInteger(element.selectionStart) ? element.selectionStart : null,
    end: Number.isInteger(element.selectionEnd) ? element.selectionEnd : null,
    contentScrollTop: panel?.querySelector?.(".xlib-content")?.scrollTop || 0,
  };
}

function restoreFocusState(state) {
  if (!state?.panelName || !state.focusId) return;
  requestAnimationFrame(() => {
    const panel = XLIB.panels[state.panelName];
    if (!panel) return;
    const content = panel.querySelector(".xlib-content");
    if (content) content.scrollTop = state.contentScrollTop || 0;
    const target = [...panel.querySelectorAll("[data-xlib-focus-id]")].find((element) => element.dataset.xlibFocusId === state.focusId);
    if (!target) return;
    target.focus({ preventScroll: true });
    if (Number.isInteger(state.start) && Number.isInteger(state.end) && typeof target.setSelectionRange === "function") {
      try {
        target.setSelectionRange(state.start, state.end);
      } catch {
      }
    }
  });
}

function renderActivePanelWithFocus(element, update) {
  const focusState = captureFocusState(element);
  update();
  renderActivePanel({ restoreFocus: focusState });
}

function settingStorageKey(id) {
  return `${SETTINGS_PREFIX}.${id}`;
}

function readFeatureSetting(feature) {
  const spec = FEATURE_SETTINGS[feature];
  if (!spec) return true;
  try {
    const value = app.ui?.settings?.getSettingValue?.(spec.id);
    if (value !== undefined && value !== null) return value !== false && value !== "false";
  } catch {}
  const stored = localStorage.getItem(settingStorageKey(spec.id));
  return stored == null ? spec.defaultValue : stored !== "false";
}

function setWorkflowXFeature(feature, enabled) {
  const spec = FEATURE_SETTINGS[feature];
  if (!spec) return;
  localStorage.setItem(settingStorageKey(spec.id), String(Boolean(enabled)));
  try {
    app.ui?.settings?.setSettingValue?.(spec.id, Boolean(enabled));
  } catch {}
  try {
    api.storeSetting?.(spec.id, Boolean(enabled));
  } catch {}
  window.dispatchEvent(new CustomEvent("workflowx:feature-settings-changed", { detail: { id: spec.id, feature, enabled: Boolean(enabled) } }));
  applyFeatureVisibility();
}

function featureToggleControl(feature) {
  const spec = FEATURE_SETTINGS[feature];
  const label = $el("label.workflowx-settings-toggle", { title: spec.tooltip });
  const checkbox = $el("input", {
    type: "checkbox",
    checked: readFeatureSetting(feature),
    onchange: (event) => setWorkflowXFeature(feature, event.target.checked),
    parent: label,
  });
  checkbox.checked = readFeatureSetting(feature);
  label.append($el("span", { textContent: spec.name.replace("Enable ", "") }));
  return label;
}

function workflowXSettingRow(controls) {
  return $el("tr.workflowx-settings-row", [
    $el("td", { colSpan: 2 }, [$el("div.workflowx-settings-controls", controls)]),
  ]);
}

function registerWorkflowXSettings() {
  try {
    app.ui?.settings?.addSetting?.({
      id: "WorkflowX.FeatureToggles",
      category: WORKFLOWX_FEATURE_ROW_CATEGORY,
      name: " ",
      defaultValue: null,
      type: () => {
        for (const feature of ["xflows", "xprompts", "xnodes"]) {
          const spec = FEATURE_SETTINGS[feature];
          if (localStorage.getItem(settingStorageKey(spec.id)) == null) {
            localStorage.setItem(settingStorageKey(spec.id), String(spec.defaultValue));
          }
        }
        return workflowXSettingRow([
          featureToggleControl("xflows"),
          featureToggleControl("xprompts"),
          featureToggleControl("xnodes"),
        ]);
      },
    });

    app.ui?.settings?.addSetting?.({
      id: "WorkflowX.ImportExport",
      category: WORKFLOWX_IMPORT_EXPORT_ROW_CATEGORY,
      name: " ",
      defaultValue: null,
      type: () => workflowXSettingRow([
        button({ label: "Export WorkflowX Data", iconName: "pi-download", className: "workflowx-settings-action", title: "Export workflows and WorkflowX metadata", onClick: () => openTransferDialog("export") }),
        button({ label: "Import WorkflowX Data", iconName: "pi-upload", className: "workflowx-settings-action", title: "Import workflows and WorkflowX metadata", onClick: () => openTransferDialog("import") }),
      ]),
    });
  } catch (error) {
    console.warn("[WorkflowX] Failed to register settings", error);
  }
}

function syncFeatureDefaults() {
  for (const feature of ["xflows", "xprompts", "xnodes"]) {
    const spec = FEATURE_SETTINGS[feature];
    if (localStorage.getItem(settingStorageKey(spec.id)) == null) {
      localStorage.setItem(settingStorageKey(spec.id), String(spec.defaultValue));
    }
  }
}

function setButtonVisible(buttonRef, visible) {
  const target = buttonRef?.element || buttonRef?.button || buttonRef?.root || buttonRef;
  if (target?.style) target.style.display = visible ? "" : "none";
}

function applyFeatureVisibility() {
  const promptsEnabled = readFeatureSetting("xprompts");
  const nodesEnabled = readFeatureSetting("xnodes");
  setButtonVisible(XLIB.buttons.prompts, promptsEnabled);
  setButtonVisible(XLIB.buttons.snips, nodesEnabled);
  if (!promptsEnabled && XLIB.activePanel === "prompts") XLIB.activePanel = null;
  if (!nodesEnabled && XLIB.activePanel === "snips") XLIB.activePanel = null;
  if (!promptsEnabled || !nodesEnabled) renderActivePanel();
}

async function apiJson(path, options = {}) {
  const response = await api.fetchApi(path, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.error || response.statusText || `Request failed: ${response.status}`);
  return data;
}

async function postJson(path, body = {}) {
  return apiJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function fileFromPayload(file) {
  const binary = atob(file.content || "");
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: file.mime || "application/octet-stream" });
}

function downloadPayload(file) {
  const blob = fileFromPayload(file);
  const url = URL.createObjectURL(blob);
  const link = $el("a", { href: url, download: file.name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function writePayloadToDirectory(directoryHandle, file) {
  const handle = await directoryHandle.getFileHandle(file.name, { create: true });
  const writable = await handle.createWritable();
  await writable.write(fileFromPayload(file));
  await writable.close();
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error || new Error(`Could not read ${file.name}`));
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve({
        name: file.name,
        content: result.includes(",") ? result.split(",").pop() : result,
      });
    };
    reader.readAsDataURL(file);
  });
}

function setMessage(text) {
  XLIB.message = text || "";
  if (XLIB.activePanel) renderActivePanel();
}

function isTextTarget(element) {
  if (!element) return false;
  if (element instanceof HTMLTextAreaElement) return true;
  if (element instanceof HTMLInputElement) {
    return ["", "text", "search", "url"].includes(String(element.type || "").toLowerCase());
  }
  return Boolean(element.isContentEditable);
}

function rememberTextTarget(event) {
  if (isTextTarget(event.target) && !event.target.closest?.(".xlib-panel")) {
    XLIB.lastTextTarget = event.target;
  }
}

function currentTextTarget() {
  const active = document.activeElement;
  if (isTextTarget(active) && !active.closest?.(".xlib-panel")) return active;
  if (isTextTarget(XLIB.lastTextTarget) && document.contains(XLIB.lastTextTarget)) return XLIB.lastTextTarget;
  return null;
}

function insertText(text) {
  const target = currentTextTarget();
  if (!target) {
    setMessage("Focus a ComfyUI text field first, then use an item.");
    return false;
  }
  target.focus({ preventScroll: true });
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
    const start = Number.isInteger(target.selectionStart) ? target.selectionStart : target.value.length;
    const end = Number.isInteger(target.selectionEnd) ? target.selectionEnd : start;
    target.value = `${target.value.slice(0, start)}${text}${target.value.slice(end)}`;
    const pos = start + text.length;
    target.setSelectionRange(pos, pos);
    target.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
    setMessage("Inserted text.");
    return true;
  }
  if (target.isContentEditable) {
    const selection = window.getSelection();
    if (selection?.rangeCount) {
      const range = selection.getRangeAt(0);
      if (!target.contains(range.commonAncestorContainer)) range.selectNodeContents(target);
      range.deleteContents();
      range.insertNode(document.createTextNode(text));
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    } else {
      target.append(document.createTextNode(text));
    }
    target.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
    setMessage("Inserted text.");
    return true;
  }
  return false;
}

function selectedText() {
  const target = currentTextTarget();
  if (!target) return "";
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
    const start = Number.isInteger(target.selectionStart) ? target.selectionStart : 0;
    const end = Number.isInteger(target.selectionEnd) ? target.selectionEnd : 0;
    return target.value.slice(start, end);
  }
  if (target.isContentEditable) {
    const selection = window.getSelection();
    if (selection?.rangeCount && target.contains(selection.anchorNode)) return String(selection);
  }
  return "";
}

function parseTags(value) {
  return String(value || "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function shortDate(ms) {
  if (!ms) return "never";
  try {
    return new Date(ms).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "unknown";
  }
}

function preview(text, length = 220) {
  const value = String(text || "").trim();
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function collectSearchStrings(value, output = [], depth = 0) {
  if (depth > 6 || value == null) return output;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    output.push(String(value));
    return output;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectSearchStrings(item, output, depth + 1);
    return output;
  }
  if (typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      if (["pos", "size", "color", "bgcolor", "flags"].includes(key)) continue;
      output.push(key);
      collectSearchStrings(item, output, depth + 1);
    }
  }
  return output;
}

async function loadLibrary() {
  const data = await apiJson(`${ROUTE}/all`, { cache: "no-store" });
  XLIB.prompts = data.prompts || [];
  XLIB.presets = data.presets || [];
  XLIB.snips = data.node_snips || [];
}

async function refreshPanel() {
  await loadLibrary();
  renderActivePanel();
}

function openPanel(name) {
  if (name === "prompts" && !readFeatureSetting("xprompts")) return;
  if (name === "snips" && !readFeatureSetting("xnodes")) return;
  XLIB.activePanel = XLIB.activePanel === name ? null : name;
  XLIB.dialog = null;
  renderActivePanel();
  if (XLIB.activePanel) refreshPanel().catch((error) => setMessage(error.message));
}

function ensurePanels() {
  if (XLIB.panels.prompts) return;
  XLIB.panels.prompts = $el("div.xlib-panel", { parent: document.body });
  XLIB.panels.snips = $el("div.xlib-panel", { parent: document.body });
}

function renderActivePanel(options = {}) {
  ensurePanels();
  for (const [name, panel] of Object.entries(XLIB.panels)) {
    const enabled = name === "prompts" ? readFeatureSetting("xprompts") : readFeatureSetting("xnodes");
    panel.style.display = enabled && XLIB.activePanel === name ? "flex" : "none";
    if (XLIB.activePanel === name) renderPanel(panel, name);
  }
  if (options.restoreFocus) restoreFocusState(options.restoreFocus);
}

function renderPanel(panel, name) {
  panel.replaceChildren();
  if (name === "prompts") renderPromptPanel(panel);
  if (name === "snips") renderSnipPanel(panel);
  if (XLIB.dialog) renderDialog(panel);
}

function panelHeader(panel, title, count) {
  const header = $el("div.xlib-header", { parent: panel });
  const row = $el("div.xlib-title-row", { parent: header });
  $el("div.xlib-title", { textContent: title, parent: row });
  $el("div.xlib-subtle", { textContent: count == null ? "" : String(count), parent: row });
  row.append(iconButton("pi-times", "Close", () => openPanel(XLIB.activePanel)));
  if (XLIB.message) $el("div.xlib-status", { textContent: XLIB.message, parent: header });
  return header;
}

function sortedPrompts() {
  const query = XLIB.promptQuery.trim().toLowerCase();
  const items = XLIB.prompts.filter((item) => {
    if (XLIB.promptFavorites && !item.favorite) return false;
    if (!query) return true;
    return [
      item.title,
      item.text,
      ...(item.tags || []),
      item.favorite ? "favorite starred" : "",
      `${item.use_count || 0} uses`,
      shortDate(item.updated_at),
      shortDate(item.last_used_at),
    ].join("\n").toLowerCase().includes(query);
  });
  items.sort((a, b) => {
    if (XLIB.promptSort === "favorite") return Number(Boolean(b.favorite)) - Number(Boolean(a.favorite)) || a.title.localeCompare(b.title);
    if (XLIB.promptSort === "used") return (b.use_count || 0) - (a.use_count || 0) || a.title.localeCompare(b.title);
    if (XLIB.promptSort === "name") return a.title.localeCompare(b.title);
    return (b.updated_at || 0) - (a.updated_at || 0) || a.title.localeCompare(b.title);
  });
  return items;
}

function renderPromptPanel(panel) {
  const count = XLIB.promptTab === "prompts" ? XLIB.prompts.length : XLIB.presets.length;
  const header = panelHeader(panel, "XPrompts", count);
  const tabs = $el("div.xlib-segment", { parent: header });
  tabs.append(
    button({ label: "Prompts", iconName: "pi-align-left", className: XLIB.promptTab === "prompts" ? "active" : "", pressed: XLIB.promptTab === "prompts", onClick: () => { XLIB.promptTab = "prompts"; renderActivePanel(); } }),
    button({ label: "Presets", iconName: "pi-bolt", className: XLIB.promptTab === "presets" ? "active" : "", pressed: XLIB.promptTab === "presets", onClick: () => { XLIB.promptTab = "presets"; renderActivePanel(); } })
  );
  if (XLIB.promptTab === "prompts") renderPromptTab(panel, header);
  else renderPresetTab(panel, header);
}

function renderPromptTab(panel, header) {
  const toolbar = $el("div.xlib-toolbar", { parent: header });
  toolbar.append(
    inputField({
      value: XLIB.promptQuery,
      placeholder: "Search prompts...",
      oninput: (event) => renderActivePanelWithFocus(event.target, () => { XLIB.promptQuery = event.target.value; }),
    }, "prompt-search"),
    iconButton("pi-plus", "Add prompt", () => openPromptDialog()),
    iconButton("pi-save", "Save current selection", () => saveCurrentSelection())
  );
  const controls = $el("div.xlib-toolbar", { parent: header });
  const sort = selectField({
    value: XLIB.promptSort,
    onchange: (event) => { XLIB.promptSort = event.target.value; renderActivePanel(); },
  }, [
    $el("option", { value: "updated", textContent: "Updated" }),
    $el("option", { value: "name", textContent: "Name" }),
    $el("option", { value: "used", textContent: "Most used" }),
    $el("option", { value: "favorite", textContent: "Favorites first" }),
  ], "prompt-sort");
  sort.value = XLIB.promptSort;
  controls.append(sort, button({ label: "Favorites", iconName: "pi-star", className: XLIB.promptFavorites ? "active" : "", pressed: XLIB.promptFavorites, onClick: () => { XLIB.promptFavorites = !XLIB.promptFavorites; renderActivePanel(); } }));
  const content = $el("div.xlib-content", { parent: panel });
  const items = sortedPrompts();
  if (!items.length) $el("div.xlib-empty", { textContent: "No prompts match the current filters.", parent: content });
  for (const item of items) renderPromptCard(content, item);
}

function renderPromptCard(parent, item) {
  const card = $el("div.xlib-card", { parent });
  const top = $el("div.xlib-card-top", { parent: card });
  $el("div.xlib-card-title", { textContent: item.title || "Untitled prompt", parent: top });
  top.append(iconButton(item.favorite ? "pi-star-fill" : "pi-star", item.favorite ? "Remove favorite" : "Add favorite", () => savePrompt({ ...item, favorite: !item.favorite }), item.favorite ? "xlib-star active" : "xlib-star"));
  $el("div.xlib-preview", { textContent: preview(item.text), parent: card });
  $el("div.xlib-meta", { textContent: `${item.use_count || 0} uses | updated ${shortDate(item.updated_at)}`, parent: card });
  const tags = $el("div.xlib-tags", { parent: card });
  for (const tag of item.tags || []) tags.append($el("span.xlib-pill", { textContent: tag }));
  const actions = $el("div.xlib-actions", { parent: card });
  actions.append(
    button({ label: "Use", iconName: "pi-plus-circle", className: "active", onClick: () => usePrompt(item) }),
    button({ label: "Edit", iconName: "pi-pencil", onClick: () => openPromptDialog(item) }),
    button({ label: "Delete", iconName: "pi-trash", className: "xlib-danger", onClick: () => openDeleteDialog("prompt", item) })
  );
}

function openPromptDialog(item = null, text = "") {
  XLIB.dialog = {
    type: "prompt",
    item,
    title: item?.title || "",
    text: item?.text || text || "",
    tags: (item?.tags || []).join(", "),
  };
  renderActivePanel();
}

function saveCurrentSelection() {
  const text = selectedText().trim();
  if (!text) {
    setMessage("Select text in a ComfyUI text field first.");
    return;
  }
  openPromptDialog(null, text);
}

async function savePrompt(data) {
  const response = await postJson(`${ROUTE}/prompts/upsert`, data);
  XLIB.prompts = response.prompts || XLIB.prompts;
  XLIB.dialog = null;
  renderActivePanel();
}

async function usePrompt(item) {
  if (insertText(item.text || "")) {
    const response = await postJson(`${ROUTE}/prompts/use`, { id: item.id });
    const updated = response.prompt;
    XLIB.prompts = XLIB.prompts.map((prompt) => prompt.id === updated.id ? updated : prompt);
    renderActivePanel();
  }
}

async function deletePrompt(item) {
  const response = await postJson(`${ROUTE}/prompts/delete`, { id: item.id });
  XLIB.prompts = response.prompts || [];
  XLIB.dialog = null;
  renderActivePanel();
}

function filteredPresetCategories() {
  const query = XLIB.presetQuery.trim().toLowerCase();
  const categories = [];
  for (const category of XLIB.presets || []) {
    const categoryMatches = query && String(category.name || "").toLowerCase().includes(query);
    let snippets = (category.snippets || []).filter((snippet) => {
      if (XLIB.presetFavorites && !snippet.favorite) return false;
      if (!query || categoryMatches) return true;
      return [
        category.name,
        snippet.text,
        snippet.favorite ? "favorite starred" : "",
        `${snippet.use_count || 0} uses`,
        shortDate(snippet.updated_at),
        shortDate(snippet.last_used_at),
      ].join("\n").toLowerCase().includes(query);
    });
    snippets = snippets.sort((a, b) => {
      if (XLIB.presetSort === "favorite") return Number(Boolean(b.favorite)) - Number(Boolean(a.favorite)) || String(a.text || "").localeCompare(String(b.text || ""));
      if (XLIB.presetSort === "used") return (b.use_count || 0) - (a.use_count || 0) || String(a.text || "").localeCompare(String(b.text || ""));
      if (XLIB.presetSort === "name") return String(a.text || "").localeCompare(String(b.text || ""));
      return (b.updated_at || 0) - (a.updated_at || 0) || String(a.text || "").localeCompare(String(b.text || ""));
    });
    if (snippets.length || (categoryMatches && !XLIB.presetFavorites)) categories.push({ ...category, snippets });
  }
  return categories;
}

function saveCollapsedState(key, set) {
  localStorage.setItem(`${STORAGE_PREFIX}.${key}`, JSON.stringify([...set]));
}

function setPresetCategoryCollapsed(categoryId, collapsed) {
  if (collapsed) XLIB.collapsedPresetCategories.add(categoryId);
  else XLIB.collapsedPresetCategories.delete(categoryId);
  saveCollapsedState("collapsedPresetCategories", XLIB.collapsedPresetCategories);
}

function setAllPresetCategories(collapsed) {
  XLIB.collapsedPresetCategories = collapsed ? new Set((XLIB.presets || []).map((category) => category.id)) : new Set();
  saveCollapsedState("collapsedPresetCategories", XLIB.collapsedPresetCategories);
  renderActivePanel();
}

function setSnipSectionCollapsed(section, collapsed) {
  if (collapsed) XLIB.collapsedSnipSections.add(section);
  else XLIB.collapsedSnipSections.delete(section);
  saveCollapsedState("collapsedSnipSections", XLIB.collapsedSnipSections);
}

function setAllSnipSections(collapsed) {
  XLIB.collapsedSnipSections = collapsed ? new Set(["node", "group"]) : new Set();
  saveCollapsedState("collapsedSnipSections", XLIB.collapsedSnipSections);
  renderActivePanel();
}

function renderPresetTab(panel, header) {
  const toolbar = $el("div.xlib-toolbar", { parent: header });
  toolbar.append(
    inputField({
      value: XLIB.presetQuery,
      placeholder: "Search preset snippets...",
      oninput: (event) => renderActivePanelWithFocus(event.target, () => { XLIB.presetQuery = event.target.value; }),
    }, "preset-search"),
    iconButton("pi-folder-plus", "Add category", () => openCategoryDialog())
  );
  const controls = $el("div.xlib-toolbar", { parent: header });
  const sort = selectField({
    value: XLIB.presetSort,
    onchange: (event) => { XLIB.presetSort = event.target.value; renderActivePanel(); },
  }, [
    $el("option", { value: "updated", textContent: "Updated" }),
    $el("option", { value: "name", textContent: "Name" }),
    $el("option", { value: "used", textContent: "Most used" }),
    $el("option", { value: "favorite", textContent: "Favorites first" }),
  ], "preset-sort");
  sort.value = XLIB.presetSort;
  controls.append(sort, button({ label: "Favorites", iconName: "pi-star", className: XLIB.presetFavorites ? "active" : "", pressed: XLIB.presetFavorites, onClick: () => { XLIB.presetFavorites = !XLIB.presetFavorites; renderActivePanel(); } }));
  const sectionControls = $el("div.xlib-toolbar", { parent: header });
  sectionControls.append(
    button({ label: "Expand all", iconName: "pi-angle-double-down", onClick: () => setAllPresetCategories(false) }),
    button({ label: "Collapse all", iconName: "pi-angle-double-up", onClick: () => setAllPresetCategories(true) })
  );
  const content = $el("div.xlib-content", { parent: panel });
  const categories = filteredPresetCategories();
  if (!categories.length) $el("div.xlib-empty", { textContent: "No preset snippets match the current filters.", parent: content });
  for (const category of categories) renderPresetCategory(content, category);
}

function renderPresetCategory(parent, category) {
  const collapsed = XLIB.collapsedPresetCategories.has(category.id);
  const section = $el("details.xlib-section", {
    ontoggle: (event) => setPresetCategoryCollapsed(category.id, !event.currentTarget.open),
    parent,
  });
  section.open = !collapsed;
  const summary = $el("summary", { parent: section });
  $el("div.xlib-card-title", { textContent: category.name || "Category", parent: summary });
  $el("div.xlib-meta", { textContent: `${(category.snippets || []).length} snippets`, parent: summary });
  const body = $el("div.xlib-section-body", { parent: section });
  const snippets = category.snippets || [];
  for (const snippet of snippets) {
    const row = $el("div.xlib-row-card", { parent: body });
    const top = $el("div.xlib-card-top", { parent: row });
    $el("div.xlib-preview", { textContent: preview(snippet.text, 160), parent: top });
    top.append(iconButton(snippet.favorite ? "pi-star-fill" : "pi-star", snippet.favorite ? "Remove favorite" : "Add favorite", () => saveSnippet({ category_id: category.id, id: snippet.id, text: snippet.text, favorite: !snippet.favorite }), snippet.favorite ? "xlib-star active" : "xlib-star"));
    $el("div.xlib-meta", { textContent: `${snippet.use_count || 0} uses | updated ${shortDate(snippet.updated_at)}`, parent: row });
    const actions = $el("div.xlib-actions", { parent: row });
    actions.append(
      button({ label: "Use", iconName: "pi-plus-circle", className: "active", onClick: () => usePresetSnippet(category, snippet) }),
      button({ label: "Edit", iconName: "pi-pencil", onClick: () => openSnippetDialog(category, snippet) }),
      button({ label: "Delete", iconName: "pi-trash", className: "xlib-danger", onClick: () => openDeleteDialog("snippet", snippet, category) })
    );
  }
  const actions = $el("div.xlib-actions", { parent: body });
  actions.append(
    button({ label: "Add snippet", iconName: "pi-plus", onClick: () => openSnippetDialog(category) }),
    button({ label: "Edit category", iconName: "pi-pencil", onClick: () => openCategoryDialog(category) }),
    button({ label: "Delete category", iconName: "pi-trash", className: "xlib-danger", onClick: () => openDeleteDialog("category", category) })
  );
}

function openCategoryDialog(category = null) {
  XLIB.dialog = { type: "category", category, name: category?.name || "" };
  renderActivePanel();
}

function openSnippetDialog(category, snippet = null) {
  XLIB.dialog = { type: "snippet", category, snippet, text: snippet?.text || "" };
  renderActivePanel();
}

async function saveCategory(data) {
  const response = await postJson(`${ROUTE}/presets/category/upsert`, data);
  XLIB.presets = response.categories || XLIB.presets;
  XLIB.dialog = null;
  renderActivePanel();
}

async function saveSnippet(data) {
  const response = await postJson(`${ROUTE}/presets/snippet/upsert`, data);
  XLIB.presets = response.categories || XLIB.presets;
  XLIB.dialog = null;
  renderActivePanel();
}

async function usePresetSnippet(category, snippet) {
  if (insertText(snippet.text || "")) {
    const response = await postJson(`${ROUTE}/presets/snippet/use`, { category_id: category.id, id: snippet.id });
    XLIB.presets = response.categories || XLIB.presets;
    renderActivePanel();
  }
}

async function deleteCategory(category) {
  const response = await postJson(`${ROUTE}/presets/category/delete`, { id: category.id });
  XLIB.presets = response.categories || [];
  XLIB.dialog = null;
  renderActivePanel();
}

async function deleteSnippet(category, snippet) {
  const response = await postJson(`${ROUTE}/presets/snippet/delete`, { category_id: category.id, id: snippet.id });
  XLIB.presets = response.categories || [];
  XLIB.dialog = null;
  renderActivePanel();
}

function selectedNodes() {
  const nodes = [];
  const selected = app.canvas?.selected_nodes;
  if (selected && typeof selected === "object") {
    for (const node of Object.values(selected)) if (node && !nodes.includes(node)) nodes.push(node);
  }
  if (app.canvas?.selected_node && !nodes.includes(app.canvas.selected_node)) nodes.push(app.canvas.selected_node);
  return nodes;
}

function serializedSelection() {
  const nodes = selectedNodes();
  if (!nodes.length) return null;
  const selectedIds = new Set(nodes.map((node) => Number(node.id)));
  const graphData = app.graph.serialize();
  const serializedNodes = (graphData.nodes || [])
    .filter((node) => selectedIds.has(Number(node.id)))
    .map((node) => scrubNodeLinks(JSON.parse(JSON.stringify(node))));
  const rawLinks = Array.isArray(graphData.links) ? graphData.links : Object.values(graphData.links || {});
  const links = rawLinks.filter((link) => {
    const origin = Array.isArray(link) ? link[1] : link.origin_id;
    const target = Array.isArray(link) ? link[3] : link.target_id;
    return selectedIds.has(Number(origin)) && selectedIds.has(Number(target));
  }).map((link) => JSON.parse(JSON.stringify(link)));
  return { type: serializedNodes.length > 1 ? "group" : "node", nodes: serializedNodes, links };
}

function scrubNodeLinks(node) {
  for (const input of node.inputs || []) input.link = null;
  for (const output of node.outputs || []) output.links = [];
  return node;
}

function viewportCenter() {
  const canvas = app.canvas;
  const scale = canvas?.ds?.scale || 1;
  const offset = canvas?.ds?.offset || [0, 0];
  const element = canvas?.canvas || { width: 800, height: 600 };
  return [(element.width / 2 - offset[0]) / scale, (element.height / 2 - offset[1]) / scale];
}

function insertNodeSnip(snip) {
  const LiteGraph = window.LiteGraph;
  const payload = snip.payload || {};
  const savedNodes = payload.nodes || [];
  if (!LiteGraph || !savedNodes.length) {
    setMessage("Could not recreate this node snip in the current graph.");
    return;
  }
  const center = viewportCenter();
  const minX = Math.min(...savedNodes.map((node) => Number(node.pos?.[0] || 0)));
  const minY = Math.min(...savedNodes.map((node) => Number(node.pos?.[1] || 0)));
  const oldToNode = new Map();
  for (const saved of savedNodes) {
    const node = LiteGraph.createNode(saved.type);
    if (!node) continue;
    const data = JSON.parse(JSON.stringify(saved));
    const oldId = Number(data.id);
    delete data.id;
    data.pos = [center[0] + Number(saved.pos?.[0] || 0) - minX, center[1] + Number(saved.pos?.[1] || 0) - minY];
    node.configure(data);
    app.graph.add(node);
    oldToNode.set(oldId, node);
  }
  for (const link of payload.links || []) {
    const originId = Number(Array.isArray(link) ? link[1] : link.origin_id);
    const originSlot = Number(Array.isArray(link) ? link[2] : link.origin_slot);
    const targetId = Number(Array.isArray(link) ? link[3] : link.target_id);
    const targetSlot = Number(Array.isArray(link) ? link[4] : link.target_slot);
    const origin = oldToNode.get(originId);
    const target = oldToNode.get(targetId);
    if (origin && target && typeof origin.connect === "function") origin.connect(originSlot, target, targetSlot);
  }
  app.graph.setDirtyCanvas(true, true);
  setMessage(`Inserted ${snip.type === "group" ? "node group" : "node"}.`);
}

function sortedSnips() {
  const query = XLIB.snipQuery.trim().toLowerCase();
  const items = XLIB.snips.filter((item) => {
    if (XLIB.snipFavorites && !item.favorite) return false;
    if (XLIB.snipType !== "all" && item.type !== XLIB.snipType) return false;
    if (!query) return true;
    return [
      item.title,
      item.type,
      ...(item.tags || []),
      item.favorite ? "favorite starred" : "",
      `${item.use_count || 0} uses`,
      shortDate(item.updated_at),
      shortDate(item.last_used_at),
      ...collectSearchStrings(item.payload),
    ].join("\n").toLowerCase().includes(query);
  });
  items.sort((a, b) => {
    if (XLIB.snipSort === "favorite") return Number(Boolean(b.favorite)) - Number(Boolean(a.favorite)) || a.title.localeCompare(b.title);
    if (XLIB.snipSort === "used") return (b.use_count || 0) - (a.use_count || 0) || a.title.localeCompare(b.title);
    if (XLIB.snipSort === "name") return a.title.localeCompare(b.title);
    return (b.updated_at || 0) - (a.updated_at || 0) || a.title.localeCompare(b.title);
  });
  return items;
}

function renderSnipPanel(panel) {
  const header = panelHeader(panel, "XNodes", XLIB.snips.length);
  const toolbar = $el("div.xlib-toolbar", { parent: header });
  toolbar.append(
    inputField({
      value: XLIB.snipQuery,
      placeholder: "Search node snips...",
      oninput: (event) => renderActivePanelWithFocus(event.target, () => { XLIB.snipQuery = event.target.value; }),
    }, "snip-search"),
    iconButton("pi-save", "Save selected node(s)", () => openSaveSnipDialog())
  );
  const controls = $el("div.xlib-toolbar", { parent: header });
  const sort = selectField({
    value: XLIB.snipSort,
    onchange: (event) => { XLIB.snipSort = event.target.value; renderActivePanel(); },
  }, [
    $el("option", { value: "updated", textContent: "Updated" }),
    $el("option", { value: "name", textContent: "Name" }),
    $el("option", { value: "used", textContent: "Most used" }),
    $el("option", { value: "favorite", textContent: "Favorites first" }),
  ], "snip-sort");
  sort.value = XLIB.snipSort;
  const type = selectField({
    value: XLIB.snipType,
    onchange: (event) => { XLIB.snipType = event.target.value; renderActivePanel(); },
  }, [
    $el("option", { value: "all", textContent: "All types" }),
    $el("option", { value: "node", textContent: "Nodes" }),
    $el("option", { value: "group", textContent: "Groups" }),
  ], "snip-type");
  type.value = XLIB.snipType;
  controls.append(sort, type, button({ label: "Favorites", iconName: "pi-star", className: XLIB.snipFavorites ? "active" : "", pressed: XLIB.snipFavorites, onClick: () => { XLIB.snipFavorites = !XLIB.snipFavorites; renderActivePanel(); } }));
  const sectionControls = $el("div.xlib-toolbar", { parent: header });
  sectionControls.append(
    button({ label: "Expand all", iconName: "pi-angle-double-down", onClick: () => setAllSnipSections(false) }),
    button({ label: "Collapse all", iconName: "pi-angle-double-up", onClick: () => setAllSnipSections(true) })
  );
  const content = $el("div.xlib-content", { parent: panel });
  const items = sortedSnips();
  if (!items.length) $el("div.xlib-empty", { textContent: "No node snips match the current filters.", parent: content });
  if (XLIB.snipType !== "group") {
    renderSnipSection(content, "node", "Nodes", items.filter((item) => item.type !== "group"));
  }
  if (XLIB.snipType !== "node") {
    renderSnipSection(content, "group", "Groups", items.filter((item) => item.type === "group"));
  }
}

function renderSnipSection(parent, sectionKey, title, items) {
  if (!items.length) return;
  const collapsed = XLIB.collapsedSnipSections.has(sectionKey);
  const section = $el("details.xlib-section", {
    ontoggle: (event) => setSnipSectionCollapsed(sectionKey, !event.currentTarget.open),
    parent,
  });
  section.open = !collapsed;
  const summary = $el("summary", { parent: section });
  $el("div.xlib-card-title", { textContent: title, parent: summary });
  $el("div.xlib-meta", { textContent: `${items.length} saved`, parent: summary });
  const body = $el("div.xlib-section-body", { parent: section });
  for (const item of items) renderSnipCard(body, item);
}

function renderSnipCard(parent, item) {
  const card = $el("div.xlib-card", { parent });
  const top = $el("div.xlib-card-top", { parent: card });
  $el("div.xlib-card-title", { textContent: item.title || "Untitled snip", parent: top });
  top.append(iconButton(item.favorite ? "pi-star-fill" : "pi-star", item.favorite ? "Remove favorite" : "Add favorite", () => saveSnip({ ...item, favorite: !item.favorite }), item.favorite ? "xlib-star active" : "xlib-star"));
  const count = item.payload?.nodes?.length || 0;
  $el("div.xlib-meta", { textContent: `${item.type || "node"} | ${count} node${count === 1 ? "" : "s"} | ${item.use_count || 0} uses`, parent: card });
  const tags = $el("div.xlib-tags", { parent: card });
  for (const tag of item.tags || []) tags.append($el("span.xlib-pill", { textContent: tag }));
  const actions = $el("div.xlib-actions", { parent: card });
  actions.append(
    button({ label: "Use", iconName: "pi-plus-circle", className: "active", onClick: () => useSnip(item) }),
    button({ label: "Edit", iconName: "pi-pencil", onClick: () => openEditSnipDialog(item) }),
    button({ label: "Delete", iconName: "pi-trash", className: "xlib-danger", onClick: () => openDeleteDialog("snip", item) })
  );
}

function openSaveSnipDialog() {
  const payload = serializedSelection();
  if (!payload) {
    setMessage("Select one or more nodes first.");
    return;
  }
  XLIB.dialog = {
    type: "snip",
    mode: "create",
    title: payload.type === "group" ? "Node group" : payload.nodes[0]?.title || payload.nodes[0]?.type || "Node",
    tags: "",
    payload,
    snipType: payload.type,
  };
  renderActivePanel();
}

function openEditSnipDialog(item) {
  XLIB.dialog = { type: "snip", mode: "edit", item, title: item.title || "", tags: (item.tags || []).join(", "), payload: item.payload || {}, snipType: item.type || "node" };
  renderActivePanel();
}

async function saveSnip(data) {
  const response = await postJson(`${ROUTE}/node-snips/upsert`, data);
  XLIB.snips = response.snips || XLIB.snips;
  XLIB.dialog = null;
  renderActivePanel();
}

async function useSnip(item) {
  insertNodeSnip(item);
  const response = await postJson(`${ROUTE}/node-snips/use`, { id: item.id });
  const updated = response.snip;
  XLIB.snips = XLIB.snips.map((snip) => snip.id === updated.id ? updated : snip);
  renderActivePanel();
}

async function deleteSnip(item) {
  const response = await postJson(`${ROUTE}/node-snips/delete`, { id: item.id });
  XLIB.snips = response.snips || [];
  XLIB.dialog = null;
  renderActivePanel();
}

function openDeleteDialog(kind, item, parent = null) {
  XLIB.dialog = { type: "delete", kind, item, parent };
  renderActivePanel();
}

function defaultTransferParts(enabled = true) {
  return Object.fromEntries(TRANSFER_PARTS.map((part) => [part.key, enabled]));
}

function selectedTransferParts(dialog = XLIB.transferDialog) {
  return Object.fromEntries(TRANSFER_PARTS.map((part) => [part.key, Boolean(dialog?.parts?.[part.key])]));
}

function openTransferDialog(mode) {
  XLIB.transferDialog = {
    mode,
    parts: defaultTransferParts(mode === "export"),
    files: [],
    preview: null,
    busy: false,
    status: "",
  };
  renderTransferDialog();
}

function closeTransferDialog() {
  XLIB.transferDialog = null;
  renderTransferDialog();
}

function setTransferStatus(status) {
  if (!XLIB.transferDialog) return;
  XLIB.transferDialog.status = status || "";
  renderTransferDialog();
}

async function chooseExportFolderAndWrite(files) {
  if (!window.showDirectoryPicker) return false;
  const directory = await window.showDirectoryPicker({ mode: "readwrite" });
  for (const file of files) await writePayloadToDirectory(directory, file);
  return true;
}

async function exportWorkflowX(useFolder) {
  const dialog = XLIB.transferDialog;
  if (!dialog) return;
  dialog.busy = true;
  dialog.status = "Preparing export...";
  renderTransferDialog();
  try {
    const data = await postJson(`${TRANSFER_ROUTE}/export`, { parts: selectedTransferParts(dialog) });
    const files = data.files || [];
    if (useFolder && await chooseExportFolderAndWrite(files)) {
      dialog.status = `Exported ${files.length} file(s) to selected folder.`;
    } else {
      files.forEach(downloadPayload);
      dialog.status = `Downloaded ${files.length} export file(s).`;
    }
  } catch (error) {
    dialog.status = `Export failed: ${error.message}`;
  } finally {
    dialog.busy = false;
    renderTransferDialog();
  }
}

async function readTransferFilesFromFolder() {
  if (!window.showDirectoryPicker) {
    setTransferStatus("Folder picker is not available in this browser. Use Upload files.");
    return;
  }
  const directory = await window.showDirectoryPicker({ mode: "read" });
  const names = [...TRANSFER_PARTS.map((part) => part.file), "workflowx_manifest.json"];
  const files = [];
  for (const name of names) {
    try {
      const handle = await directory.getFileHandle(name);
      files.push(await readFileAsBase64(await handle.getFile()));
    } catch {}
  }
  await previewImportFiles(files);
}

async function readTransferFilesFromPicker() {
  const input = $el("input", {
    type: "file",
    multiple: true,
    accept: TRANSFER_PARTS.map((part) => part.accept).join(","),
    style: { display: "none" },
  });
  document.body.append(input);
  input.onchange = async () => {
    const files = await Promise.all([...input.files].map(readFileAsBase64));
    input.remove();
    await previewImportFiles(files);
  };
  input.click();
}

async function previewImportFiles(files) {
  const dialog = XLIB.transferDialog;
  if (!dialog) return;
  dialog.busy = true;
  dialog.status = "Inspecting import files...";
  renderTransferDialog();
  try {
    const data = await postJson(`${TRANSFER_ROUTE}/import/preview`, { files });
    dialog.files = files;
    dialog.preview = data;
    dialog.parts = Object.fromEntries(TRANSFER_PARTS.map((part) => [part.key, Boolean(data.detected?.[part.key])]));
    dialog.status = data.errors?.length ? `Ready with ${data.errors.length} warning(s).` : "Ready to import.";
  } catch (error) {
    dialog.files = [];
    dialog.preview = null;
    dialog.status = `Preview failed: ${error.message}`;
  } finally {
    dialog.busy = false;
    renderTransferDialog();
  }
}

async function importWorkflowX() {
  const dialog = XLIB.transferDialog;
  if (!dialog?.files?.length) return;
  dialog.busy = true;
  dialog.status = "Importing selected data...";
  renderTransferDialog();
  try {
    const data = await postJson(`${TRANSFER_ROUTE}/import`, {
      files: dialog.files,
      parts: selectedTransferParts(dialog),
    });
    dialog.status = `Import complete. Backup: ${data.backup_path}`;
    await loadLibrary().catch(() => {});
    window.dispatchEvent(new CustomEvent("workflowx:imported", { detail: data }));
  } catch (error) {
    dialog.status = `Import failed: ${error.message}`;
  } finally {
    dialog.busy = false;
    renderTransferDialog();
    renderActivePanel();
  }
}

function renderTransferPartRows(parent, dialog, disabledMissing = false) {
  const list = $el("div.xlib-check-list", { parent });
  for (const part of TRANSFER_PARTS) {
    const detected = dialog.preview?.detected?.[part.key];
    const disabled = disabledMissing && !detected;
    const row = $el("label.xlib-check-row" + (disabled ? ".disabled" : ""), { parent: list });
    row.append($el("input", {
      type: "checkbox",
      checked: Boolean(dialog.parts?.[part.key]) && !disabled,
      disabled,
      onchange: (event) => {
        dialog.parts[part.key] = event.target.checked;
        renderTransferDialog();
      },
    }));
    $el("span", { textContent: part.label, parent: row });
    $el("span.xlib-meta", {
      textContent: detected ? `${detected.count} item(s)` : part.file,
      title: part.file,
      parent: row,
    });
  }
}

function renderTransferDialog() {
  document.getElementById("workflowx-transfer-dialog")?.remove();
  const dialog = XLIB.transferDialog;
  if (!dialog) return;
  const backdrop = $el("div.xlib-dialog-backdrop.xlib-global", { id: "workflowx-transfer-dialog", parent: document.body });
  const modal = $el("div.xlib-dialog.wide", { parent: backdrop });
  const title = $el("div.xlib-dialog-title", { parent: modal });
  $el("div.xlib-title", { textContent: dialog.mode === "export" ? "Export WorkflowX Data" : "Import WorkflowX Data", parent: title });
  title.append(iconButton("pi-times", "Close", closeTransferDialog));

  if (dialog.mode === "export") {
    $el("div.xlib-subtle", { textContent: "Choose what to export. Workflows are packaged as a zip; metadata and libraries are written as JSON files.", parent: modal });
    renderTransferPartRows(modal, dialog);
    const actions = $el("div.xlib-dialog-actions", { parent: modal });
    actions.append(
      button({ label: "Cancel", onClick: closeTransferDialog }),
      button({ label: "Download files", iconName: "pi-download", onClick: () => exportWorkflowX(false) }),
      button({ label: "Export to folder", iconName: "pi-folder", className: "active", onClick: () => exportWorkflowX(true) })
    );
  } else {
    $el("div.xlib-subtle", { textContent: "Choose a folder or upload export files, then select the parts to restore. Import overrides selected local data after creating a backup.", parent: modal });
    const pickActions = $el("div.xlib-dialog-actions", { parent: modal });
    pickActions.append(
      button({ label: "Upload files", iconName: "pi-upload", onClick: readTransferFilesFromPicker }),
      button({ label: "Choose folder", iconName: "pi-folder-open", className: "active", onClick: readTransferFilesFromFolder })
    );
    if (dialog.files?.length) {
      const fileList = $el("div.xlib-file-list", { parent: modal });
      for (const file of dialog.files) {
        const row = $el("div.xlib-file-row", { parent: fileList });
        $el("span", { textContent: file.name, title: file.name, parent: row });
      }
    }
    renderTransferPartRows(modal, dialog, true);
    if (dialog.preview?.errors?.length) {
      const errors = $el("div.xlib-file-list", { parent: modal });
      for (const error of dialog.preview.errors) $el("div.xlib-file-row", { textContent: error, parent: errors });
    }
    const actions = $el("div.xlib-dialog-actions", { parent: modal });
    actions.append(
      button({ label: "Cancel", onClick: closeTransferDialog }),
      button({ label: "Import selected", iconName: "pi-upload", className: "active", onClick: importWorkflowX })
    );
  }

  if (dialog.status) $el("div.xlib-status", { textContent: dialog.status, parent: modal });
  if (dialog.busy) $el("div.xlib-subtle", { textContent: "Working...", parent: modal });
}

function renderDialog(panel) {
  const backdrop = $el("div.xlib-dialog-backdrop", { parent: panel });
  const modal = $el("div.xlib-dialog", { parent: backdrop });
  const title = $el("div.xlib-dialog-title", { parent: modal });
  const close = () => { XLIB.dialog = null; renderActivePanel(); };
  const dialog = XLIB.dialog;

  if (dialog.type === "prompt") {
    $el("div.xlib-title", { textContent: dialog.item ? "Edit prompt" : "Add prompt", parent: title });
    title.append(iconButton("pi-times", "Close", close));
    modal.append(inputField({ value: dialog.title, placeholder: "Title", oninput: (event) => { dialog.title = event.target.value; } }, "dialog-prompt-title"));
    modal.append(textField({ value: dialog.text, placeholder: "Prompt text", oninput: (event) => { dialog.text = event.target.value; } }, "dialog-prompt-text"));
    modal.append(inputField({ value: dialog.tags, placeholder: "Tags, comma separated", oninput: (event) => { dialog.tags = event.target.value; } }, "dialog-prompt-tags"));
    const actions = $el("div.xlib-dialog-actions", { parent: modal });
    actions.append(button({ label: "Cancel", onClick: close }), button({ label: "Save", iconName: "pi-save", className: "active", onClick: () => savePrompt({ id: dialog.item?.id, title: dialog.title, text: dialog.text, tags: parseTags(dialog.tags), favorite: Boolean(dialog.item?.favorite) }) }));
    return;
  }

  if (dialog.type === "category") {
    $el("div.xlib-title", { textContent: dialog.category ? "Edit category" : "Add category", parent: title });
    title.append(iconButton("pi-times", "Close", close));
    modal.append(inputField({ value: dialog.name, placeholder: "Category name", oninput: (event) => { dialog.name = event.target.value; } }, "dialog-category-name"));
    const actions = $el("div.xlib-dialog-actions", { parent: modal });
    actions.append(button({ label: "Cancel", onClick: close }), button({ label: "Save", iconName: "pi-save", className: "active", onClick: () => saveCategory({ id: dialog.category?.id, name: dialog.name }) }));
    return;
  }

  if (dialog.type === "snippet") {
    $el("div.xlib-title", { textContent: dialog.snippet ? "Edit snippet" : "Add snippet", parent: title });
    title.append(iconButton("pi-times", "Close", close));
    modal.append(textField({ value: dialog.text, placeholder: "Snippet text", oninput: (event) => { dialog.text = event.target.value; } }, "dialog-snippet-text"));
    const actions = $el("div.xlib-dialog-actions", { parent: modal });
    actions.append(button({ label: "Cancel", onClick: close }), button({ label: "Save", iconName: "pi-save", className: "active", onClick: () => saveSnippet({ category_id: dialog.category.id, id: dialog.snippet?.id, text: dialog.text, favorite: Boolean(dialog.snippet?.favorite) }) }));
    return;
  }

  if (dialog.type === "snip") {
    $el("div.xlib-title", { textContent: dialog.mode === "edit" ? "Edit node snip" : "Save node snip", parent: title });
    title.append(iconButton("pi-times", "Close", close));
    modal.append(inputField({ value: dialog.title, placeholder: "Title", oninput: (event) => { dialog.title = event.target.value; } }, "dialog-snip-title"));
    modal.append(inputField({ value: dialog.tags, placeholder: "Tags, comma separated", oninput: (event) => { dialog.tags = event.target.value; } }, "dialog-snip-tags"));
    $el("div.xlib-subtle", { textContent: `${dialog.snipType} | ${(dialog.payload.nodes || []).length} node(s)`, parent: modal });
    const actions = $el("div.xlib-dialog-actions", { parent: modal });
    actions.append(button({ label: "Cancel", onClick: close }), button({ label: "Save", iconName: "pi-save", className: "active", onClick: () => saveSnip({ id: dialog.item?.id, title: dialog.title, type: dialog.snipType, tags: parseTags(dialog.tags), payload: dialog.payload, favorite: Boolean(dialog.item?.favorite) }) }));
    return;
  }

  if (dialog.type === "delete") {
    const label = dialog.kind === "category" ? "category" : dialog.kind === "snippet" ? "snippet" : dialog.kind === "snip" ? "node snip" : "prompt";
    $el("div.xlib-title", { textContent: `Delete ${label}?`, parent: title });
    title.append(iconButton("pi-times", "Close", close));
    $el("div.xlib-subtle", { textContent: "This removes it from the saved library JSON.", parent: modal });
    const actions = $el("div.xlib-dialog-actions", { parent: modal });
    const action = () => {
      if (dialog.kind === "prompt") return deletePrompt(dialog.item);
      if (dialog.kind === "category") return deleteCategory(dialog.item);
      if (dialog.kind === "snippet") return deleteSnippet(dialog.parent, dialog.item);
      return deleteSnip(dialog.item);
    };
    actions.append(button({ label: "Cancel", onClick: close }), button({ label: "Delete", iconName: "pi-trash", className: "xlib-danger", onClick: action }));
  }
}

async function registerButtons() {
  ensurePanels();
  const promptToggle = () => openPanel("prompts");
  const snipToggle = () => openPanel("snips");
  try {
    const { ComfyButton } = await import("../../scripts/ui/components/button.js");
    XLIB.buttons.prompts = new ComfyButton({ icon: "text", action: promptToggle, tooltip: "WorkflowX Prompts", content: "XPrompts" });
    XLIB.buttons.snips = new ComfyButton({ icon: "box", action: snipToggle, tooltip: "WorkflowX Nodes", content: "XNodes" });
    app.menu?.settingsGroup?.append(XLIB.buttons.prompts);
    app.menu?.settingsGroup?.append(XLIB.buttons.snips);
  } catch {
    const menu = document.querySelector(".comfy-menu") || document.body;
    XLIB.buttons.prompts = button({ label: "XPrompts", iconName: "pi-align-left", title: "WorkflowX Prompts", onClick: promptToggle });
    XLIB.buttons.snips = button({ label: "XNodes", iconName: "pi-box", title: "WorkflowX Nodes", onClick: snipToggle });
    menu.append(XLIB.buttons.prompts, XLIB.buttons.snips);
  }
  applyFeatureVisibility();
}

app.registerExtension({
  name: "Comfy.WorkflowXLibraryPanels",
  init() {
    if (!document.getElementById("xflows-library-style")) {
      $el("style", { id: "xflows-library-style", textContent: style, parent: document.head });
    }
    document.addEventListener("focusin", rememberTextTarget, true);
  },
  async setup() {
    syncFeatureDefaults();
    registerWorkflowXSettings();
    await registerButtons();
    await loadLibrary().catch((error) => setMessage(error.message));
  },
});
