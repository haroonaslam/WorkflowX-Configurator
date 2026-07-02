import { app } from "../../scripts/app.js";

const TARGET_NODE = "UnifiedAutoprompterX";
const ROUTE = "/workflowx/unified_autoprompter";
const GEMINI_KEY_STORAGE_KEY = "workflowx_unified_autoprompter_gemini_api_key";
const MODEL_SELECTION_STORAGE_KEY = "workflowx_unified_autoprompter_model_selection";
const IDEOGRAM_TEMPLATE_STORAGE_KEY = "workflowx_unified_autoprompter_ideogram_templates";
const IDEOGRAM_TEMPLATE_DIR = "workflowx/unified-autoprompter/ideogram4/templates";
const DEFAULT_OLLAMA_HOST = "http://localhost:11434";
const IDEOGRAM_MAX_ELEM_COLORS = 5;
const IDEOGRAM_MAX_STYLE_COLORS = 16;
const IDEOGRAM_PANEL_DEFAULT_HEIGHT = 176;
const IDEOGRAM_PANEL_MIN_HEIGHT = 132;
const IDEOGRAM_PANEL_MAX_HEIGHT = 340;
const ALL_PROMPT_FORMATS = ["natural", "tags", "json"];

function fallbackRule(enabled, text = "") {
  return {
    enabled,
    common_instructions: text,
    output_contract_negative_off: enabled ? '{"positive":"the final prompt","negative":""}' : "",
    output_contract_negative_on: enabled ? '{"positive":"the final positive prompt","negative":"the final negative prompt"}' : "",
    with_image_reference_instructions: enabled ? "Use the connected image as visual reference." : "",
    without_image_reference_instructions: enabled ? "Use the text fields only." : "",
  };
}

const FALLBACK_PROFILES = [
  { key: "ideogram4", label: "Ideogram 4", formats: { natural: fallbackRule(true, "Write an Ideogram natural-language prompt."), tags: fallbackRule(false), json: fallbackRule(true, "Write Ideogram structured caption JSON.") }, default_format: "json", negative_supported: true, json_supported: true, media_type: "image", notes: "" },
  { key: "sdxl", label: "SDXL", formats: { natural: fallbackRule(true, "Write an SDXL natural prompt."), tags: fallbackRule(true, "Write comma-separated SDXL tags."), json: fallbackRule(false) }, default_format: "tags", negative_supported: true, json_supported: false, media_type: "image", notes: "" },
  { key: "qwen_image", label: "Qwen-Image", formats: { natural: fallbackRule(true, "Write a Qwen-Image natural prompt."), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "image", notes: "" },
  { key: "flux1_dev", label: "FLUX.1 dev", formats: { natural: fallbackRule(true, "Write a FLUX.1 natural prompt."), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "image", notes: "" },
  { key: "flux2_dev", label: "FLUX.2 dev", formats: { natural: fallbackRule(true, "Write a FLUX.2 natural prompt."), tags: fallbackRule(false), json: fallbackRule(true, "Write FLUX.2 structured JSON.") }, default_format: "natural", negative_supported: true, json_supported: true, media_type: "image", notes: "" },
  { key: "flux_klein", label: "Flux Klein", formats: { natural: fallbackRule(true, "Write a compact Flux Klein prompt."), tags: fallbackRule(false), json: fallbackRule(true, "Write compact Flux Klein JSON.") }, default_format: "natural", negative_supported: true, json_supported: true, media_type: "image", notes: "" },
  { key: "z_image", label: "Z-Image", formats: { natural: fallbackRule(true, "Write a detailed Z-Image natural prompt."), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "image", notes: "" },
  { key: "wan2_2", label: "WAN 2.2", formats: { natural: fallbackRule(true, "Write a WAN 2.2 video prompt."), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "video", notes: "" },
  { key: "ltx_2_3", label: "LTX 2.3", formats: { natural: fallbackRule(true, "Write an LTX 2.3 chronological video prompt."), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "video", notes: "" },
];
const NODE_MIN_WIDGET_HEIGHT = 420;
let nextDockZ = 12000;

let profilesPromise = null;
const pinnedDocks = new Set();
let dockRAF = 0;
let dockWakesInstalled = false;

function chainCallback(object, callbackName, callback) {
  const original = object?.[callbackName];
  object[callbackName] = function workflowXUnifiedCallback() {
    const result = original?.apply(this, arguments);
    callback?.apply(this, arguments);
    return result;
  };
}

function applyPinnedDockTransform(node) {
  const canvas = app.canvas;
  const dock = node?.__workflowXUapPinnedDock;
  const graph = dock?.__workflowXGraph;
  if (!canvas || !dock || !graph) return;

  let nodeEl = null;
  if (window.LiteGraph?.vueNodesMode && node.id != null) {
    nodeEl = node.__workflowXUapDockNodeEl;
    if (!nodeEl || !nodeEl.isConnected) {
      nodeEl = node.__workflowXUapDockNodeEl = document.querySelector(`[data-node-id="${node.id}"]`);
    }
  }

  if (nodeEl) {
    const titleHeight = window.LiteGraph?.NODE_TITLE_HEIGHT ?? 30;
    if (dock.parentElement !== nodeEl) {
      nodeEl.appendChild(dock);
      dock.style.position = "absolute";
      dock.style.transform = "";
      dock.style.transformOrigin = "";
      dock.style.zIndex = "";
      node.__workflowXUapDockSig = "";
    }
    const sig = `vue|${graph.x}|${graph.y}`;
    if (node.__workflowXUapDockSig !== sig) {
      dock.style.left = `${graph.x}px`;
      dock.style.top = `${titleHeight + graph.y}px`;
      node.__workflowXUapDockSig = sig;
    }
    return;
  }

  if (dock.parentElement !== document.body) {
    document.body.appendChild(dock);
    node.__workflowXUapDockSig = "";
  }
  if (!node.pos) return;
  const ds = canvas.ds;
  const scale = ds.scale || 1;
  const rect = canvas.canvas.getBoundingClientRect();
  const left = rect.left + (node.pos[0] + graph.x + ds.offset[0]) * scale;
  const top = rect.top + (node.pos[1] + graph.y + ds.offset[1]) * scale;
  const sig = `fixed|${left}|${top}|${scale}`;
  if (node.__workflowXUapDockSig !== sig) {
    dock.style.position = "fixed";
    dock.style.transformOrigin = "top left";
    dock.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
    node.__workflowXUapDockSig = sig;
  }
}

function tickPinnedDocks() {
  dockRAF = 0;
  for (const node of pinnedDocks) applyPinnedDockTransform(node);
}

function wakePinnedDocks() {
  if (!dockRAF && pinnedDocks.size) dockRAF = requestAnimationFrame(tickPinnedDocks);
}

function installDockWakes() {
  if (dockWakesInstalled) return;
  if (!app.canvas) return;
  dockWakesInstalled = true;
  chainCallback(app.canvas, "onDrawForeground", wakePinnedDocks);
  window.addEventListener("resize", wakePinnedDocks);
}

function injectStyle() {
  if (document.getElementById("workflowx-uap-style")) return;
  const style = document.createElement("style");
  style.id = "workflowx-uap-style";
  style.textContent = `
.workflowx-uap {
  background: #101214;
  border: 1px solid #2b3036;
  border-radius: 6px;
  color: #e9eef3;
  display: flex;
  flex-direction: column;
  font: 11px ui-sans-serif, system-ui, sans-serif;
  gap: 7px;
  overflow: visible;
  padding: 8px;
  pointer-events: auto;
}
.workflowx-uap-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.workflowx-uap-grid {
  display: grid;
  gap: 6px;
  grid-template-columns: 1fr 1fr;
}
.workflowx-uap-label {
  color: #aab4be;
  display: block;
  font-size: 10px;
  margin: 0 0 3px;
}
.workflowx-uap-input,
.workflowx-uap-select,
.workflowx-uap-text {
  background: #0a0c0e;
  border: 1px solid #343a42;
  border-radius: 5px;
  box-sizing: border-box;
  color: #f3f6f8;
  font: 11px ui-sans-serif, system-ui, sans-serif;
  min-width: 0;
  padding: 5px 7px;
  width: 100%;
}
.workflowx-uap-text {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  min-height: 46px;
  resize: vertical;
}
.workflowx-uap-preview {
  background: #07090b;
  border: 1px solid #3a4149;
  border-radius: 6px;
  box-sizing: border-box;
  color: #eef3f7;
  font: 11px ui-monospace, SFMono-Regular, Consolas, monospace;
  max-height: 170px;
  min-height: 82px;
  overflow: auto;
  padding: 7px;
  white-space: pre-wrap;
  word-break: break-word;
}
.workflowx-uap-dock {
  background: #101214;
  border: 1px solid #3d4650;
  border-radius: 8px;
  box-shadow: 0 18px 56px rgba(0, 0, 0, .55);
  color: #e9eef3;
  display: flex;
  flex-direction: column;
  font: 11px ui-sans-serif, system-ui, sans-serif;
  min-height: 220px;
  min-width: 320px;
  overflow: hidden;
  position: fixed;
  pointer-events: auto;
}
.workflowx-uap-dock-head {
  align-items: center;
  background: #20262c;
  border-bottom: 1px solid #343d46;
  cursor: move;
  display: flex;
  flex: 0 0 auto;
  gap: 7px;
  padding: 5px 8px;
  user-select: none;
}
.workflowx-uap-dock-title {
  color: #f2f6f8;
  flex: 1;
  font-size: 12px;
  font-weight: 650;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflowx-uap-dock-body {
  box-sizing: border-box;
  display: grid;
  flex: 1 1 auto;
  gap: 8px;
  min-height: 0;
  overflow: auto;
  padding: 9px;
}
.workflowx-uap-dock.minimized {
  height: auto !important;
  min-height: 0;
}
.workflowx-uap-dock.minimized .workflowx-uap-dock-body,
.workflowx-uap-dock.minimized .workflowx-uap-dock-rsz {
  display: none;
}
.workflowx-uap-dock.fullscreen {
  border-radius: 0;
  bottom: 10px !important;
  height: auto !important;
  left: 10px !important;
  right: 10px !important;
  top: 10px !important;
  width: auto !important;
}
.workflowx-uap-dock-rsz {
  position: absolute;
  z-index: 2;
}
.workflowx-uap-dock-rsz.n,
.workflowx-uap-dock-rsz.s {
  cursor: ns-resize;
  height: 7px;
  left: 8px;
  right: 8px;
}
.workflowx-uap-dock-rsz.e,
.workflowx-uap-dock-rsz.w {
  bottom: 8px;
  cursor: ew-resize;
  top: 8px;
  width: 7px;
}
.workflowx-uap-dock-rsz.n { top: 0; }
.workflowx-uap-dock-rsz.s { bottom: 0; }
.workflowx-uap-dock-rsz.e { right: 0; }
.workflowx-uap-dock-rsz.w { left: 0; }
.workflowx-uap-dock-rsz.ne,
.workflowx-uap-dock-rsz.nw,
.workflowx-uap-dock-rsz.se,
.workflowx-uap-dock-rsz.sw {
  height: 12px;
  width: 12px;
}
.workflowx-uap-dock-rsz.ne { cursor: nesw-resize; right: 0; top: 0; }
.workflowx-uap-dock-rsz.nw { cursor: nwse-resize; left: 0; top: 0; }
.workflowx-uap-dock-rsz.se { bottom: 0; cursor: nwse-resize; right: 0; }
.workflowx-uap-dock-rsz.sw { bottom: 0; cursor: nesw-resize; left: 0; }
.workflowx-uap-dock-text {
  background: #07090b;
  border: 1px solid #3a4149;
  border-radius: 6px;
  box-sizing: border-box;
  color: #eef3f7;
  font: 12px ui-monospace, SFMono-Regular, Consolas, monospace;
  min-height: 260px;
  padding: 8px;
  resize: none;
  width: 100%;
}
.workflowx-uap-ideo-editor {
  display: flex;
  flex-direction: column;
  gap: 7px;
  height: 100%;
  min-height: 0;
}
.workflowx-uap-ideo-bar {
  align-items: center;
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: 6px;
}
.workflowx-uap-ideo-token {
  color: #8b949e;
  flex: 1 1 auto;
  white-space: nowrap;
}
.workflowx-uap-ideo-menu {
  background: #14181c;
  border: 1px solid #3a4149;
  border-radius: 6px;
  box-shadow: 0 12px 32px rgba(0,0,0,.45);
  color: #e9eef3;
  display: grid;
  gap: 7px;
  padding: 8px;
  position: fixed;
  z-index: 13000;
}
.workflowx-uap-ideo-layer-menu {
  background: #242424;
  border: 1px solid #555;
  border-radius: 7px;
  box-shadow: 0 10px 32px rgba(0,0,0,.55);
  color: #ddd;
  font: 12px ui-sans-serif, system-ui, sans-serif;
  max-height: 60vh;
  min-width: 360px;
  overflow-y: auto;
  padding: 8px;
  position: fixed;
  z-index: 13000;
}
.workflowx-uap-ideo-layer-header {
  color: #999;
  margin-bottom: 6px;
  white-space: nowrap;
}
.workflowx-uap-ideo-layer-row {
  align-items: center;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  gap: 8px;
  min-height: 27px;
  padding: 3px 4px;
  transition: transform .16s ease, background .12s ease;
}
.workflowx-uap-ideo-layer-row.active {
  background: #333;
}
.workflowx-uap-ideo-layer-row.dragging {
  opacity: .55;
}
.workflowx-uap-ideo-layer-swatch {
  border: 1px solid #666;
  border-radius: 3px;
  flex: 0 0 auto;
  height: 16px;
  width: 16px;
}
.workflowx-uap-ideo-layer-num {
  color: #999;
  flex: 0 0 auto;
  font: 700 11px ui-monospace, SFMono-Regular, Consolas, monospace;
  width: 20px;
}
.workflowx-uap-ideo-layer-text {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflowx-uap-ideo-layer-text.empty {
  color: #888;
}
.workflowx-uap-ideo-layer-btn {
  background: none;
  border: 0;
  border-radius: 3px;
  color: #aaa;
  cursor: pointer;
  flex: 0 0 auto;
  font: 12px ui-sans-serif, system-ui, sans-serif;
  padding: 2px 5px;
}
.workflowx-uap-ideo-layer-btn.on {
  background: #7a5a16;
  color: #fff;
}
.workflowx-uap-ideo-menu-row {
  align-items: center;
  display: flex;
  gap: 7px;
  min-width: 210px;
}
.workflowx-uap-ideo-swatch {
  border: 1px solid #4b5561;
  border-radius: 4px;
  cursor: pointer;
  display: inline-block;
  flex: 0 0 auto;
  height: 22px;
  position: relative;
  transition: transform .16s ease, box-shadow .12s ease, opacity .12s ease;
  width: 22px;
}
.workflowx-uap-ideo-swatch.dragging {
  opacity: .6;
}
.workflowx-uap-ideo-swatch input {
  height: 0;
  opacity: 0;
  pointer-events: none;
  position: absolute;
  width: 0;
}
.workflowx-uap-ideo-cv {
  align-items: center;
  background: #151719;
  border-radius: 4px;
  display: flex;
  flex: 1 1 auto;
  justify-content: center;
  min-height: 150px;
  overflow: hidden;
  position: relative;
}
.workflowx-uap-ideo-canvas {
  background: #2a2a2a;
  border-radius: 3px;
  box-sizing: border-box;
  cursor: crosshair;
  display: block;
  max-height: 100%;
  max-width: 100%;
}
.workflowx-uap-ideo-split {
  background: #595f66;
  border-radius: 99px;
  cursor: ns-resize;
  flex: 0 0 auto;
  height: 3px;
  margin: 0 auto;
  opacity: .75;
  width: 60px;
}
.workflowx-uap-ideo-panel {
  background: #202224;
  border-radius: 4px;
  box-sizing: border-box;
  color: #c8d0d7;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: ${IDEOGRAM_PANEL_MIN_HEIGHT}px;
  overflow: auto;
  padding: 6px;
}
.workflowx-uap-ideo-inline {
  background: rgba(18,18,18,.92);
  border: 2px solid #46b4e6;
  border-radius: 3px;
  box-sizing: border-box;
  color: #fff;
  font: 13px ui-monospace, SFMono-Regular, Consolas, monospace;
  outline: none;
  padding: 3px 4px;
  position: absolute;
  resize: none;
  z-index: 4;
}
.workflowx-uap-ideo-empty {
  color: #9aa3ac;
}
.workflowx-uap-ideo-panel-hint {
  color: #8f989f;
}
.workflowx-uap-ideo-active-row {
  align-items: center;
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: 6px;
}
.workflowx-uap-ideo-active-row span {
  color: #9aa3ac;
}
.workflowx-uap-ideo-bbox {
  background: #1d1d1d;
  border: 1px solid #444;
  border-radius: 4px;
  box-sizing: border-box;
  color: #bbb;
  font: 11px ui-monospace, SFMono-Regular, Consolas, monospace;
  padding: 3px 5px;
  width: 128px;
}
.workflowx-uap-ideo-area {
  background: #1d1d1d;
  border: 1px solid #444;
  border-radius: 4px;
  box-sizing: border-box;
  color: #ddd;
  flex: 1 1 auto;
  font: 13px ui-monospace, SFMono-Regular, Consolas, monospace;
  line-height: 1.35;
  min-height: 78px;
  padding: 4px 6px;
  resize: none;
  width: 100%;
}
.workflowx-uap-btn {
  background: #18222b;
  border: 1px solid #435160;
  border-radius: 5px;
  color: #f4f7fa;
  cursor: pointer;
  font: 11px ui-sans-serif, system-ui, sans-serif;
  min-height: 25px;
  padding: 4px 9px;
  white-space: nowrap;
}
.workflowx-uap-btn.primary {
  background: #f2f5f7;
  border-color: #f2f5f7;
  color: #111418;
  font-weight: 650;
}
.workflowx-uap-btn.active {
  background: #2f526f;
  border-color: #7bafd1;
}
.workflowx-uap-btn:disabled {
  cursor: default;
  opacity: .45;
}
.workflowx-uap-toggle {
  align-items: center;
  color: #c0c9d1;
  display: inline-flex;
  gap: 5px;
  user-select: none;
}
.workflowx-uap-panel {
  border: 1px solid #272d33;
  border-radius: 6px;
  display: grid;
  gap: 6px;
  padding: 7px;
}
.workflowx-uap-status {
  color: #aeb8c1;
  flex: 1;
  min-height: 14px;
}
.workflowx-uap-status.error {
  color: #ff8585;
}
.workflowx-uap-modal-backdrop {
  align-items: center;
  background: rgba(0,0,0,.58);
  display: flex;
  inset: 0;
  justify-content: center;
  position: fixed;
  z-index: 15000;
}
.workflowx-uap-modal {
  background: #111417;
  border: 1px solid #3b4550;
  border-radius: 8px;
  box-shadow: 0 18px 64px rgba(0,0,0,.62);
  color: #e9eef3;
  display: flex;
  flex-direction: column;
  font: 12px ui-sans-serif, system-ui, sans-serif;
  height: min(880px, 94vh);
  overflow: hidden;
  width: min(1380px, 96vw);
}
.workflowx-uap-modal-head {
  align-items: center;
  border-bottom: 1px solid #303842;
  display: flex;
  gap: 8px;
  padding: 10px 12px;
}
.workflowx-uap-modal-title {
  flex: 1 1 auto;
  font-size: 15px;
  font-weight: 650;
}
.workflowx-uap-settings-body {
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: 285px minmax(0, 1fr);
  min-height: 0;
}
.workflowx-uap-settings-list {
  border-right: 1px solid #303842;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  padding: 10px;
}
.workflowx-uap-settings-items {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 5px;
  min-height: 0;
  overflow: auto;
}
.workflowx-uap-settings-item {
  background: #171c21;
  border: 1px solid #303842;
  border-radius: 6px;
  color: #dbe3ea;
  cursor: pointer;
  padding: 8px;
  text-align: left;
}
.workflowx-uap-settings-item.active {
  background: #223143;
  border-color: #7bafd1;
}
.workflowx-uap-settings-key {
  color: #94a1ad;
  font: 11px ui-monospace, SFMono-Regular, Consolas, monospace;
  margin-top: 2px;
}
.workflowx-uap-settings-form {
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-height: 0;
  overflow: auto;
  padding: 10px 12px;
}
.workflowx-uap-settings-form .workflowx-uap-text {
  min-height: 170px;
  resize: vertical;
}
.workflowx-uap-settings-preview {
  background: #080b0e;
  border: 1px solid #303842;
  border-radius: 6px;
  color: #cfd8df;
  font: 11px ui-monospace, SFMono-Regular, Consolas, monospace;
  min-height: 280px;
  max-height: 46vh;
  overflow: auto;
  padding: 8px;
  white-space: pre-wrap;
}
.workflowx-uap-settings-tabs,
.workflowx-uap-settings-segment {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.workflowx-uap-settings-tab,
.workflowx-uap-settings-segment button {
  background: #171c21;
  border: 1px solid #303842;
  border-radius: 6px;
  color: #dbe3ea;
  cursor: pointer;
  padding: 7px 10px;
}
.workflowx-uap-settings-tab.active,
.workflowx-uap-settings-segment button.active {
  background: #223143;
  border-color: #7bafd1;
}
.workflowx-uap-settings-card {
  border: 1px solid #303842;
  border-radius: 6px;
  display: grid;
  gap: 10px;
  padding: 10px;
}
.workflowx-uap-settings-large {
  min-height: 260px !important;
}
.workflowx-uap-settings-contract {
  min-height: 150px !important;
}
.workflowx-uap-modal-foot {
  align-items: center;
  border-top: 1px solid #303842;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
}
.workflowx-uap-modal-message {
  color: #aeb8c1;
  flex: 1 1 auto;
  min-width: 240px;
}
.workflowx-uap-modal-message.error {
  color: #ff8585;
}
.workflowx-uap-hidden {
  display: none !important;
}
`;
  document.head.appendChild(style);
}

function loadStoredGeminiKey() {
  try {
    return window.localStorage?.getItem(GEMINI_KEY_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function storeGeminiKey(key) {
  try {
    const trimmed = String(key || "").trim();
    if (trimmed) window.localStorage?.setItem(GEMINI_KEY_STORAGE_KEY, trimmed);
    else window.localStorage?.removeItem(GEMINI_KEY_STORAGE_KEY);
  } catch {
    // Browser storage can be unavailable in restricted contexts.
  }
}

function loadStoredModelSelection() {
  try {
    const parsed = JSON.parse(window.localStorage?.getItem(MODEL_SELECTION_STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function storeModelSelection(selection) {
  try {
    const next = loadStoredModelSelection();
    const backend = String(selection?.backend || "").trim();
    if (["gemini", "ollama", "local"].includes(backend)) next.backend = backend;
    for (const key of ["gemini_model", "ollama_model", "local_model"]) {
      const value = String(selection?.[key] || "").trim();
      if (value) next[key] = value;
    }
    window.localStorage?.setItem(MODEL_SELECTION_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Browser storage can be unavailable in restricted contexts.
  }
}

function loadIdeogramTemplates() {
  try {
    const parsed = JSON.parse(window.localStorage?.getItem(IDEOGRAM_TEMPLATE_STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function storeIdeogramTemplates(templates) {
  try {
    window.localStorage?.setItem(IDEOGRAM_TEMPLATE_STORAGE_KEY, JSON.stringify(templates || {}));
  } catch {
    // Browser storage can be unavailable in restricted contexts.
  }
}

const ideogramTemplateSafeName = (name) => String(name || "").replace(/[\/\\:*?"<>|]+/g, "_").trim();
const ideogramTemplateFile = (name) => `${IDEOGRAM_TEMPLATE_DIR}/${ideogramTemplateSafeName(name)}.json`;

async function listIdeogramTemplateNames() {
  try {
    const items = await app.api?.listUserDataFullInfo?.(IDEOGRAM_TEMPLATE_DIR);
    if (!Array.isArray(items)) return Object.keys(loadIdeogramTemplates()).sort((a, b) => a.localeCompare(b));
    return items
      .map((item) => String(item.path || "").split(/[\\/]/).pop() || "")
      .filter((file) => /\.json$/i.test(file))
      .map((file) => file.replace(/\.json$/i, ""))
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b));
  } catch {
    return Object.keys(loadIdeogramTemplates()).sort((a, b) => a.localeCompare(b));
  }
}

async function loadIdeogramTemplate(name) {
  try {
    const response = await app.api?.getUserData?.(ideogramTemplateFile(name));
    if (response?.status === 200) return await response.text();
  } catch {
    // Fall through to legacy localStorage fallback.
  }
  const fallback = loadIdeogramTemplates()[name];
  return fallback ? JSON.stringify(fallback, null, 2) : null;
}

async function saveIdeogramTemplate(name, caption) {
  const safeName = ideogramTemplateSafeName(name);
  if (!safeName) return false;
  const text = typeof caption === "string" ? caption : JSON.stringify(caption, null, 2);
  try {
    if (!app.api?.storeUserData) throw new Error("userdata unavailable");
    await app.api.storeUserData(ideogramTemplateFile(safeName), text, {
      overwrite: true,
      stringify: false,
      throwOnError: true,
    });
    return true;
  } catch {
    const fallback = loadIdeogramTemplates();
    fallback[safeName] = typeof caption === "string" ? parseJsonObject(caption) : caption;
    storeIdeogramTemplates(fallback);
    return true;
  }
}

async function deleteIdeogramTemplate(name) {
  try {
    if (!app.api?.deleteUserData) throw new Error("userdata unavailable");
    await app.api.deleteUserData(ideogramTemplateFile(name));
  } catch {
    const fallback = loadIdeogramTemplates();
    delete fallback[name];
    storeIdeogramTemplates(fallback);
  }
}

function stopGraphEvents(element) {
  for (const eventName of ["mousedown", "pointerdown", "wheel", "dblclick"]) {
    element.addEventListener(eventName, (event) => event.stopPropagation());
  }
}

function findWidget(node, name) {
  return node.widgets?.find((widget) => widget.name === name) || null;
}

function widgetValue(node, name, fallback = "") {
  const widget = findWidget(node, name);
  return widget ? widget.value : fallback;
}

function setWidgetValue(node, name, value) {
  const widget = findWidget(node, name);
  if (!widget) return;
  widget.value = value;
  try {
    widget.callback?.call(widget, value, app.canvas, node, app.canvas?.graph_mouse);
  } catch (error) {
    console.warn("[WorkflowX Unified Autoprompter] Widget callback failed", name, error);
  }
}

function hideWidget(node, name) {
  const widget = findWidget(node, name);
  if (!widget) return;
  widget.hidden = true;
  widget.computeSize = () => [0, -4];
  const index = node.inputs?.findIndex((input) => input.name === name);
  if (index != null && index !== -1) node.removeInput(index);
}

function markDirty() {
  app.graph?.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
}

function option(select, value, label) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label || value;
  select.appendChild(item);
  return item;
}

async function loadProfiles() {
  if (!profilesPromise) {
    profilesPromise = fetch(`${ROUTE}/profiles`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => (data?.profiles || FALLBACK_PROFILES).map(ensureProfileShape))
      .catch(() => FALLBACK_PROFILES.map(ensureProfileShape));
  }
  return profilesPromise;
}

async function fetchJsonChecked(url, options = {}, label = "Request") {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  if (text.trim()) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(`${label} returned non-JSON HTTP ${response.status}: ${text.slice(0, 180)}`);
    }
  }
  if (!data) {
    const restartHint = "Restart ComfyUI so the new WorkflowX backend routes are registered.";
    throw new Error(`${label} returned an empty response${response.status ? ` (HTTP ${response.status})` : ""}. ${restartHint}`);
  }
  if (!response.ok || data.error) {
    throw new Error(data.error || `${label} failed with HTTP ${response.status}`);
  }
  return data;
}

function clearProfileCache() {
  profilesPromise = null;
}

function profileMap(profiles) {
  return new Map(profiles.map((profile) => {
    const shaped = ensureProfileShape(profile);
    return [shaped.key, shaped];
  }));
}

function profileIsVideo(profile) {
  return profile?.media_type === "video";
}

function formatRule(profile, promptFormat) {
  return profile?.formats?.[promptFormat] || null;
}

function enabledProfileFormats(profile) {
  const formats = profile?.formats;
  if (Array.isArray(formats)) return formats;
  return ALL_PROMPT_FORMATS.filter((format) => formats?.[format]?.enabled);
}

function ensureRule(rule = {}, enabled = false) {
  return {
    enabled: Boolean(rule.enabled ?? enabled),
    common_instructions: rule.common_instructions || "",
    output_contract_negative_off: rule.output_contract_negative_off || "",
    output_contract_negative_on: rule.output_contract_negative_on || "",
    with_image_reference_instructions: rule.with_image_reference_instructions || "",
    without_image_reference_instructions: rule.without_image_reference_instructions || "",
  };
}

function ensureProfileShape(profile) {
  const next = { ...profile };
  const rawFormats = next.formats;
  if (Array.isArray(rawFormats)) {
    next.formats = Object.fromEntries(ALL_PROMPT_FORMATS.map((format) => [format, fallbackRule(rawFormats.includes(format))]));
  } else {
    next.formats = Object.fromEntries(ALL_PROMPT_FORMATS.map((format) => [format, ensureRule(rawFormats?.[format])]));
  }
  const enabled = enabledProfileFormats(next);
  if (!enabled.includes(next.default_format)) next.default_format = enabled[0] || "natural";
  next.negative_supported = Boolean(next.negative_supported);
  next.json_supported = Boolean(next.json_supported);
  next.media_type ||= "image";
  next.notes ||= "";
  return next;
}

function profileOutputContract(profile, promptFormat, negativeEnabled) {
  const rule = formatRule(profile, promptFormat);
  return negativeEnabled ? rule?.output_contract_negative_on || "" : rule?.output_contract_negative_off || "";
}

function negativeInstruction(negativeEnabled) {
  return negativeEnabled
    ? "Generate the negative output only in the contract's negative field. Keep it separate from the positive prompt."
    : "Do not invent a negative prompt. Return an empty negative string when the output contract includes negative.";
}

function renderTemplatePreview(profile, promptFormat, negativeEnabled, hasImage = false) {
  profile = ensureProfileShape(profile || {});
  promptFormat = promptFormat || profile?.default_format || "natural";
  const rule = formatRule(profile, promptFormat) || ensureRule();
  const contract = profileOutputContract(profile, promptFormat, negativeEnabled);
  const imageRule = hasImage ? rule.with_image_reference_instructions : rule.without_image_reference_instructions;
  const template = [
    "You are Unified Autoprompter X.",
    `Target model: ${profile?.label || ""}`,
    `Target key: ${profile?.key || ""}`,
    `Output format: ${promptFormat}`,
    "",
    "Model notes:",
    profile?.notes || "",
    "",
    "Format-specific instructions:",
    rule.common_instructions || "",
    "",
    "Image reference mode:",
    imageRule || "",
    "",
    "Negative prompt handling:",
    negativeInstruction(negativeEnabled),
    "",
    "Output contract:",
    contract || "",
    "",
    "Return valid JSON only. No markdown fences, no commentary.",
  ].join("\n");
  const values = {
    target_label: profile?.label || "",
    target_key: profile?.key || "",
    prompt_format: promptFormat,
    output_contract: contract || "",
    negative_instruction: negativeInstruction(negativeEnabled),
    notes: profile?.notes || "",
  };
  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, key) => values[key] ?? match);
}

function normalizeIdeogramPanelHeight(value) {
  const height = Number(value || 0);
  if (!Number.isFinite(height) || height <= 120) return IDEOGRAM_PANEL_DEFAULT_HEIGHT;
  return Math.max(IDEOGRAM_PANEL_MIN_HEIGHT, Math.min(IDEOGRAM_PANEL_MAX_HEIGHT, Math.round(height)));
}

function defaultState(node) {
  let saved = {};
  try {
    saved = JSON.parse(widgetValue(node, "ui_state", "{}") || "{}");
  } catch {
    saved = {};
  }
  const storedModels = loadStoredModelSelection();
  const generatedPositive = widgetValue(node, "generated_positive", "");
  const generatedNegative = widgetValue(node, "generated_negative", "");
  const finalPrompt = widgetValue(node, "final_prompt", "");
  const savedGeneration = saved.last_generation && typeof saved.last_generation === "object"
    ? saved.last_generation
    : null;

  return {
    backend: saved.backend || storedModels.backend || "gemini",
    target_model: saved.target_model || widgetValue(node, "target_model", "ideogram4"),
    prompt_format: saved.prompt_format || widgetValue(node, "prompt_format", "json"),
    negative_enabled: saved.negative_enabled == null
      ? Boolean(widgetValue(node, "negative_enabled", false))
      : Boolean(saved.negative_enabled),
    idea: saved.idea || "",
    subject: saved.subject || "",
    style: saved.style || "",
    lighting: saved.lighting || "",
    composition: saved.composition || "",
    text: saved.text || "",
    detail: saved.detail || "high",
    image_note: saved.image_note || "",
    ideogram_layout: saved.ideogram_layout || "",
    ideogram_palette: saved.ideogram_palette || "",
    ideogram_overlay_visible: saved.ideogram_overlay_visible !== false,
    ideogram_overlay_brightness: saved.ideogram_overlay_brightness == null
      ? 35
      : Number(saved.ideogram_overlay_brightness) <= 1
        ? Math.round(Number(saved.ideogram_overlay_brightness) * 100)
        : Number(saved.ideogram_overlay_brightness),
    ideogram_width: Number(saved.ideogram_width || 1024),
    ideogram_height: Number(saved.ideogram_height || 1024),
    ideogram_manual_dims: Boolean(saved.ideogram_manual_dims || false),
    ideogram_panel_height: normalizeIdeogramPanelHeight(saved.ideogram_panel_height),
    video_duration_or_frames: saved.video_duration_or_frames || "",
    motion_action: saved.motion_action || "",
    temporal_beats: saved.temporal_beats || "",
    camera_movement: saved.camera_movement || "",
    audio_dialogue: saved.audio_dialogue || "",
    reference_or_control_notes: saved.reference_or_control_notes || "",
    extra_instructions: saved.extra_instructions || "",
    gemini_model: saved.gemini_model || storedModels.gemini_model || "",
    gemini_timeout: saved.gemini_timeout || 120,
    ollama_host: saved.ollama_host || DEFAULT_OLLAMA_HOST,
    ollama_model: saved.ollama_model || storedModels.ollama_model || "",
    ollama_think: Boolean(saved.ollama_think || false),
    unload_after: saved.unload_after !== false,
    local_model: saved.local_model || storedModels.local_model || "",
    local_mmproj: saved.local_mmproj || "none",
    local_system_prompt_preset: saved.local_system_prompt_preset || "none",
    max_tokens: saved.max_tokens || 768,
    temperature: saved.temperature || 0.7,
    top_p: saved.top_p || 0.9,
    top_k: saved.top_k || 40,
    ctx_size: saved.ctx_size || 8192,
    memory_mode: saved.memory_mode || "auto",
    n_gpu_layers: saved.n_gpu_layers || 99,
    n_cpu_moe_layers: saved.n_cpu_moe_layers || 0,
    reasoning: saved.reasoning || "auto",
    seed: saved.seed ?? -1,
    generated_positive: generatedPositive,
    generated_negative: generatedNegative,
    final_prompt: finalPrompt,
    last_generation: savedGeneration || (finalPrompt || generatedPositive || generatedNegative ? {
      prompt: finalPrompt || positiveAndNegativePrompt(generatedPositive, generatedNegative, Boolean(widgetValue(node, "negative_enabled", false)), widgetValue(node, "prompt_format", saved.prompt_format || "natural")),
      positive: generatedPositive,
      negative: generatedNegative,
      target_model: widgetValue(node, "target_model", saved.target_model || "ideogram4"),
      prompt_format: widgetValue(node, "prompt_format", saved.prompt_format || "natural"),
      negative_enabled: Boolean(widgetValue(node, "negative_enabled", false)),
      generated_at: saved.generated_at || "",
    } : null),
  };
}

function serializableState(state) {
  const {
    generated_positive,
    generated_negative,
    final_prompt,
    connected_image_b64,
    connected_image_url,
    connected_image_available,
    gemini_key,
    ...rest
  } = state;
  return rest;
}

function positiveAndNegativePrompt(positive, negative, negativeEnabled, promptFormat) {
  positive = String(positive || "").trim();
  negative = String(negative || "").trim();
  if (promptFormat === "json") return positive;
  if (negativeEnabled && negative) return `Positive:\n${positive}\n\nNegative:\n${negative}`;
  return positive;
}

function syncOutputWidgets(node, state, activeProfile) {
  const cached = state.last_generation || null;
  const negativeEnabled = cached ? Boolean(cached.negative_enabled) : Boolean(state.negative_enabled);
  const profileFormats = enabledProfileFormats(activeProfile);
  const promptFormat = profileFormats.includes(state.prompt_format)
    ? state.prompt_format
    : activeProfile?.default_format || profileFormats[0] || "natural";
  const outputFormat = cached?.prompt_format || promptFormat;
  const outputTarget = cached?.target_model || state.target_model;
  const positive = cached ? cached.positive || "" : state.generated_positive || "";
  const negative = cached ? cached.negative || "" : state.generated_negative || "";
  const finalPrompt = cached?.prompt || state.final_prompt || positiveAndNegativePrompt(
    positive,
    negative,
    negativeEnabled,
    outputFormat,
  );

  setWidgetValue(node, "target_model", outputTarget);
  setWidgetValue(node, "prompt_format", outputFormat);
  setWidgetValue(node, "negative_enabled", negativeEnabled);
  setWidgetValue(node, "generated_positive", positive || "");
  setWidgetValue(node, "generated_negative", negative || "");
  setWidgetValue(node, "final_prompt", finalPrompt || "");
  setWidgetValue(node, "ui_state", JSON.stringify(serializableState({ ...state, prompt_format: promptFormat }), null, 2));
  markDirty();
  return finalPrompt;
}

function buildDom(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function field(parent, label, control) {
  const wrap = buildDom("div");
  const lbl = buildDom("label", "workflowx-uap-label", label);
  wrap.appendChild(lbl);
  wrap.appendChild(control);
  parent.appendChild(wrap);
  return control;
}

function createInput(type = "text") {
  const input = document.createElement("input");
  input.type = type;
  input.className = "workflowx-uap-input";
  return input;
}

function createTextarea(rows = 2) {
  const textarea = document.createElement("textarea");
  textarea.className = "workflowx-uap-text";
  textarea.rows = rows;
  return textarea;
}

function createSelect() {
  const select = document.createElement("select");
  select.className = "workflowx-uap-select";
  return select;
}

function setSelectOptions(select, values, selectedValue, labeler = null) {
  select.innerHTML = "";
  for (const value of values) {
    option(select, value.value ?? value, value.label ?? labeler?.(value) ?? value);
  }
  if (selectedValue && Array.from(select.options).some((item) => item.value === selectedValue)) {
    select.value = selectedValue;
  } else if (select.options.length) {
    select.selectedIndex = 0;
  }
}

function fillModelSelect(select, models, selectedValue) {
  select.innerHTML = "";
  for (const model of models || []) {
    const value = model.id || model.name || model;
    const label = model.display_name || model.name || model.id || model;
    option(select, value, label);
  }
  if (selectedValue && Array.from(select.options).some((item) => item.value === selectedValue)) {
    select.value = selectedValue;
  }
}

function graphLink(graph, linkId) {
  const links = graph?.links;
  if (!links || linkId == null) return null;
  if (typeof links.get === "function") return links.get(linkId);
  return links[linkId] || null;
}

function resolveSourcePreview(node, inputName) {
  if (!node?.graph || !node.inputs) return null;
  const inputSlot = node.inputs.findIndex((input) => input.name === inputName);
  if (inputSlot < 0) return null;
  const input = node.inputs[inputSlot];
  if (!input || input.link == null) return null;
  const link = graphLink(node.graph, input.link);
  if (!link) return null;
  const srcNode = node.graph.getNodeById?.(link.origin_id);
  if (!srcNode) return null;

  const videoWidget = srcNode.widgets?.find((widget) => widget.name === "videopreview");
  if (videoWidget?.videoEl?.src) return { isVideo: true, videoEl: videoWidget.videoEl };

  const mediaWidget = srcNode.widgets?.find((widget) => widget.name === "image" || widget.name === "video");
  if (mediaWidget?.value) {
    let filename = String(mediaWidget.value);
    let subfolder = "";
    const slash = filename.lastIndexOf("/");
    if (slash >= 0) {
      subfolder = filename.slice(0, slash);
      filename = filename.slice(slash + 1);
    }
    return {
      url: `/view?filename=${encodeURIComponent(filename)}&type=input&subfolder=${encodeURIComponent(subfolder)}`,
      isVideo: mediaWidget.name === "video",
    };
  }

  if (srcNode.imgs?.length && srcNode.imgs[0]?.src) return { url: srcNode.imgs[0].src, isVideo: false };
  return null;
}

function captureVideoFrame(videoEl, callback) {
  const capture = () => {
    if (!videoEl?.videoWidth || !videoEl?.videoHeight) return;
    const canvas = document.createElement("canvas");
    canvas.width = videoEl.videoWidth;
    canvas.height = videoEl.videoHeight;
    canvas.getContext("2d")?.drawImage(videoEl, 0, 0);
    callback(canvas);
  };
  if (videoEl?.readyState >= 2) capture();
  else videoEl?.addEventListener("loadeddata", capture, { once: true });
}

function watchImageInputs(node, inputName, onChange) {
  let watchedWidgets = [];

  function unwatch() {
    for (const { widget, callback } of watchedWidgets) widget.callback = callback;
    watchedWidgets = [];
  }

  function resolve() {
    const source = resolveSourcePreview(node, inputName);
    return source ? [source] : [];
  }

  function watchSourceWidget() {
    unwatch();
    if (!node?.graph || !node.inputs) return;
    const input = node.inputs.find((item) => item.name === inputName);
    const link = graphLink(node.graph, input?.link);
    const srcNode = link ? node.graph.getNodeById?.(link.origin_id) : null;
    const widget = srcNode?.widgets?.find((item) => item.name === "image" || item.name === "video");
    if (!widget) return;
    const callback = widget.callback;
    widget.callback = function workflowXImageWidgetChanged() {
      const result = callback?.apply(this, arguments);
      setTimeout(() => onChange(resolve()), 100);
      return result;
    };
    watchedWidgets.push({ widget, callback });
  }

  chainCallback(node, "onConnectionsChange", function workflowXUapImageChanged(type) {
    if (type != null && type !== 1) return;
    setTimeout(() => {
      watchSourceWidget();
      onChange(resolve());
    }, 100);
  });
  chainCallback(node, "onRemoved", unwatch);
  setTimeout(() => {
    watchSourceWidget();
    onChange(resolve());
  }, 100);
  return unwatch;
}

function savedDockGeometry(node, key, fallback) {
  node.properties ||= {};
  node.properties.workflowx_uap_docks ||= {};
  const saved = node.properties.workflowx_uap_docks[key] || {};
  const graph = saved.graph && typeof saved.graph === "object" ? saved.graph : null;
  return {
    pinned: saved.pinned !== false,
    graph: graph ? {
      x: Number.isFinite(graph.x) ? graph.x : fallback.graph.x,
      y: Number.isFinite(graph.y) ? graph.y : fallback.graph.y,
      w: Number.isFinite(graph.w) ? graph.w : fallback.graph.w,
      h: Number.isFinite(graph.h) ? graph.h : fallback.graph.h,
    } : { ...fallback.graph },
    x: Number.isFinite(saved.x) ? saved.x : fallback.x,
    y: Number.isFinite(saved.y) ? saved.y : fallback.y,
    w: Number.isFinite(saved.w) ? saved.w : fallback.w,
    h: Number.isFinite(saved.h) ? saved.h : fallback.h,
    minimized: Boolean(saved.minimized),
  };
}

function storeDockGeometry(node, key, dock, minimized = false) {
  if (!node?.properties || !dock) return;
  node.properties.workflowx_uap_docks ||= {};
  if (dock.classList.contains("fullscreen")) return;
  const pinned = Boolean(dock.__workflowXPinned);
  const graph = dock.__workflowXGraph || { x: 0, y: (node.size?.[1] || 0) + 12, w: dock.offsetWidth, h: dock.offsetHeight };
  node.properties.workflowx_uap_docks[key] = {
    pinned,
    graph: {
      x: graph.x,
      y: graph.y,
      w: Math.max(320, dock.offsetWidth),
      h: Math.max(220, dock.offsetHeight),
    },
    x: Math.max(0, dock.offsetLeft),
    y: Math.max(0, dock.offsetTop),
    w: Math.max(320, dock.offsetWidth),
    h: Math.max(220, dock.offsetHeight),
    minimized,
  };
  markDirty();
}

function closeDock(node, key) {
  const dock = node?.__workflowXUapDocks?.[key];
  if (!dock) return;
  dock.__workflowXCleanup?.();
  dock.__workflowXOnClose?.();
  dock.remove();
  delete node.__workflowXUapDocks[key];
  if (node.__workflowXUapPinnedDock === dock) {
    node.__workflowXUapPinnedDock = null;
    pinnedDocks.delete(node);
  }
}

function dockIsOpen(node, key) {
  const dock = node?.__workflowXUapDocks?.[key];
  return Boolean(dock && document.body.contains(dock));
}

function bringDockForward(dock) {
  dock.style.zIndex = String(++nextDockZ);
}

function createDockWindow(node, key, title, options = {}) {
  node.__workflowXUapDocks ||= {};
  closeDock(node, key);

  const defaultWidth = options.matchNodeWidth === false
    ? options.width || 720
    : Math.max(360, Math.round(node.size?.[0] || options.width || 520));
  const defaultHeight = options.height || 470;
  const fallback = {
    graph: {
      x: 0,
      y: Math.round((node.size?.[1] || 0) + 12),
      w: defaultWidth,
      h: defaultHeight,
    },
    x: Math.max(20, Math.round((window.innerWidth - defaultWidth) / 2)),
    y: Math.max(20, Math.round((window.innerHeight - defaultHeight) / 2)),
    w: defaultWidth,
    h: defaultHeight,
  };
  const geom = savedDockGeometry(node, key, fallback);
  const dock = buildDom("div", "workflowx-uap-dock");
  const pinned = options.pinned !== false && geom.pinned !== false;
  dock.__workflowXPinned = pinned;
  dock.__workflowXGraph = { ...geom.graph };
  if (pinned) {
    dock.style.width = `${geom.graph.w}px`;
    dock.style.height = `${geom.graph.h}px`;
  } else {
    dock.style.left = `${geom.x}px`;
    dock.style.top = `${geom.y}px`;
    dock.style.width = `${geom.w}px`;
    dock.style.height = `${geom.h}px`;
  }
  bringDockForward(dock);

  const head = buildDom("div", "workflowx-uap-dock-head");
  const titleEl = buildDom("div", "workflowx-uap-dock-title", title);
  const minBtn = buildDom("button", "workflowx-uap-btn", "_");
  const fullBtn = buildDom("button", "workflowx-uap-btn", "[]");
  const pinBtn = buildDom("button", `workflowx-uap-btn${pinned ? " active" : ""}`, "pin");
  const closeBtn = buildDom("button", "workflowx-uap-btn", "x");
  for (const button of [minBtn, fullBtn, pinBtn, closeBtn]) button.type = "button";
  head.appendChild(titleEl);
  head.appendChild(minBtn);
  head.appendChild(fullBtn);
  head.appendChild(pinBtn);
  head.appendChild(closeBtn);
  dock.appendChild(head);
  const body = buildDom("div", "workflowx-uap-dock-body");
  dock.appendChild(body);
  document.body.appendChild(dock);
  stopGraphEvents(dock);
  if (pinned) {
    node.__workflowXUapPinnedDock = dock;
    pinnedDocks.add(node);
    installDockWakes();
    wakePinnedDocks();
  }

  if (geom.minimized) dock.classList.add("minimized");

  let dragging = null;
  const pointerMove = (event) => {
    if (!dragging) return;
    event.preventDefault();
    const dx = (event.clientX - dragging.x) / dragging.scale;
    const dy = (event.clientY - dragging.y) / dragging.scale;
    if (dock.__workflowXPinned) {
      dock.__workflowXGraph.x = dragging.graphX + dx;
      dock.__workflowXGraph.y = dragging.graphY + dy;
      node.__workflowXUapDockSig = "";
      applyPinnedDockTransform(node);
    } else {
      const x = Math.max(0, dragging.left + dx);
      const y = Math.max(0, dragging.top + dy);
      dock.style.left = `${Math.min(window.innerWidth - 80, x)}px`;
      dock.style.top = `${Math.min(window.innerHeight - 40, y)}px`;
    }
  };
  const pointerUp = () => {
    if (dragging) storeDockGeometry(node, key, dock, dock.classList.contains("minimized"));
    dragging = null;
    document.removeEventListener("pointermove", pointerMove, true);
    document.removeEventListener("pointerup", pointerUp, true);
  };
  head.addEventListener("pointerdown", (event) => {
    if (event.target !== head && event.target !== titleEl) return;
    if (dock.classList.contains("fullscreen")) return;
    bringDockForward(dock);
    dragging = {
      x: event.clientX,
      y: event.clientY,
      left: dock.offsetLeft,
      top: dock.offsetTop,
      graphX: dock.__workflowXGraph?.x || 0,
      graphY: dock.__workflowXGraph?.y || 0,
      scale: dock.__workflowXPinned ? app.canvas?.ds?.scale || 1 : 1,
    };
    document.addEventListener("pointermove", pointerMove, true);
    document.addEventListener("pointerup", pointerUp, true);
  });

  const dirs = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];
  for (const dir of dirs) {
    const handle = buildDom("div", `workflowx-uap-dock-rsz ${dir}`);
    dock.appendChild(handle);
    handle.addEventListener("pointerdown", (event) => {
      if (dock.classList.contains("fullscreen")) return;
      event.preventDefault();
      bringDockForward(dock);
      const start = {
        x: event.clientX,
        y: event.clientY,
        left: dock.offsetLeft,
        top: dock.offsetTop,
        graphX: dock.__workflowXGraph?.x || 0,
        graphY: dock.__workflowXGraph?.y || 0,
        width: dock.offsetWidth,
        height: dock.offsetHeight,
        scale: dock.__workflowXPinned ? app.canvas?.ds?.scale || 1 : 1,
      };
      const resizeMove = (moveEvent) => {
        let left = start.left;
        let top = start.top;
        let width = start.width;
        let height = start.height;
        const dx = (moveEvent.clientX - start.x) / start.scale;
        const dy = (moveEvent.clientY - start.y) / start.scale;
        let graphX = start.graphX;
        let graphY = start.graphY;
        if (dir.includes("e")) width = start.width + dx;
        if (dir.includes("s")) height = start.height + dy;
        if (dir.includes("w")) {
          width = start.width - dx;
          left = start.left + dx;
          graphX = start.graphX + dx;
        }
        if (dir.includes("n")) {
          height = start.height - dy;
          top = start.top + dy;
          graphY = start.graphY + dy;
        }
        width = Math.max(320, width);
        height = Math.max(220, height);
        dock.style.width = `${width}px`;
        dock.style.height = `${height}px`;
        if (dock.__workflowXPinned) {
          dock.__workflowXGraph.x = graphX;
          dock.__workflowXGraph.y = graphY;
          dock.__workflowXGraph.w = width;
          dock.__workflowXGraph.h = height;
          node.__workflowXUapDockSig = "";
          applyPinnedDockTransform(node);
        } else {
          dock.style.left = `${Math.max(0, left)}px`;
          dock.style.top = `${Math.max(0, top)}px`;
        }
      };
      const resizeUp = () => {
        storeDockGeometry(node, key, dock, dock.classList.contains("minimized"));
        document.removeEventListener("pointermove", resizeMove, true);
        document.removeEventListener("pointerup", resizeUp, true);
      };
      document.addEventListener("pointermove", resizeMove, true);
      document.addEventListener("pointerup", resizeUp, true);
    });
  }

  minBtn.addEventListener("click", () => {
    dock.classList.toggle("minimized");
    storeDockGeometry(node, key, dock, dock.classList.contains("minimized"));
  });
  fullBtn.addEventListener("click", () => {
    dock.classList.toggle("fullscreen");
    bringDockForward(dock);
    if (!dock.classList.contains("fullscreen")) storeDockGeometry(node, key, dock, dock.classList.contains("minimized"));
  });
  pinBtn.addEventListener("click", () => {
    dock.__workflowXPinned = !dock.__workflowXPinned;
    pinBtn.classList.toggle("active", dock.__workflowXPinned);
    if (dock.__workflowXPinned) {
      const rect = dock.getBoundingClientRect();
      const canvas = app.canvas;
      const ds = canvas?.ds;
      const canvasRect = canvas?.canvas?.getBoundingClientRect();
      if (ds && canvasRect) {
        dock.__workflowXGraph = {
          x: (rect.left - canvasRect.left) / (ds.scale || 1) - ds.offset[0] - node.pos[0],
          y: (rect.top - canvasRect.top) / (ds.scale || 1) - ds.offset[1] - node.pos[1],
          w: rect.width,
          h: rect.height,
        };
      }
      node.__workflowXUapPinnedDock = dock;
      pinnedDocks.add(node);
      installDockWakes();
      node.__workflowXUapDockSig = "";
      applyPinnedDockTransform(node);
    } else {
      pinnedDocks.delete(node);
      if (node.__workflowXUapPinnedDock === dock) node.__workflowXUapPinnedDock = null;
      const rect = dock.getBoundingClientRect();
      document.body.appendChild(dock);
      dock.style.position = "fixed";
      dock.style.transform = "";
      dock.style.transformOrigin = "";
      dock.style.left = `${rect.left}px`;
      dock.style.top = `${rect.top}px`;
    }
    storeDockGeometry(node, key, dock, dock.classList.contains("minimized"));
  });
  closeBtn.addEventListener("click", () => closeDock(node, key));
  dock.addEventListener("pointerdown", () => bringDockForward(dock));
  dock.__workflowXCleanup = () => {
    document.removeEventListener("pointermove", pointerMove, true);
    document.removeEventListener("pointerup", pointerUp, true);
  };
  node.__workflowXUapDocks[key] = dock;
  return { dock, body, close: () => closeDock(node, key) };
}

function parseJsonObject(text) {
  try {
    const parsed = JSON.parse(String(text || "{}"));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function clamp01(value) {
  return Math.max(0, Math.min(1, Number(value) || 0));
}

function setupUnifiedAutoprompter(node) {
  if (node.__workflowXUnifiedAutoprompterReady) return;
  node.__workflowXUnifiedAutoprompterReady = true;
  injectStyle();

  for (const name of [
    "target_model",
    "prompt_format",
    "negative_enabled",
    "generated_positive",
    "generated_negative",
    "final_prompt",
    "ui_state",
  ]) {
    hideWidget(node, name);
  }

  const state = defaultState(node);
  state.gemini_key = loadStoredGeminiKey();
  state.connected_image_b64 = "";
  state.connected_image_url = "";
  state.connected_image_available = false;
  state.ideogram_overlay_visible = state.ideogram_overlay_visible !== false;
  state.ideogram_overlay_brightness = Number(state.ideogram_overlay_brightness || 35);
  state.ideogram_width = Math.max(16, Number(state.ideogram_width || 1024));
  state.ideogram_height = Math.max(16, Number(state.ideogram_height || 1024));
  node.__workflowXUapOverlayImage = null;

  const wrap = buildDom("div", "workflowx-uap");
  stopGraphEvents(wrap);

  const topGrid = buildDom("div", "workflowx-uap-grid");
  const targetSelect = createSelect();
  const formatSelect = createSelect();
  field(topGrid, "Target model", targetSelect);
  field(topGrid, "Prompt format", formatSelect);
  wrap.appendChild(topGrid);

  const backendRow = buildDom("div", "workflowx-uap-row");
  const geminiBtn = buildDom("button", "workflowx-uap-btn", "Gemini");
  const ollamaBtn = buildDom("button", "workflowx-uap-btn", "Ollama");
  const localBtn = buildDom("button", "workflowx-uap-btn", "Local GGUF");
  for (const button of [geminiBtn, ollamaBtn, localBtn]) {
    button.type = "button";
    backendRow.appendChild(button);
  }
  wrap.appendChild(backendRow);

  const geminiPanel = buildDom("div", "workflowx-uap-panel");
  const geminiGrid = buildDom("div", "workflowx-uap-grid");
  const keyInput = createInput("password");
  keyInput.placeholder = "Gemini API key";
  keyInput.value = state.gemini_key || "";
  const timeoutInput = createInput("number");
  timeoutInput.min = "5";
  timeoutInput.max = "3600";
  timeoutInput.step = "1";
  timeoutInput.value = String(state.gemini_timeout || 120);
  field(geminiGrid, "Gemini key", keyInput);
  field(geminiGrid, "Timeout seconds", timeoutInput);
  geminiPanel.appendChild(geminiGrid);
  const geminiModelsRow = buildDom("div", "workflowx-uap-row");
  const fetchGeminiBtn = buildDom("button", "workflowx-uap-btn", "Fetch models");
  fetchGeminiBtn.type = "button";
  const geminiModelSelect = createSelect();
  geminiModelSelect.style.flex = "1";
  option(geminiModelSelect, state.gemini_model || "", state.gemini_model || "No model selected");
  geminiModelsRow.appendChild(fetchGeminiBtn);
  geminiModelsRow.appendChild(geminiModelSelect);
  geminiPanel.appendChild(geminiModelsRow);
  wrap.appendChild(geminiPanel);

  const ollamaPanel = buildDom("div", "workflowx-uap-panel");
  const ollamaGrid = buildDom("div", "workflowx-uap-grid");
  const hostInput = createInput("text");
  hostInput.value = state.ollama_host || DEFAULT_OLLAMA_HOST;
  const ollamaModelSelect = createSelect();
  option(ollamaModelSelect, state.ollama_model || "", state.ollama_model || "No model selected");
  field(ollamaGrid, "Ollama host", hostInput);
  field(ollamaGrid, "Ollama model", ollamaModelSelect);
  ollamaPanel.appendChild(ollamaGrid);
  const ollamaRow = buildDom("div", "workflowx-uap-row");
  const fetchOllamaBtn = buildDom("button", "workflowx-uap-btn", "Fetch models");
  fetchOllamaBtn.type = "button";
  const thinkToggle = buildDom("label", "workflowx-uap-toggle");
  const thinkInput = document.createElement("input");
  thinkInput.type = "checkbox";
  thinkInput.checked = state.ollama_think;
  thinkToggle.appendChild(thinkInput);
  thinkToggle.appendChild(document.createTextNode("think"));
  const unloadToggle = buildDom("label", "workflowx-uap-toggle");
  const unloadInput = document.createElement("input");
  unloadInput.type = "checkbox";
  unloadInput.checked = state.unload_after !== false;
  unloadToggle.appendChild(unloadInput);
  unloadToggle.appendChild(document.createTextNode("unload after"));
  ollamaRow.appendChild(fetchOllamaBtn);
  ollamaRow.appendChild(thinkToggle);
  ollamaRow.appendChild(unloadToggle);
  ollamaPanel.appendChild(ollamaRow);
  wrap.appendChild(ollamaPanel);

  const localPanel = buildDom("div", "workflowx-uap-panel");
  const localGrid = buildDom("div", "workflowx-uap-grid");
  const localModelSelect = createSelect();
  const mmprojSelect = createSelect();
  const systemPresetSelect = createSelect();
  const maxTokensInput = createInput("number");
  maxTokensInput.min = "32";
  maxTokensInput.value = String(state.max_tokens);
  const tempInput = createInput("number");
  tempInput.step = "0.05";
  tempInput.value = String(state.temperature);
  const ctxInput = createInput("number");
  ctxInput.min = "512";
  ctxInput.value = String(state.ctx_size);
  const memorySelect = createSelect();
  setSelectOptions(memorySelect, [
    { value: "auto", label: "Auto memory" },
    { value: "gpu_layers", label: "GPU layers" },
    { value: "cpu_moe_layers", label: "CPU MoE layers" },
    { value: "gpu_and_cpu_moe_layers", label: "GPU + CPU MoE" },
  ], state.memory_mode);
  option(localModelSelect, state.local_model || "", state.local_model || "Fetch local models");
  option(mmprojSelect, state.local_mmproj || "none", state.local_mmproj || "none");
  option(systemPresetSelect, state.local_system_prompt_preset || "none", state.local_system_prompt_preset || "none");
  field(localGrid, "GGUF model", localModelSelect);
  field(localGrid, "mmproj", mmprojSelect);
  field(localGrid, "System preset fallback", systemPresetSelect);
  field(localGrid, "Max tokens", maxTokensInput);
  field(localGrid, "Temperature", tempInput);
  field(localGrid, "Context", ctxInput);
  field(localGrid, "Memory mode", memorySelect);
  const reasoningSelect = createSelect();
  setSelectOptions(reasoningSelect, ["auto", "none", "deepseek", "qwen3"], state.reasoning);
  field(localGrid, "Reasoning", reasoningSelect);
  localPanel.appendChild(localGrid);
  const fetchLocalBtn = buildDom("button", "workflowx-uap-btn", "Refresh local GGUF list");
  fetchLocalBtn.type = "button";
  localPanel.appendChild(fetchLocalBtn);
  wrap.appendChild(localPanel);

  const inputGrid = buildDom("div", "workflowx-uap-grid");
  const ideaArea = createTextarea(2);
  const subjectArea = createTextarea(2);
  const styleInput = createInput("text");
  const lightingInput = createInput("text");
  const compositionInput = createInput("text");
  const textInput = createInput("text");
  const detailSelect = createSelect();
  setSelectOptions(detailSelect, ["concise", "balanced", "high", "very high"], state.detail);
  const imageNoteInput = createInput("text");
  field(inputGrid, "Idea", ideaArea);
  field(inputGrid, "Subject", subjectArea);
  field(inputGrid, "Style", styleInput);
  field(inputGrid, "Lighting", lightingInput);
  field(inputGrid, "Camera / composition", compositionInput);
  field(inputGrid, "Text / typography", textInput);
  field(inputGrid, "Detail level", detailSelect);
  field(inputGrid, "Reference image note", imageNoteInput);
  wrap.appendChild(inputGrid);

  const videoPanel = buildDom("div", "workflowx-uap-panel");
  const videoGrid = buildDom("div", "workflowx-uap-grid");
  const videoDurationInput = createInput("text");
  videoDurationInput.placeholder = "5s, 121 frames, 720p/24fps, etc.";
  const motionActionArea = createTextarea(2);
  motionActionArea.placeholder = "Primary movement, gesture, action, or scene change";
  const temporalBeatsArea = createTextarea(2);
  temporalBeatsArea.placeholder = "Beat 1..., then..., final moment...";
  const cameraMovementInput = createInput("text");
  cameraMovementInput.placeholder = "tracking shot, handheld push-in, locked wide shot";
  const audioDialogueArea = createTextarea(2);
  audioDialogueArea.placeholder = "dialogue, music, ambient sound, speech sync notes";
  const controlNotesArea = createTextarea(2);
  controlNotesArea.placeholder = "I2V/TI2V/S2V, pose, audio, reference image, or control notes";
  field(videoGrid, "Video duration / frames", videoDurationInput);
  field(videoGrid, "Camera movement", cameraMovementInput);
  field(videoGrid, "Motion / action", motionActionArea);
  field(videoGrid, "Temporal beats", temporalBeatsArea);
  field(videoGrid, "Audio / dialogue", audioDialogueArea);
  field(videoGrid, "Reference / control notes", controlNotesArea);
  videoPanel.appendChild(videoGrid);
  wrap.appendChild(videoPanel);

  const ideogramPanel = buildDom("div", "workflowx-uap-panel");
  const ideogramLayoutArea = createTextarea(3);
  ideogramLayoutArea.placeholder = '{"background":"...","elements":[{"type":"obj","bbox":[200,250,800,750],"desc":"..."}]}';
  const ideogramPaletteInput = createInput("text");
  ideogramPaletteInput.placeholder = "#FFFFFF, #111111, #E43F5A";
  field(ideogramPanel, "Ideogram bbox/layout JSON hints", ideogramLayoutArea);
  field(ideogramPanel, "Ideogram palette hints", ideogramPaletteInput);
  ideogramPanel.classList.add("workflowx-uap-hidden");
  wrap.appendChild(ideogramPanel);

  const extraArea = createTextarea(2);
  field(wrap, "Extra instructions", extraArea);

  const imageRow = buildDom("div", "workflowx-uap-row");
  const negativeToggle = buildDom("label", "workflowx-uap-toggle");
  const negativeInput = document.createElement("input");
  negativeInput.type = "checkbox";
  negativeInput.checked = Boolean(state.negative_enabled);
  negativeToggle.appendChild(negativeInput);
  negativeToggle.appendChild(document.createTextNode("generate negative"));
  imageRow.appendChild(negativeToggle);
  wrap.appendChild(imageRow);

  const toolsRow = buildDom("div", "workflowx-uap-row");
  const positivePreviewBtn = buildDom("button", "workflowx-uap-btn", "Show positive");
  positivePreviewBtn.type = "button";
  const negativePreviewBtn = buildDom("button", "workflowx-uap-btn", "Show negative");
  negativePreviewBtn.type = "button";
  const ideogramBtn = buildDom("button", "workflowx-uap-btn", "Ideogram layout");
  ideogramBtn.type = "button";
  const modelSettingsBtn = buildDom("button", "workflowx-uap-btn", "Model settings");
  modelSettingsBtn.type = "button";
  toolsRow.appendChild(positivePreviewBtn);
  toolsRow.appendChild(negativePreviewBtn);
  toolsRow.appendChild(ideogramBtn);
  toolsRow.appendChild(modelSettingsBtn);
  wrap.appendChild(toolsRow);

  const generateRow = buildDom("div", "workflowx-uap-row");
  const generateBtn = buildDom("button", "workflowx-uap-btn primary", "Generate");
  generateBtn.type = "button";
  const status = buildDom("div", "workflowx-uap-status", "Ready.");
  generateRow.appendChild(generateBtn);
  generateRow.appendChild(status);
  wrap.appendChild(generateRow);

  const preview = buildDom("div", "workflowx-uap-preview");
  preview.classList.add("workflowx-uap-hidden");
  wrap.appendChild(preview);

  ideaArea.value = state.idea;
  subjectArea.value = state.subject;
  styleInput.value = state.style;
  lightingInput.value = state.lighting;
  compositionInput.value = state.composition;
  textInput.value = state.text;
  imageNoteInput.value = state.image_note;
  videoDurationInput.value = state.video_duration_or_frames;
  motionActionArea.value = state.motion_action;
  temporalBeatsArea.value = state.temporal_beats;
  cameraMovementInput.value = state.camera_movement;
  audioDialogueArea.value = state.audio_dialogue;
  controlNotesArea.value = state.reference_or_control_notes;
  ideogramLayoutArea.value = state.ideogram_layout;
  ideogramPaletteInput.value = state.ideogram_palette;
  extraArea.value = state.extra_instructions;

  let profiles = FALLBACK_PROFILES.map(ensureProfileShape);
  let profilesByKey = profileMap(profiles);

  function activeProfile() {
    return profilesByKey.get(state.target_model) || profiles[0];
  }

  function setStatus(message, isError = false) {
    status.textContent = message || "";
    status.classList.toggle("error", Boolean(isError));
  }

  function refreshBackends() {
    geminiBtn.classList.toggle("active", state.backend === "gemini");
    ollamaBtn.classList.toggle("active", state.backend === "ollama");
    localBtn.classList.toggle("active", state.backend === "local");
    geminiPanel.classList.toggle("workflowx-uap-hidden", state.backend !== "gemini");
    ollamaPanel.classList.toggle("workflowx-uap-hidden", state.backend !== "ollama");
    localPanel.classList.toggle("workflowx-uap-hidden", state.backend !== "local");
    requestAnimationFrame(resizeNodeToVisibleContent);
  }

  function refreshProfiles() {
    setSelectOptions(targetSelect, profiles.map((profile) => ({
      value: profile.key,
      label: profile.label || profile.key,
    })), state.target_model);
    state.target_model = targetSelect.value;
    refreshFormats();
  }

  function refreshFormats() {
    const profile = activeProfile();
    const formats = enabledProfileFormats(profile);
    if (!formats.includes(state.prompt_format)) state.prompt_format = profile.default_format || formats[0];
    setSelectOptions(formatSelect, formats, state.prompt_format, (value) => value);
    state.prompt_format = formatSelect.value;
    ideogramPanel.classList.add("workflowx-uap-hidden");
    ideogramBtn.classList.toggle("workflowx-uap-hidden", state.target_model !== "ideogram4");
    if (state.target_model !== "ideogram4") closeDock(node, "ideogram");
    videoPanel.classList.toggle("workflowx-uap-hidden", !profileIsVideo(profile));
    state.negative_enabled = Boolean(state.negative_enabled);
    negativeInput.checked = state.negative_enabled;
    syncPreview();
    requestAnimationFrame(resizeNodeToVisibleContent);
  }

  function readFieldsIntoState() {
    state.idea = ideaArea.value;
    state.subject = subjectArea.value;
    state.style = styleInput.value;
    state.lighting = lightingInput.value;
    state.composition = compositionInput.value;
    state.text = textInput.value;
    state.detail = detailSelect.value;
    state.image_note = imageNoteInput.value;
    state.ideogram_layout = ideogramLayoutArea.value;
    state.ideogram_palette = ideogramPaletteInput.value;
    state.video_duration_or_frames = videoDurationInput.value;
    state.motion_action = motionActionArea.value;
    state.temporal_beats = temporalBeatsArea.value;
    state.camera_movement = cameraMovementInput.value;
    state.audio_dialogue = audioDialogueArea.value;
    state.reference_or_control_notes = controlNotesArea.value;
    state.extra_instructions = extraArea.value;
    state.gemini_timeout = Number(timeoutInput.value || 120);
    state.ollama_host = hostInput.value || DEFAULT_OLLAMA_HOST;
    state.ollama_think = thinkInput.checked;
    state.unload_after = unloadInput.checked;
    state.max_tokens = Number(maxTokensInput.value || 768);
    state.temperature = Number(tempInput.value || 0.7);
    state.ctx_size = Number(ctxInput.value || 8192);
    state.memory_mode = memorySelect.value;
    state.reasoning = reasoningSelect.value;
    state.local_model = localModelSelect.value || "";
    state.local_mmproj = mmprojSelect.value || "none";
    state.local_system_prompt_preset = systemPresetSelect.value || "none";
  }

  function syncPreview() {
    readFieldsIntoState();
    const prompt = syncOutputWidgets(node, state, activeProfile());
    preview.textContent = prompt || "(Generate or type prompt output to preview here.)";
    updateOutputDocks();
  }

  function persistModelSelection() {
    storeModelSelection({
      backend: state.backend,
      gemini_model: state.gemini_model,
      ollama_model: state.ollama_model,
      local_model: state.local_model,
    });
  }

  function cachedOutput() {
    return state.last_generation || {
      prompt: widgetValue(node, "final_prompt", ""),
      positive: widgetValue(node, "generated_positive", ""),
      negative: widgetValue(node, "generated_negative", ""),
    };
  }

  function setPreviewButtonLabels() {
    positivePreviewBtn.textContent = dockIsOpen(node, "output_positive") ? "Hide positive" : "Show positive";
    negativePreviewBtn.textContent = dockIsOpen(node, "output_negative") ? "Hide negative" : "Show negative";
  }

  function updateOutputDocks() {
    const refs = node.__workflowXUapOutputRefs;
    if (!refs) return;
    const cached = cachedOutput();
    if (refs.positive?.view && document.body.contains(refs.positive.view)) {
      refs.positive.view.value = cached.positive || "";
      refs.positive.prompt = cached.prompt || "";
    } else if (refs.positive) {
      delete refs.positive;
    }
    if (refs.negative?.view && document.body.contains(refs.negative.view)) {
      refs.negative.view.value = cached.negative || "";
      refs.negative.prompt = cached.prompt || "";
    } else if (refs.negative) {
      delete refs.negative;
    }
    setPreviewButtonLabels();
  }

  function setBusy(isBusy) {
    generateBtn.disabled = isBusy;
    generateBtn.textContent = isBusy ? "Generating..." : "Generate";
  }

  function fitNode() {
    if (!node.__workflowXUapWidget) return;
    const rectHeight = Math.ceil(wrap.scrollHeight || wrap.getBoundingClientRect().height || NODE_MIN_WIDGET_HEIGHT);
    node.__workflowXUapWidgetHeight = Math.max(NODE_MIN_WIDGET_HEIGHT, rectHeight + 12);
    markDirty();
  }

  function resizeNodeToVisibleContent() {
    if (!node.__workflowXUapWidget || node.__workflowXUapFitting) return;
    node.__workflowXUapFitting = true;
    try {
      fitNode();
      const width = Math.max(node.size?.[0] || 0, 440);
      const computed = node.computeSize?.();
      const targetHeight = Math.max(NODE_MIN_WIDGET_HEIGHT + 80, Math.ceil(computed?.[1] || node.__workflowXUapWidgetHeight + 80));
      if (Math.abs((node.size?.[1] || 0) - targetHeight) > 8 || (node.size?.[0] || 0) < width) {
        node.setSize?.([width, targetHeight]);
      }
    } finally {
      node.__workflowXUapFitting = false;
    }
  }

  function toggleOutputPreview(kind) {
    const key = kind === "negative" ? "output_negative" : "output_positive";
    if (dockIsOpen(node, key)) {
      closeDock(node, key);
      setPreviewButtonLabels();
      return;
    }
    syncPreview();
    const cached = cachedOutput();
    const label = kind === "negative" ? "Negative" : "Positive";
    const dock = createDockWindow(node, key, `${label} Preview`, {
      width: 520,
      height: 440,
      pinned: false,
      matchNodeWidth: false,
    });
    const view = document.createElement("textarea");
    view.className = "workflowx-uap-dock-text";
    view.value = kind === "negative" ? cached.negative || "" : cached.positive || "";
    view.readOnly = true;
    field(dock.body, label, view);
    node.__workflowXUapOutputRefs ||= {};
    node.__workflowXUapOutputRefs[kind] = {
      view,
      prompt: cached.prompt || "",
    };
    dock.dock.__workflowXOnClose = () => {
      if (node.__workflowXUapOutputRefs) delete node.__workflowXUapOutputRefs[kind];
      setPreviewButtonLabels();
    };

    const copyRow = buildDom("div", "workflowx-uap-row");
    const copyValue = buildDom("button", "workflowx-uap-btn primary", `Copy ${kind}`);
    const copyPrompt = buildDom("button", "workflowx-uap-btn", "Copy final prompt");
    for (const button of [copyValue, copyPrompt]) button.type = "button";
    copyValue.addEventListener("click", () => navigator.clipboard?.writeText?.(view.value || ""));
    copyPrompt.addEventListener("click", () => navigator.clipboard?.writeText?.(node.__workflowXUapOutputRefs?.[kind]?.prompt || ""));
    copyRow.appendChild(copyValue);
    copyRow.appendChild(copyPrompt);
    dock.body.appendChild(copyRow);
    setPreviewButtonLabels();
  }

  async function openModelSettingsModal() {
    let config;
    try {
      config = await fetchJsonChecked(`${ROUTE}/profile_config`, {}, "Model settings");
    } catch (error) {
      setStatus(`Model settings error: ${error.message}`, true);
      return;
    }

    let draft = JSON.parse(JSON.stringify(config.profiles || []));
    const defaultsByKey = new Map((config.default_profiles || []).map((profile) => [profile.key, profile]));
    const builtinKeys = new Set(config.builtin_keys || []);
    const formats = config.formats || ["natural", "tags", "json"];
    const mediaTypes = config.media_types || ["image", "video"];
    let selectedKey = draft.some((profile) => profile.key === state.target_model) ? state.target_model : draft[0]?.key || "";

    const backdrop = buildDom("div", "workflowx-uap-modal-backdrop");
    const modal = buildDom("div", "workflowx-uap-modal");
    const head = buildDom("div", "workflowx-uap-modal-head");
    const title = buildDom("div", "workflowx-uap-modal-title", "Unified Autoprompter Model Settings");
    const closeBtn = buildDom("button", "workflowx-uap-btn", "x");
    closeBtn.type = "button";
    head.appendChild(title);
    head.appendChild(closeBtn);
    modal.appendChild(head);

    const body = buildDom("div", "workflowx-uap-settings-body");
    const listPane = buildDom("div", "workflowx-uap-settings-list");
    const searchInput = createInput("text");
    searchInput.placeholder = "Search models";
    const listActions = buildDom("div", "workflowx-uap-row");
    const addBtn = buildDom("button", "workflowx-uap-btn", "Add");
    const duplicateBtn = buildDom("button", "workflowx-uap-btn", "Duplicate");
    const deleteBtn = buildDom("button", "workflowx-uap-btn", "Delete");
    const resetOneBtn = buildDom("button", "workflowx-uap-btn", "Reset profile");
    for (const button of [addBtn, duplicateBtn, deleteBtn, resetOneBtn]) button.type = "button";
    listActions.appendChild(addBtn);
    listActions.appendChild(duplicateBtn);
    listActions.appendChild(deleteBtn);
    listActions.appendChild(resetOneBtn);
    const items = buildDom("div", "workflowx-uap-settings-items");
    listPane.appendChild(searchInput);
    listPane.appendChild(listActions);
    listPane.appendChild(items);

    const formPane = buildDom("div", "workflowx-uap-settings-form");
    const formGrid = buildDom("div", "workflowx-uap-grid");
    const keyInput = createInput("text");
    const labelInput = createInput("text");
    const mediaSelect = createSelect();
    const defaultFormatSelect = createSelect();
    field(formGrid, "Model key", keyInput);
    field(formGrid, "Display label", labelInput);
    field(formGrid, "Media type", mediaSelect);
    field(formGrid, "Default format", defaultFormatSelect);
    formPane.appendChild(formGrid);

    const formatRow = buildDom("div", "workflowx-uap-row");
    formatRow.appendChild(buildDom("span", "workflowx-uap-label", "Supported formats"));
    const formatInputs = new Map();
    for (const format of formats) {
      const label = buildDom("label", "workflowx-uap-toggle");
      const input = document.createElement("input");
      input.type = "checkbox";
      label.appendChild(input);
      label.appendChild(document.createTextNode(format));
      formatRow.appendChild(label);
      formatInputs.set(format, input);
    }
    formPane.appendChild(formatRow);

    const optionRow = buildDom("div", "workflowx-uap-row");
    const negativeLabel = buildDom("label", "workflowx-uap-toggle");
    const negativeSupportedInput = document.createElement("input");
    negativeSupportedInput.type = "checkbox";
    negativeLabel.appendChild(negativeSupportedInput);
    negativeLabel.appendChild(document.createTextNode("supports negative"));
    const jsonLabel = buildDom("label", "workflowx-uap-toggle");
    const jsonSupportedInput = document.createElement("input");
    jsonSupportedInput.type = "checkbox";
    jsonLabel.appendChild(jsonSupportedInput);
    jsonLabel.appendChild(document.createTextNode("JSON supported"));
    optionRow.appendChild(negativeLabel);
    optionRow.appendChild(jsonLabel);
    formPane.appendChild(optionRow);

    const notesArea = createTextarea(3);
    field(formPane, "Model notes", notesArea);
    const templateArea = createTextarea(10);
    field(formPane, "System prompt template", templateArea);
    const previewControls = buildDom("div", "workflowx-uap-row");
    const previewFormatSelect = createSelect();
    const previewNegativeLabel = buildDom("label", "workflowx-uap-toggle");
    const previewNegativeInput = document.createElement("input");
    previewNegativeInput.type = "checkbox";
    previewNegativeLabel.appendChild(previewNegativeInput);
    previewNegativeLabel.appendChild(document.createTextNode("negative preview"));
    previewControls.appendChild(buildDom("span", "workflowx-uap-label", "Preview"));
    previewControls.appendChild(previewFormatSelect);
    previewControls.appendChild(previewNegativeLabel);
    formPane.appendChild(previewControls);
    const preview = buildDom("pre", "workflowx-uap-settings-preview");
    formPane.appendChild(preview);
    body.appendChild(listPane);
    body.appendChild(formPane);
    modal.appendChild(body);

    const foot = buildDom("div", "workflowx-uap-modal-foot");
    const message = buildDom("div", "workflowx-uap-modal-message", `Config file: ${config.path || ""}`);
    const revertBtn = buildDom("button", "workflowx-uap-btn", "Revert");
    const resetAllBtn = buildDom("button", "workflowx-uap-btn", "Reset all defaults");
    const saveBtn = buildDom("button", "workflowx-uap-btn primary", "Save");
    for (const button of [revertBtn, resetAllBtn, saveBtn, closeBtn]) button.type = "button";
    foot.appendChild(message);
    foot.appendChild(revertBtn);
    foot.appendChild(resetAllBtn);
    foot.appendChild(saveBtn);
    modal.appendChild(foot);
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);

    const selectedProfile = () => draft.find((profile) => profile.key === selectedKey) || draft[0] || null;
    const showMessage = (text, isError = false) => {
      message.textContent = text || "";
      message.classList.toggle("error", Boolean(isError));
    };
    const safeKey = (value) => String(value || "").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    const uniqueKey = (base) => {
      const clean = safeKey(base) || "custom_model";
      const keys = new Set(draft.map((profile) => profile.key));
      if (!keys.has(clean)) return clean;
      let index = 2;
      while (keys.has(`${clean}_${index}`)) index += 1;
      return `${clean}_${index}`;
    };

    function readForm() {
      const profile = selectedProfile();
      if (!profile) return;
      profile.key = safeKey(keyInput.value);
      profile.label = labelInput.value.trim();
      profile.media_type = mediaSelect.value || "image";
      profile.formats = formats.filter((format) => formatInputs.get(format)?.checked);
      profile.default_format = defaultFormatSelect.value || profile.formats[0] || "natural";
      if (profile.formats.length && !profile.formats.includes(profile.default_format)) {
        profile.default_format = profile.formats[0];
      }
      profile.negative_supported = negativeSupportedInput.checked;
      profile.json_supported = jsonSupportedInput.checked;
      profile.notes = notesArea.value;
      profile.system_prompt_template = templateArea.value;
      selectedKey = profile.key;
    }

    function validateDraft() {
      const seen = new Set();
      for (const profile of draft) {
        if (!/^[a-z0-9][a-z0-9_]*$/.test(profile.key || "")) throw new Error("Every model key must use lowercase letters, numbers, and underscores.");
        if (seen.has(profile.key)) throw new Error(`Duplicate model key: ${profile.key}`);
        seen.add(profile.key);
        if (!profile.label?.trim()) throw new Error(`Profile ${profile.key} needs a display label.`);
        if (!profile.formats?.length) throw new Error(`Profile ${profile.key} needs at least one format.`);
        if (!profile.formats.includes(profile.default_format)) throw new Error(`Profile ${profile.key} default format must be selected.`);
        if (!profile.system_prompt_template?.trim()) throw new Error(`Profile ${profile.key} needs a system prompt template.`);
      }
    }

    function renderPreview() {
      const profile = selectedProfile();
      if (!profile) {
        preview.textContent = "";
        return;
      }
      const previewProfile = {
        ...profile,
        system_prompt_template: templateArea.value,
        notes: notesArea.value,
      };
      preview.textContent = renderTemplatePreview(previewProfile, previewFormatSelect.value || profile.default_format, previewNegativeInput.checked);
    }

    function renderList() {
      const filter = searchInput.value.trim().toLowerCase();
      items.replaceChildren();
      for (const profile of draft) {
        if (filter && !`${profile.label} ${profile.key} ${profile.notes || ""}`.toLowerCase().includes(filter)) continue;
        const item = buildDom("button", `workflowx-uap-settings-item${profile.key === selectedKey ? " active" : ""}`);
        item.type = "button";
        item.appendChild(buildDom("div", "", profile.label || profile.key));
        item.appendChild(buildDom("div", "workflowx-uap-settings-key", `${profile.key}${builtinKeys.has(profile.key) ? " - built-in" : " - custom"}`));
        item.addEventListener("click", () => {
          readForm();
          selectedKey = profile.key;
          renderAll();
        });
        items.appendChild(item);
      }
    }

    function renderForm() {
      const profile = selectedProfile();
      formPane.classList.toggle("workflowx-uap-hidden", !profile);
      if (!profile) return;
      keyInput.value = profile.key || "";
      keyInput.disabled = builtinKeys.has(profile.key);
      labelInput.value = profile.label || "";
      setSelectOptions(mediaSelect, mediaTypes, profile.media_type || "image");
      for (const format of formats) formatInputs.get(format).checked = (profile.formats || []).includes(format);
      setSelectOptions(defaultFormatSelect, profile.formats?.length ? profile.formats : formats, profile.default_format || profile.formats?.[0] || "natural");
      setSelectOptions(previewFormatSelect, profile.formats?.length ? profile.formats : formats, previewFormatSelect.value || profile.default_format || "natural");
      negativeSupportedInput.checked = Boolean(profile.negative_supported);
      jsonSupportedInput.checked = Boolean(profile.json_supported);
      notesArea.value = profile.notes || "";
      templateArea.value = profile.system_prompt_template || "";
      deleteBtn.disabled = builtinKeys.has(profile.key);
      resetOneBtn.disabled = !builtinKeys.has(profile.key);
      renderPreview();
    }

    function renderAll() {
      renderList();
      renderForm();
    }

    function onFormInput() {
      readForm();
      renderList();
      const profile = selectedProfile();
      setSelectOptions(defaultFormatSelect, profile?.formats?.length ? profile.formats : formats, profile?.default_format || "natural");
      setSelectOptions(previewFormatSelect, profile?.formats?.length ? profile.formats : formats, previewFormatSelect.value || profile?.default_format || "natural");
      renderPreview();
    }

    for (const input of [keyInput, labelInput, mediaSelect, defaultFormatSelect, negativeSupportedInput, jsonSupportedInput, notesArea, templateArea]) {
      input.addEventListener("input", onFormInput);
      input.addEventListener("change", onFormInput);
    }
    for (const input of formatInputs.values()) input.addEventListener("change", onFormInput);
    previewFormatSelect.addEventListener("change", renderPreview);
    previewNegativeInput.addEventListener("change", renderPreview);
    searchInput.addEventListener("input", renderList);

    addBtn.addEventListener("click", () => {
      readForm();
      const base = defaultsByKey.get("ideogram4") || draft[0] || {};
      const key = uniqueKey("custom_model");
      draft.push({
        ...JSON.parse(JSON.stringify(base)),
        key,
        label: "Custom Model",
      });
      selectedKey = key;
      renderAll();
    });
    duplicateBtn.addEventListener("click", () => {
      readForm();
      const profile = selectedProfile();
      if (!profile) return;
      const key = uniqueKey(`${profile.key}_copy`);
      draft.push({
        ...JSON.parse(JSON.stringify(profile)),
        key,
        label: `${profile.label || profile.key} Copy`,
      });
      selectedKey = key;
      renderAll();
    });
    deleteBtn.addEventListener("click", () => {
      const profile = selectedProfile();
      if (!profile || builtinKeys.has(profile.key)) return;
      draft = draft.filter((item) => item !== profile);
      selectedKey = draft[0]?.key || "";
      renderAll();
    });
    resetOneBtn.addEventListener("click", () => {
      const profile = selectedProfile();
      if (!profile || !builtinKeys.has(profile.key)) return;
      const restored = defaultsByKey.get(profile.key);
      if (!restored) return;
      const index = draft.findIndex((item) => item.key === profile.key);
      draft[index] = JSON.parse(JSON.stringify(restored));
      renderAll();
    });
    closeBtn.addEventListener("click", () => backdrop.remove());
    backdrop.addEventListener("mousedown", (event) => {
      if (event.target === backdrop) backdrop.remove();
    });
    revertBtn.addEventListener("click", () => {
      backdrop.remove();
      openModelSettingsModal();
    });
    resetAllBtn.addEventListener("click", async () => {
      if (!window.confirm("Reset all model profiles to WorkflowX defaults?")) return;
      try {
        const data = await fetchJsonChecked(`${ROUTE}/profile_config/reset`, { method: "POST" }, "Reset model settings");
        config = data;
        draft = JSON.parse(JSON.stringify(data.profiles || []));
        selectedKey = draft.some((profile) => profile.key === state.target_model) ? state.target_model : draft[0]?.key || "";
        clearProfileCache();
        profiles = await loadProfiles();
        profilesByKey = profileMap(profiles);
        refreshProfiles();
        showMessage("Profiles reset to defaults.");
        renderAll();
      } catch (error) {
        showMessage(error.message, true);
      }
    });
    saveBtn.addEventListener("click", async () => {
      try {
        readForm();
        validateDraft();
        const data = await fetchJsonChecked(`${ROUTE}/profile_config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ version: 1, profiles: draft }),
        }, "Save model settings");
        clearProfileCache();
        profiles = await loadProfiles();
        profilesByKey = profileMap(profiles);
        if (profilesByKey.has(selectedKey)) state.target_model = selectedKey;
        refreshProfiles();
        showMessage("Profiles saved.");
        setStatus("Model settings saved.");
      } catch (error) {
        showMessage(error.message, true);
      }
    });

    renderAll();
  }

  async function openModelSettingsModalV3() {
    let config;
    try {
      config = await fetchJsonChecked(`${ROUTE}/profile_config`, {}, "Model settings");
    } catch (error) {
      setStatus(`Model settings error: ${error.message}`, true);
      return;
    }

    let draft = JSON.parse(JSON.stringify(config.profiles || [])).map(ensureProfileShape);
    const defaultsByKey = new Map((config.default_profiles || []).map((profile) => {
      const shaped = ensureProfileShape(profile);
      return [shaped.key, shaped];
    }));
    const builtinKeys = new Set(config.builtin_keys || []);
    const formats = config.formats || ALL_PROMPT_FORMATS;
    const mediaTypes = config.media_types || ["image", "video"];
    let selectedKey = draft.some((profile) => profile.key === state.target_model) ? state.target_model : draft[0]?.key || "";
    let activeTab = "model";
    let activeFormat = state.prompt_format || "natural";
    let activeImageMode = state.connected_image_available ? "with_image" : "without_image";

    const backdrop = buildDom("div", "workflowx-uap-modal-backdrop");
    const modal = buildDom("div", "workflowx-uap-modal");
    const head = buildDom("div", "workflowx-uap-modal-head");
    const title = buildDom("div", "workflowx-uap-modal-title", "Unified Autoprompter Model Settings");
    const closeBtn = buildDom("button", "workflowx-uap-btn", "x");
    closeBtn.type = "button";
    head.appendChild(title);
    head.appendChild(closeBtn);
    modal.appendChild(head);

    const body = buildDom("div", "workflowx-uap-settings-body");
    const listPane = buildDom("div", "workflowx-uap-settings-list");
    const searchInput = createInput("text");
    searchInput.placeholder = "Search models";
    const listActions = buildDom("div", "workflowx-uap-row");
    const addBtn = buildDom("button", "workflowx-uap-btn", "Add");
    const duplicateBtn = buildDom("button", "workflowx-uap-btn", "Duplicate");
    const deleteBtn = buildDom("button", "workflowx-uap-btn", "Delete");
    const resetOneBtn = buildDom("button", "workflowx-uap-btn", "Reset profile");
    for (const button of [addBtn, duplicateBtn, deleteBtn, resetOneBtn]) button.type = "button";
    listActions.appendChild(addBtn);
    listActions.appendChild(duplicateBtn);
    listActions.appendChild(deleteBtn);
    listActions.appendChild(resetOneBtn);
    const items = buildDom("div", "workflowx-uap-settings-items");
    listPane.appendChild(searchInput);
    listPane.appendChild(listActions);
    listPane.appendChild(items);

    const formPane = buildDom("div", "workflowx-uap-settings-form");
    const tabs = buildDom("div", "workflowx-uap-settings-tabs");
    const tabButtons = new Map();
    for (const [key, label] of [["model", "Model"], ["formats", "Formats"], ["prompt", "Prompt"], ["contract", "Output Contract"], ["preview", "Preview"]]) {
      const button = buildDom("button", "workflowx-uap-settings-tab", label);
      button.type = "button";
      button.addEventListener("click", () => {
        readCurrentView();
        activeTab = key;
        renderAll();
      });
      tabs.appendChild(button);
      tabButtons.set(key, button);
    }
    const editor = buildDom("div", "workflowx-uap-settings-card");
    formPane.appendChild(tabs);
    formPane.appendChild(editor);
    body.appendChild(listPane);
    body.appendChild(formPane);
    modal.appendChild(body);

    const foot = buildDom("div", "workflowx-uap-modal-foot");
    const message = buildDom("div", "workflowx-uap-modal-message", `Config file: ${config.path || ""}`);
    const exportBtn = buildDom("button", "workflowx-uap-btn", "Export JSON");
    const importBtn = buildDom("button", "workflowx-uap-btn", "Import JSON");
    const revertBtn = buildDom("button", "workflowx-uap-btn", "Revert");
    const resetAllBtn = buildDom("button", "workflowx-uap-btn", "Reset all defaults");
    const saveBtn = buildDom("button", "workflowx-uap-btn primary", "Save");
    const importInput = document.createElement("input");
    importInput.type = "file";
    importInput.accept = "application/json,.json";
    importInput.className = "workflowx-uap-hidden";
    for (const button of [exportBtn, importBtn, revertBtn, resetAllBtn, saveBtn]) button.type = "button";
    foot.appendChild(message);
    foot.appendChild(exportBtn);
    foot.appendChild(importBtn);
    foot.appendChild(revertBtn);
    foot.appendChild(resetAllBtn);
    foot.appendChild(saveBtn);
    foot.appendChild(importInput);
    modal.appendChild(foot);
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);

    const selectedProfile = () => draft.find((profile) => profile.key === selectedKey) || draft[0] || null;
    const showMessage = (text, isError = false) => {
      message.textContent = text || "";
      message.classList.toggle("error", Boolean(isError));
    };
    const safeKey = (value) => String(value || "").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    const uniqueKey = (base) => {
      const clean = safeKey(base) || "custom_model";
      const keys = new Set(draft.map((profile) => profile.key));
      if (!keys.has(clean)) return clean;
      let index = 2;
      while (keys.has(`${clean}_${index}`)) index += 1;
      return `${clean}_${index}`;
    };
    const profileRule = (profile, format = activeFormat) => {
      profile.formats ||= {};
      profile.formats[format] = ensureRule(profile.formats[format]);
      return profile.formats[format];
    };
    const enabledFormatsFor = (profile) => enabledProfileFormats(profile);
    const cleanProfile = (profile) => {
      const shaped = ensureProfileShape(profile);
      return {
        key: shaped.key || "",
        label: shaped.label || shaped.key || "",
        media_type: shaped.media_type || "image",
        default_format: shaped.default_format || "natural",
        negative_supported: Boolean(shaped.negative_supported),
        json_supported: Boolean(shaped.json_supported),
        notes: shaped.notes || "",
        formats: Object.fromEntries(formats.map((format) => [format, ensureRule(shaped.formats?.[format])])),
      };
    };
    const cleanProfiles = (profileList) => (profileList || []).map(cleanProfile);
    const exportedFilename = () => {
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      return `workflowx-unified-autoprompter-model-settings-${stamp}.json`;
    };
    const exportPayload = () => ({
      export_format: "workflowx_unified_autoprompter_model_settings",
      export_version: 1,
      exported_at: new Date().toISOString(),
      version: config.version || 3,
      source: {
        config_path: config.path || "",
        default_path: config.default_path || "",
      },
      profiles: cleanProfiles(draft),
      default_profiles: cleanProfiles(config.default_profiles || []),
      builtin_keys: [...builtinKeys].sort(),
      formats: [...formats],
      media_types: [...mediaTypes],
    });
    const saveJsonFile = async (payload) => {
      const text = `${JSON.stringify(payload, null, 2)}\n`;
      const filename = exportedFilename();
      if (window.showSaveFilePicker) {
        const handle = await window.showSaveFilePicker({
          suggestedName: filename,
          types: [
            {
              description: "JSON file",
              accept: { "application/json": [".json"] },
            },
          ],
        });
        const writable = await handle.createWritable();
        await writable.write(text);
        await writable.close();
        return "Model settings exported.";
      }

      const blob = new Blob([text], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return "Model settings export downloaded.";
    };
    const importedProfilesFromPayload = (payload) => {
      const profilesList = Array.isArray(payload?.profiles) ? payload.profiles : null;
      if (!profilesList) throw new Error("Import JSON must contain a profiles array.");
      return profilesList.map((profile) => cleanProfile(profile));
    };
    const normalizeActiveFormat = (profile) => {
      const enabled = enabledFormatsFor(profile);
      if (!enabled.includes(profile.default_format)) profile.default_format = enabled[0] || "natural";
      if (!formats.includes(activeFormat)) activeFormat = profile.default_format || "natural";
      if (!profile.formats?.[activeFormat]) activeFormat = profile.default_format || enabled[0] || "natural";
    };

    function bindInput(input, bind) {
      input.dataset.bind = bind;
      input.addEventListener("input", onFormInput);
      input.addEventListener("change", onFormInput);
      return input;
    }

    function readCurrentView() {
      const profile = selectedProfile();
      if (!profile) return;
      for (const input of editor.querySelectorAll("[data-bind]")) {
        const bind = input.dataset.bind;
        if (bind === "key") {
          profile.key = safeKey(input.value);
          selectedKey = profile.key;
        } else if (bind === "label") profile.label = input.value.trim();
        else if (bind === "media_type") profile.media_type = input.value || "image";
        else if (bind === "default_format") profile.default_format = input.value || profile.default_format;
        else if (bind === "negative_supported") profile.negative_supported = input.checked;
        else if (bind === "json_supported") profile.json_supported = input.checked;
        else if (bind === "notes") profile.notes = input.value;
        else if (bind.startsWith("format_enabled:")) profileRule(profile, bind.split(":")[1]).enabled = input.checked;
        else if (bind === "common_instructions") profileRule(profile).common_instructions = input.value;
        else if (bind === "with_image_reference_instructions") profileRule(profile).with_image_reference_instructions = input.value;
        else if (bind === "without_image_reference_instructions") profileRule(profile).without_image_reference_instructions = input.value;
        else if (bind === "output_contract_negative_off") profileRule(profile).output_contract_negative_off = input.value;
        else if (bind === "output_contract_negative_on") profileRule(profile).output_contract_negative_on = input.value;
      }
      normalizeActiveFormat(profile);
    }

    function validateDraft(profilesToValidate = draft) {
      const seen = new Set();
      for (const raw of profilesToValidate) {
        const profile = ensureProfileShape(raw);
        if (!/^[a-z0-9][a-z0-9_]*$/.test(profile.key || "")) throw new Error("Every model key must use lowercase letters, numbers, and underscores.");
        if (seen.has(profile.key)) throw new Error(`Duplicate model key: ${profile.key}`);
        seen.add(profile.key);
        if (!profile.label?.trim()) throw new Error(`Profile ${profile.key} needs a display label.`);
        const enabled = enabledFormatsFor(profile);
        if (!enabled.length) throw new Error(`Profile ${profile.key} needs at least one enabled format.`);
        if (!enabled.includes(profile.default_format)) throw new Error(`Profile ${profile.key} default format must be enabled.`);
        for (const format of enabled) {
          const rule = profile.formats[format];
          if (!rule.common_instructions?.trim()) throw new Error(`${profile.key} ${format} needs common instructions.`);
          if (!rule.with_image_reference_instructions?.trim()) throw new Error(`${profile.key} ${format} needs with-image instructions.`);
          if (!rule.without_image_reference_instructions?.trim()) throw new Error(`${profile.key} ${format} needs without-image instructions.`);
          if (!rule.output_contract_negative_off?.trim()) throw new Error(`${profile.key} ${format} needs a negative-off output contract.`);
          if (!rule.output_contract_negative_on?.trim()) throw new Error(`${profile.key} ${format} needs a negative-on output contract.`);
        }
      }
    }

    function formatSegment(profile) {
      const row = buildDom("div", "workflowx-uap-settings-segment");
      for (const format of formats) {
        const button = buildDom("button", "", `${format}${profile.formats[format]?.enabled ? "" : " off"}`);
        button.type = "button";
        button.classList.toggle("active", format === activeFormat);
        button.addEventListener("click", () => {
          readCurrentView();
          activeFormat = format;
          renderAll();
        });
        row.appendChild(button);
      }
      return row;
    }

    function imageModeSegment() {
      const row = buildDom("div", "workflowx-uap-settings-segment");
      for (const [mode, label] of [["with_image", "With image"], ["without_image", "Without image"]]) {
        const button = buildDom("button", "", label);
        button.type = "button";
        button.classList.toggle("active", mode === activeImageMode);
        button.addEventListener("click", () => {
          readCurrentView();
          activeImageMode = mode;
          renderAll();
        });
        row.appendChild(button);
      }
      return row;
    }

    function renderModelTab(profile) {
      const grid = buildDom("div", "workflowx-uap-grid");
      const keyInput = bindInput(createInput("text"), "key");
      keyInput.value = profile.key || "";
      keyInput.disabled = builtinKeys.has(profile.key);
      const labelInput = bindInput(createInput("text"), "label");
      labelInput.value = profile.label || "";
      const mediaSelect = bindInput(createSelect(), "media_type");
      setSelectOptions(mediaSelect, mediaTypes, profile.media_type || "image");
      const defaultFormatSelect = bindInput(createSelect(), "default_format");
      setSelectOptions(defaultFormatSelect, enabledFormatsFor(profile), profile.default_format || enabledFormatsFor(profile)[0] || "natural");
      field(grid, "Model key", keyInput);
      field(grid, "Display label", labelInput);
      field(grid, "Media type", mediaSelect);
      field(grid, "Default format", defaultFormatSelect);
      editor.appendChild(grid);
      const optionRow = buildDom("div", "workflowx-uap-row");
      for (const [bind, labelText] of [["negative_supported", "supports negative"], ["json_supported", "JSON supported"]]) {
        const label = buildDom("label", "workflowx-uap-toggle");
        const input = bindInput(document.createElement("input"), bind);
        input.type = "checkbox";
        input.checked = Boolean(profile[bind]);
        label.appendChild(input);
        label.appendChild(document.createTextNode(labelText));
        optionRow.appendChild(label);
      }
      editor.appendChild(optionRow);
      const notes = bindInput(createTextarea(6), "notes");
      notes.value = profile.notes || "";
      field(editor, "Model notes", notes);
    }

    function renderFormatsTab(profile) {
      editor.appendChild(buildDom("div", "workflowx-uap-label", "Enable formats"));
      for (const format of formats) {
        const label = buildDom("label", "workflowx-uap-toggle");
        const input = bindInput(document.createElement("input"), `format_enabled:${format}`);
        input.type = "checkbox";
        input.checked = Boolean(profile.formats[format]?.enabled);
        label.appendChild(input);
        label.appendChild(document.createTextNode(format));
        editor.appendChild(label);
      }
      const defaultSelect = bindInput(createSelect(), "default_format");
      setSelectOptions(defaultSelect, enabledFormatsFor(profile), profile.default_format || enabledFormatsFor(profile)[0] || "natural");
      field(editor, "Default format", defaultSelect);
    }

    function renderPromptTab(profile) {
      editor.appendChild(formatSegment(profile));
      editor.appendChild(imageModeSegment());
      const rule = profileRule(profile);
      const common = bindInput(createTextarea(9), "common_instructions");
      common.classList.add("workflowx-uap-settings-large");
      common.value = rule.common_instructions || "";
      field(editor, `${activeFormat} common instructions`, common);
      const modeKey = activeImageMode === "with_image" ? "with_image_reference_instructions" : "without_image_reference_instructions";
      const modeArea = bindInput(createTextarea(8), modeKey);
      modeArea.classList.add("workflowx-uap-settings-large");
      modeArea.value = rule[modeKey] || "";
      field(editor, activeImageMode === "with_image" ? "With image reference instructions" : "Without image reference instructions", modeArea);
    }

    function renderContractTab(profile) {
      editor.appendChild(formatSegment(profile));
      const rule = profileRule(profile);
      const off = bindInput(createTextarea(6), "output_contract_negative_off");
      off.classList.add("workflowx-uap-settings-contract");
      off.value = rule.output_contract_negative_off || "";
      const on = bindInput(createTextarea(6), "output_contract_negative_on");
      on.classList.add("workflowx-uap-settings-contract");
      on.value = rule.output_contract_negative_on || "";
      field(editor, `${activeFormat} contract when negative is off`, off);
      field(editor, `${activeFormat} contract when negative is on`, on);
    }

    function renderPreviewTab(profile) {
      const controls = buildDom("div", "workflowx-uap-row");
      controls.appendChild(formatSegment(profile));
      controls.appendChild(imageModeSegment());
      const negativeLabel = buildDom("label", "workflowx-uap-toggle");
      const negativePreviewInput = document.createElement("input");
      negativePreviewInput.type = "checkbox";
      negativePreviewInput.checked = Boolean(profile.__preview_negative);
      negativePreviewInput.addEventListener("change", () => {
        profile.__preview_negative = negativePreviewInput.checked;
        renderAll();
      });
      negativeLabel.appendChild(negativePreviewInput);
      negativeLabel.appendChild(document.createTextNode("negative preview"));
      controls.appendChild(negativeLabel);
      editor.appendChild(controls);
      const preview = buildDom("pre", "workflowx-uap-settings-preview");
      preview.textContent = renderTemplatePreview(profile, activeFormat, Boolean(profile.__preview_negative), activeImageMode === "with_image");
      editor.appendChild(preview);
    }

    function renderList() {
      const filter = searchInput.value.trim().toLowerCase();
      items.replaceChildren();
      for (const profile of draft) {
        if (filter && !`${profile.label} ${profile.key} ${profile.notes || ""}`.toLowerCase().includes(filter)) continue;
        const item = buildDom("button", `workflowx-uap-settings-item${profile.key === selectedKey ? " active" : ""}`);
        item.type = "button";
        item.appendChild(buildDom("div", "", profile.label || profile.key));
        item.appendChild(buildDom("div", "workflowx-uap-settings-key", `${profile.key}${builtinKeys.has(profile.key) ? " - built-in" : " - custom"}`));
        item.addEventListener("click", () => {
          readCurrentView();
          selectedKey = profile.key;
          activeFormat = profile.default_format || activeFormat;
          renderAll();
        });
        items.appendChild(item);
      }
    }

    function renderForm() {
      const profile = selectedProfile();
      formPane.classList.toggle("workflowx-uap-hidden", !profile);
      if (!profile) return;
      Object.assign(profile, ensureProfileShape(profile));
      normalizeActiveFormat(profile);
      for (const [key, button] of tabButtons) button.classList.toggle("active", key === activeTab);
      editor.replaceChildren();
      deleteBtn.disabled = builtinKeys.has(profile.key);
      resetOneBtn.disabled = !builtinKeys.has(profile.key);
      if (activeTab === "model") renderModelTab(profile);
      else if (activeTab === "formats") renderFormatsTab(profile);
      else if (activeTab === "prompt") renderPromptTab(profile);
      else if (activeTab === "contract") renderContractTab(profile);
      else renderPreviewTab(profile);
    }

    function renderAll() {
      renderList();
      renderForm();
    }

    function onFormInput() {
      readCurrentView();
      renderList();
    }

    searchInput.addEventListener("input", renderList);
    addBtn.addEventListener("click", () => {
      readCurrentView();
      const base = JSON.parse(JSON.stringify(defaultsByKey.get("ideogram4") || draft[0] || {}));
      const key = uniqueKey("custom_model");
      draft.push(ensureProfileShape({ ...base, key, label: "Custom Model" }));
      selectedKey = key;
      activeTab = "model";
      renderAll();
    });
    duplicateBtn.addEventListener("click", () => {
      readCurrentView();
      const profile = selectedProfile();
      if (!profile) return;
      const key = uniqueKey(`${profile.key}_copy`);
      draft.push(ensureProfileShape({ ...JSON.parse(JSON.stringify(profile)), key, label: `${profile.label || profile.key} Copy` }));
      selectedKey = key;
      activeTab = "model";
      renderAll();
    });
    deleteBtn.addEventListener("click", () => {
      const profile = selectedProfile();
      if (!profile || builtinKeys.has(profile.key)) return;
      draft = draft.filter((item) => item !== profile);
      selectedKey = draft[0]?.key || "";
      renderAll();
    });
    resetOneBtn.addEventListener("click", () => {
      const profile = selectedProfile();
      if (!profile || !builtinKeys.has(profile.key)) return;
      const restored = defaultsByKey.get(profile.key);
      if (!restored) return;
      const index = draft.findIndex((item) => item.key === profile.key);
      draft[index] = JSON.parse(JSON.stringify(restored));
      renderAll();
    });
    closeBtn.addEventListener("click", () => backdrop.remove());
    backdrop.addEventListener("mousedown", (event) => {
      if (event.target === backdrop) backdrop.remove();
    });
    revertBtn.addEventListener("click", () => {
      backdrop.remove();
      openModelSettingsModalV3();
    });
    exportBtn.addEventListener("click", async () => {
      try {
        readCurrentView();
        draft = cleanProfiles(draft);
        validateDraft(draft);
        const messageText = await saveJsonFile(exportPayload());
        showMessage(messageText);
      } catch (error) {
        if (error?.name === "AbortError") {
          showMessage("Export cancelled.");
        } else {
          showMessage(error.message, true);
        }
      }
    });
    importBtn.addEventListener("click", () => {
      importInput.value = "";
      importInput.click();
    });
    importInput.addEventListener("change", async () => {
      const file = importInput.files?.[0];
      if (!file) return;
      try {
        const payload = JSON.parse(await file.text());
        const importedProfiles = importedProfilesFromPayload(payload);
        validateDraft(importedProfiles);
        readCurrentView();
        draft = importedProfiles;
        selectedKey = draft.some((profile) => profile.key === selectedKey) ? selectedKey : draft[0]?.key || "";
        const selected = selectedProfile();
        activeFormat = selected?.default_format || activeFormat;
        searchInput.value = "";
        showMessage(`Imported ${draft.length} profiles from ${file.name}. Review and Save to apply.`);
        renderAll();
      } catch (error) {
        showMessage(`Import failed: ${error.message}`, true);
      }
    });
    resetAllBtn.addEventListener("click", async () => {
      if (!window.confirm("Reset all model profiles to WorkflowX defaults?")) return;
      try {
        const data = await fetchJsonChecked(`${ROUTE}/profile_config/reset`, { method: "POST" }, "Reset model settings");
        config = data;
        draft = JSON.parse(JSON.stringify(data.profiles || [])).map(ensureProfileShape);
        selectedKey = draft.some((profile) => profile.key === state.target_model) ? state.target_model : draft[0]?.key || "";
        clearProfileCache();
        profiles = await loadProfiles();
        profilesByKey = profileMap(profiles);
        refreshProfiles();
        showMessage("Profiles reset to defaults.");
        renderAll();
      } catch (error) {
        showMessage(error.message, true);
      }
    });
    saveBtn.addEventListener("click", async () => {
      try {
        readCurrentView();
        draft = cleanProfiles(draft);
        validateDraft();
        const data = await fetchJsonChecked(`${ROUTE}/profile_config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ version: 3, profiles: draft }),
        }, "Save model settings");
        clearProfileCache();
        profiles = await loadProfiles();
        profilesByKey = profileMap(profiles);
        if (profilesByKey.has(selectedKey)) state.target_model = selectedKey;
        refreshProfiles();
        showMessage("Profiles saved.");
        setStatus("Model settings saved.");
      } catch (error) {
        showMessage(error.message, true);
      }
    });

    renderAll();
  }

  function normalizeBoxFromBbox(element, index) {
    const bbox = Array.isArray(element?.bbox) ? element.bbox : [80 + index * 40, 80 + index * 40, 320 + index * 40, 360 + index * 40];
    const ymin = clamp01(Number(bbox[0]) / 1000);
    const xmin = clamp01(Number(bbox[1]) / 1000);
    const ymax = clamp01(Number(bbox[2]) / 1000);
    const xmax = clamp01(Number(bbox[3]) / 1000);
    const palette = Array.isArray(element?.color_palette)
      ? element.color_palette.map((item) => String(item || "").trim()).filter(Boolean)
      : [];
    const fallbackColor = String(element?.color || ideogramPaletteInput.value.split(",")[0] || "#8c8c8c").trim();
    if (!palette.length && fallbackColor) palette.push(fallbackColor);
    return {
      type: element?.type === "text" ? "text" : "obj",
      text: String(element?.text || ""),
      desc: String(element?.desc || element?.description || ""),
      palette,
      x: Math.min(xmin, xmax),
      y: Math.min(ymin, ymax),
      w: Math.max(0.04, Math.abs(xmax - xmin)),
      h: Math.max(0.04, Math.abs(ymax - ymin)),
    };
  }

  function openIdeogramLayoutEditor() {
    if (state.target_model !== "ideogram4") return;
    readFieldsIntoState();
    const dock = createDockWindow(node, "ideogram", "ideogram 4 prompt editor X", { height: 470, pinned: true, matchNodeWidth: true });

    function normalizeCaptionPayload(payload) {
      if (!payload || typeof payload !== "object") return {};
      if (payload.prompt_json && typeof payload.prompt_json === "object") return payload.prompt_json;
      return payload;
    }

    function parseCaptionText(text) {
      const parsedText = parseJsonObject(text);
      return normalizeCaptionPayload(parsedText);
    }

    function hasCaptionContent(caption) {
      const decomp = caption?.compositional_deconstruction || {};
      return Boolean(
        caption?.high_level_description
        || decomp.background
        || (Array.isArray(decomp.elements) && decomp.elements.length)
        || (Array.isArray(caption?.elements) && caption.elements.length)
      );
    }

    function activeIdeogramCaption() {
      const candidates = [];
      if (state.last_generation?.target_model === "ideogram4" && state.last_generation?.prompt_format === "json") {
        candidates.push(state.last_generation.prompt);
        candidates.push(state.last_generation.positive);
      }
      candidates.push(widgetValue(node, "final_prompt", ""));
      candidates.push(state.final_prompt || "");
      candidates.push(state.ideogram_layout || "");
      for (const candidate of candidates) {
        const caption = parseCaptionText(candidate);
        if (hasCaptionContent(caption)) return caption;
      }
      return {};
    }

    const parsed = activeIdeogramCaption();
    const decomp = parsed.compositional_deconstruction || {};
    const sourceElements = Array.isArray(decomp.elements) ? decomp.elements : Array.isArray(parsed.elements) ? parsed.elements : [];
    const boxes = sourceElements.map(normalizeBoxFromBbox);
    let activeIndex = boxes.length ? 0 : -1;
    let drawing = null;
    let draggingBox = null;
    let inlineEditor = null;
    let layerMenu = null;
    let highLevelDescription = parsed.high_level_description || state.subject || state.idea || "";
    let backgroundDescription = decomp.background || state.idea || "";
    let stylePalette = String(state.ideogram_palette || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!stylePalette.length && Array.isArray(parsed.style_description?.color_palette)) {
      stylePalette = parsed.style_description.color_palette
        .map((item) => String(item || "").trim())
        .filter(Boolean);
    }
    if (!stylePalette.length) {
      for (const box of boxes) {
        const color = box.palette?.find(Boolean) || box.color;
        if (color) stylePalette.push(color);
      }
      stylePalette = [...new Set(stylePalette)].slice(0, 8);
    }
    state.ideogram_show_text = state.ideogram_show_text !== false;
    state.ideogram_box_opacity = state.ideogram_box_opacity ?? 18;
    const round16 = (value) => Math.max(16, Math.round(Number(value || 1024) / 16) * 16);
    state.ideogram_width = round16(state.ideogram_width || 1024);
    state.ideogram_height = round16(state.ideogram_height || 1024);

    const editor = buildDom("div", "workflowx-uap-ideo-editor");
    dock.body.appendChild(editor);

    const bar = buildDom("div", "workflowx-uap-ideo-bar");
    const tokenSpan = buildDom("span", "workflowx-uap-ideo-token", "~0 tok");
    const bgBtn = buildDom("button", "workflowx-uap-btn", "Background v");
    const textBtn = buildDom("button", "workflowx-uap-btn", "Text v");
    const copyBtn = buildDom("button", "workflowx-uap-btn", "Copy");
    const applyBtn = buildDom("button", "workflowx-uap-btn", "Apply layout to output");
    const syncBtn = buildDom("button", "workflowx-uap-btn", "Sync");
    const templatesBtn = buildDom("button", "workflowx-uap-btn", "Templates v");
    const clearBtn = buildDom("button", "workflowx-uap-btn", "Clear all");
    for (const button of [bgBtn, textBtn, copyBtn, applyBtn, syncBtn, templatesBtn, clearBtn]) button.type = "button";
    bar.appendChild(tokenSpan);
    bar.appendChild(bgBtn);
    bar.appendChild(textBtn);
    bar.appendChild(copyBtn);
    bar.appendChild(applyBtn);
    bar.appendChild(syncBtn);
    bar.appendChild(templatesBtn);
    bar.appendChild(clearBtn);
    editor.appendChild(bar);

    const styleBar = buildDom("div", "workflowx-uap-ideo-bar");
    styleBar.appendChild(buildDom("span", "", "Style colors:"));
    editor.appendChild(styleBar);

    const cvBox = buildDom("div", "workflowx-uap-ideo-cv");
    const canvas = document.createElement("canvas");
    canvas.className = "workflowx-uap-ideo-canvas";
    canvas.width = state.ideogram_width;
    canvas.height = state.ideogram_height;
    cvBox.appendChild(canvas);
    editor.appendChild(cvBox);

    const splitter = buildDom("div", "workflowx-uap-ideo-split");
    editor.appendChild(splitter);

    const panel = buildDom("div", "workflowx-uap-ideo-panel");
    panel.style.height = `${state.ideogram_panel_height}px`;
    editor.appendChild(panel);

    const bgMenu = buildDom("div", "workflowx-uap-ideo-menu workflowx-uap-hidden");
    const overlayToggle = buildDom("label", "workflowx-uap-toggle");
    const overlayInput = document.createElement("input");
    overlayInput.type = "checkbox";
    overlayInput.checked = state.ideogram_overlay_visible !== false;
    overlayToggle.appendChild(overlayInput);
    overlayToggle.appendChild(document.createTextNode("show image overlay"));
    const brightnessInput = createInput("range");
    brightnessInput.min = "0";
    brightnessInput.max = "100";
    brightnessInput.step = "1";
    brightnessInput.value = String(state.ideogram_overlay_brightness || 35);
    const widthInput = createInput("number");
    widthInput.min = "16";
    widthInput.step = "16";
    widthInput.value = String(state.ideogram_width);
    const heightInput = createInput("number");
    heightInput.min = "16";
    heightInput.step = "16";
    heightInput.value = String(state.ideogram_height);
    const manualDimsToggle = buildDom("label", "workflowx-uap-toggle");
    const manualDimsInput = document.createElement("input");
    manualDimsInput.type = "checkbox";
    manualDimsInput.checked = Boolean(state.ideogram_manual_dims);
    manualDimsToggle.appendChild(manualDimsInput);
    manualDimsToggle.appendChild(document.createTextNode("lock resolution"));
    const highInput = createTextarea(2);
    highInput.value = highLevelDescription;
    const bgInput = createTextarea(2);
    bgInput.value = backgroundDescription;
    const bgRow1 = buildDom("div", "workflowx-uap-ideo-menu-row");
    bgRow1.appendChild(overlayToggle);
    const bgRow2 = buildDom("div", "workflowx-uap-ideo-menu-row");
    bgRow2.appendChild(buildDom("span", "", "Brightness"));
    bgRow2.appendChild(brightnessInput);
    const dimsRow = buildDom("div", "workflowx-uap-ideo-menu-row");
    dimsRow.appendChild(buildDom("span", "", "Width"));
    dimsRow.appendChild(widthInput);
    dimsRow.appendChild(buildDom("span", "", "Height"));
    dimsRow.appendChild(heightInput);
    field(bgMenu, "High level description", highInput);
    field(bgMenu, "Background", bgInput);
    bgMenu.appendChild(bgRow1);
    bgMenu.appendChild(bgRow2);
    bgMenu.appendChild(dimsRow);
    bgMenu.appendChild(manualDimsToggle);
    document.body.appendChild(bgMenu);

    const textMenu = buildDom("div", "workflowx-uap-ideo-menu workflowx-uap-hidden");
    const showTextToggle = buildDom("label", "workflowx-uap-toggle");
    const showTextInput = document.createElement("input");
    showTextInput.type = "checkbox";
    showTextInput.checked = state.ideogram_show_text !== false;
    showTextToggle.appendChild(showTextInput);
    showTextToggle.appendChild(document.createTextNode("show text"));
    const opacityInput = createInput("range");
    opacityInput.min = "0";
    opacityInput.max = "55";
    opacityInput.step = "1";
    opacityInput.value = String(state.ideogram_box_opacity ?? 18);
    const textRow1 = buildDom("div", "workflowx-uap-ideo-menu-row");
    textRow1.appendChild(showTextToggle);
    const textRow2 = buildDom("div", "workflowx-uap-ideo-menu-row");
    textRow2.appendChild(buildDom("span", "", "Box opacity"));
    textRow2.appendChild(opacityInput);
    textMenu.appendChild(textRow1);
    textMenu.appendChild(textRow2);
    document.body.appendChild(textMenu);

    const templatesMenu = buildDom("div", "workflowx-uap-ideo-menu workflowx-uap-hidden");
    document.body.appendChild(templatesMenu);

    function showMenu(menu, button) {
      for (const item of [bgMenu, textMenu, templatesMenu]) {
        if (item !== menu) item.classList.add("workflowx-uap-hidden");
      }
      menu.classList.toggle("workflowx-uap-hidden");
      if (menu.classList.contains("workflowx-uap-hidden")) return;
      const rect = button.getBoundingClientRect();
      menu.style.left = `${Math.max(4, Math.min(rect.left, window.innerWidth - 260))}px`;
      menu.style.top = `${Math.min(rect.bottom + 4, window.innerHeight - 180)}px`;
    }

    async function buildTemplatesMenu() {
      templatesMenu.replaceChildren();
      const saveRow = buildDom("div", "workflowx-uap-ideo-menu-row");
      const saveBtn = buildDom("button", "workflowx-uap-btn", "+ Save as...");
      saveBtn.type = "button";
      saveBtn.addEventListener("click", async () => {
        const name = ideogramTemplateSafeName(window.prompt("Save template as:", "") || "");
        if (!name) return;
        const existing = await listIdeogramTemplateNames();
        if (existing.includes(name) && !window.confirm(`Overwrite template "${name}"?`)) return;
        if (await saveIdeogramTemplate(name, buildCaption())) await buildTemplatesMenu();
      });
      saveRow.appendChild(saveBtn);
      templatesMenu.appendChild(saveRow);
      const names = await listIdeogramTemplateNames();
      if (!names.length) {
        templatesMenu.appendChild(buildDom("div", "workflowx-uap-ideo-empty", "No templates saved."));
        return;
      }
      for (const name of names) {
        const row = buildDom("div", "workflowx-uap-ideo-menu-row");
        const label = buildDom("span", "", name);
        label.style.flex = "1";
        const loadBtn = buildDom("button", "workflowx-uap-btn", "Load");
        const insertBtn = buildDom("button", "workflowx-uap-btn", "Insert");
        const deleteBtn = buildDom("button", "workflowx-uap-btn", "x");
        for (const button of [loadBtn, insertBtn, deleteBtn]) button.type = "button";
        loadBtn.addEventListener("click", async () => {
          const caption = parseJsonObject(await loadIdeogramTemplate(name));
          if (caption) loadCaption(caption, false);
        });
        insertBtn.addEventListener("click", async () => {
          const caption = parseJsonObject(await loadIdeogramTemplate(name));
          if (caption) loadCaption(caption, true);
        });
        deleteBtn.addEventListener("click", async () => {
          if (!window.confirm(`Delete template "${name}"?`)) return;
          await deleteIdeogramTemplate(name);
          await buildTemplatesMenu();
        });
        row.appendChild(label);
        row.appendChild(loadBtn);
        row.appendChild(insertBtn);
        row.appendChild(deleteBtn);
        templatesMenu.appendChild(row);
      }
    }

    dock.dock.__workflowXCleanup = (() => {
      const previous = dock.dock.__workflowXCleanup;
      return () => {
        previous?.();
        bgMenu.remove();
        textMenu.remove();
        templatesMenu.remove();
        inlineEditor?.remove();
        layerMenu?.remove();
        canvasResizeObserver?.disconnect?.();
        if (node.__workflowXUapRenderIdeogram === renderAll) node.__workflowXUapRenderIdeogram = null;
        if (node.__workflowXUapOnOverlayImageLoad) node.__workflowXUapOnOverlayImageLoad = null;
      };
    })();

    function buildCaption() {
      const elements = boxes.map((box) => {
        const element = {
          type: box.type === "text" ? "text" : "obj",
          bbox: [
            Math.round(box.y * 1000),
            Math.round(box.x * 1000),
            Math.round((box.y + box.h) * 1000),
            Math.round((box.x + box.w) * 1000),
          ],
        };
        if (box.type === "text") element.text = box.text || "";
        element.desc = box.desc || "";
        const palette = (box.palette || (box.color ? [box.color] : []))
          .filter(Boolean)
          .slice(0, IDEOGRAM_MAX_ELEM_COLORS)
          .map((color) => String(color).toUpperCase());
        if (palette.length) element.color_palette = palette;
        return element;
      });
      return {
        high_level_description: highLevelDescription || state.subject || state.idea || "",
        style_description: stylePalette.length ? {
          aesthetics: state.style || "",
          lighting: state.lighting || "",
          medium: state.detail || "",
          color_palette: stylePalette.map((color) => String(color).toUpperCase()),
        } : undefined,
        compositional_deconstruction: {
          background: backgroundDescription || state.idea || "",
          elements,
        },
      };
    }

    function loadCaption(caption, insertOnly = false) {
      if (!caption || typeof caption !== "object") return;
      const nextDecomp = caption.compositional_deconstruction || {};
      const nextElements = Array.isArray(nextDecomp.elements) ? nextDecomp.elements : Array.isArray(caption.elements) ? caption.elements : [];
      const nextBoxes = nextElements.map(normalizeBoxFromBbox);
      if (insertOnly) {
        boxes.push(...nextBoxes.map((box) => ({ ...box, x: clamp01(box.x + 0.04), y: clamp01(box.y + 0.04) })));
      } else {
        boxes.splice(0, boxes.length, ...nextBoxes);
        highLevelDescription = caption.high_level_description || highLevelDescription;
        backgroundDescription = nextDecomp.background || backgroundDescription;
        if (Array.isArray(caption.style_description?.color_palette)) {
          stylePalette = caption.style_description.color_palette
            .map((item) => String(item || "").trim())
            .filter(Boolean);
        }
        highInput.value = highLevelDescription;
        bgInput.value = backgroundDescription;
      }
      activeIndex = boxes.length ? Math.max(0, boxes.length - nextBoxes.length) : -1;
      commitIdeogramState();
      renderAll();
    }

    function commitIdeogramState() {
      const caption = buildCaption();
      ideogramLayoutArea.value = JSON.stringify(caption, null, 2);
      ideogramPaletteInput.value = stylePalette.join(", ");
      state.ideogram_layout = ideogramLayoutArea.value;
      state.ideogram_palette = ideogramPaletteInput.value;
      syncPreview();
      updateTokenEstimate();
    }

    function applyIdeogramLayoutToOutput() {
      const prompt = JSON.stringify(buildCaption(), null, 2);
      ideogramLayoutArea.value = prompt;
      state.ideogram_layout = prompt;
      state.target_model = "ideogram4";
      state.prompt_format = "json";
      targetSelect.value = "ideogram4";
      if (Array.from(formatSelect.options).some((option) => option.value === "json")) {
        formatSelect.value = "json";
      }
      const negative = state.negative_enabled ? (state.last_generation?.negative || state.generated_negative || widgetValue(node, "generated_negative", "")) : "";
      state.generated_positive = prompt;
      state.generated_negative = negative;
      state.final_prompt = prompt;
      state.last_generation = {
        prompt,
        positive: prompt,
        negative,
        target_model: "ideogram4",
        prompt_format: "json",
        negative_enabled: Boolean(state.negative_enabled),
        source: "ideogram_layout_apply",
        generated_at: new Date().toISOString(),
      };
      syncPreview();
      setStatus("Ideogram layout applied to output.");
    }

    function activeBox() {
      return boxes[activeIndex] || null;
    }

    function boxColor(box) {
      return box?.palette?.find(Boolean) || box?.color || "#8c8c8c";
    }

    function boxLabel(box, index) {
      const main = box.type === "text" && box.text ? `"${box.text}"` : box.desc || "";
      return main || (box.type === "text" ? "(text)" : "(empty)");
    }

    function stopEditorEvents(element) {
      for (const eventName of ["mousedown", "pointerdown", "wheel", "dblclick"]) {
        element.addEventListener(eventName, (event) => event.stopPropagation());
      }
    }

    function parseColorString(text) {
      const value = String(text || "").trim();
      const hex = value.match(/^#?([0-9a-fA-F]{6})$/);
      if (hex) return `#${hex[1].toLowerCase()}`;
      const shortHex = value.match(/^#?([0-9a-fA-F]{3})$/);
      if (shortHex) return `#${shortHex[1].split("").map((char) => char + char).join("").toLowerCase()}`;
      return null;
    }

    function commitSwatchEdit() {
      ideogramPaletteInput.value = stylePalette.join(", ");
      state.ideogram_palette = ideogramPaletteInput.value;
      syncPreview();
      renderCanvas();
      updateTokenEstimate();
    }

    function buildSwatchRow(container, palette, maxColors, onEdit, onStructure) {
      const normalized = palette
        .map((color) => parseColorString(color) || String(color || "").trim())
        .filter(Boolean);
      palette.splice(0, palette.length, ...normalized);
      for (const color of palette) {
        const index = palette.indexOf(color);
        const swatch = buildDom("div", "workflowx-uap-ideo-swatch");
        swatch.style.background = color;
        swatch.dataset.color = color;
        swatch.title = "Click edit, drag reorder, right-click remove";
        const input = document.createElement("input");
        input.type = "color";
        input.value = parseColorString(color) || "#ffffff";
        swatch.appendChild(input);
        container.appendChild(swatch);
        const setColor = (nextColor) => {
          const safe = parseColorString(nextColor) || nextColor;
          const currentIndex = palette.indexOf(swatch.dataset.color);
          if (currentIndex >= 0) palette[currentIndex] = safe;
          input.value = parseColorString(safe) || "#ffffff";
          swatch.style.background = safe;
          swatch.dataset.color = safe;
          onEdit();
        };
        input.addEventListener("input", () => setColor(input.value));
        swatch.addEventListener("contextmenu", (event) => {
          event.preventDefault();
          event.stopPropagation();
          const currentIndex = palette.indexOf(swatch.dataset.color);
          if (currentIndex >= 0) palette.splice(currentIndex, 1);
          onStructure();
        });
        swatch.addEventListener("pointerdown", (event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          event.stopPropagation();
          const startX = event.clientX;
          const startY = event.clientY;
          let draggingSwatch = false;
          try {
            swatch.setPointerCapture(event.pointerId);
          } catch {
            // Pointer capture can fail if the element detaches during rebuild.
          }
          const move = (moveEvent) => {
            if (!draggingSwatch) {
              if (Math.abs(moveEvent.clientX - startX) + Math.abs(moveEvent.clientY - startY) < 4) return;
              draggingSwatch = true;
              swatch.classList.add("dragging");
            }
            for (const other of container.querySelectorAll(".workflowx-uap-ideo-swatch")) {
              if (other === swatch) continue;
              const rect = other.getBoundingClientRect();
              if (moveEvent.clientX >= rect.left && moveEvent.clientX <= rect.right && moveEvent.clientY >= rect.top - 6 && moveEvent.clientY <= rect.bottom + 6) {
                const ref = moveEvent.clientX > rect.left + rect.width / 2 ? other.nextSibling : other;
                if (ref === swatch || ref === swatch.nextSibling) break;
                container.insertBefore(swatch, ref);
                break;
              }
            }
          };
          const up = () => {
            swatch.removeEventListener("pointermove", move);
            swatch.removeEventListener("pointerup", up);
            swatch.removeEventListener("pointercancel", up);
            if (draggingSwatch) {
              swatch.classList.remove("dragging");
              const nextOrder = Array.from(container.querySelectorAll(".workflowx-uap-ideo-swatch"))
                .map((item) => item.dataset.color)
                .filter(Boolean);
              if (nextOrder.length === palette.length) palette.splice(0, palette.length, ...nextOrder);
              onStructure();
            } else {
              input.click();
            }
          };
          swatch.addEventListener("pointermove", move);
          swatch.addEventListener("pointerup", up);
          swatch.addEventListener("pointercancel", up);
        });
        if (index < 0) swatch.remove();
      }
      if (palette.length < maxColors) {
        const add = buildDom("button", "workflowx-uap-btn", "+");
        add.type = "button";
        add.title = "Add a color";
        stopEditorEvents(add);
        add.addEventListener("click", async () => {
          let next = "#ffffff";
          try {
            next = parseColorString(await navigator.clipboard?.readText?.()) || next;
          } catch {
            // Clipboard is optional.
          }
          palette.push(next);
          onStructure();
        });
        container.appendChild(add);
      }
    }

    function updateTokenEstimate() {
      const chars = ideogramLayoutArea.value.length;
      const tokens = Math.max(0, Math.round(chars / 4));
      tokenSpan.textContent = `~${tokens} tok`;
      tokenSpan.style.color = tokens >= 2048 ? "#ff8585" : tokens >= 1500 ? "#ffb86c" : tokens >= 256 ? "#9fd28f" : "#8b949e";
    }

    function fitCanvas() {
      const targetWidth = round16(state.ideogram_width || 1024);
      const targetHeight = round16(state.ideogram_height || 1024);
      canvas.width = targetWidth;
      canvas.height = targetHeight;
      const boxWidth = Math.max(1, cvBox.clientWidth || targetWidth);
      const boxHeight = Math.max(1, cvBox.clientHeight || targetHeight);
      const scale = Math.min(boxWidth / targetWidth, boxHeight / targetHeight);
      canvas.style.width = `${Math.max(1, Math.round(targetWidth * scale))}px`;
      canvas.style.height = `${Math.max(1, Math.round(targetHeight * scale))}px`;
    }

    function syncResolutionInputs() {
      widthInput.value = String(round16(state.ideogram_width));
      heightInput.value = String(round16(state.ideogram_height));
      manualDimsInput.checked = Boolean(state.ideogram_manual_dims);
    }

    function setResolution(width, height, manual = true) {
      state.ideogram_width = round16(width);
      state.ideogram_height = round16(height);
      state.ideogram_manual_dims = Boolean(manual);
      syncResolutionInputs();
      fitCanvas();
      syncPreview();
      renderCanvas();
    }

    node.__workflowXUapOnOverlayImageLoad = (img) => {
      if (img && !state.ideogram_manual_dims) {
        setResolution(img.naturalWidth || img.width || state.ideogram_width, img.naturalHeight || img.height || state.ideogram_height, false);
      } else {
        renderCanvas();
      }
    };
    if (node.__workflowXUapOverlayImage) node.__workflowXUapOnOverlayImageLoad(node.__workflowXUapOverlayImage);

    function renderStyleBar() {
      while (styleBar.children.length > 1) styleBar.lastChild.remove();
      buildSwatchRow(styleBar, stylePalette, IDEOGRAM_MAX_STYLE_COLORS, commitSwatchEdit, () => {
        commitSwatchEdit();
        renderStyleBar();
      });
    }

    function renderCanvas() {
      fitCanvas();
      const ctx = canvas.getContext("2d");
      const canvasWidth = canvas.width;
      const canvasHeight = canvas.height;
      ctx.clearRect(0, 0, canvasWidth, canvasHeight);
      ctx.fillStyle = "#2a2a2a";
      ctx.fillRect(0, 0, canvasWidth, canvasHeight);
      const overlay = node.__workflowXUapOverlayImage;
      if (overlay && state.ideogram_overlay_visible !== false) {
        ctx.drawImage(overlay, 0, 0, canvasWidth, canvasHeight);
        const dim = 1 - Math.max(0, Math.min(100, Number(state.ideogram_overlay_brightness || 35))) / 100;
        if (dim > 0) {
          ctx.fillStyle = `rgba(0,0,0,${dim})`;
          ctx.fillRect(0, 0, canvasWidth, canvasHeight);
        }
      } else {
        const grey = Math.round(Math.max(0, Math.min(100, Number(state.ideogram_overlay_brightness || 35))) / 100 * 128);
        ctx.fillStyle = `rgb(${grey},${grey},${grey})`;
        ctx.fillRect(0, 0, canvasWidth, canvasHeight);
      }
      ctx.strokeStyle = "rgba(255,255,255,.12)";
      ctx.lineWidth = 1;
      for (let line = 0.1; line < 1; line += 0.1) {
        ctx.beginPath();
        ctx.moveTo(line * canvasWidth, 0);
        ctx.lineTo(line * canvasWidth, canvasHeight);
        ctx.moveTo(0, line * canvasHeight);
        ctx.lineTo(canvasWidth, line * canvasHeight);
        ctx.stroke();
      }
      for (let index = boxes.length - 1; index >= 0; index -= 1) {
        const box = boxes[index];
        const x = box.x * canvasWidth;
        const y = box.y * canvasHeight;
        const w = box.w * canvasWidth;
        const h = box.h * canvasHeight;
        const color = boxColor(box);
        ctx.strokeStyle = color;
        ctx.lineWidth = index === activeIndex ? 5 : 3;
        ctx.strokeRect(x, y, w, h);
        ctx.fillStyle = color;
        ctx.globalAlpha = clamp01(Number(state.ideogram_box_opacity ?? 18) / 100);
        ctx.fillRect(x, y, w, h);
        ctx.globalAlpha = 1;
        if (state.ideogram_show_text !== false) {
          ctx.fillStyle = "#ffffff";
          ctx.font = "24px sans-serif";
          ctx.fillText(String(index + 1), x + 8, y + 28);
          const label = box.type === "text" && box.text ? box.text : box.desc;
          if (label) ctx.fillText(String(label).slice(0, 32), x + 8, Math.min(y + h - 12, y + 58));
        }
        if (index === activeIndex) {
          const handle = Math.max(8, Math.min(14, Math.min(canvasWidth, canvasHeight) * 0.012));
          ctx.fillStyle = "#ffffff";
          ctx.strokeStyle = "#10151a";
          ctx.lineWidth = 2;
          [
            [x, y],
            [x + w, y],
            [x, y + h],
            [x + w, y + h],
          ].forEach(([hx, hy]) => {
            ctx.beginPath();
            ctx.rect(hx - handle / 2, hy - handle / 2, handle, handle);
            ctx.fill();
            ctx.stroke();
          });
        }
      }
    }

    function dims() {
      return [round16(state.ideogram_width), round16(state.ideogram_height)];
    }

    function boxToPx(box) {
      const [width, height] = dims();
      return [
        Math.round(box.y * height),
        Math.round(box.x * width),
        Math.round((box.y + box.h) * height),
        Math.round((box.x + box.w) * width),
      ];
    }

    function boxToGrid(box) {
      return [
        Math.round(box.y * 1000),
        Math.round(box.x * 1000),
        Math.round((box.y + box.h) * 1000),
        Math.round((box.x + box.w) * 1000),
      ];
    }

    function parseBboxNumbers(input) {
      const numbers = input.value.split(/[,\s]+/).map(Number).filter((number) => !Number.isNaN(number));
      return numbers.length === 4 ? numbers : null;
    }

    function makeBboxField(placeholder, title, onCommit) {
      const input = document.createElement("input");
      input.type = "text";
      input.className = "workflowx-uap-ideo-bbox";
      input.placeholder = placeholder;
      input.title = title;
      stopEditorEvents(input);
      input.addEventListener("keydown", (event) => {
        event.stopPropagation();
        if (event.key === "Enter") input.blur();
        else if (event.key === "Escape") {
          renderPanel();
          input.blur();
        }
      });
      input.addEventListener("change", onCommit);
      return input;
    }

    function makePanelArea(value, placeholder, onInput) {
      const textarea = document.createElement("textarea");
      textarea.className = "workflowx-uap-ideo-area";
      textarea.placeholder = placeholder;
      textarea.value = value || "";
      stopEditorEvents(textarea);
      textarea.addEventListener("input", onInput);
      return textarea;
    }

    function renderPanel() {
      panel.replaceChildren();
      if (!boxes.length) {
        panel.appendChild(buildDom("div", "workflowx-uap-ideo-empty", "No regions yet."));
        return;
      }
      const box = activeBox();
      if (!box) {
        panel.appendChild(buildDom("div", "workflowx-uap-ideo-empty", "Click a region to edit it."));
        return;
      }

      const hint = buildDom("div", "workflowx-uap-ideo-panel-hint");
      const tag = document.createElement("b");
      tag.style.color = boxColor(box);
      tag.textContent = `region ${activeIndex + 1}`;
      hint.appendChild(tag);
      panel.appendChild(hint);

      const typeRow = buildDom("div", "workflowx-uap-ideo-active-row");
      typeRow.appendChild(buildDom("span", "", "type:"));
      for (const type of ["obj", "text"]) {
        const button = buildDom("button", `workflowx-uap-btn${box.type === type ? " active" : ""}`, type);
        button.type = "button";
        stopEditorEvents(button);
        button.addEventListener("click", () => {
          box.type = type;
          commitIdeogramState();
          renderAll();
        });
        typeRow.appendChild(button);
      }
      typeRow.appendChild(buildDom("span", "", "px:"));
      const pxField = makeBboxField("ymin, xmin, ymax, xmax", "Pixel bbox: ymin, xmin, ymax, xmax", () => {
        const nums = parseBboxNumbers(pxField);
        if (!nums) {
          pxField.value = boxToPx(box).join(", ");
          return;
        }
        const [width, height] = dims();
        let [ymin, xmin, ymax, xmax] = nums;
        ymin = Math.max(0, Math.min(height, ymin));
        ymax = Math.max(0, Math.min(height, ymax));
        xmin = Math.max(0, Math.min(width, xmin));
        xmax = Math.max(0, Math.min(width, xmax));
        if (ymin > ymax) [ymin, ymax] = [ymax, ymin];
        if (xmin > xmax) [xmin, xmax] = [xmax, xmin];
        box.y = ymin / height;
        box.x = xmin / width;
        box.h = Math.max(0.01, (ymax - ymin) / height);
        box.w = Math.max(0.01, (xmax - xmin) / width);
        normalizeBox(box);
        commitIdeogramState();
        renderAll();
      });
      pxField.value = boxToPx(box).join(", ");
      typeRow.appendChild(pxField);
      typeRow.appendChild(buildDom("span", "", "out:"));
      const gridField = makeBboxField("ymin, xmin, ymax, xmax", "Exported 0-1000 bbox: ymin, xmin, ymax, xmax", () => {
        const nums = parseBboxNumbers(gridField);
        if (!nums) {
          gridField.value = boxToGrid(box).join(", ");
          return;
        }
        let [ymin, xmin, ymax, xmax] = nums.map((number) => Math.max(0, Math.min(1000, number)));
        if (ymin > ymax) [ymin, ymax] = [ymax, ymin];
        if (xmin > xmax) [xmin, xmax] = [xmax, xmin];
        box.y = ymin / 1000;
        box.x = xmin / 1000;
        box.h = Math.max(0.01, (ymax - ymin) / 1000);
        box.w = Math.max(0.01, (xmax - xmin) / 1000);
        normalizeBox(box);
        commitIdeogramState();
        renderAll();
      });
      gridField.value = boxToGrid(box).join(", ");
      typeRow.appendChild(gridField);
      panel.appendChild(typeRow);

      if (box.type === "text") {
        panel.appendChild(makePanelArea(box.text, "text to render (verbatim)", function onTextInput() {
          box.text = this.value;
          commitIdeogramState();
          renderCanvas();
        }));
      }
      panel.appendChild(makePanelArea(box.desc, "description of this region", function onDescInput() {
        box.desc = this.value;
        commitIdeogramState();
        renderCanvas();
      }));

      const paletteRow = buildDom("div", "workflowx-uap-ideo-active-row");
      paletteRow.appendChild(buildDom("span", "", "colors:"));
      box.palette ||= [];
      buildSwatchRow(paletteRow, box.palette, IDEOGRAM_MAX_ELEM_COLORS, () => {
        commitIdeogramState();
        renderCanvas();
      }, () => {
        commitIdeogramState();
        renderPanel();
        renderCanvas();
      });
      panel.appendChild(paletteRow);
    }

    function renderAll() {
      renderStyleBar();
      renderCanvas();
      renderPanel();
    }
    node.__workflowXUapRenderIdeogram = renderAll;
    let canvasResizeObserver = null;
    try {
      canvasResizeObserver = new ResizeObserver(() => renderCanvas());
      canvasResizeObserver.observe(cvBox);
      canvasResizeObserver.observe(dock.dock);
    } catch {
      canvasResizeObserver = null;
    }

    function eventPoint(event) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: clamp01((event.clientX - rect.left) / rect.width),
        y: clamp01((event.clientY - rect.top) / rect.height),
      };
    }

    function normalizeBox(box) {
      if (!box) return box;
      let { x, y, w, h } = box;
      if (w < 0) {
        x += w;
        w = -w;
      }
      if (h < 0) {
        y += h;
        h = -h;
      }
      x = clamp01(x);
      y = clamp01(y);
      w = Math.min(Math.max(0.01, w), 1 - x);
      h = Math.min(Math.max(0.01, h), 1 - y);
      Object.assign(box, { x, y, w, h });
      return box;
    }

    function hitTest(point) {
      const handleX = Math.min(10 / Math.max(1, canvas.getBoundingClientRect().width), 0.04);
      const handleY = Math.min(10 / Math.max(1, canvas.getBoundingClientRect().height), 0.04);
      const handleHit = (pointValue, target, radius) => Math.abs(pointValue - target) <= radius;
      for (let index = 0; index < boxes.length; index += 1) {
        const box = boxes[index];
        const x1 = box.x;
        const y1 = box.y;
        const x2 = box.x + box.w;
        const y2 = box.y + box.h;
        if (point.x < x1 - handleX || point.x > x2 + handleX || point.y < y1 - handleY || point.y > y2 + handleY) continue;
        const nearL = handleHit(point.x, x1, handleX);
        const nearR = handleHit(point.x, x2, handleX);
        const nearT = handleHit(point.y, y1, handleY);
        const nearB = handleHit(point.y, y2, handleY);
        if (nearL && nearT) return { index, mode: "resize-tl" };
        if (nearR && nearT) return { index, mode: "resize-tr" };
        if (nearL && nearB) return { index, mode: "resize-bl" };
        if (nearR && nearB) return { index, mode: "resize-br" };
        if (nearL && point.y >= y1 && point.y <= y2) return { index, mode: "resize-l" };
        if (nearR && point.y >= y1 && point.y <= y2) return { index, mode: "resize-r" };
        if (nearT && point.x >= x1 && point.x <= x2) return { index, mode: "resize-t" };
        if (nearB && point.x >= x1 && point.x <= x2) return { index, mode: "resize-b" };
        if (point.x >= x1 && point.x <= x2 && point.y >= y1 && point.y <= y2) {
          return { index, mode: "move" };
        }
      }
      return null;
    }

    function closeInlineEditor() {
      inlineEditor?.remove();
      inlineEditor = null;
    }

    function openInlineEditor(index) {
      closeInlineEditor();
      const box = boxes[index];
      if (!box) return;
      activeIndex = index;
      const canvasRect = canvas.getBoundingClientRect();
      const boxRect = cvBox.getBoundingClientRect();
      const displayWidth = canvasRect.width;
      const displayHeight = canvasRect.height;
      const width = Math.min(displayWidth, Math.max(70, box.w * displayWidth));
      const height = Math.min(displayHeight, Math.max(42, box.h * displayHeight));
      const left = Math.max(0, Math.min((canvasRect.left - boxRect.left) + box.x * displayWidth, (canvasRect.left - boxRect.left) + displayWidth - width));
      const top = Math.max(0, Math.min((canvasRect.top - boxRect.top) + box.y * displayHeight, (canvasRect.top - boxRect.top) + displayHeight - height));
      const textarea = document.createElement("textarea");
      textarea.className = "workflowx-uap-ideo-inline";
      textarea.value = box.desc || "";
      textarea.style.left = `${left}px`;
      textarea.style.top = `${top}px`;
      textarea.style.width = `${width}px`;
      textarea.style.height = `${height}px`;
      textarea.style.borderColor = boxColor(box);
      stopEditorEvents(textarea);
      cvBox.appendChild(textarea);
      inlineEditor = textarea;
      textarea.focus();
      textarea.select();
      const original = box.desc || "";
      let cancelled = false;
      textarea.addEventListener("input", () => {
        box.desc = textarea.value;
        renderCanvas();
        updateTokenEstimate();
      });
      textarea.addEventListener("keydown", (event) => {
        event.stopPropagation();
        if (event.key === "Escape") {
          cancelled = true;
          box.desc = original;
          textarea.blur();
        } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
          textarea.blur();
        }
      });
      textarea.addEventListener("blur", () => {
        if (!cancelled) box.desc = textarea.value;
        closeInlineEditor();
        commitIdeogramState();
        renderAll();
      });
    }

    function closeLayerMenu() {
      layerMenu?.remove();
      layerMenu = null;
    }

    function renderLayerMenuRows(list) {
      list.replaceChildren();
      if (!boxes.length) {
        list.appendChild(buildDom("div", "workflowx-uap-ideo-layer-header", "No regions yet."));
        return;
      }
      boxes.forEach((box, index) => {
        const row = buildDom("div", `workflowx-uap-ideo-layer-row${index === activeIndex ? " active" : ""}`);
        row.__workflowXBox = box;
        const swatch = buildDom("div", "workflowx-uap-ideo-layer-swatch");
        swatch.style.background = boxColor(box);
        const num = buildDom("span", "workflowx-uap-ideo-layer-num", String(index + 1).padStart(2, "0"));
        const text = buildDom("span", `workflowx-uap-ideo-layer-text${boxLabel(box, index) ? "" : " empty"}`, boxLabel(box, index));
        text.title = boxLabel(box, index);
        const lock = buildDom("button", `workflowx-uap-ideo-layer-btn${box.locked ? " on" : ""}`, box.locked ? "lock" : "open");
        const duplicate = buildDom("button", "workflowx-uap-ideo-layer-btn", "copy");
        const remove = buildDom("button", "workflowx-uap-ideo-layer-btn", "x");
        for (const button of [lock, duplicate, remove]) button.type = "button";
        row.appendChild(swatch);
        row.appendChild(num);
        row.appendChild(text);
        row.appendChild(lock);
        row.appendChild(duplicate);
        row.appendChild(remove);
        list.appendChild(row);

        row.addEventListener("click", () => {
          if (row.__workflowXDragged) {
            row.__workflowXDragged = false;
            return;
          }
          activeIndex = boxes.indexOf(box);
          renderAll();
          renderLayerMenuRows(list);
        });
        lock.addEventListener("click", (event) => {
          event.stopPropagation();
          box.locked = !box.locked;
          commitIdeogramState();
          renderAll();
          renderLayerMenuRows(list);
        });
        duplicate.addEventListener("click", (event) => {
          event.stopPropagation();
          boxes.push({ ...box, palette: [...(box.palette || [])], x: clamp01(box.x + 0.04), y: clamp01(box.y + 0.04), locked: false });
          activeIndex = boxes.length - 1;
          commitIdeogramState();
          renderAll();
          renderLayerMenuRows(list);
        });
        remove.addEventListener("click", (event) => {
          event.stopPropagation();
          if (box.locked) return;
          const current = boxes.indexOf(box);
          if (current >= 0) boxes.splice(current, 1);
          activeIndex = Math.min(activeIndex, boxes.length - 1);
          commitIdeogramState();
          renderAll();
          renderLayerMenuRows(list);
        });
        row.addEventListener("pointerdown", (event) => {
          if (event.button !== 0 || [lock, duplicate, remove].includes(event.target)) return;
          event.preventDefault();
          event.stopPropagation();
          const startX = event.clientX;
          const startY = event.clientY;
          let draggingRow = false;
          const move = (moveEvent) => {
            if (!draggingRow) {
              if (Math.abs(moveEvent.clientX - startX) + Math.abs(moveEvent.clientY - startY) < 4) return;
              draggingRow = true;
              row.classList.add("dragging");
            }
            for (const other of list.querySelectorAll(".workflowx-uap-ideo-layer-row")) {
              if (other === row) continue;
              const rect = other.getBoundingClientRect();
              if (moveEvent.clientY >= rect.top && moveEvent.clientY <= rect.bottom) {
                const ref = moveEvent.clientY > rect.top + rect.height / 2 ? other.nextSibling : other;
                if (ref === row || ref === row.nextSibling) break;
                list.insertBefore(row, ref);
                break;
              }
            }
          };
          const up = () => {
            document.removeEventListener("pointermove", move, true);
            document.removeEventListener("pointerup", up, true);
            document.removeEventListener("pointercancel", up, true);
            if (draggingRow) {
              row.classList.remove("dragging");
              row.__workflowXDragged = true;
              const activeBoxBefore = activeBox();
              const nextOrder = Array.from(list.querySelectorAll(".workflowx-uap-ideo-layer-row"))
                .map((item) => item.__workflowXBox)
                .filter(Boolean);
              if (nextOrder.length === boxes.length) boxes.splice(0, boxes.length, ...nextOrder);
              activeIndex = activeBoxBefore ? boxes.indexOf(activeBoxBefore) : -1;
              commitIdeogramState();
              renderAll();
              renderLayerMenuRows(list);
            }
          };
          document.addEventListener("pointermove", move, true);
          document.addEventListener("pointerup", up, true);
          document.addEventListener("pointercancel", up, true);
        });
      });
    }

    function openLayerMenu(clientX, clientY) {
      closeLayerMenu();
      const menu = buildDom("div", "workflowx-uap-ideo-layer-menu");
      menu.appendChild(buildDom("div", "workflowx-uap-ideo-layer-header", "Regions - top = front - click select - drag reorder"));
      const list = buildDom("div");
      menu.appendChild(list);
      document.body.appendChild(menu);
      layerMenu = menu;
      renderLayerMenuRows(list);
      const rect = menu.getBoundingClientRect();
      const left = Math.max(4, Math.min(clientX, window.innerWidth - rect.width - 4));
      const top = Math.max(4, Math.min(clientY, window.innerHeight - rect.height - 4));
      menu.style.left = `${left}px`;
      menu.style.top = `${top}px`;
      const dismiss = (event) => {
        if (menu.contains(event.target)) return;
        closeLayerMenu();
        document.removeEventListener("mousedown", dismiss, true);
      };
      setTimeout(() => document.addEventListener("mousedown", dismiss, true), 0);
    }

    canvas.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      closeInlineEditor();
      const point = eventPoint(event);
      const hit = hitTest(point);
      if (hit) {
        activeIndex = hit.index;
        if (boxes[hit.index]?.locked) {
          renderAll();
          return;
        }
        draggingBox = {
          mode: hit.mode,
          start: point,
          box: { ...boxes[activeIndex] },
        };
        canvas.setPointerCapture?.(event.pointerId);
        renderAll();
        return;
      }
      drawing = { x: point.x, y: point.y };
      const box = {
        type: "obj",
        text: "",
        desc: "",
        palette: stylePalette[0] ? [stylePalette[0]] : [],
        x: point.x,
        y: point.y,
        w: 0.04,
        h: 0.04,
      };
      boxes.push(box);
      activeIndex = boxes.length - 1;
      commitIdeogramState();
      renderAll();
    });
    canvas.addEventListener("dblclick", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const hit = hitTest(eventPoint(event));
      if (hit) openInlineEditor(hit.index);
    });
    canvas.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      closeInlineEditor();
      openLayerMenu(event.clientX, event.clientY);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (draggingBox && activeIndex >= 0) {
        const point = eventPoint(event);
        const dx = point.x - draggingBox.start.x;
        const dy = point.y - draggingBox.start.y;
        const box = activeBox();
        const start = draggingBox.box;
        if (draggingBox.mode === "move") {
          box.x = start.x + dx;
          box.y = start.y + dy;
        } else {
          let x1 = start.x;
          let y1 = start.y;
          let x2 = start.x + start.w;
          let y2 = start.y + start.h;
          if (draggingBox.mode.includes("l")) x1 += dx;
          if (draggingBox.mode.includes("r")) x2 += dx;
          if (draggingBox.mode.includes("t")) y1 += dy;
          if (draggingBox.mode.includes("b")) y2 += dy;
          box.x = x1;
          box.y = y1;
          box.w = x2 - x1;
          box.h = y2 - y1;
        }
        normalizeBox(box);
        commitIdeogramState();
        renderAll();
        return;
      }
      if (!drawing || activeIndex < 0) return;
      const point = eventPoint(event);
      const box = activeBox();
      box.x = Math.min(drawing.x, point.x);
      box.y = Math.min(drawing.y, point.y);
      box.w = Math.max(0.02, Math.abs(point.x - drawing.x));
      box.h = Math.max(0.02, Math.abs(point.y - drawing.y));
      commitIdeogramState();
      renderAll();
    });
    canvas.addEventListener("pointerup", (event) => {
      drawing = null;
      draggingBox = null;
      canvas.releasePointerCapture?.(event.pointerId);
    });
    canvas.addEventListener("pointercancel", (event) => {
      drawing = null;
      draggingBox = null;
      canvas.releasePointerCapture?.(event.pointerId);
    });

    bgBtn.addEventListener("click", () => showMenu(bgMenu, bgBtn));
    textBtn.addEventListener("click", () => showMenu(textMenu, textBtn));
    templatesBtn.addEventListener("click", async () => {
      await buildTemplatesMenu();
      showMenu(templatesMenu, templatesBtn);
    });
    copyBtn.addEventListener("click", () => navigator.clipboard?.writeText?.(ideogramLayoutArea.value || JSON.stringify(buildCaption(), null, 2)));
    applyBtn.addEventListener("click", applyIdeogramLayoutToOutput);
    syncBtn.addEventListener("click", () => {
      const caption = activeIdeogramCaption();
      if (!hasCaptionContent(caption)) {
        setStatus("No Ideogram JSON available to sync.", true);
        return;
      }
      loadCaption(caption, false);
      setStatus("Ideogram layout synced.");
    });
    clearBtn.addEventListener("click", () => {
      closeInlineEditor();
      closeLayerMenu();
      boxes.splice(0, boxes.length);
      stylePalette.splice(0, stylePalette.length);
      activeIndex = -1;
      commitIdeogramState();
      renderAll();
    });
    highInput.addEventListener("input", () => {
      highLevelDescription = highInput.value;
      commitIdeogramState();
    });
    bgInput.addEventListener("input", () => {
      backgroundDescription = bgInput.value;
      commitIdeogramState();
    });
    overlayInput.addEventListener("change", () => {
      state.ideogram_overlay_visible = overlayInput.checked;
      syncPreview();
      renderCanvas();
    });
    brightnessInput.addEventListener("input", () => {
      state.ideogram_overlay_brightness = Number(brightnessInput.value || 35);
      syncPreview();
      renderCanvas();
    });
    widthInput.addEventListener("change", () => setResolution(widthInput.value, state.ideogram_height, true));
    heightInput.addEventListener("change", () => setResolution(state.ideogram_width, heightInput.value, true));
    widthInput.addEventListener("input", () => {
      state.ideogram_width = round16(widthInput.value);
      state.ideogram_manual_dims = true;
      manualDimsInput.checked = true;
      syncPreview();
    });
    heightInput.addEventListener("input", () => {
      state.ideogram_height = round16(heightInput.value);
      state.ideogram_manual_dims = true;
      manualDimsInput.checked = true;
      syncPreview();
    });
    manualDimsInput.addEventListener("change", () => {
      state.ideogram_manual_dims = manualDimsInput.checked;
      syncPreview();
    });
    showTextInput.addEventListener("change", () => {
      state.ideogram_show_text = showTextInput.checked;
      syncPreview();
      renderCanvas();
    });
    opacityInput.addEventListener("input", () => {
      state.ideogram_box_opacity = Number(opacityInput.value || 18);
      syncPreview();
      renderCanvas();
    });
    splitter.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const startY = event.clientY;
      const startHeight = panel.offsetHeight;
      const move = (moveEvent) => {
        const height = Math.max(
          IDEOGRAM_PANEL_MIN_HEIGHT,
          Math.min(IDEOGRAM_PANEL_MAX_HEIGHT, startHeight - (moveEvent.clientY - startY))
        );
        state.ideogram_panel_height = Math.round(height);
        panel.style.height = `${state.ideogram_panel_height}px`;
        syncPreview();
      };
      const up = () => {
        document.removeEventListener("pointermove", move, true);
        document.removeEventListener("pointerup", up, true);
      };
      document.addEventListener("pointermove", move, true);
      document.addEventListener("pointerup", up, true);
    });

    if (hasCaptionContent(parsed)) commitIdeogramState();
    else updateTokenEstimate();
    renderAll();
  }

  async function fetchGeminiModels() {
    state.gemini_key = keyInput.value.trim();
    storeGeminiKey(state.gemini_key);
    if (!state.gemini_key) {
      setStatus("Enter a Gemini API key first.", true);
      return;
    }
    fetchGeminiBtn.disabled = true;
    setStatus("Fetching Gemini models...");
    try {
      const response = await fetch(`${ROUTE}/gemini/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: state.gemini_key, timeout: Number(timeoutInput.value || 120) }),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
      fillModelSelect(geminiModelSelect, data.models, state.gemini_model);
      if (!geminiModelSelect.value && geminiModelSelect.options.length) geminiModelSelect.selectedIndex = 0;
      state.gemini_model = geminiModelSelect.value;
      persistModelSelection();
      syncPreview();
      setStatus(`${data.models.length} Gemini models loaded.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchGeminiBtn.disabled = false;
    }
  }

  async function fetchOllamaModels() {
    fetchOllamaBtn.disabled = true;
    setStatus("Fetching Ollama models...");
    try {
      const response = await fetch(`${ROUTE}/ollama/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host: hostInput.value || DEFAULT_OLLAMA_HOST }),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
      fillModelSelect(ollamaModelSelect, data.models, state.ollama_model);
      if (!ollamaModelSelect.value && ollamaModelSelect.options.length) ollamaModelSelect.selectedIndex = 0;
      state.ollama_model = ollamaModelSelect.value;
      persistModelSelection();
      syncPreview();
      setStatus(`${data.models.length} Ollama models loaded.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchOllamaBtn.disabled = false;
    }
  }

  async function fetchLocalModels() {
    fetchLocalBtn.disabled = true;
    setStatus("Refreshing local GGUF files...");
    try {
      const response = await fetch(`${ROUTE}/local/models`);
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
      setSelectOptions(localModelSelect, data.models || [], state.local_model);
      setSelectOptions(mmprojSelect, data.mmproj || ["none"], state.local_mmproj);
      setSelectOptions(systemPresetSelect, data.system_prompts || ["none"], state.local_system_prompt_preset);
      state.local_model = localModelSelect.value || "";
      state.local_mmproj = mmprojSelect.value || "none";
      state.local_system_prompt_preset = systemPresetSelect.value || "none";
      persistModelSelection();
      syncPreview();
      setStatus("Local model list refreshed.");
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchLocalBtn.disabled = false;
    }
  }

  async function generatePrompt() {
    readFieldsIntoState();
    const hasTextSeed = Boolean(state.idea.trim() || state.subject.trim());
    const hasConnectedImage = Boolean(state.connected_image_b64);
    const hasUnresolvedConnectedImage = Boolean(
      node.inputs?.some((input) => input.name === "image" && input.link != null) && !hasConnectedImage
    );
    if (!hasTextSeed && !hasConnectedImage) {
      setStatus(
        hasUnresolvedConnectedImage
          ? "Connected image has no preview yet. Run or refresh the upstream image node first."
          : "Enter an idea, subject, or connect an image.",
        true,
      );
      return;
    }

    const payload = {
      backend: state.backend,
      target_model: state.target_model,
      prompt_format: state.prompt_format,
      negative_enabled: state.negative_enabled,
      image_b64: state.connected_image_b64 || "",
      fields: {
        idea: state.idea,
        subject: state.subject,
        style: state.style,
        lighting: state.lighting,
        composition: state.composition,
        text: state.text,
        detail: state.detail,
        image_note: state.image_note,
        ideogram_layout: state.target_model === "ideogram4" ? state.ideogram_layout : "",
        ideogram_palette: state.target_model === "ideogram4" ? state.ideogram_palette : "",
        video_duration_or_frames: profileIsVideo(activeProfile()) ? state.video_duration_or_frames : "",
        motion_action: profileIsVideo(activeProfile()) ? state.motion_action : "",
        temporal_beats: profileIsVideo(activeProfile()) ? state.temporal_beats : "",
        camera_movement: profileIsVideo(activeProfile()) ? state.camera_movement : "",
        audio_dialogue: profileIsVideo(activeProfile()) ? state.audio_dialogue : "",
        reference_or_control_notes: profileIsVideo(activeProfile()) ? state.reference_or_control_notes : "",
        extra_instructions: state.extra_instructions,
      },
      timeout: state.gemini_timeout,
    };

    if (state.backend === "gemini") {
      state.gemini_key = keyInput.value.trim();
      storeGeminiKey(state.gemini_key);
      if (!state.gemini_key || !geminiModelSelect.value) {
        setStatus("Set a Gemini key and model first.", true);
        return;
      }
      payload.api_key = state.gemini_key;
      payload.model = geminiModelSelect.value;
      state.gemini_model = geminiModelSelect.value;
    } else if (state.backend === "ollama") {
      if (!ollamaModelSelect.value) {
        setStatus("Fetch and select an Ollama model first.", true);
        return;
      }
      payload.host = state.ollama_host || DEFAULT_OLLAMA_HOST;
      payload.model = ollamaModelSelect.value;
      payload.think = state.ollama_think;
      payload.unload_after = state.unload_after;
      state.ollama_model = ollamaModelSelect.value;
    } else {
      if (!localModelSelect.value) {
        setStatus("Refresh and select a local GGUF model first.", true);
        return;
      }
      payload.model = localModelSelect.value;
      payload.mmproj = mmprojSelect.value || "none";
      payload.system_prompt_preset = systemPresetSelect.value || "none";
      payload.local_options = {
        max_tokens: state.max_tokens,
        temperature: state.temperature,
        top_p: state.top_p,
        top_k: state.top_k,
        ctx_size: state.ctx_size,
        memory_mode: state.memory_mode,
        n_gpu_layers: state.n_gpu_layers,
        n_cpu_moe_layers: state.n_cpu_moe_layers,
        reasoning: state.reasoning,
        seed: state.seed,
        timeout: state.gemini_timeout,
      };
    }

    persistModelSelection();
    setBusy(true);
    setStatus("Generating...");
    try {
      const response = await fetch(`${ROUTE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
      state.generated_positive = data.positive || "";
      state.generated_negative = data.negative || "";
      state.final_prompt = data.prompt || "";
      state.prompt_format = data.prompt_format || state.prompt_format;
      state.negative_enabled = Boolean(data.negative_enabled);
      state.last_generation = {
        prompt: state.final_prompt,
        positive: state.generated_positive,
        negative: state.generated_negative,
        target_model: state.target_model,
        prompt_format: state.prompt_format,
        negative_enabled: state.negative_enabled,
        generated_at: new Date().toISOString(),
      };
      syncPreview();
      setStatus("Prompt generated.");
    } catch (error) {
      syncPreview();
      setStatus(`Error: ${error.message}. Previous output kept.`, true);
    } finally {
      setBusy(false);
    }
  }

  const stateInputs = [
    targetSelect,
    formatSelect,
    ideaArea,
    subjectArea,
    styleInput,
    lightingInput,
    compositionInput,
    textInput,
    detailSelect,
    imageNoteInput,
    videoDurationInput,
    motionActionArea,
    temporalBeatsArea,
    cameraMovementInput,
    audioDialogueArea,
    controlNotesArea,
    ideogramLayoutArea,
    ideogramPaletteInput,
    extraArea,
    timeoutInput,
    hostInput,
    thinkInput,
    unloadInput,
    localModelSelect,
    mmprojSelect,
    systemPresetSelect,
    maxTokensInput,
    tempInput,
    ctxInput,
    memorySelect,
    reasoningSelect,
    negativeInput,
  ];
  for (const input of stateInputs) {
    input.addEventListener("input", syncPreview);
    input.addEventListener("change", syncPreview);
  }

  targetSelect.addEventListener("change", () => {
    state.target_model = targetSelect.value;
    state.final_prompt = "";
    refreshFormats();
  });
  formatSelect.addEventListener("change", () => {
    state.prompt_format = formatSelect.value;
    state.final_prompt = "";
    syncPreview();
  });
  negativeInput.addEventListener("change", () => {
    state.negative_enabled = negativeInput.checked;
    state.final_prompt = "";
    syncPreview();
  });
  geminiBtn.addEventListener("click", () => {
    state.backend = "gemini";
    refreshBackends();
    persistModelSelection();
    syncPreview();
  });
  ollamaBtn.addEventListener("click", () => {
    state.backend = "ollama";
    refreshBackends();
    persistModelSelection();
    syncPreview();
  });
  localBtn.addEventListener("click", () => {
    state.backend = "local";
    refreshBackends();
    persistModelSelection();
    syncPreview();
  });
  keyInput.addEventListener("input", () => {
    state.gemini_key = keyInput.value;
    storeGeminiKey(state.gemini_key);
  });
  geminiModelSelect.addEventListener("change", () => {
    state.gemini_model = geminiModelSelect.value;
    persistModelSelection();
    syncPreview();
  });
  ollamaModelSelect.addEventListener("change", () => {
    state.ollama_model = ollamaModelSelect.value;
    persistModelSelection();
    syncPreview();
  });
  localModelSelect.addEventListener("change", () => {
    state.local_model = localModelSelect.value || "";
    persistModelSelection();
  });
  fetchGeminiBtn.addEventListener("click", fetchGeminiModels);
  fetchOllamaBtn.addEventListener("click", fetchOllamaModels);
  fetchLocalBtn.addEventListener("click", fetchLocalModels);
  positivePreviewBtn.addEventListener("click", () => toggleOutputPreview("positive"));
  negativePreviewBtn.addEventListener("click", () => toggleOutputPreview("negative"));
  ideogramBtn.addEventListener("click", openIdeogramLayoutEditor);
  modelSettingsBtn.addEventListener("click", openModelSettingsModalV3);
  generateBtn.addEventListener("click", generatePrompt);

  const hasConnectedImageInput = () => Boolean(
    node.inputs?.some((input) => input.name === "image" && input.link != null)
  );

  const setConnectedImageDataUrl = (dataUrl) => {
    state.connected_image_b64 = dataUrl || "";
    state.connected_image_available = Boolean(dataUrl);
    syncPreview();
  };

  const canvasToConnectedImage = (canvas) => {
    try {
      setConnectedImageDataUrl(canvas.toDataURL("image/png"));
    } catch (error) {
      console.warn("[WorkflowX Unified Autoprompter] Could not convert connected image to base64", error);
      setConnectedImageDataUrl("");
    }
  };

  const imageToConnectedDataUrl = (img) => {
    try {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth || img.width || 1;
      canvas.height = img.naturalHeight || img.height || 1;
      canvas.getContext("2d")?.drawImage(img, 0, 0);
      canvasToConnectedImage(canvas);
    } catch (error) {
      console.warn("[WorkflowX Unified Autoprompter] Could not capture connected image", error);
      setConnectedImageDataUrl("");
    }
  };

  const loadOverlayImage = (src, dataUrl = "") => {
    if (!src) {
      node.__workflowXUapOverlayImage = null;
      state.connected_image_url = "";
      setConnectedImageDataUrl("");
      node.__workflowXUapOnOverlayImageLoad?.(null);
      node.__workflowXUapRenderIdeogram?.();
      if (hasConnectedImageInput()) {
        setStatus("Connected image has no preview yet. Run or refresh the upstream image node first.", true);
      }
      return;
    }
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      node.__workflowXUapOverlayImage = img;
      state.connected_image_url = src;
      if (dataUrl) setConnectedImageDataUrl(dataUrl);
      else imageToConnectedDataUrl(img);
      node.__workflowXUapOnOverlayImageLoad?.(img);
      node.__workflowXUapRenderIdeogram?.();
      setStatus(`Connected image loaded: ${img.naturalWidth || img.width || 0} x ${img.naturalHeight || img.height || 0}.`);
    };
    img.onerror = () => {
      node.__workflowXUapOverlayImage = null;
      state.connected_image_url = "";
      setConnectedImageDataUrl("");
      node.__workflowXUapOnOverlayImageLoad?.(null);
      node.__workflowXUapRenderIdeogram?.();
      setStatus("Connected image preview could not be loaded.", true);
    };
    img.src = src;
  };
  const unwatchImageInput = watchImageInputs(node, "image", (sources) => {
    const source = sources?.[0];
    if (!source) {
      loadOverlayImage("");
    } else if (source.isVideo && source.videoEl) {
      captureVideoFrame(source.videoEl, (canvas) => {
        const dataUrl = canvas.toDataURL("image/png");
        loadOverlayImage(dataUrl, dataUrl);
      });
    } else if (source.url && !source.isVideo) {
      loadOverlayImage(source.url);
    }
  });

  node.__workflowXUapWidgetHeight = NODE_MIN_WIDGET_HEIGHT;
  node.__workflowXUapWidget = node.addDOMWidget("unified_autoprompter_x", "Unified Autoprompter X", wrap, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => node.__workflowXUapWidgetHeight || NODE_MIN_WIDGET_HEIGHT,
  });
  node.resizable = true;

  chainCallback(node, "onRemoved", () => {
    unwatchImageInput?.();
    closeDock(node, "output_positive");
    closeDock(node, "output_negative");
    closeDock(node, "ideogram");
  });

  loadProfiles().then((loadedProfiles) => {
    profiles = loadedProfiles;
    profilesByKey = profileMap(profiles);
    refreshProfiles();
    refreshBackends();
    syncPreview();
    setTimeout(fetchLocalModels, 0);
    requestAnimationFrame(resizeNodeToVisibleContent);
  });
}

app.registerExtension({
  name: "WorkflowX.UnifiedAutoprompterX",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TARGET_NODE) return;

    chainCallback(nodeType.prototype, "onNodeCreated", function workflowXUnifiedCreated() {
      setupUnifiedAutoprompter(this);
    });

    chainCallback(nodeType.prototype, "onConfigure", function workflowXUnifiedConfigured() {
      setTimeout(() => setupUnifiedAutoprompter(this), 0);
    });
  },
});
