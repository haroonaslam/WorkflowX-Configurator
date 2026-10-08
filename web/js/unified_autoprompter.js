import { app } from "../../scripts/app.js";
import { graphDockScreenRect } from "./workflowx_graph_dock.mjs";

const TARGET_NODE = "UnifiedAutoprompterX";
const ROUTE = "/workflowx/unified_autoprompter";
const FRONTEND_SCHEMA_VERSION = 8;
const GENERAL_SCHEMA_VERSION = 1;
const GENERAL_PROFILE = { key: "general", label: "General", engine: "general", default_format: "natural", formats: { natural: { enabled: true } } };
const REFERENCE_SCHEMA_VERSION = 2;
const JSONX_REFERENCE_SCHEMA_VERSION = 1;
const PRESET_SCHEMA_VERSION = 1;
const GEMINI_KEY_STORAGE_KEY = "workflowx_unified_autoprompter_gemini_api_key";
const OPENAI_KEY_STORAGE_KEY = "workflowx_unified_autoprompter_openai_api_key";
const GROK_KEY_STORAGE_KEY = "workflowx_unified_autoprompter_grok_api_key";
const DEEPSEEK_KEY_STORAGE_KEY = "workflowx_unified_autoprompter_deepseek_api_key";
const OPENAI_BASE_URL_STORAGE_KEY = "workflowx_unified_autoprompter_openai_base_url";
const MODEL_SELECTION_STORAGE_KEY = "workflowx_unified_autoprompter_model_selection";
const ADDITIONAL_LOCAL_MODEL_PATHS_STORAGE_KEY = "workflowx_unified_autoprompter_additional_local_model_paths";
const IDEOGRAM_TEMPLATE_STORAGE_KEY = "workflowx_unified_autoprompter_ideogram_templates";
const IDEOGRAM_TEMPLATE_DIR = "workflowx/unified-autoprompter/ideogram4/templates";
const DEFAULT_OLLAMA_HOST = "http://localhost:11434";
const DEFAULT_OPENAI_BASE_URL = "http://localhost:1234/v1";
const IDEOGRAM_MAX_ELEM_COLORS = 5;
const IDEOGRAM_MAX_STYLE_COLORS = 16;
const IDEOGRAM_PANEL_DEFAULT_HEIGHT = 176;
const IDEOGRAM_PANEL_MIN_HEIGHT = 132;
const IDEOGRAM_PANEL_MAX_HEIGHT = 340;
const ALL_PROMPT_FORMATS = ["natural", "tags", "json"];
const REFERENCE_IMAGE_RE = /^image_(\d+)$/;
const MAX_REFERENCE_IMAGES = 9;
const GEMINI_SAFETY_OPTIONS = [
  "BLOCK_DEFAULT",
  "BLOCK_NONE",
  "BLOCK_LOW_AND_ABOVE",
  "BLOCK_MEDIUM_AND_ABOVE",
  "BLOCK_ONLY_HIGH",
];
const GEMINI_SAFETY_FIELDS = [
  ["safety_harassment", "Harassment"],
  ["safety_hate_speech", "Hate speech"],
  ["safety_sexual", "Sexual"],
  ["safety_dangerous", "Dangerous"],
];
const JSONX_ROUTE = `${ROUTE}/jsonx`;
const JSONX_SETTINGS_KEY = "workflowx_unified_jsonx_provider_settings";
const JSONX_GEMINI_KEY = "workflowx_unified_jsonx_gemini_api_key";
const JSONX_OPENAI_KEY = "workflowx_unified_jsonx_openai_api_key";
const JSONX_GROK_KEY = "workflowx_unified_jsonx_grok_api_key";
const JSONX_DEEPSEEK_KEY = "workflowx_unified_jsonx_deepseek_api_key";
const STANDARD_PROVIDER_SETTINGS_KEY = "workflowx_unified_provider_settings_v5";
const JSONX_PROVIDER_SETTINGS_KEY = "workflowx_unified_jsonx_provider_settings_v5";
const PROVIDERS = [
  ["gemini", "Gemini"],
  ["grok", "Grok API"],
  ["deepseek", "DeepSeek API"],
  ["openai", "OpenAI Compatible"],
  ["lm_studio", "LM Studio"],
  ["unsloth", "Unsloth Studio"],
  ["ollama", "Ollama"],
  ["local", "Local GGUF"],
];
const DEEPSEEK_VISION_MODELS = new Set(["deepseek-v4-flash-vision-exp"]);
function deepseekModelSupportsVision(modelId) {
  return DEEPSEEK_VISION_MODELS.has(String(modelId || "").trim().toLowerCase());
}
const GENERATION_TYPES = [
  ["text_to_image", "Text to Image", 0, 0],
  ["image_to_image", "Image to Image", 1, null],
  ["text_to_video", "Text to Video", 0, 0],
  ["first_frame_to_video", "First Frame to Video", 1, 1],
  ["first_last_frame_to_video", "First–Last Frame to Video", 2, 2],
  ["last_frame_to_video", "Last Frame to Video", 1, 1],
  ["reference_to_video", "Reference to Video", 1, null],
  ["video_to_video", "Video to Video", 1, null],
];
const MAX_AUTHORING_IMAGES = 9;
const IMAGE_STATE_KEYS = ["supported_with_image", "supported_without_image", "unsupported_with_image_guidance"];
const GENERATION_TYPE_MAP = new Map(GENERATION_TYPES.map(([value, label, min, max]) => [value, {
  value,
  label,
  min,
  max,
  supportsImages: max !== 0,
}]));

function loadProviderSettings(engine = "standard") {
  const key = engine === "jsonx" ? JSONX_PROVIDER_SETTINGS_KEY : STANDARD_PROVIDER_SETTINGS_KEY;
  try {
    const value = JSON.parse(localStorage.getItem(key) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function saveProviderSettings(engine, settings) {
  const key = engine === "jsonx" ? JSONX_PROVIDER_SETTINGS_KEY : STANDARD_PROVIDER_SETTINGS_KEY;
  localStorage.setItem(key, JSON.stringify(settings && typeof settings === "object" ? settings : {}));
}

function loadDedicatedApiKey(storageKey, legacyValue = "") {
  try {
    const stored = window.localStorage?.getItem(storageKey);
    if (stored !== null && stored !== undefined) return stored;
    const legacy = String(legacyValue || "");
    if (legacy) window.localStorage?.setItem(storageKey, legacy);
    return legacy;
  } catch {
    return String(legacyValue || "");
  }
}

function storeDedicatedApiKey(storageKey, value) {
  try {
    const key = String(value || "").trim();
    if (key) window.localStorage?.setItem(storageKey, key);
    else window.localStorage?.removeItem(storageKey);
  } catch {
    // Browser storage can be unavailable in restricted contexts.
  }
}

function withoutApiKey(settings) {
  const { api_key, ...safe } = settings && typeof settings === "object" ? settings : {};
  return safe;
}

function optionalNumber(value, integer = false) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;
  const number = integer ? Number.parseInt(text, 10) : Number(text);
  return Number.isFinite(number) ? number : undefined;
}

const JSONX_BEHAVIOR_KEYS = [
  "generation_profile", "generation_mode", "preset_context_mode", "template_use_presets",
  "enable_framing_and_placement", "detail_level",
];

function defaultJsonXConfig() {
  return {
    generation_profile: "adaptive",
    generation_mode: "fast",
    preset_context_mode: "optimized",
    template_use_presets: false,
    enable_framing_and_placement: false,
    detail_level: "deep",
  };
}

function jsonxBehaviorConfig(value = {}) {
  const source = value && typeof value === "object" ? value : {};
  const defaults = defaultJsonXConfig();
  return Object.fromEntries(JSONX_BEHAVIOR_KEYS.map((key) => [
    key,
    typeof defaults[key] === "boolean" ? Boolean(source[key] ?? defaults[key]) : String(source[key] || defaults[key]),
  ]));
}

function workflowJsonXProviderSettings(settings = {}) {
  const source = settings && typeof settings === "object" ? settings : {};
  if (!Object.keys(source).length) return {};
  const backend = PROVIDERS.some(([value]) => value === source.backend)
    ? source.backend
    : "gemini";
  return {
    backend,
    gemini_model: String(source.gemini_model || ""),
    gemini_timeout: Number(source.gemini_timeout || 180),
    gemini_safety: { ...(source.gemini_safety && typeof source.gemini_safety === "object" ? source.gemini_safety : {}) },
    openai_model: String(source.openai_model || ""),
    openai_timeout: Number(source.openai_timeout || 180),
    openai_server_type: normalizeOpenAIServerType(source.openai_server_type),
    openai_lifecycle: normalizeOpenAILifecycle(
      source.openai_lifecycle || (source.unload_after === true ? "unload_after" : "server_managed"),
    ),
    openai_reasoning_effort: normalizeOpenAIReasoning(source.openai_reasoning_effort),
    ollama_model: String(source.ollama_model || ""),
    ollama_timeout: Number(source.ollama_timeout || 180),
    ollama_think: Boolean(source.ollama_think),
    unload_after: source.unload_after !== false,
    local_model: String(source.local_model || ""),
    local_timeout: Number(source.local_timeout || 180),
    local_mmproj: String(source.local_mmproj || "none"),
    local_system_prompt_preset: String(source.local_system_prompt_preset || "none"),
    local_options: { ...(source.local_options && typeof source.local_options === "object" ? source.local_options : {}) },
  };
}

function normalizeOpenAIServerType(value) {
  const mode = String(value || "auto").toLowerCase().replaceAll("-", "_");
  if (mode === "lmstudio") return "lm_studio";
  if (mode === "unsloth_studio") return "unsloth";
  return ["auto", "generic", "lm_studio", "unsloth"].includes(mode) ? mode : "auto";
}

function normalizeOpenAILifecycle(value) {
  const mode = String(value || "server_managed").toLowerCase().replaceAll("-", "_");
  return ["server_managed", "keep_loaded", "unload_after"].includes(mode) ? mode : "server_managed";
}

function normalizeOpenAIReasoning(value) {
  let mode = String(value || "default").toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  if (mode === "off") mode = "none";
  if (mode === "extra_high") mode = "xhigh";
  return ["default", "none", "on", "minimal", "low", "medium", "high", "max", "xhigh"].includes(mode)
    ? mode
    : "default";
}

function normalizeUnifiedReasoning(value) {
  const mode = String(value || "auto").toLowerCase();
  if (mode === "none") return "off";
  if (["deepseek", "qwen3"].includes(mode)) return "auto";
  return ["auto", "on", "off"].includes(mode) ? mode : "auto";
}
const BBOX_LAYOUT_TARGETS = {
  ideogram4: { label: "Ideogram 4", order: "yx", orderLabel: "ymin, xmin, ymax, xmax" },
  krea2: { label: "Krea2", order: "xy", orderLabel: "xmin, ymin, xmax, ymax" },
};
const COLOR_PALETTE_TARGETS = new Set(["ideogram4", "flux2_dev", "flux_klein", "jsonx"]);

function fallbackRule(enabled, text = "") {
  return {
    enabled,
    common_rules: ensureInstructionBlock({ title: "Core Model Rules", text: enabled ? text : "", source: "Frontend fallback" }),
    common_guide: ensureInstructionBlock({ title: "Profile Guide", text: "", source: "Frontend fallback" }),
  };
}

const FALLBACK_PROFILES = [
  { key: "ideogram4", label: "Ideogram 4", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(true) }, default_format: "json", negative_supported: true, json_supported: true, media_type: "image", notes: "" },
  { key: "sdxl", label: "SDXL", formats: { natural: fallbackRule(true), tags: fallbackRule(true), json: fallbackRule(false) }, default_format: "tags", negative_supported: true, json_supported: false, media_type: "image", notes: "" },
  { key: "qwen_image", label: "Qwen-Image", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "image", notes: "" },
  { key: "flux1_dev", label: "FLUX.1 dev", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "image", notes: "" },
  { key: "flux2_dev", label: "FLUX.2 dev", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(true) }, default_format: "natural", negative_supported: true, json_supported: true, media_type: "image", notes: "" },
  { key: "flux_klein", label: "Flux Klein", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(true) }, default_format: "natural", negative_supported: true, json_supported: true, media_type: "image", notes: "" },
  { key: "krea2", label: "Krea2", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(true) }, default_format: "natural", negative_supported: true, json_supported: true, media_type: "image", notes: "" },
  { key: "z_image", label: "Z-Image", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "image", notes: "" },
  { key: "wan2_2", label: "WAN 2.2", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "video", notes: "" },
  { key: "ltx_2_3", label: "LTX 2.3", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: true, json_supported: false, media_type: "video", notes: "" },
  { key: "minimax_h3_official", label: "MiniMax H3 Official", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: false, json_supported: false, media_type: "video", notes: "" },
  { key: "minimax_h3_alternate", label: "MiniMax H3 Alternate", formats: { natural: fallbackRule(true), tags: fallbackRule(false), json: fallbackRule(false) }, default_format: "natural", negative_supported: false, json_supported: false, media_type: "video", notes: "" },
  { key: "jsonx", label: "JsonX", engine: "jsonx", jsonx_config: defaultJsonXConfig(), formats: { natural: fallbackRule(true, "Convert validated JsonX into natural language."), tags: fallbackRule(false), json: fallbackRule(true, "Generate validated JsonX JSON.") }, default_format: "json", negative_supported: true, json_supported: true, media_type: "image", notes: "JsonX structured prompt profile." },
];
const NODE_MIN_WIDGET_HEIGHT = 420;
const DOCK_Z_BASE = 9000;
const DOCK_Z_LIMIT = 9499;
const DOCK_OBSCURING_MODAL_SELECTOR = [
  "dialog[open]",
  "[aria-modal='true']",
  "[role='dialog']",
  ".comfy-modal",
  ".comfy-modal-backdrop",
  ".comfy-modal-wrapper",
  ".comfyui-manager",
  ".p-dialog",
  ".p-dialog-mask",
  ".el-dialog__wrapper",
  ".modal",
  ".modal-backdrop",
  ".v-overlay",
].join(",");
let nextDockZ = DOCK_Z_BASE;

let profilesPromise = null;
let backendSchemaVersion = 0;
let backendReferenceSchemaVersion = 0;
let backendJsonXReferenceSchemaVersion = 0;
let backendPresetSchemaVersion = 0;
let profileLoadError = "";
const graphDocks = new Set();
const unifiedQueueNodes = new Set();
let dockRAF = 0;
let dockWakesInstalled = false;
let dockModalObserver = null;
let dockModalRAF = 0;

function chainCallback(object, callbackName, callback) {
  const original = object?.[callbackName];
  object[callbackName] = function workflowXUnifiedCallback() {
    const result = original?.apply(this, arguments);
    callback?.apply(this, arguments);
    return result;
  };
}

function screenGeometryToGraph(node, rect, fallbackGraph) {
  const canvas = app.canvas;
  const ds = canvas?.ds;
  const canvasRect = canvas?.canvas?.getBoundingClientRect?.();
  if (!node?.pos || !ds || !canvasRect || !rect) return { ...fallbackGraph };
  const scale = ds.scale || 1;
  return {
    x: (rect.x - canvasRect.left) / scale - ds.offset[0] - node.pos[0],
    y: (rect.y - canvasRect.top) / scale - ds.offset[1] - node.pos[1],
    w: Math.max(320, rect.w / scale),
    h: Math.max(220, rect.h / scale),
  };
}

function resolveDockCanvasLayer(node) {
  const root = node?.__workflowXUapRoot || node?.__workflowXUapWidget?.element;
  const widgetHost = root?.closest?.(".dom-widget");
  const layerHost = widgetHost?.parentElement;
  if (!widgetHost || !layerHost?.classList?.contains("isolate")) return null;
  return { widgetHost, layerHost };
}

function syncDockCanvasLayer(dock) {
  const layer = resolveDockCanvasLayer(dock?.__workflowXNode);
  if (!layer) return null;
  if (dock.parentElement !== layer.layerHost) layer.layerHost.appendChild(dock);
  const ownerZ = window.getComputedStyle(layer.widgetHost).zIndex;
  dock.style.zIndex = ownerZ && ownerZ !== "auto"
    ? ownerZ
    : String(Number(layer.widgetHost.style.zIndex) || 1);
  return layer;
}

function applyGraphDockTransform(dock) {
  const canvas = app.canvas;
  const node = dock?.__workflowXNode;
  const graph = dock?.__workflowXGraph;
  if (!canvas || !dock || !node || !graph) return;
  const canvasLayer = syncDockCanvasLayer(dock);
  if (dock.classList.contains("fullscreen")) return;

  let nodeEl = null;
  if (!canvasLayer && window.LiteGraph?.vueNodesMode && node.id != null) {
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
      dock.__workflowXDockSig = "";
    }
    const sig = `vue|${graph.x}|${graph.y}|${graph.w}|${graph.h}`;
    if (dock.__workflowXDockSig !== sig) {
      dock.style.left = `${graph.x}px`;
      dock.style.top = `${titleHeight + graph.y}px`;
      dock.style.width = `${graph.w}px`;
      dock.style.height = `${graph.h}px`;
      dock.__workflowXDockSig = sig;
    }
    return;
  }

  if (!canvasLayer && dock.parentElement !== document.body) {
    document.body.appendChild(dock);
    dock.__workflowXDockSig = "";
  }
  if (!node.pos) return;
  const screen = graphDockScreenRect(app, node, graph);
  if (!screen) return;
  const { left, top, scale } = screen;
  const sig = `fixed|${left}|${top}|${scale}|${graph.w}|${graph.h}`;
  if (dock.__workflowXDockSig !== sig) {
    dock.style.position = "fixed";
    dock.style.left = "0px";
    dock.style.top = "0px";
    dock.style.width = `${graph.w}px`;
    dock.style.height = `${graph.h}px`;
    dock.style.transformOrigin = "top left";
    dock.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
    dock.__workflowXDockSig = sig;
  }
}

function tickGraphDocks() {
  dockRAF = 0;
  for (const dock of graphDocks) applyGraphDockTransform(dock);
}

function wakeGraphDocks() {
  if (!dockRAF && graphDocks.size) dockRAF = requestAnimationFrame(tickGraphDocks);
}

function elementLooksVisible(element) {
  if (!element || !document.body.contains(element)) return false;
  if (element.closest(".workflowx-uap-dock, .workflowx-uap-ideo-menu, .workflowx-uap-ideo-layer-menu")) return false;
  const style = window.getComputedStyle(element);
  if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity || 1) <= 0) return false;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function hasObscuringModal() {
  for (const element of document.querySelectorAll(DOCK_OBSCURING_MODAL_SELECTOR)) {
    if (elementLooksVisible(element)) return true;
  }
  return false;
}

function refreshDockModalOcclusion() {
  dockModalRAF = 0;
  const obscured = hasObscuringModal();
  for (const dock of graphDocks) {
    dock.classList.toggle("workflowx-uap-dock-obscured", obscured);
  }
}

function wakeDockModalOcclusion() {
  if (!dockModalRAF) dockModalRAF = requestAnimationFrame(refreshDockModalOcclusion);
}

function installDockWakes() {
  if (dockWakesInstalled) return;
  if (!app.canvas) return;
  dockWakesInstalled = true;
  chainCallback(app.canvas, "onDrawForeground", wakeGraphDocks);
  window.addEventListener("resize", wakeGraphDocks);
  dockModalObserver = new MutationObserver(wakeDockModalOcclusion);
  dockModalObserver.observe(document.body, {
    attributes: true,
    attributeFilter: ["class", "style", "open", "aria-modal", "role"],
    childList: true,
    subtree: true,
  });
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
.workflowx-uap-dock.workflowx-uap-dock-obscured {
  pointer-events: none !important;
  visibility: hidden !important;
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
  z-index: 9400;
}
.workflowx-uap-ideo-layer-menu {
  background: #242424;
  border: 1px solid #555;
  border-radius: 7px;
  box-sizing: border-box;
  box-shadow: 0 10px 32px rgba(0,0,0,.55);
  color: #ddd;
  font: 12px ui-sans-serif, system-ui, sans-serif;
  max-height: 56vh;
  max-width: calc(100vw - 16px);
  min-width: 320px;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 6px;
  position: fixed;
  width: min(560px, calc(100vw - 16px));
  z-index: 9400;
}
.workflowx-uap-ideo-layer-header {
  color: #999;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflowx-uap-ideo-layer-row {
  align-items: center;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  gap: 6px;
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
  min-width: 38px;
  padding: 2px 5px;
  text-align: center;
}
.workflowx-uap-ideo-layer-btn.on {
  background: #7a5a16;
  color: #fff;
}
.workflowx-uap-ideo-layer-btn:disabled {
  cursor: default;
  opacity: .35;
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
.workflowx-uap-model-settings {
  border: 1px solid #303842;
  border-radius: 6px;
  min-width: 0;
}
.workflowx-uap-model-settings > summary {
  color: #cbd7e1;
  cursor: pointer;
  font-weight: 600;
  padding: 7px 9px;
  user-select: none;
}
.workflowx-uap-model-settings > summary::marker {
  color: #8fc7ed;
}
.workflowx-uap-model-settings-body {
  display: grid;
  gap: 6px;
  padding: 0 7px 7px;
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
.workflowx-uap-settings-body.global-rules-mode {
  grid-template-columns: minmax(0, 1fr);
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
  background: #121820;
  border: 1px solid #303842;
  border-radius: 9px;
  display: grid;
  gap: 10px;
  padding: 12px;
}
.workflowx-uap-settings-card-head {
  align-items: flex-start;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}
.workflowx-uap-settings-card-title {
  color: #eef4f8;
  font-size: 13px;
  font-weight: 650;
}
.workflowx-uap-settings-card-source {
  color: #8fa0ad;
  font: 10px ui-monospace, SFMono-Regular, Consolas, monospace;
  margin-top: 3px;
}
.workflowx-uap-condition-badge {
  background: #172536;
  border: 1px solid #36506a;
  border-radius: 999px;
  color: #9dcae9;
  font-size: 10px;
  line-height: 1.25;
  max-width: 420px;
  padding: 4px 8px;
  text-align: right;
}
.workflowx-uap-field-help {
  color: #91a0ad;
  font-size: 10px;
  line-height: 1.35;
  margin-top: 4px;
}
.workflowx-uap-field.is-disabled .workflowx-uap-label,
.workflowx-uap-field.is-disabled .workflowx-uap-field-help,
.workflowx-uap-toggle.is-disabled {
  opacity: .58;
}
.workflowx-uap-field select:disabled,
.workflowx-uap-field input:disabled {
  cursor: not-allowed;
}
.workflowx-uap-preview-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, .55fr);
}
.workflowx-uap-preview-section {
  display: grid;
  gap: 10px;
  min-width: 0;
}
.workflowx-uap-preview-heading {
  color: #eef4f8;
  font-size: 14px;
  font-weight: 700;
}
.workflowx-uap-routing-list {
  color: #c6d1da;
  display: grid;
  gap: 7px;
  margin: 0;
  padding-left: 18px;
}
.workflowx-uap-global-rules-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
@media (max-width: 980px) {
  .workflowx-uap-global-rules-grid {
    grid-template-columns: minmax(0, 1fr);
  }
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
.workflowx-uap-modal-v6 {
  background: linear-gradient(180deg, #12171c 0%, #0d1115 100%);
  height: min(920px, 96vh);
  width: min(1500px, 98vw);
}
.workflowx-uap-modal-v6 .workflowx-uap-settings-form {
  background: rgba(9, 13, 17, .55);
  overflow: hidden;
}
.workflowx-uap-settings-page {
  display: grid;
  gap: 12px;
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}
.workflowx-uap-settings-page > .workflowx-uap-field {
  background: #121820;
  border: 1px solid #283440;
  border-radius: 8px;
  padding: 9px;
}
.workflowx-uap-settings-page .workflowx-uap-text {
  min-height: 150px;
}
@media (max-width: 980px) {
  .workflowx-uap-preview-grid { grid-template-columns: 1fr; }
}
.workflowx-uap-modal-v6 .workflowx-uap-modal-head:last-child .workflowx-uap-status {
  flex: 1 1 auto;
  min-width: 260px;
}
.workflowx-uap-preset-modal {
  height: min(680px, 86vh);
  width: min(940px, 94vw);
}
.workflowx-uap-preset-body {
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: 230px minmax(0, 1fr);
  min-height: 0;
}
.workflowx-uap-preset-sidebar {
  border-right: 1px solid #303842;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  padding: 10px;
}
.workflowx-uap-preset-list {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 5px;
  min-height: 0;
  overflow: auto;
}
.workflowx-uap-preset-item {
  background: #171c21;
  border: 1px solid #303842;
  border-radius: 6px;
  color: #dbe3ea;
  cursor: pointer;
  padding: 8px;
  text-align: left;
}
.workflowx-uap-preset-item.active {
  background: #223143;
  border-color: #7bafd1;
}
.workflowx-uap-preset-item small {
  color: #91a0ad;
  display: block;
  margin-top: 3px;
}
.workflowx-uap-preset-new-actions {
  display: grid;
  gap: 6px;
}
.workflowx-uap-preset-editor {
  display: grid;
  gap: 9px;
  min-height: 0;
  overflow: auto;
  padding: 10px 12px;
}
.workflowx-uap-preset-meta {
  display: grid;
  gap: 9px;
  grid-template-columns: 150px minmax(0, 1fr) minmax(0, 1fr);
}
.workflowx-uap-preset-editor .workflowx-uap-text.profile-details {
  min-height: 150px;
}
.workflowx-uap-preset-editor .workflowx-uap-text.adaptation-guidance {
  min-height: 105px;
}
@media (max-width: 720px) {
  .workflowx-uap-preset-modal { height: min(760px, 94vh); }
  .workflowx-uap-preset-body { grid-template-columns: 1fr; }
  .workflowx-uap-preset-sidebar { border-bottom: 1px solid #303842; border-right: 0; max-height: 190px; }
  .workflowx-uap-preset-meta { grid-template-columns: 1fr; }
}
.workflowx-uap-tag-suggestions {
  background: #111820;
  border: 1px solid #3a5368;
  border-radius: 7px;
  box-shadow: 0 8px 24px rgba(0,0,0,.45);
  display: grid;
  gap: 2px;
  max-height: 210px;
  min-width: 230px;
  overflow: auto;
  padding: 5px;
  position: fixed;
  z-index: 10050;
}
.workflowx-uap-tag-suggestion {
  background: transparent;
  border: 0;
  border-radius: 5px;
  color: #dce7ef;
  cursor: pointer;
  padding: 7px 9px;
  text-align: left;
}
.workflowx-uap-tag-suggestion:hover,
.workflowx-uap-tag-suggestion.active { background: #243747; }
.workflowx-uap-tag-suggestion small { color: #8fa4b4; margin-left: 7px; }
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

function loadStoredOpenAIKey() {
  try {
    return window.localStorage?.getItem(OPENAI_KEY_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function storeOpenAIKey(key) {
  try {
    const trimmed = String(key || "").trim();
    if (trimmed) window.localStorage?.setItem(OPENAI_KEY_STORAGE_KEY, trimmed);
    else window.localStorage?.removeItem(OPENAI_KEY_STORAGE_KEY);
  } catch {
    // Browser storage can be unavailable in restricted contexts.
  }
}

function loadStoredOpenAIBaseUrl() {
  try {
    return window.localStorage?.getItem(OPENAI_BASE_URL_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function storeOpenAIBaseUrl(baseUrl) {
  try {
    const trimmed = String(baseUrl || "").trim();
    if (trimmed) window.localStorage?.setItem(OPENAI_BASE_URL_STORAGE_KEY, trimmed);
    else window.localStorage?.removeItem(OPENAI_BASE_URL_STORAGE_KEY);
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
    if (["gemini", "openai", "ollama", "local"].includes(backend)) next.backend = backend;
    for (const key of ["gemini_model", "openai_model", "ollama_model", "local_model"]) {
      const value = String(selection?.[key] || "").trim();
      if (value) next[key] = value;
    }
    window.localStorage?.setItem(MODEL_SELECTION_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Browser storage can be unavailable in restricted contexts.
  }
}

function loadStoredAdditionalLocalModelPaths() {
  try {
    return window.localStorage?.getItem(ADDITIONAL_LOCAL_MODEL_PATHS_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function storeAdditionalLocalModelPaths(value) {
  try {
    const clean = String(value || "").trim();
    if (clean) window.localStorage?.setItem(ADDITIONAL_LOCAL_MODEL_PATHS_STORAGE_KEY, clean);
    else window.localStorage?.removeItem(ADDITIONAL_LOCAL_MODEL_PATHS_STORAGE_KEY);
  } catch {
    // Browser storage can be unavailable in restricted contexts.
  }
}

function additionalLocalModelPaths(value) {
  return String(value || "")
    .split(/[;\r\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
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

function ensureInputSocket(node, name, type) {
  if (!node) return;
  node.inputs ||= [];
  if (node.inputs.some((input) => input.name === name)) return;
  node.addInput?.(name, type);
  markDirty();
}

function referenceImageNumbers(node) {
  return (node.inputs || [])
    .map((input) => REFERENCE_IMAGE_RE.exec(String(input.name || "")))
    .filter(Boolean)
    .map((match) => Number(match[1]))
    .sort((a, b) => a - b);
}

function referenceImageInputNames(node) {
  const names = [];
  if (node.inputs?.some((input) => input.name === "image")) names.push("image");
  for (const number of referenceImageNumbers(node)) names.push(`image_${number}`);
  return names;
}

function imageInputLinked(node, name) {
  return Boolean(node?.inputs?.some((input) => input.name === name && input.link != null));
}

function linkedReferenceImageInputNames(node) {
  return referenceImageInputNames(node).filter((name) => imageInputLinked(node, name));
}

function syncReferenceImageSockets(node) {
  if (!node) return;
  let numbers = referenceImageNumbers(node);
  if (!numbers.length) {
    ensureInputSocket(node, "image_1", "IMAGE");
    numbers = [1];
  }
  while (numbers.length > 1) {
    const last = numbers.at(-1);
    const previous = numbers.at(-2);
    if (imageInputLinked(node, `image_${last}`) || imageInputLinked(node, `image_${previous}`)) break;
    const index = node.inputs?.findIndex((input) => input.name === `image_${last}`);
    if (index >= 0) node.removeInput(index);
    numbers = referenceImageNumbers(node);
  }
  const last = numbers.at(-1) || 1;
  if (last < MAX_REFERENCE_IMAGES && imageInputLinked(node, `image_${last}`)) {
    ensureInputSocket(node, `image_${last + 1}`, "IMAGE");
  }
  markDirty();
}

function markDirty() {
  app.graph?.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
}

function installQueueGenerationHooks() {
  if (app.__workflowXUapQueueGenerationPatched || typeof app.queuePrompt !== "function" || typeof app.graphToPrompt !== "function") return;
  const originalQueuePrompt = app.queuePrompt.bind(app);
  const originalGraphToPrompt = app.graphToPrompt.bind(app);
  let queueDepth = 0;

  app.queuePrompt = async function (...args) {
    queueDepth += 1;
    try {
      return await originalQueuePrompt(...args);
    } finally {
      queueDepth = Math.max(0, queueDepth - 1);
    }
  };

  app.graphToPrompt = async function (...args) {
    const initial = await originalGraphToPrompt(...args);
    if (queueDepth <= 0) return initial;
    const activeIds = new Set(Object.entries(initial?.output || {})
      .filter(([, entry]) => entry?.class_type === TARGET_NODE)
      .map(([id]) => String(id)));
    const generators = [...unifiedQueueNodes].filter((node) =>
      activeIds.has(String(node?.id)) && typeof node.__workflowXUapGenerateOnQueue === "function"
    );
    let generated = false;
    for (const node of generators) {
      generated = (await node.__workflowXUapGenerateOnQueue()) || generated;
    }
    return generated ? originalGraphToPrompt(...args) : initial;
  };

  app.__workflowXUapQueueGenerationPatched = true;
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
      .then(async (response) => {
        if (!response.ok) throw new Error(`Profile schema request failed with HTTP ${response.status}.`);
        const data = await response.json();
        backendSchemaVersion = Number(data?.schema_version || 0);
        backendReferenceSchemaVersion = Number(data?.reference_schema_version || 0);
        backendJsonXReferenceSchemaVersion = Number(data?.jsonx_reference_schema_version || 0);
        backendPresetSchemaVersion = Number(data?.preset_schema_version || 0);
        if (Number(data?.general_schema_version || 0) !== GENERAL_SCHEMA_VERSION) {
          throw new Error("General frontend/backend mismatch. Restart ComfyUI and hard-refresh the browser.");
        }
        if (backendSchemaVersion !== FRONTEND_SCHEMA_VERSION) {
          throw new Error(
            `Unified schema mismatch (frontend ${FRONTEND_SCHEMA_VERSION}, backend ${backendSchemaVersion || "missing"}). ` +
            "Restart ComfyUI and hard-refresh the browser.",
          );
        }
        if (backendReferenceSchemaVersion !== REFERENCE_SCHEMA_VERSION) {
          throw new Error(
            `Unified reference schema mismatch (frontend ${REFERENCE_SCHEMA_VERSION}, backend ${backendReferenceSchemaVersion || "missing"}). ` +
            "Restart ComfyUI and hard-refresh the browser.",
          );
        }
        if (backendJsonXReferenceSchemaVersion !== JSONX_REFERENCE_SCHEMA_VERSION) {
          throw new Error(
            `Unified JsonX reference schema mismatch (frontend ${JSONX_REFERENCE_SCHEMA_VERSION}, backend ${backendJsonXReferenceSchemaVersion || "missing"}). ` +
            "Restart ComfyUI and hard-refresh the browser.",
          );
        }
        if (backendPresetSchemaVersion !== PRESET_SCHEMA_VERSION) {
          throw new Error(
            `Unified prompt preset schema mismatch (frontend ${PRESET_SCHEMA_VERSION}, backend ${backendPresetSchemaVersion || "missing"}). ` +
            "Restart ComfyUI and hard-refresh the browser.",
          );
        }
        profileLoadError = "";
        return (data?.profiles || FALLBACK_PROFILES).map(ensureProfileShape);
      })
      .catch((error) => {
        profileLoadError = error?.message || String(error);
        return FALLBACK_PROFILES.map(ensureProfileShape);
      });
  }
  return profilesPromise;
}

async function fetchJsonChecked(url, options = {}, label = "Request") {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  const restartHint = "Restart ComfyUI so the new WorkflowX backend routes are registered.";
  if (text.trim()) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(`${label} returned non-JSON HTTP ${response.status}: ${text.slice(0, 180)}. ${restartHint}`);
    }
  }
  if (!data) {
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

function bboxTargetConfig(targetModel) {
  return BBOX_LAYOUT_TARGETS[targetModel] || null;
}

function isBboxLayoutTarget(targetModel) {
  return Boolean(bboxTargetConfig(targetModel));
}

function bboxOrder(targetModel) {
  return bboxTargetConfig(targetModel)?.order || "yx";
}

function bboxOrderLabel(targetModel) {
  return bboxTargetConfig(targetModel)?.orderLabel || BBOX_LAYOUT_TARGETS.ideogram4.orderLabel;
}

function formatRule(profile, promptFormat) {
  return profile?.formats?.[promptFormat] || null;
}

function enabledProfileFormats(profile) {
  const formats = profile?.formats;
  if (Array.isArray(formats)) return formats;
  return ALL_PROMPT_FORMATS.filter((format) => formats?.[format]?.enabled);
}

function ensureInstructionBlock(value = {}, defaultTitle = "Instructions") {
  if (typeof value === "string") value = { text: value };
  return {
    title: String(value?.title || defaultTitle),
    text: String(value?.text || ""),
    source: String(value?.source || ""),
  };
}

function ensureInstructionBlocks(value, defaultTitle) {
  const values = Array.isArray(value) ? value : value ? [value] : [];
  return values.map((item) => ensureInstructionBlock(item, defaultTitle));
}

function collapseInstructionBlocks(value, title, source) {
  const blocks = ensureInstructionBlocks(value, title);
  return ensureInstructionBlock({
    title,
    text: blocks
      .filter((item) => String(item.text || "").trim())
      .map((item) => `${item.title ? `## ${item.title}\n` : ""}${String(item.text || "").trim()}`)
      .join("\n\n"),
    source: blocks.map((item) => item.source).filter(Boolean).join("; ") || source,
  }, title);
}

function ensureRule(rule = {}, enabled = false) {
  const legacy = rule.common_blocks ?? (rule.common_instructions
    ? [{ title: "Core model behavior", text: rule.common_instructions, source: "Legacy profile rule" }]
    : []);
  return {
    enabled: Boolean(rule.enabled ?? enabled),
    common_rules: ensureInstructionBlock(
      rule.common_rules || collapseInstructionBlocks(legacy, "Core Model Rules", "Migrated profile rules"),
      "Core Model Rules",
    ),
    common_guide: ensureInstructionBlock(rule.common_guide, "Profile Guide"),
  };
}

function ensureProfileShape(profile) {
  const next = { ...profile };
  next.engine = String(next.engine || (next.key === "jsonx" ? "jsonx" : "standard")).toLowerCase();
  next.jsonx_config = next.engine === "jsonx"
    ? jsonxBehaviorConfig(next.jsonx_config)
    : {};
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
  const defaultTypes = next.media_type === "video"
    ? ["text_to_video", "first_frame_to_video", "first_last_frame_to_video"]
    : ["text_to_image", "image_to_image"];
  const sourcePaths = next.generation_paths && typeof next.generation_paths === "object"
    ? next.generation_paths
    : Object.fromEntries(defaultTypes.map((type) => [type, {
      label: GENERATION_TYPE_MAP.get(type)?.label || type,
      path_rules: ensureInstructionBlock({}, "Generation Path Rules"),
      path_guide: ensureInstructionBlock({}, "Generation Path Guide"),
      image_state_blocks: {},
      output_contracts: {},
    }]));
  next.generation_paths = Object.fromEntries(Object.entries(sourcePaths).map(([type, path]) => {
    const contracts = path?.output_contracts && typeof path.output_contracts === "object" ? path.output_contracts : {};
    for (const format of ALL_PROMPT_FORMATS) {
      if (!contracts[format]) {
        const rule = next.formats[format] || ensureRule();
        contracts[format] = {
          negative_off: rule.output_contract_negative_off || "",
          negative_on: rule.output_contract_negative_on || "",
        };
      }
    }
    return [type, {
      label: path?.label || GENERATION_TYPE_MAP.get(type)?.label || type,
      path_rules: ensureInstructionBlock(
        path?.path_rules || collapseInstructionBlocks(
          path?.instruction_blocks ?? (path?.instructions
            ? [{ title: "Generation-path guide", text: path.instructions, source: "Legacy generation-path rule" }]
            : []),
          "Generation Path Rules",
          "Migrated generation-path rules",
        ),
        "Generation Path Rules",
      ),
      path_guide: ensureInstructionBlock(path?.path_guide, "Generation Path Guide"),
      image_state_blocks: Object.fromEntries(IMAGE_STATE_KEYS.map((key) => [
        key,
        ensureInstructionBlock(path?.image_state_blocks?.[key], key.replaceAll("_", " ")),
      ])),
      output_contracts: contracts,
    }];
  }));
  const pathKeys = Object.keys(next.generation_paths);
  if (!pathKeys.includes(next.default_generation_type)) next.default_generation_type = pathKeys[0] || defaultTypes[0];
  return next;
}

function isMiniMaxProfile(profile) {
  const key = typeof profile === "string" ? profile : profile?.key;
  return key === "minimax_h3_official" || key === "minimax_h3_alternate";
}

function promptInstructionsPlaceholder(profile) {
  if (profile?.engine === "jsonx") {
    return [
      "Describe the requested scene, subjects, environment, style, lighting, camera, interactions, and constraints.",
      "Create the deepest coherent JsonX hierarchy possible, using detailed branches and leaves wherever they apply.",
    ].join("\n");
  }
  if (isMiniMaxProfile(profile)) {
    return [
      "Idea: A 5-second cinematic video of the subject performing a clear action.",
      "Action and timing: 0-2s ..., 2-4s ..., 4-5s ...",
      "Camera: Describe framing and any material camera change or cut.",
      "Audio / dialogue: Describe speech, music, ambience, or reference <Audio 1>.",
      "Reference intent: Explain what <Picture 1> or <Video 1> supplies and what must not be inferred from it.",
    ].join("\n");
  }
  if (profileIsVideo(profile)) {
    return [
      "Idea: A 5-second video of a woman walking steadily along a beach.",
      "Action and timing: 0-2s she enters frame, 2-4s she follows the shoreline, 4-5s she pauses at the water.",
      "Camera: Static locked camera with a medium-wide composition.",
      "Audio / dialogue: Gentle surf and light wind; no dialogue.",
      "Reference intent: Preserve the connected image subject's identity and clothing if provided.",
    ].join("\n");
  }
  return [
    "Idea: Create a detailed image of a woman walking along a beach.",
    "Subject and environment: Describe the subject, clothing, action, setting, and important objects.",
    "Style and lighting: Natural editorial photography in soft overcast daylight.",
    "Camera / composition: Eye-level medium-wide framing using the rule of thirds.",
    "Text / typography: State any required visible text, or specify none.",
    "Reference intent: Explain what to preserve from connected images if provided.",
  ].join("\n");
}

function renderTemplatePreview(profile, promptFormat, negativeEnabled, hasImage = false) {
  profile = ensureProfileShape(profile || {});
  if (profile.engine !== "jsonx") return "";
  return "Use Refresh effective instructions to preview the isolated JsonX engine prompts.";
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
  const storedOpenAIBaseUrl = loadStoredOpenAIBaseUrl();
  const browserProvider = loadProviderSettings("standard");
  const generatedPositive = widgetValue(node, "generated_positive", "");
  const generatedNegative = widgetValue(node, "generated_negative", "");
  const finalPrompt = widgetValue(node, "final_prompt", "");
  const savedGeneration = saved.last_generation && typeof saved.last_generation === "object"
    ? saved.last_generation
    : null;

  return {
    backend: browserProvider.backend || saved.backend || storedModels.backend || "gemini",
    model_settings_open: Boolean(saved.model_settings_open),
    target_model: saved.target_model || widgetValue(node, "target_model", "ideogram4"),
    prompt_format: saved.prompt_format || widgetValue(node, "prompt_format", "json"),
    generation_type: saved.generation_type || widgetValue(node, "generation_type", "text_to_image"),
    nsfw_enabled: saved.nsfw_enabled == null
      ? Boolean(widgetValue(node, "nsfw_enabled", false))
      : Boolean(saved.nsfw_enabled),
    negative_enabled: saved.negative_enabled == null
      ? Boolean(widgetValue(node, "negative_enabled", false))
      : Boolean(saved.negative_enabled),
    audit_mode: ["none", "add_pass", "audit_only"].includes(saved.audit_mode || widgetValue(node, "audit_mode", "none"))
      ? (saved.audit_mode || widgetValue(node, "audit_mode", "none"))
      : "none",
    working_mode: ["on_generate", "on_queue"].includes(saved.working_mode)
      ? saved.working_mode
      : "on_generate",
    prompt_text: saved.prompt_text || "",
    detail: saved.detail || "high",
    enable_bbox_json_input: saved.enable_bbox_json_input == null
      ? Boolean(widgetValue(node, "enable_bbox_json_input", false))
      : Boolean(saved.enable_bbox_json_input),
    enable_text_input: saved.enable_text_input == null
      ? Boolean(widgetValue(node, "enable_text_input", false))
      : Boolean(saved.enable_text_input),
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
    jsonx: saved.jsonx && typeof saved.jsonx === "object" ? saved.jsonx : { diagnostics: null },
    jsonx_provider: workflowJsonXProviderSettings(saved.jsonx_provider),
    jsonx_profile_configs: Object.fromEntries(Object.entries(
      saved.jsonx_profile_configs && typeof saved.jsonx_profile_configs === "object"
        ? saved.jsonx_profile_configs
        : {},
    ).map(([key, value]) => [key, jsonxBehaviorConfig(value)])),
    gemini_model: browserProvider.gemini_model || saved.gemini_model || storedModels.gemini_model || "",
    gemini_timeout: browserProvider.gemini_timeout || saved.gemini_timeout || 120,
    safety_harassment: browserProvider.safety_harassment || saved.safety_harassment || "BLOCK_NONE",
    safety_hate_speech: browserProvider.safety_hate_speech || saved.safety_hate_speech || "BLOCK_NONE",
    safety_sexual: browserProvider.safety_sexual || saved.safety_sexual || "BLOCK_NONE",
    safety_dangerous: browserProvider.safety_dangerous || saved.safety_dangerous || "BLOCK_NONE",
    openai_base_url: browserProvider.openai_base_url || saved.openai_base_url || storedOpenAIBaseUrl || DEFAULT_OPENAI_BASE_URL,
    openai_model: browserProvider.openai_model || saved.openai_model || storedModels.openai_model || "",
    openai_timeout: browserProvider.openai_timeout || saved.openai_timeout || 120,
    openai_server_type: normalizeOpenAIServerType(saved.openai_server_type),
    openai_lifecycle: normalizeOpenAILifecycle(
      saved.openai_lifecycle || (
        Object.prototype.hasOwnProperty.call(saved, "unload_after")
          ? (saved.unload_after ? "unload_after" : "keep_loaded")
          : "server_managed"
      ),
    ),
    openai_reasoning_effort: normalizeOpenAIReasoning(saved.openai_reasoning_effort),
    ollama_timeout: browserProvider.ollama_timeout || saved.ollama_timeout || 120,
    local_timeout: browserProvider.local_timeout || saved.local_timeout || 180,
    ollama_host: browserProvider.ollama_host || saved.ollama_host || DEFAULT_OLLAMA_HOST,
    ollama_model: browserProvider.ollama_model || saved.ollama_model || storedModels.ollama_model || "",
    ollama_think: Boolean(browserProvider.ollama_think ?? saved.ollama_think ?? false),
    ollama_options: { ...(browserProvider.ollama_options || {}) },
    unload_after: saved.unload_after !== false,
    refresh_vram: saved.refresh_vram == null
      ? Boolean(widgetValue(node, "refresh_vram", false))
      : Boolean(saved.refresh_vram),
    disable_color_palette: saved.disable_color_palette == null
      ? Boolean(widgetValue(node, "disable_color_palette", false))
      : Boolean(saved.disable_color_palette),
    local_model: browserProvider.local_model || saved.local_model || storedModels.local_model || "",
    local_mmproj: saved.local_mmproj || "none",
    local_system_prompt_preset: saved.local_system_prompt_preset || "none",
    general_preset: saved.general_preset || "none",
    thinking_level: browserProvider.thinking_level || "default",
    thinking_budget: browserProvider.thinking_budget || 2048,
    max_tokens: saved.max_tokens || 768,
    temperature: saved.temperature || 0.7,
    top_p: saved.top_p || 0.9,
    top_k: saved.top_k || 40,
    repeat_penalty: saved.repeat_penalty || 1.05,
    ctx_size: saved.ctx_size || 8192,
    memory_mode: saved.memory_mode || "auto",
    n_gpu_layers: saved.n_gpu_layers || 99,
    n_cpu_moe_layers: saved.n_cpu_moe_layers || 0,
    reasoning: normalizeUnifiedReasoning(saved.reasoning),
    speculative_mode: saved.speculative_mode || "auto",
    mtp_draft_tokens: saved.mtp_draft_tokens || 2,
    seed: saved.seed ?? -1,
    grok: {
      ...(browserProvider.grok || {}),
      api_key: loadDedicatedApiKey(GROK_KEY_STORAGE_KEY, browserProvider.grok?.api_key),
    },
    deepseek: {
      ...(browserProvider.deepseek || {}),
      api_key: loadDedicatedApiKey(DEEPSEEK_KEY_STORAGE_KEY, browserProvider.deepseek?.api_key),
    },
    lm_studio: { ...(browserProvider.lm_studio || {}) },
    unsloth: { ...(browserProvider.unsloth || {}) },
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
    connected_images_b64,
    connected_image_url,
    connected_image_urls,
    connected_image_available,
    connected_image_count,
    connected_bbox_json,
    connected_bbox_json_available,
    connected_raw_prompt_text,
    connected_raw_prompt_text_available,
    gemini_key,
    openai_key,
    ...rest
  } = state;
  const result = { ...rest };
  result.jsonx_profile_configs = Object.fromEntries(Object.entries(result.jsonx_profile_configs || {})
    .map(([key, value]) => [key, jsonxBehaviorConfig(value)]));
  for (const key of [
    "backend", "jsonx_provider", "gemini_model", "gemini_timeout", "safety_harassment",
    "safety_hate_speech", "safety_sexual", "safety_dangerous", "openai_base_url",
    "openai_model", "openai_timeout", "openai_server_type", "openai_lifecycle",
    "openai_reasoning_effort", "ollama_timeout", "ollama_host", "ollama_model",
    "ollama_think", "ollama_options", "unload_after", "local_timeout", "local_model", "local_mmproj",
    "local_system_prompt_preset", "max_tokens", "temperature", "top_p", "top_k",
    "repeat_penalty", "ctx_size", "memory_mode", "n_gpu_layers", "n_cpu_moe_layers",
    "reasoning", "speculative_mode", "mtp_draft_tokens", "seed", "grok", "deepseek", "lm_studio",
    "unsloth", "thinking_level", "thinking_budget",
  ]) delete result[key];
  return result;
}

function positiveAndNegativePrompt(positive, negative, negativeEnabled, promptFormat) {
  positive = String(positive || "").trim();
  negative = String(negative || "").trim();
  if (promptFormat === "json") return positive;
  if (negativeEnabled && negative) return `Positive:\n${positive}\n\nNegative:\n${negative}`;
  return positive;
}

function stripColorPalettesFromValue(value) {
  if (Array.isArray(value)) return value.map((item) => stripColorPalettesFromValue(item));
  if (value && typeof value === "object") {
    const stripped = {};
    for (const [key, item] of Object.entries(value)) {
      if (key === "color_palette") continue;
      stripped[key] = stripColorPalettesFromValue(item);
    }
    return stripped;
  }
  return value;
}

function stripColorPalettesFromPrompt(text, promptFormat) {
  const raw = String(text || "").trim();
  if (promptFormat !== "json" || !raw) return raw;
  try {
    return JSON.stringify(stripColorPalettesFromValue(JSON.parse(raw)), null, 2);
  } catch {
    return raw;
  }
}

function outputTextForState(state, text, promptFormat) {
  if ((state.last_generation?.target_model || state.target_model) === "general") return String(text ?? "");
  const target = state.last_generation?.target_model || state.target_model;
  return state.disable_color_palette && COLOR_PALETTE_TARGETS.has(target) && promptFormat === "json"
    ? stripColorPalettesFromPrompt(text, promptFormat)
    : String(text || "");
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
  const outputPositive = outputTextForState(state, positive, outputFormat);
  const outputFinalPrompt = outputTextForState(state, finalPrompt, outputFormat);

  setWidgetValue(node, "target_model", state.target_model);
  setWidgetValue(node, "prompt_format", outputFormat);
  setWidgetValue(node, "generation_type", state.generation_type || activeProfile?.default_generation_type || "text_to_image");
  setWidgetValue(node, "nsfw_enabled", Boolean(state.nsfw_enabled));
  setWidgetValue(node, "negative_enabled", negativeEnabled);
  setWidgetValue(node, "enable_bbox_json_input", Boolean(state.enable_bbox_json_input));
  setWidgetValue(node, "enable_text_input", Boolean(state.enable_text_input));
  setWidgetValue(node, "refresh_vram", Boolean(state.refresh_vram));
  setWidgetValue(node, "disable_color_palette", Boolean(
    state.disable_color_palette && COLOR_PALETTE_TARGETS.has(outputTarget) && outputFormat === "json",
  ));
  setWidgetValue(node, "generated_positive", positive || "");
  setWidgetValue(node, "generated_negative", negative || "");
  setWidgetValue(node, "final_prompt", finalPrompt || "");
  setWidgetValue(node, "audit_mode", state.audit_mode || "none");
  setWidgetValue(node, "ui_state", JSON.stringify(serializableState({ ...state, prompt_format: state.target_model === "general" ? state.prompt_format : promptFormat }), null, 2));
  markDirty();
  return outputFinalPrompt || outputPositive;
}

function buildDom(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function field(parent, label, control) {
  const wrap = buildDom("div", "workflowx-uap-field");
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

function inputIsLinked(node, inputName) {
  return Boolean(node?.inputs?.some((input) => input.name === inputName && input.link != null));
}

function coerceTextValue(value) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value || "");
  }
}

function resolveSourceText(node, inputName) {
  if (!node?.graph || !node.inputs) return null;
  const inputSlot = node.inputs.findIndex((input) => input.name === inputName);
  if (inputSlot < 0) return null;
  const input = node.inputs[inputSlot];
  if (!input || input.link == null) return null;
  const link = graphLink(node.graph, input.link);
  if (!link) return null;
  const srcNode = node.graph.getNodeById?.(link.origin_id);
  if (!srcNode) return null;

  const aliases = [
    srcNode.outputs?.[link.origin_slot]?.name,
    inputName,
    "text",
    "string",
    "value",
    "prompt",
    "json",
    "output",
  ].map((name) => String(name || "").trim().toLowerCase()).filter(Boolean);

  const widgets = Array.isArray(srcNode.widgets) ? srcNode.widgets : [];
  let widget = widgets.find((item) => aliases.includes(String(item.name || "").trim().toLowerCase()));
  if (!widget && Number.isInteger(link.origin_slot) && widgets[link.origin_slot]) widget = widgets[link.origin_slot];
  if (!widget) {
    widget = widgets.find((item) => ["string", "text", "customtext", "combo"].includes(String(item.type || "").toLowerCase()));
  }
  if (!widget && widgets.length === 1) widget = widgets[0];
  if (widget && "value" in widget) return { value: coerceTextValue(widget.value), widget, sourceNode: srcNode };

  if (Array.isArray(srcNode.widgets_values) && link.origin_slot < srcNode.widgets_values.length) {
    return { value: coerceTextValue(srcNode.widgets_values[link.origin_slot]), widget: null, sourceNode: srcNode };
  }
  for (const key of ["value", "text", "prompt", "json"]) {
    if (srcNode.properties && srcNode.properties[key] != null) {
      return { value: coerceTextValue(srcNode.properties[key]), widget: null, sourceNode: srcNode };
    }
  }
  return { value: "", widget: null, sourceNode: srcNode };
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

function watchReferenceImageInputs(node, onChange) {
  let watchedWidgets = [];

  function unwatch() {
    for (const { widget, callback } of watchedWidgets) widget.callback = callback;
    watchedWidgets = [];
  }

  function resolve() {
    return linkedReferenceImageInputNames(node)
      .map((name) => {
        const source = resolveSourcePreview(node, name);
        return source ? { ...source, inputName: name } : null;
      })
      .filter(Boolean);
  }

  function watchSourceWidgets() {
    unwatch();
    if (!node?.graph || !node.inputs) return;
    for (const inputName of linkedReferenceImageInputNames(node)) {
      const input = node.inputs.find((item) => item.name === inputName);
      const link = graphLink(node.graph, input?.link);
      const srcNode = link ? node.graph.getNodeById?.(link.origin_id) : null;
      const widget = srcNode?.widgets?.find((item) => item.name === "image" || item.name === "video");
      if (!widget) continue;
      const callback = widget.callback;
      widget.callback = function workflowXReferenceImageWidgetChanged() {
        const result = callback?.apply(this, arguments);
        setTimeout(() => onChange(resolve()), 100);
        return result;
      };
      watchedWidgets.push({ widget, callback });
    }
  }

  chainCallback(node, "onConnectionsChange", function workflowXUapReferenceImagesChanged(type) {
    if (type != null && type !== 1) return;
    setTimeout(() => {
      syncReferenceImageSockets(node);
      watchSourceWidgets();
      onChange(resolve());
    }, 100);
  });
  chainCallback(node, "onRemoved", unwatch);
  setTimeout(() => {
    syncReferenceImageSockets(node);
    watchSourceWidgets();
    onChange(resolve());
  }, 100);
  return unwatch;
}

function watchTextInput(node, inputName, onChange) {
  let watchedWidgets = [];

  function unwatch() {
    for (const { widget, callback } of watchedWidgets) widget.callback = callback;
    watchedWidgets = [];
  }

  function resolve() {
    const source = resolveSourceText(node, inputName);
    return {
      connected: inputIsLinked(node, inputName),
      value: source ? source.value : "",
      available: Boolean(source),
    };
  }

  function watchSourceWidget() {
    unwatch();
    const source = resolveSourceText(node, inputName);
    const widget = source?.widget;
    if (!widget) return;
    const callback = widget.callback;
    widget.callback = function workflowXTextWidgetChanged() {
      const result = callback?.apply(this, arguments);
      setTimeout(() => onChange(resolve()), 80);
      return result;
    };
    watchedWidgets.push({ widget, callback });
  }

  chainCallback(node, "onConnectionsChange", function workflowXUapTextInputChanged(type) {
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
  let graph = saved.graph && typeof saved.graph === "object" ? saved.graph : null;
  const hasScreenGeometry = Number.isFinite(saved.x) && Number.isFinite(saved.y) && Number.isFinite(saved.w) && Number.isFinite(saved.h);
  if (saved.attached !== true && saved.pinned === false && hasScreenGeometry) {
    graph = screenGeometryToGraph(node, {
      x: saved.x,
      y: saved.y,
      w: saved.w,
      h: saved.h,
    }, fallback.graph);
  }
  return {
    locked: Boolean(saved.locked),
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
  const graph = dock.__workflowXGraph || { x: 0, y: (node.size?.[1] || 0) + 12, w: dock.offsetWidth, h: dock.offsetHeight };
  const rect = dock.getBoundingClientRect();
  node.properties.workflowx_uap_docks[key] = {
    attached: true,
    locked: Boolean(dock.__workflowXLocked),
    graph: {
      x: graph.x,
      y: graph.y,
      w: Math.max(320, graph.w),
      h: Math.max(220, graph.h),
    },
    x: Math.max(0, rect.left),
    y: Math.max(0, rect.top),
    w: Math.max(320, rect.width),
    h: Math.max(220, rect.height),
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
  graphDocks.delete(dock);
  wakeDockModalOcclusion();
}

function dockIsOpen(node, key) {
  const dock = node?.__workflowXUapDocks?.[key];
  return Boolean(dock && document.body.contains(dock));
}

function bringDockForward(dock) {
  const canvasLayer = syncDockCanvasLayer(dock);
  if (canvasLayer) return;
  if (nextDockZ >= DOCK_Z_LIMIT) {
    let z = DOCK_Z_BASE;
    for (const openDock of graphDocks) openDock.style.zIndex = String(++z);
    nextDockZ = z;
  }
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
  const locked = Boolean(geom.locked);
  dock.__workflowXNode = node;
  dock.__workflowXKey = key;
  dock.__workflowXLocked = locked;
  dock.__workflowXGraph = { ...geom.graph };
  dock.style.width = `${geom.graph.w}px`;
  dock.style.height = `${geom.graph.h}px`;
  bringDockForward(dock);

  const head = buildDom("div", "workflowx-uap-dock-head");
  const titleEl = buildDom("div", "workflowx-uap-dock-title", title);
  const minBtn = buildDom("button", "workflowx-uap-btn", "_");
  const fullBtn = buildDom("button", "workflowx-uap-btn", "[]");
  const pinBtn = buildDom("button", `workflowx-uap-btn${locked ? " active" : ""}`, "pin");
  const closeBtn = buildDom("button", "workflowx-uap-btn", "x");
  for (const button of [minBtn, fullBtn, pinBtn, closeBtn]) button.type = "button";
  minBtn.title = "Minimize or restore this dock";
  fullBtn.title = "Toggle fullscreen";
  pinBtn.title = locked ? "Unlock moving and resizing" : "Lock moving and resizing";
  closeBtn.title = "Close this dock";
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
  graphDocks.add(dock);
  installDockWakes();
  wakeGraphDocks();
  wakeDockModalOcclusion();

  if (geom.minimized) dock.classList.add("minimized");

  let dragging = null;
  const pointerMove = (event) => {
    if (!dragging) return;
    event.preventDefault();
    const dx = (event.clientX - dragging.x) / dragging.scale;
    const dy = (event.clientY - dragging.y) / dragging.scale;
    dock.__workflowXGraph.x = dragging.graphX + dx;
    dock.__workflowXGraph.y = dragging.graphY + dy;
    dock.__workflowXDockSig = "";
    applyGraphDockTransform(dock);
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
    if (dock.__workflowXLocked) return;
    bringDockForward(dock);
    dragging = {
      x: event.clientX,
      y: event.clientY,
      graphX: dock.__workflowXGraph?.x || 0,
      graphY: dock.__workflowXGraph?.y || 0,
      scale: app.canvas?.ds?.scale || 1,
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
      if (dock.__workflowXLocked) return;
      event.preventDefault();
      bringDockForward(dock);
      const start = {
        x: event.clientX,
        y: event.clientY,
        graphX: dock.__workflowXGraph?.x || 0,
        graphY: dock.__workflowXGraph?.y || 0,
        width: dock.__workflowXGraph?.w || dock.offsetWidth,
        height: dock.__workflowXGraph?.h || dock.offsetHeight,
        scale: app.canvas?.ds?.scale || 1,
      };
      const resizeMove = (moveEvent) => {
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
          graphX = start.graphX + dx;
        }
        if (dir.includes("n")) {
          height = start.height - dy;
          graphY = start.graphY + dy;
        }
        width = Math.max(320, width);
        height = Math.max(220, height);
        dock.__workflowXGraph.x = graphX;
        dock.__workflowXGraph.y = graphY;
        dock.__workflowXGraph.w = width;
        dock.__workflowXGraph.h = height;
        dock.__workflowXDockSig = "";
        applyGraphDockTransform(dock);
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
    const entering = !dock.classList.contains("fullscreen");
    dock.classList.toggle("fullscreen", entering);
    bringDockForward(dock);
    if (entering) {
      dock.style.position = "fixed";
      dock.style.transform = "";
      dock.style.transformOrigin = "";
      dock.__workflowXDockSig = "";
    } else {
      dock.__workflowXDockSig = "";
      applyGraphDockTransform(dock);
      storeDockGeometry(node, key, dock, dock.classList.contains("minimized"));
    }
  });
  pinBtn.addEventListener("click", () => {
    dock.__workflowXLocked = !dock.__workflowXLocked;
    pinBtn.classList.toggle("active", dock.__workflowXLocked);
    pinBtn.title = dock.__workflowXLocked ? "Unlock moving and resizing" : "Lock moving and resizing";
    storeDockGeometry(node, key, dock, dock.classList.contains("minimized"));
  });
  closeBtn.addEventListener("click", () => closeDock(node, key));
  dock.addEventListener("pointerdown", () => bringDockForward(dock));
  dock.__workflowXCleanup = () => {
    document.removeEventListener("pointermove", pointerMove, true);
    document.removeEventListener("pointerup", pointerUp, true);
  };
  node.__workflowXUapDocks[key] = dock;
  pinBtn.title = dock.__workflowXLocked ? "Unlock moving and resizing" : "Lock moving and resizing";
  applyGraphDockTransform(dock);
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
  installQueueGenerationHooks();
  injectStyle();

  for (const name of [
    "target_model",
    "prompt_format",
    "generation_type",
    "nsfw_enabled",
    "negative_enabled",
    "enable_bbox_json_input",
    "enable_text_input",
    "refresh_vram",
    "disable_color_palette",
    "generated_positive",
    "generated_negative",
    "final_prompt",
    "audit_mode",
    "ui_state",
  ]) {
    hideWidget(node, name);
  }
  ensureInputSocket(node, "bbox_json", "STRING");
  ensureInputSocket(node, "raw_prompt_text", "STRING");
  syncReferenceImageSockets(node);

  const state = defaultState(node);
  state.gemini_key = loadStoredGeminiKey();
  state.openai_key = loadStoredOpenAIKey();
  state.openai_base_url = state.openai_base_url || DEFAULT_OPENAI_BASE_URL;
  state.connected_image_b64 = "";
  state.connected_images_b64 = [];
  state.connected_image_url = "";
  state.connected_image_urls = [];
  state.connected_image_available = false;
  state.connected_image_count = 0;
  state.connected_bbox_json = "";
  state.connected_bbox_json_available = false;
  state.connected_raw_prompt_text = "";
  state.connected_raw_prompt_text_available = false;
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
  const generationTypeSelect = createSelect();
  const providerSelect = createSelect();
  setSelectOptions(providerSelect, PROVIDERS.map(([value, label]) => ({ value, label })), state.backend);
  field(topGrid, "Target model", targetSelect);
  field(topGrid, "Prompt format", formatSelect);
  field(topGrid, "Generation type", generationTypeSelect);
  field(topGrid, "Provider", providerSelect);
  wrap.appendChild(topGrid);

  const generalPresetRow = buildDom("div", "workflowx-uap-row workflowx-uap-hidden");
  const generalPresetSelect = createSelect();
  option(generalPresetSelect, "none", "None");
  if (state.general_preset !== "none") option(generalPresetSelect, state.general_preset, state.general_preset);
  generalPresetSelect.value = state.general_preset;
  field(generalPresetRow, "Use preset", generalPresetSelect);
  const refreshPresetsBtn = buildDom("button", "workflowx-uap-btn", "Refresh");
  refreshPresetsBtn.type = "button";
  generalPresetRow.appendChild(refreshPresetsBtn);
  wrap.appendChild(generalPresetRow);

  // Provider credentials and tuning are useful, but should not dominate the
  // node surface.  Keep the active provider's panel in one collapsible group.
  const modelSettingsDetails = buildDom("details", "workflowx-uap-model-settings");
  modelSettingsDetails.open = Boolean(state.model_settings_open);
  const modelSettingsSummary = buildDom("summary", "", "Model settings");
  modelSettingsSummary.title = "Show or hide provider credentials, model selection, and runtime options";
  const modelSettingsBody = buildDom("div", "workflowx-uap-model-settings-body");
  modelSettingsDetails.appendChild(modelSettingsSummary);
  modelSettingsDetails.appendChild(modelSettingsBody);
  wrap.appendChild(modelSettingsDetails);

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
  const geminiSafetySelects = {};
  for (const [key, label] of GEMINI_SAFETY_FIELDS) {
    const safetySelect = createSelect();
    setSelectOptions(safetySelect, GEMINI_SAFETY_OPTIONS, state[key] || "BLOCK_NONE");
    geminiSafetySelects[key] = safetySelect;
    field(geminiGrid, `Safety: ${label}`, safetySelect);
  }
  geminiPanel.appendChild(geminiGrid);
  const geminiModelsRow = buildDom("div", "workflowx-uap-row");
  const fetchGeminiBtn = buildDom("button", "workflowx-uap-btn", "Fetch Gemini models");
  fetchGeminiBtn.type = "button";
  fetchGeminiBtn.title = "Fetch the Gemini models available to this API key";
  const geminiModelSelect = createSelect();
  geminiModelSelect.style.flex = "1";
  option(geminiModelSelect, state.gemini_model || "", state.gemini_model || "No model selected");
  geminiModelsRow.appendChild(fetchGeminiBtn);
  geminiModelsRow.appendChild(geminiModelSelect);
  geminiPanel.appendChild(geminiModelsRow);
  modelSettingsBody.appendChild(geminiPanel);

  const openaiPanel = buildDom("div", "workflowx-uap-panel");
  const openaiGrid = buildDom("div", "workflowx-uap-grid");
  const openaiBaseUrlInput = createInput("text");
  openaiBaseUrlInput.placeholder = DEFAULT_OPENAI_BASE_URL;
  openaiBaseUrlInput.value = state.openai_base_url || DEFAULT_OPENAI_BASE_URL;
  const openaiKeyInput = createInput("password");
  openaiKeyInput.placeholder = "optional for local servers";
  openaiKeyInput.value = state.openai_key || "";
  const openaiModelInput = createInput("text");
  openaiModelInput.placeholder = "Only needed when model discovery is unavailable";
  openaiModelInput.value = state.openai_model || "";
  const openaiTimeoutInput = createInput("number");
  openaiTimeoutInput.min = "5";
  openaiTimeoutInput.max = "3600";
  openaiTimeoutInput.step = "1";
  openaiTimeoutInput.value = String(state.openai_timeout || 120);
  const openaiServerTypeSelect = createSelect();
  setSelectOptions(openaiServerTypeSelect, [
    { value: "generic", label: "Generic OpenAI-compatible" },
  ], "generic");
  const openaiLifecycleSelect = createSelect();
  setSelectOptions(openaiLifecycleSelect, [
    { value: "server_managed", label: "Server managed (recommended)" },
    { value: "keep_loaded", label: "Keep loaded" },
    { value: "unload_after", label: "Unload after generation" },
  ], normalizeOpenAILifecycle(state.openai_lifecycle));
  const openaiReasoningSelect = createSelect();
  const openaiReasoningChoices = [
    { value: "default", label: "Provider / model default" },
    { value: "none", label: "None / Off" },
    { value: "on", label: "On (model-defined)" },
    { value: "minimal", label: "Minimal" },
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "max", label: "Maximum" },
    { value: "xhigh", label: "Extra high" },
  ];
  setSelectOptions(openaiReasoningSelect, openaiReasoningChoices, normalizeOpenAIReasoning(state.openai_reasoning_effort));
  field(openaiGrid, "Base URL", openaiBaseUrlInput);
  field(openaiGrid, "API key", openaiKeyInput);
  field(openaiGrid, "Timeout seconds", openaiTimeoutInput);
  field(openaiGrid, "Model lifecycle", openaiLifecycleSelect);
  field(openaiGrid, "Reasoning", openaiReasoningSelect);
  field(openaiGrid, "Manual model ID (fallback)", openaiModelInput);
  openaiPanel.appendChild(openaiGrid);
  const openaiModelsRow = buildDom("div", "workflowx-uap-row");
  const fetchOpenaiBtn = buildDom("button", "workflowx-uap-btn", "Fetch OpenAI-compatible models");
  fetchOpenaiBtn.type = "button";
  fetchOpenaiBtn.title = "Fetch models from the configured OpenAI-compatible server";
  const openaiModelSelect = createSelect();
  openaiModelSelect.style.flex = "1";
  option(openaiModelSelect, state.openai_model || "", state.openai_model || "No model selected");
  openaiModelsRow.appendChild(fetchOpenaiBtn);
  openaiModelsRow.appendChild(openaiModelSelect);
  openaiPanel.appendChild(openaiModelsRow);
  modelSettingsBody.appendChild(openaiPanel);
  let openaiDetectedServerType = "auto";
  // Profile helpers depend on profilesByKey, which is initialized later in this
  // setup function. Resolve the discovery scope lazily on the first refresh.
  let openaiDiscoveryScope = null;
  let openaiModelsById = new Map();
  let openaiReasoningCapabilities = {};

  function syncOpenAIReasoningOptions() {
    const requested = normalizeOpenAIServerType(openaiServerTypeSelect.value);
    const provider = requested === "auto" ? openaiDetectedServerType : requested;
    const current = normalizeOpenAIReasoning(openaiReasoningSelect.value);
    let allowed = openaiReasoningChoices.map((item) => item.value);
    if (provider === "lm_studio") {
      const model = openaiModelsById.get(openaiModelSelect.value);
      const advertised = Array.isArray(model?.reasoning_options) ? model.reasoning_options : [];
      allowed = advertised.length
        ? ["default", ...advertised.map((value) => normalizeOpenAIReasoning(value))]
        : ["default", "none", "on", "low", "medium", "high"];
    } else if (provider === "unsloth") {
      const advertised = Array.isArray(openaiReasoningCapabilities?.options)
        ? openaiReasoningCapabilities.options
        : [];
      allowed = advertised.length
        ? ["default", "none", "on", ...advertised.map((value) => normalizeOpenAIReasoning(value))]
        : allowed;
    } else if (provider === "generic") {
      allowed = allowed.filter((value) => value !== "on");
    }
    allowed = [...new Set(allowed)];
    const choices = openaiReasoningChoices.filter((item) => allowed.includes(item.value));
    setSelectOptions(openaiReasoningSelect, choices, allowed.includes(current) ? current : "default");
  }

  const providerDefaultPlaceholder = "Provider Default";

  const grokPanel = buildDom("div", "workflowx-uap-panel");
  const grokGrid = buildDom("div", "workflowx-uap-grid");
  const grokKeyInput = createInput("password");
  let grokKeyDirty = false;
  const markGrokKeyDirty = () => { grokKeyDirty = true; };
  grokKeyInput.addEventListener("input", markGrokKeyDirty);
  grokKeyInput.addEventListener("change", markGrokKeyDirty);
  const grokModelSelect = createSelect();
  const grokModelInput = createInput("text");
  const grokTimeoutInput = createInput("number");
  const grokMaxTokensInput = createInput("number");
  const grokTemperatureInput = createInput("number");
  const grokTopPInput = createInput("number");
  const grokReasoningSelect = createSelect();
  const grokCacheSelect = createSelect();
  grokKeyInput.placeholder = "xAI API key";
  grokModelInput.placeholder = "Manual model ID when discovery is unavailable";
  grokTimeoutInput.placeholder = "120";
  grokMaxTokensInput.placeholder = providerDefaultPlaceholder;
  grokTemperatureInput.placeholder = providerDefaultPlaceholder;
  grokTopPInput.placeholder = providerDefaultPlaceholder;
  setSelectOptions(grokReasoningSelect, [
    { value: "default", label: "Provider Default" }, { value: "low", label: "Low" },
    { value: "medium", label: "Medium" }, { value: "high", label: "High" },
    { value: "xhigh", label: "Extra high" },
  ], "default");
  setSelectOptions(grokCacheSelect, [{ value: "auto", label: "Auto" }, { value: "off", label: "Off" }], "auto");
  field(grokGrid, "xAI API key", grokKeyInput);
  field(grokGrid, "Timeout seconds", grokTimeoutInput);
  field(grokGrid, "Model", grokModelSelect);
  field(grokGrid, "Manual model ID", grokModelInput);
  field(grokGrid, "Maximum output tokens", grokMaxTokensInput);
  field(grokGrid, "Temperature", grokTemperatureInput);
  field(grokGrid, "Top P", grokTopPInput);
  field(grokGrid, "Reasoning effort", grokReasoningSelect);
  field(grokGrid, "Prompt caching", grokCacheSelect);
  grokPanel.appendChild(grokGrid);
  const fetchGrokBtn = buildDom("button", "workflowx-uap-btn", "Fetch xAI models");
  fetchGrokBtn.type = "button";
  grokPanel.appendChild(fetchGrokBtn);
  const grokCapabilityInfo = buildDom("div", "workflowx-uap-status", "Model capabilities will appear after discovery.");
  grokPanel.appendChild(grokCapabilityInfo);
  modelSettingsBody.appendChild(grokPanel);
  let grokModelsById = new Map();

  function syncGrokReasoningOptions() {
    const modelId = String(grokModelSelect.value || grokModelInput.value || "").toLowerCase();
    const discovered = grokModelsById.get(grokModelSelect.value);
    let allowed = Array.isArray(discovered?.reasoning_options)
      ? discovered.reasoning_options.map((value) => String(value).toLowerCase())
      : [];
    if (!allowed.length && modelId.includes("grok-4.6")) allowed = ["default", "low", "medium", "high", "xhigh"];
    else if (!allowed.length && (modelId.includes("grok-4.5") || modelId.includes("reasoning"))) {
      allowed = ["default", "low", "medium", "high"];
    } else if (!allowed.length) allowed = ["default"];
    const current = grokReasoningSelect.value || "default";
    const choices = [
      { value: "default", label: "Provider Default" }, { value: "low", label: "Low" },
      { value: "medium", label: "Medium" }, { value: "high", label: "High" },
      { value: "xhigh", label: "Extra high" },
    ].filter((item) => allowed.includes(item.value));
    setSelectOptions(grokReasoningSelect, choices, allowed.includes(current) ? current : "default");
  }

  const deepseekPanel = buildDom("div", "workflowx-uap-panel");
  const deepseekGrid = buildDom("div", "workflowx-uap-grid");
  const deepseekKeyInput = createInput("password");
  let deepseekKeyDirty = false;
  const markDeepseekKeyDirty = () => { deepseekKeyDirty = true; };
  deepseekKeyInput.addEventListener("input", markDeepseekKeyDirty);
  deepseekKeyInput.addEventListener("change", markDeepseekKeyDirty);
  const deepseekModelSelect = createSelect();
  const deepseekModelInput = createInput("text");
  const deepseekTimeoutInput = createInput("number");
  const deepseekMaxTokensInput = createInput("number");
  const deepseekThinkingSelect = createSelect();
  const deepseekReasoningSelect = createSelect();
  const deepseekTemperatureInput = createInput("number");
  const deepseekTopPInput = createInput("number");
  const deepseekImageDetailSelect = createSelect();
  deepseekKeyInput.placeholder = "DeepSeek API key";
  deepseekModelInput.placeholder = "Manual model ID when discovery is unavailable";
  deepseekTimeoutInput.placeholder = "120";
  deepseekMaxTokensInput.placeholder = providerDefaultPlaceholder;
  deepseekTemperatureInput.placeholder = "Provider Default · non-thinking only";
  deepseekTopPInput.placeholder = "Provider Default · non-thinking only";
  setSelectOptions(deepseekThinkingSelect, [
    { value: "default", label: "Provider Default (thinking enabled)" },
    { value: "enabled", label: "Enabled" },
    { value: "disabled", label: "Disabled" },
  ], "default");
  setSelectOptions(deepseekReasoningSelect, [
    { value: "default", label: "Provider Default (High)" },
    { value: "low", label: "Low" },
    { value: "high", label: "High" },
    { value: "max", label: "Maximum" },
  ], "default");
  setSelectOptions(deepseekImageDetailSelect, [
    { value: "default", label: "Provider Default" },
    { value: "auto", label: "Auto" },
    { value: "low", label: "Low (512×512)" },
    { value: "high", label: "High" },
    { value: "original", label: "Original" },
  ], "default");
  field(deepseekGrid, "DeepSeek API key", deepseekKeyInput);
  field(deepseekGrid, "Timeout seconds", deepseekTimeoutInput);
  field(deepseekGrid, "Model", deepseekModelSelect);
  field(deepseekGrid, "Manual model ID", deepseekModelInput);
  field(deepseekGrid, "Maximum output tokens", deepseekMaxTokensInput);
  field(deepseekGrid, "Thinking mode", deepseekThinkingSelect);
  field(deepseekGrid, "Reasoning effort", deepseekReasoningSelect);
  field(deepseekGrid, "Temperature (non-thinking only)", deepseekTemperatureInput);
  field(deepseekGrid, "Top P (non-thinking only)", deepseekTopPInput);
  field(deepseekGrid, "Image detail", deepseekImageDetailSelect);
  deepseekPanel.appendChild(deepseekGrid);
  const fetchDeepSeekBtn = buildDom("button", "workflowx-uap-btn", "Fetch DeepSeek models");
  fetchDeepSeekBtn.type = "button";
  deepseekPanel.appendChild(fetchDeepSeekBtn);
  const deepseekCapabilityInfo = buildDom(
    "div",
    "workflowx-uap-status",
    "Select a DeepSeek model to see its image capability. Context caching is automatic.",
  );
  deepseekPanel.appendChild(deepseekCapabilityInfo);
  modelSettingsBody.appendChild(deepseekPanel);
  let deepseekModelsById = new Map();

  function syncDeepSeekControls() {
    const modelId = String(deepseekModelSelect.value || deepseekModelInput.value || "").toLowerCase();
    const forcedNonThinking = modelId === "deepseek-chat";
    const forcedThinking = modelId === "deepseek-reasoner";
    if (forcedNonThinking) deepseekThinkingSelect.value = "disabled";
    if (forcedThinking) deepseekThinkingSelect.value = "enabled";
    deepseekThinkingSelect.disabled = forcedNonThinking || forcedThinking;
    const nonThinking = deepseekThinkingSelect.value === "disabled";
    deepseekReasoningSelect.disabled = nonThinking;
    deepseekTemperatureInput.disabled = !nonThinking;
    deepseekTopPInput.disabled = !nonThinking;
    const model = deepseekModelsById.get(deepseekModelSelect.value);
    const vision = model?.vision === true || deepseekModelSupportsVision(modelId);
    deepseekImageDetailSelect.disabled = !vision;
    const context = Number(model?.context_length || 0);
    const maximum = Number(model?.max_output_tokens || 0);
    deepseekCapabilityInfo.textContent = [
      vision ? "text + image input" : "text input only",
      context ? `context ${context.toLocaleString()} tokens` : "context not advertised",
      maximum ? `maximum output ${maximum.toLocaleString()} tokens` : "output limit not advertised",
      "automatic context caching",
    ].join(" · ");
  }

  function createStudioPanel(kind) {
    const panel = buildDom("div", "workflowx-uap-panel");
    const grid = buildDom("div", "workflowx-uap-grid");
    const baseUrl = createInput("text");
    const key = createInput("password");
    const model = createSelect();
    const manualModel = createInput("text");
    const timeout = createInput("number");
    const lifecycle = createSelect();
    const maxTokens = createInput("number");
    const context = createInput("number");
    const temperature = createInput("number");
    const topP = createInput("number");
    const topK = createInput("number");
    const minP = createInput("number");
    const repeatPenalty = createInput("number");
    const presencePenalty = createInput("number");
    const reasoning = createSelect();
    const thinkingMode = createSelect();
    const preserveThinking = document.createElement("input");
    preserveThinking.type = "checkbox";
    baseUrl.placeholder = kind === "lm_studio" ? "http://localhost:1234/v1" : "http://localhost:8000/v1";
    key.placeholder = "Optional server token";
    manualModel.placeholder = "Manual model ID when discovery is unavailable";
    timeout.placeholder = "120";
    for (const input of [maxTokens, context, temperature, topP, topK, minP, repeatPenalty, presencePenalty]) {
      input.placeholder = providerDefaultPlaceholder;
    }
    setSelectOptions(lifecycle, [
      { value: "server_managed", label: "Server managed" },
      { value: "keep_loaded", label: "Keep loaded" },
      { value: "unload_after", label: "Unload after generation" },
    ], "server_managed");
    setSelectOptions(reasoning, openaiReasoningChoices, "default");
    setSelectOptions(thinkingMode, [
      { value: "default", label: "Provider Default" },
      { value: "on", label: "Enabled" },
      { value: "off", label: "Disabled" },
    ], "default");
    field(grid, "Server URL", baseUrl);
    field(grid, "Server token", key);
    field(grid, "Model", model);
    field(grid, "Manual model ID", manualModel);
    field(grid, "Timeout seconds", timeout);
    field(grid, "Model lifecycle", lifecycle);
    field(grid, kind === "unsloth" ? "Maximum new tokens" : "Maximum output tokens", maxTokens);
    if (kind === "lm_studio") field(grid, "Context length", context);
    field(grid, "Temperature", temperature);
    field(grid, "Top P", topP);
    field(grid, "Top K", topK);
    field(grid, "Min P", minP);
    field(grid, kind === "unsloth" ? "Repetition penalty" : "Repeat penalty", repeatPenalty);
    if (kind === "unsloth") field(grid, "Presence penalty", presencePenalty);
    field(grid, "Reasoning", reasoning);
    if (kind === "unsloth") {
      field(grid, "Enable thinking", thinkingMode);
      const preserve = buildDom("label", "workflowx-uap-toggle");
      preserve.appendChild(preserveThinking);
      preserve.appendChild(document.createTextNode("Preserve thinking"));
      grid.appendChild(preserve);
    }
    panel.appendChild(grid);
    const fetch = buildDom("button", "workflowx-uap-btn", `Fetch ${kind === "lm_studio" ? "LM Studio" : "Unsloth Studio"} models`);
    fetch.type = "button";
    panel.appendChild(fetch);
    const capabilities = buildDom("div", "workflowx-uap-status", "Model capabilities will appear after discovery.");
    panel.appendChild(capabilities);
    modelSettingsBody.appendChild(panel);
    return { panel, baseUrl, key, model, manualModel, timeout, lifecycle, maxTokens, context, temperature, topP, topK, minP, repeatPenalty, presencePenalty, reasoning, thinkingMode, preserveThinking, fetch, capabilities, modelsById: new Map(), preserveThinkingSupported: false };
  }

  const lmStudio = createStudioPanel("lm_studio");
  const unsloth = createStudioPanel("unsloth");

  const ollamaPanel = buildDom("div", "workflowx-uap-panel");
  const ollamaGrid = buildDom("div", "workflowx-uap-grid");
  const hostInput = createInput("text");
  hostInput.value = state.ollama_host || DEFAULT_OLLAMA_HOST;
  const ollamaModelSelect = createSelect();
  const ollamaTimeoutInput = createInput("number");
  ollamaTimeoutInput.min = "5";
  ollamaTimeoutInput.max = "3600";
  ollamaTimeoutInput.value = String(state.ollama_timeout || 120);
  option(ollamaModelSelect, state.ollama_model || "", state.ollama_model || "No model selected");
  field(ollamaGrid, "Ollama host", hostInput);
  field(ollamaGrid, "Ollama model", ollamaModelSelect);
  field(ollamaGrid, "Timeout seconds", ollamaTimeoutInput);
  const ollamaOptionInputs = {};
  for (const [key, label, integer] of [
    ["num_predict", "Maximum output tokens", true], ["num_ctx", "Context length", true],
    ["temperature", "Temperature", false], ["top_p", "Top P", false], ["top_k", "Top K", true],
    ["min_p", "Min P", false], ["repeat_penalty", "Repeat penalty", false], ["seed", "Seed", true],
  ]) {
    const input = createInput("number"); input.placeholder = providerDefaultPlaceholder;
    input.dataset.integer = integer ? "1" : "0"; ollamaOptionInputs[key] = input; field(ollamaGrid, label, input);
  }
  ollamaPanel.appendChild(ollamaGrid);
  const ollamaRow = buildDom("div", "workflowx-uap-row");
  const fetchOllamaBtn = buildDom("button", "workflowx-uap-btn", "Fetch Ollama models");
  fetchOllamaBtn.type = "button";
  fetchOllamaBtn.title = "Fetch models from the configured Ollama server";
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
  modelSettingsBody.appendChild(ollamaPanel);

  const localPanel = buildDom("div", "workflowx-uap-panel");
  const localGrid = buildDom("div", "workflowx-uap-grid");
  const localModelSelect = createSelect();
  const mmprojSelect = createSelect();
  const systemPresetSelect = createSelect();
  const localAdditionalPathsInput = createInput("text");
  localAdditionalPathsInput.value = loadStoredAdditionalLocalModelPaths();
  localAdditionalPathsInput.placeholder = "D:\\LM Studio\\models; E:\\Shared GGUF";
  localAdditionalPathsInput.title = "Optional folders scanned recursively in addition to ComfyUI/models/LLM";
  const maxTokensInput = createInput("number");
  maxTokensInput.min = "32";
  maxTokensInput.value = String(state.max_tokens);
  const tempInput = createInput("number");
  tempInput.step = "0.05";
  tempInput.value = String(state.temperature);
  const ctxInput = createInput("number");
  ctxInput.min = "512";
  ctxInput.value = String(state.ctx_size);
  const localTimeoutInput = createInput("number");
  localTimeoutInput.min = "5";
  localTimeoutInput.max = "3600";
  localTimeoutInput.value = String(state.local_timeout || 180);
  const topPInput = createInput("number");
  topPInput.min = "0";
  topPInput.max = "1";
  topPInput.step = "0.05";
  topPInput.value = String(state.top_p);
  const topKInput = createInput("number");
  topKInput.min = "0";
  topKInput.max = "10000";
  topKInput.value = String(state.top_k);
  const repeatPenaltyInput = createInput("number");
  repeatPenaltyInput.min = "0";
  repeatPenaltyInput.max = "5";
  repeatPenaltyInput.step = "0.05";
  repeatPenaltyInput.value = String(state.repeat_penalty);
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
  field(localGrid, "Additional model folders (; separated)", localAdditionalPathsInput);
  field(localGrid, "Max tokens", maxTokensInput);
  field(localGrid, "Temperature", tempInput);
  field(localGrid, "Context", ctxInput);
  field(localGrid, "Timeout seconds", localTimeoutInput);
  field(localGrid, "Top P", topPInput);
  field(localGrid, "Top K", topKInput);
  field(localGrid, "Repeat penalty", repeatPenaltyInput);
  field(localGrid, "Memory mode", memorySelect);
  const reasoningSelect = createSelect();
  setSelectOptions(reasoningSelect, [
    { value: "auto", label: "Auto (model template)" },
    { value: "on", label: "On" },
    { value: "off", label: "Off" },
  ], normalizeUnifiedReasoning(state.reasoning));
  field(localGrid, "Reasoning", reasoningSelect);
  const thinkingLevelSelect = createSelect();
  setSelectOptions(thinkingLevelSelect, ["default", "low", "medium", "high", "custom"], state.thinking_level, (value) => ({default:"Default",low:"Low — 512 tokens",medium:"Medium — 2,048 tokens",high:"High — 4,096 tokens",custom:"Custom"}[value]));
  field(localGrid, "Thinking level (token budget)", thinkingLevelSelect);
  const thinkingBudgetInput = createInput("number");
  thinkingBudgetInput.min = "1";
  thinkingBudgetInput.step = "1";
  thinkingBudgetInput.value = String(state.thinking_budget);
  field(localGrid, "Custom thinking tokens", thinkingBudgetInput);
  const thinkingHelp = buildDom("div", "workflowx-uap-status");
  localGrid.appendChild(thinkingHelp);

  function thinkingBudget() {
    if (reasoningSelect.value === "off" || thinkingLevelSelect.value === "default") return undefined;
    const budget = {low:512,medium:2048,high:4096}[thinkingLevelSelect.value] ?? Number(thinkingBudgetInput.value);
    if (!Number.isSafeInteger(budget) || budget <= 0) throw new Error("Enter a positive whole number for Custom thinking tokens.");
    return budget;
  }

  function refreshThinkingControls() {
    thinkingLevelSelect.disabled = reasoningSelect.value === "off";
    thinkingBudgetInput.disabled = reasoningSelect.value === "off";
    thinkingBudgetInput.parentElement.classList.toggle("workflowx-uap-hidden", thinkingLevelSelect.value !== "custom");
    let budget;
    try { budget = thinkingBudget(); } catch (error) { thinkingHelp.textContent = error.message; return; }
    thinkingHelp.textContent = reasoningSelect.value === "off" ? "Thinking budget is inactive while Reasoning is Off."
      : budget >= Number(maxTokensInput.value) ? "Thinking uses the output allowance. This budget meets or exceeds Max tokens; increase Max tokens to leave room for the answer."
      : "Limits thinking tokens, not model effort. Thinking shares the Max tokens allowance with the answer. Default uses the runtime default.";
  }
  const speculativeSelect = createSelect();
  setSelectOptions(speculativeSelect, [
    { value: "auto", label: "Speculative: Auto (detect embedded MTP)" },
    { value: "off", label: "Speculative: Off" },
    { value: "mtp", label: "Speculative: Force embedded MTP" },
  ], state.speculative_mode || "auto");
  const mtpDraftTokensInput = createInput("number");
  mtpDraftTokensInput.min = "1";
  mtpDraftTokensInput.max = "8";
  mtpDraftTokensInput.value = String(state.mtp_draft_tokens || 2);
  field(localGrid, "Speculative decoding", speculativeSelect);
  field(localGrid, "MTP draft tokens", mtpDraftTokensInput);
  const gpuLayersInput = createInput("number");
  gpuLayersInput.min = "0";
  gpuLayersInput.max = "999";
  gpuLayersInput.value = String(state.n_gpu_layers);
  const cpuMoeLayersInput = createInput("number");
  cpuMoeLayersInput.min = "0";
  cpuMoeLayersInput.max = "999";
  cpuMoeLayersInput.value = String(state.n_cpu_moe_layers);
  const seedInput = createInput("number");
  seedInput.min = "-1";
  seedInput.max = "4294967295";
  seedInput.value = String(state.seed);
  field(localGrid, "GPU layers", gpuLayersInput);
  field(localGrid, "CPU MoE layers", cpuMoeLayersInput);
  field(localGrid, "Seed (-1 random)", seedInput);
  localPanel.appendChild(localGrid);
  const fetchLocalBtn = buildDom("button", "workflowx-uap-btn", "Refresh local GGUF list");
  fetchLocalBtn.type = "button";
  fetchLocalBtn.title = "Rescan ComfyUI/models/LLM and any additional model folders";
  localPanel.appendChild(fetchLocalBtn);
  modelSettingsBody.appendChild(localPanel);

  const promptArea = createTextarea(7);
  const detailSelect = createSelect();
  setSelectOptions(detailSelect, ["concise", "balanced", "high", "very high"], state.detail);
  field(wrap, "Prompt instructions", promptArea);
  field(wrap, "Detail level", detailSelect);
  const auditSelect = createSelect();
  const auditOptions = [
    { value: "none", label: "No audit", short: "No extra provider call.", help: "Use the current generation flow with no audit block and no extra provider call." },
    { value: "add_pass", label: "Add audit pass", short: "Generate, then audit. Failure keeps generation.", help: "Generate normally, then refine the generated prompt in one independent audit call. If it fails, keep the generated prompt." },
    { value: "audit_only", label: "Audit only", short: "Audit textbox only. Failure keeps textbox.", help: "Skip generation and refine the visible Prompt instructions text in one audit call. If it fails, keep that text." },
  ];
  setSelectOptions(auditSelect, auditOptions.map(({value,label}) => ({value,label})), state.audit_mode || "none");
  const executionGrid = buildDom("div", "workflowx-uap-grid");
  const auditField = buildDom("div", "workflowx-uap-field");
  auditField.appendChild(buildDom("label", "workflowx-uap-label", "Audit"));
  auditField.appendChild(auditSelect);
  const auditHelp = buildDom("div", "workflowx-uap-field-help");
  auditField.appendChild(auditHelp);
  const auditResult = buildDom("div", "workflowx-uap-field-help");
  auditField.appendChild(auditResult);
  executionGrid.appendChild(auditField);
  const workingModeSelect = createSelect();
  const workingModeOptions = [
    { value: "on_generate", label: "On Generate", short: "Button generates; queue reuses saved output.", help: "Generate only when the node's Generate button is clicked. Workflow queues reuse the saved result." },
    { value: "on_queue", label: "On Queue", short: "Queue waits for a fresh prompt.", help: "Generate and wait for a fresh prompt whenever this node is included in a queued workflow." },
  ];
  setSelectOptions(workingModeSelect, workingModeOptions.map(({value,label}) => ({value,label})), state.working_mode || "on_generate");
  const workingModeField = buildDom("div", "workflowx-uap-field");
  workingModeField.appendChild(buildDom("label", "workflowx-uap-label", "Working mode"));
  workingModeField.appendChild(workingModeSelect);
  const workingModeHelp = buildDom("div", "workflowx-uap-field-help");
  workingModeField.appendChild(workingModeHelp);
  executionGrid.appendChild(workingModeField);
  wrap.appendChild(executionGrid);
  const refreshAuditHelp = () => {
    const selected = auditOptions.find((item) => item.value === auditSelect.value) || auditOptions[0];
    auditSelect.title = selected.help;
    for (const item of auditSelect.options) item.title = auditOptions.find((entry) => entry.value === item.value)?.help || "";
    auditHelp.textContent = selected.short;
  };
  refreshAuditHelp();
  const refreshAuditResult = () => {
    const audit = state.last_generation?.audit || null;
    auditResult.textContent = audit?.status === "completed"
      ? `Last audit: ${audit.changed ? "refined" : "unchanged"}.`
      : audit?.status === "failed"
        ? "Last audit: failed; fallback retained."
        : "";
  };
  refreshAuditResult();
  const refreshWorkingModeHelp = () => {
    const selected = workingModeOptions.find((item) => item.value === workingModeSelect.value) || workingModeOptions[0];
    workingModeSelect.title = selected.help;
    for (const item of workingModeSelect.options) item.title = workingModeOptions.find((entry) => entry.value === item.value)?.help || "";
    workingModeHelp.textContent = selected.short;
  };
  refreshWorkingModeHelp();

  const ideogramPanel = buildDom("div", "workflowx-uap-panel");
  const ideogramLayoutArea = createTextarea(3);
  ideogramLayoutArea.placeholder = '{"background":"...","elements":[{"type":"obj","bbox":[200,250,800,750],"desc":"..."}]}';
  const ideogramPaletteInput = createInput("text");
  ideogramPaletteInput.placeholder = "#FFFFFF, #111111, #E43F5A";
  field(ideogramPanel, "BBox layout JSON hints", ideogramLayoutArea);
  field(ideogramPanel, "BBox palette hints", ideogramPaletteInput);
  ideogramPanel.classList.add("workflowx-uap-hidden");
  wrap.appendChild(ideogramPanel);

  const connectedInputRow = buildDom("div", "workflowx-uap-row");
  const bboxJsonToggle = buildDom("label", "workflowx-uap-toggle");
  const bboxJsonInput = document.createElement("input");
  bboxJsonInput.type = "checkbox";
  bboxJsonInput.checked = Boolean(state.enable_bbox_json_input);
  bboxJsonToggle.appendChild(bboxJsonInput);
  bboxJsonToggle.appendChild(document.createTextNode("use connected bbox JSON"));
  const rawTextToggle = buildDom("label", "workflowx-uap-toggle");
  const rawTextInput = document.createElement("input");
  rawTextInput.type = "checkbox";
  rawTextInput.checked = Boolean(state.enable_text_input);
  rawTextToggle.appendChild(rawTextInput);
  rawTextToggle.appendChild(document.createTextNode("use connected text"));
  connectedInputRow.appendChild(bboxJsonToggle);
  connectedInputRow.appendChild(rawTextToggle);
  wrap.appendChild(connectedInputRow);

  const imageRow = buildDom("div", "workflowx-uap-row");
  const nsfwToggle = buildDom("label", "workflowx-uap-toggle");
  const nsfwInput = document.createElement("input");
  nsfwInput.type = "checkbox";
  nsfwInput.checked = Boolean(state.nsfw_enabled);
  nsfwToggle.appendChild(nsfwInput);
  nsfwToggle.appendChild(document.createTextNode("NSFW instructions"));
  nsfwToggle.title = "Append the selected generation path's NSFW prompt rules; provider safety controls are unchanged";
  const negativeToggle = buildDom("label", "workflowx-uap-toggle");
  const negativeInput = document.createElement("input");
  negativeInput.type = "checkbox";
  negativeInput.checked = Boolean(state.negative_enabled);
  negativeToggle.appendChild(negativeInput);
  negativeToggle.appendChild(document.createTextNode("generate negative"));
  negativeToggle.title = "Ask supported profiles to generate a separate negative prompt";
  const refreshVramToggle = buildDom("label", "workflowx-uap-toggle");
  const refreshVramInput = document.createElement("input");
  refreshVramInput.type = "checkbox";
  refreshVramInput.checked = Boolean(state.refresh_vram);
  refreshVramToggle.appendChild(refreshVramInput);
  refreshVramToggle.appendChild(document.createTextNode("refresh VRAM"));
  refreshVramToggle.title = "Unload ComfyUI models and clear cache before prompt generation";
  const disablePaletteToggle = buildDom("label", "workflowx-uap-toggle");
  const disablePaletteInput = document.createElement("input");
  disablePaletteInput.type = "checkbox";
  disablePaletteInput.checked = Boolean(state.disable_color_palette);
  disablePaletteToggle.appendChild(disablePaletteInput);
  disablePaletteToggle.appendChild(document.createTextNode("disable color palette"));
  disablePaletteToggle.title = "Remove color_palette blocks from generated JSON output";
  imageRow.appendChild(nsfwToggle);
  imageRow.appendChild(negativeToggle);
  imageRow.appendChild(refreshVramToggle);
  imageRow.appendChild(disablePaletteToggle);
  wrap.appendChild(imageRow);

  const toolsRow = buildDom("div", "workflowx-uap-row");
  const positivePreviewBtn = buildDom("button", "workflowx-uap-btn", "Show positive");
  positivePreviewBtn.type = "button";
  positivePreviewBtn.title = "Open the saved positive prompt preview";
  const negativePreviewBtn = buildDom("button", "workflowx-uap-btn", "Show negative");
  negativePreviewBtn.type = "button";
  negativePreviewBtn.title = "Open the saved negative prompt preview";
  const ideogramBtn = buildDom("button", "workflowx-uap-btn", "BBox layout");
  ideogramBtn.type = "button";
  ideogramBtn.title = "Open the bounding-box layout editor for supported targets";
  const modelSettingsBtn = buildDom("button", "workflowx-uap-btn", "Profile settings");
  modelSettingsBtn.type = "button";
  modelSettingsBtn.title = "Edit prompt profiles and JsonX generation settings";
  const presetsBtn = buildDom("button", "workflowx-uap-btn", "Presets");
  presetsBtn.type = "button";
  presetsBtn.title = "Create and edit character or scene prompt presets used by @tag";
  toolsRow.appendChild(positivePreviewBtn);
  toolsRow.appendChild(negativePreviewBtn);
  toolsRow.appendChild(ideogramBtn);
  toolsRow.appendChild(modelSettingsBtn);
  toolsRow.appendChild(presetsBtn);
  const generalPreviewBtn = buildDom("button", "workflowx-uap-btn workflowx-uap-hidden", "Payload preview");
  generalPreviewBtn.type = "button";
  toolsRow.appendChild(generalPreviewBtn);
  wrap.appendChild(toolsRow);

  const generateRow = buildDom("div", "workflowx-uap-row");
  const generateBtn = buildDom("button", "workflowx-uap-btn primary", "Generate");
  generateBtn.type = "button";
  generateBtn.title = "Generate and save the prompt using the active profile and provider";
  generateBtn.textContent = state.audit_mode === "audit_only" ? "Audit prompt" : "Generate";
  const cancelJsonXBtn = buildDom("button", "workflowx-uap-btn", "Cancel");
  cancelJsonXBtn.type = "button";
  cancelJsonXBtn.title = "Stop the active generation and keep the previous output";
  cancelJsonXBtn.classList.add("workflowx-uap-hidden");
  const status = buildDom("div", "workflowx-uap-status", "Ready.");
  generateRow.appendChild(generateBtn);
  generateRow.appendChild(cancelJsonXBtn);
  generateRow.appendChild(status);
  wrap.appendChild(generateRow);

  const preview = buildDom("div", "workflowx-uap-preview");
  preview.classList.add("workflowx-uap-hidden");
  wrap.appendChild(preview);

  promptArea.value = state.prompt_text;
  ideogramLayoutArea.value = state.ideogram_layout;
  ideogramPaletteInput.value = state.ideogram_palette;

  let profiles = FALLBACK_PROFILES.map(ensureProfileShape);
  let profilesByKey = profileMap(profiles);
  let profilesLoaded = false;

  function activeProfile() {
    if (state.target_model === "general") return GENERAL_PROFILE;
    return profilesByKey.get(state.target_model) || profiles[0];
  }

  function ensureJsonXConfigSnapshot(profile = activeProfile()) {
    if (profile?.engine !== "jsonx") return null;
    state.jsonx_profile_configs ||= {};
    const saved = state.jsonx_profile_configs[profile.key];
    if (!saved || typeof saved !== "object") {
      state.jsonx_profile_configs[profile.key] = jsonxBehaviorConfig(profile.jsonx_config);
    } else {
      state.jsonx_profile_configs[profile.key] = jsonxBehaviorConfig(saved);
    }
    return state.jsonx_profile_configs[profile.key];
  }

  function effectiveJsonXConfig(profile = activeProfile()) {
    return jsonxBehaviorConfig({
      ...(profile?.jsonx_config || {}),
      ...(ensureJsonXConfigSnapshot(profile) || {}),
    });
  }

  function setStatus(message, isError = false) {
    status.textContent = message || "";
    status.classList.toggle("error", Boolean(isError));
  }

  let promptPresets = [];
  const tagSuggestions = buildDom("div", "workflowx-uap-tag-suggestions workflowx-uap-hidden");
  document.body.appendChild(tagSuggestions);
  let tagSuggestionIndex = 0;
  let tagMatch = null;

  async function refreshPromptPresets() {
    const data = await fetchJsonChecked(`${ROUTE}/prompt_presets`, {}, "Prompt presets");
    if (Number(data.preset_schema_version || 0) !== PRESET_SCHEMA_VERSION) {
      throw new Error("Prompt preset schema mismatch. Restart ComfyUI and hard-refresh the browser.");
    }
    promptPresets = Array.isArray(data.presets) ? data.presets : [];
    return promptPresets;
  }

  function activeTagMatch() {
    const caret = Number(promptArea.selectionStart || 0);
    const before = promptArea.value.slice(0, caret);
    const match = before.match(/(?:^|[^A-Za-z0-9_@])@([A-Za-z0-9_-]*)$/);
    if (!match) return null;
    const at = before.lastIndexOf("@", caret - 1);
    return at < 0 ? null : { start: at, end: caret, query: match[1].toLowerCase() };
  }

  function closeTagSuggestions() {
    tagSuggestions.classList.add("workflowx-uap-hidden");
    tagSuggestions.replaceChildren();
    tagMatch = null;
  }

  function chooseTagPreset(preset) {
    if (!tagMatch) return;
    promptArea.setRangeText(`@${preset.tag}`, tagMatch.start, tagMatch.end, "end");
    closeTagSuggestions();
    promptArea.focus();
    syncPreview();
  }

  function renderTagSuggestions() {
    tagMatch = activeTagMatch();
    if (!tagMatch || !promptPresets.length) { closeTagSuggestions(); return; }
    const matches = promptPresets.filter((preset) =>
      String(preset.tag || "").toLowerCase().startsWith(tagMatch.query) ||
      String(preset.name || "").toLowerCase().includes(tagMatch.query),
    ).slice(0, 10);
    if (!matches.length) { closeTagSuggestions(); return; }
    tagSuggestionIndex = Math.min(tagSuggestionIndex, matches.length - 1);
    tagSuggestions.replaceChildren();
    matches.forEach((preset, index) => {
      const item = buildDom("button", `workflowx-uap-tag-suggestion${index === tagSuggestionIndex ? " active" : ""}`);
      item.type = "button";
      item.append(document.createTextNode(`@${preset.tag} — ${preset.name}`));
      item.appendChild(buildDom("small", "", preset.type));
      item.addEventListener("pointerdown", (event) => { event.preventDefault(); chooseTagPreset(preset); });
      tagSuggestions.appendChild(item);
    });
    const rect = promptArea.getBoundingClientRect();
    tagSuggestions.style.left = `${Math.max(8, rect.left)}px`;
    tagSuggestions.style.top = `${Math.min(window.innerHeight - 230, rect.bottom + 4)}px`;
    tagSuggestions.classList.remove("workflowx-uap-hidden");
    tagSuggestions.__matches = matches;
  }

  promptArea.addEventListener("input", () => { tagSuggestionIndex = 0; renderTagSuggestions(); });
  promptArea.addEventListener("click", renderTagSuggestions);
  promptArea.addEventListener("blur", () => setTimeout(closeTagSuggestions, 120));
  promptArea.addEventListener("keydown", (event) => {
    if (tagSuggestions.classList.contains("workflowx-uap-hidden")) return;
    const matches = tagSuggestions.__matches || [];
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      tagSuggestionIndex = (tagSuggestionIndex + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length;
      renderTagSuggestions();
    } else if ((event.key === "Enter" || event.key === "Tab") && matches[tagSuggestionIndex]) {
      event.preventDefault();
      chooseTagPreset(matches[tagSuggestionIndex]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeTagSuggestions();
    }
  });

  async function openPromptPresets() {
    try { await refreshPromptPresets(); }
    catch (error) { setStatus(`Presets error: ${error.message}`, true); return; }
    const backdrop = buildDom("div", "workflowx-uap-modal-backdrop");
    const modal = buildDom("div", "workflowx-uap-modal workflowx-uap-preset-modal");
    const head = buildDom("div", "workflowx-uap-modal-head");
    head.appendChild(buildDom("div", "workflowx-uap-modal-title", "Unified PrompterX · Character and Scene Presets"));
    const close = buildDom("button", "workflowx-uap-btn", "Close");
    close.type = "button"; close.onclick = () => backdrop.remove(); head.appendChild(close); modal.appendChild(head);

    const body = buildDom("div", "workflowx-uap-preset-body");
    const sidebar = buildDom("div", "workflowx-uap-preset-sidebar");
    sidebar.appendChild(buildDom("div", "workflowx-uap-label", "Saved presets"));
    const presetList = buildDom("div", "workflowx-uap-preset-list");
    sidebar.appendChild(presetList);
    const newActions = buildDom("div", "workflowx-uap-preset-new-actions");
    const createCharacter = buildDom("button", "workflowx-uap-btn", "New character");
    const createScene = buildDom("button", "workflowx-uap-btn", "New scene");
    createCharacter.type = "button"; createScene.type = "button";
    newActions.append(createCharacter, createScene); sidebar.appendChild(newActions);
    body.appendChild(sidebar);

    const editor = buildDom("div", "workflowx-uap-preset-editor");
    const meta = buildDom("div", "workflowx-uap-preset-meta");
    const type = createSelect(); setSelectOptions(type, [{value:"character",label:"Character"},{value:"scene",label:"Scene"}], "character");
    const name = createInput("text");
    const tag = createInput("text"); tag.placeholder = "tag without @";
    field(meta, "Type", type); field(meta, "Name", name); field(meta, "Tag", tag); editor.appendChild(meta);
    const profileDetails = createTextarea(9);
    profileDetails.classList.add("profile-details");
    profileDetails.placeholder = "Stable character or scene traits used as the preset baseline.";
    const guidance = createTextarea(6);
    guidance.classList.add("adaptation-guidance");
    guidance.placeholder = "How the model should adapt this preset to explicit prompt details.";
    field(editor, "Profile details", profileDetails);
    field(editor, "Adaptation guidance", guidance);
    body.appendChild(editor); modal.appendChild(body);

    const foot = buildDom("div", "workflowx-uap-modal-foot");
    const save = buildDom("button", "workflowx-uap-btn primary", "Save");
    const reset = buildDom("button", "workflowx-uap-btn", "Reset built-in");
    const remove = buildDom("button", "workflowx-uap-btn", "Delete custom");
    const message = buildDom("div", "workflowx-uap-modal-message");
    for (const button of [save, reset, remove]) button.type = "button";
    foot.append(save, reset, remove, message); modal.appendChild(foot); backdrop.appendChild(modal); document.body.appendChild(backdrop); stopGraphEvents(modal);
    backdrop.addEventListener("mousedown", (event) => { if (event.target === backdrop) backdrop.remove(); });
    let selectedId = "";
    const selectedPreset = () => promptPresets.find((preset) => preset.id === selectedId) || null;
    const renderSavedPresets = () => {
      presetList.replaceChildren();
      for (const preset of promptPresets) {
        const item = buildDom("button", `workflowx-uap-preset-item${preset.id === selectedId ? " active" : ""}`, preset.name);
        item.type = "button";
        item.appendChild(buildDom("small", "", `@${preset.tag} · ${preset.type}${preset.builtin ? " · built-in" : ""}`));
        item.addEventListener("click", () => { selectedId = preset.id; refill(selectedId); message.textContent = ""; });
        presetList.appendChild(item);
      }
    };
    const refill = (preferred = selectedId) => {
      selectedId = promptPresets.some((preset) => preset.id === preferred) ? preferred : (promptPresets[0]?.id || "");
      const preset = selectedPreset();
      renderSavedPresets();
      if (!preset) return;
      type.value = preset.type; name.value = preset.name; tag.value = preset.tag;
      profileDetails.value = preset.profile_markdown ?? preset.markdown ?? "";
      guidance.value = preset.adaptation_guidance || "";
      reset.disabled = !preset.builtin; remove.disabled = Boolean(preset.builtin);
    };
    const beginNew = (presetType) => {
      selectedId = ""; type.value = presetType; name.value = ""; tag.value = ""; profileDetails.value = "";
      guidance.value = "Integrate this preset naturally into the user prompt. Explicit user instructions override matching defaults; retain unmentioned defaults and include only details relevant to the requested composition.";
      renderSavedPresets();
      reset.disabled = true; remove.disabled = true; name.focus(); message.textContent = `Creating a new ${presetType} preset.`;
    };
    createCharacter.onclick = () => beginNew("character"); createScene.onclick = () => beginNew("scene");
    save.onclick = async () => {
      save.disabled = true;
      try {
        const data = await fetchJsonChecked(`${ROUTE}/prompt_presets`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:selectedId,type:type.value,name:name.value,tag:tag.value,profile_markdown:profileDetails.value,adaptation_guidance:guidance.value})}, "Save prompt preset");
        promptPresets = data.presets || []; selectedId = selectedId || promptPresets.find((preset) => preset.tag === tag.value.trim().replace(/^@/, "").toLowerCase())?.id || ""; refill(selectedId); message.textContent = "Preset saved."; setStatus("Prompt preset saved.");
      } catch (error) { message.textContent = `Save error: ${error.message}`; }
      finally { save.disabled = false; }
    };
    reset.onclick = async () => {
      if (!selectedId) return;
      try { const data = await fetchJsonChecked(`${ROUTE}/prompt_presets/reset`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:selectedId})}, "Reset prompt preset"); promptPresets = data.presets || []; refill(selectedId); message.textContent = "Built-in preset restored."; }
      catch (error) { message.textContent = `Reset error: ${error.message}`; }
    };
    remove.onclick = async () => {
      const preset = selectedPreset(); if (!preset || preset.builtin || !window.confirm(`Delete ${preset.name}?`)) return;
      try { const data = await fetchJsonChecked(`${ROUTE}/prompt_presets/delete`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:selectedId})}, "Delete prompt preset"); promptPresets = data.presets || []; selectedId = promptPresets[0]?.id || ""; refill(selectedId); message.textContent = "Custom preset deleted."; }
      catch (error) { message.textContent = `Delete error: ${error.message}`; }
    };
    refill(promptPresets[0]?.id || "");
  }

  function refreshBackends() {
    applyActiveProviderSettingsToControls();
    const backend = providerBackend();
    providerSelect.value = backend;
    modelSettingsDetails.classList.remove("workflowx-uap-hidden");
    geminiPanel.classList.toggle("workflowx-uap-hidden", backend !== "gemini");
    openaiPanel.classList.toggle("workflowx-uap-hidden", backend !== "openai");
    grokPanel.classList.toggle("workflowx-uap-hidden", backend !== "grok");
    deepseekPanel.classList.toggle("workflowx-uap-hidden", backend !== "deepseek");
    lmStudio.panel.classList.toggle("workflowx-uap-hidden", backend !== "lm_studio");
    unsloth.panel.classList.toggle("workflowx-uap-hidden", backend !== "unsloth");
    ollamaPanel.classList.toggle("workflowx-uap-hidden", backend !== "ollama");
    localPanel.classList.toggle("workflowx-uap-hidden", backend !== "local");
    scheduleVisibleContentResize();
  }

  function refreshProfiles() {
    const options = [GENERAL_PROFILE, ...profiles].map((profile) => ({
      value: profile.key,
      label: profile.label || profile.key,
    }));
    if (!profilesLoaded && state.target_model && !options.some((item) => item.value === state.target_model)) {
      options.push({ value: state.target_model, label: state.target_model });
    }
    setSelectOptions(targetSelect, options, state.target_model);
    state.target_model = targetSelect.value || state.target_model;
    refreshFormats();
  }

  function refreshFormats() {
    const profile = activeProfile();
    const jsonx = isJsonXProfile();
    const general = state.target_model === "general";
    for (const control of [formatSelect, generationTypeSelect, detailSelect]) control.parentElement.classList.toggle("workflowx-uap-hidden", general);
    for (const control of [nsfwToggle, negativeToggle, bboxJsonToggle, disablePaletteToggle, modelSettingsBtn]) control.classList.toggle("workflowx-uap-hidden", general);
    generalPresetRow.classList.toggle("workflowx-uap-hidden", !general);
    generalPreviewBtn.classList.toggle("workflowx-uap-hidden", !general);
    if (general) {
      promptArea.placeholder = "Enter your instructions. An optional preset supplies the system instructions.";
      ideogramBtn.classList.add("workflowx-uap-hidden");
      auditField.classList.remove("workflowx-uap-hidden");
      generateBtn.textContent = state.audit_mode === "audit_only" ? "Audit prompt" : "Generate";
      closeDock(node, "ideogram");
      refreshGeneralPresets();
      refreshBackends();
      syncPreview();
      scheduleVisibleContentResize();
      return;
    }
    if (jsonx) ensureJsonXConfigSnapshot(profile);
    const formats = enabledProfileFormats(profile);
    if (!formats.includes(state.prompt_format)) state.prompt_format = profile.default_format || formats[0];
    setSelectOptions(formatSelect, formats, state.prompt_format, (value) => jsonx
      ? (value === "json" ? "JsonX JSON" : "Natural language")
      : value);
    state.prompt_format = formatSelect.value;
    const generationPaths = Object.entries(profile.generation_paths || {});
    if (!generationPaths.some(([type]) => type === state.generation_type)) {
      state.generation_type = profile.default_generation_type || generationPaths[0]?.[0] || "text_to_image";
    }
    setSelectOptions(generationTypeSelect, generationPaths.map(([type, path]) => ({
      value: type,
      label: path?.label || GENERATION_TYPE_MAP.get(type)?.label || type,
    })), state.generation_type);
    state.generation_type = generationTypeSelect.value;
    promptArea.placeholder = promptInstructionsPlaceholder(profile);
    ideogramPanel.classList.add("workflowx-uap-hidden");
    ideogramBtn.classList.toggle("workflowx-uap-hidden", !isBboxLayoutTarget(state.target_model));
    if (!isBboxLayoutTarget(state.target_model)) closeDock(node, "ideogram");
    const negativeSupported = Boolean(profile.negative_supported);
    state.negative_enabled = negativeSupported && Boolean(state.negative_enabled);
    negativeInput.checked = state.negative_enabled;
    negativeInput.disabled = !negativeSupported;
    negativeToggle.classList.toggle("workflowx-uap-hidden", jsonx || !negativeSupported);
    bboxJsonToggle.classList.toggle("workflowx-uap-hidden", jsonx || !isBboxLayoutTarget(state.target_model));
    ideogramBtn.classList.toggle("workflowx-uap-hidden", jsonx || !isBboxLayoutTarget(state.target_model));
    disablePaletteToggle.classList.toggle("workflowx-uap-hidden", !(state.prompt_format === "json" && COLOR_PALETTE_TARGETS.has(state.target_model)));
    auditField.classList.toggle("workflowx-uap-hidden", jsonx);
    generateBtn.textContent = jsonx ? "Generate" : (state.audit_mode === "audit_only" ? "Audit prompt" : "Generate");
    modelSettingsBtn.textContent = "Profile settings";
    refreshBackends();
    syncPreview();
    scheduleVisibleContentResize();
  }

  function readFieldsIntoState() {
    state.general_preset = generalPresetSelect.value || "none";
    state.prompt_text = promptArea.value;
    state.detail = detailSelect.value;
    state.audit_mode = auditSelect.value || "none";
    state.working_mode = workingModeSelect.value || "on_generate";
    if (state.target_model !== "general") state.generation_type = generationTypeSelect.value;
    state.nsfw_enabled = nsfwInput.checked;
    state.enable_bbox_json_input = bboxJsonInput.checked;
    state.enable_text_input = rawTextInput.checked;
    state.ideogram_layout = ideogramLayoutArea.value;
    state.ideogram_palette = ideogramPaletteInput.value;
    state.refresh_vram = refreshVramInput.checked;
    state.disable_color_palette = disablePaletteInput.checked;
    if (isJsonXProfile()) {
      persistJsonXProviderFromControls();
      return;
    }
    state.gemini_timeout = Number(timeoutInput.value || 120);
    for (const [key] of GEMINI_SAFETY_FIELDS) state[key] = geminiSafetySelects[key]?.value || "BLOCK_NONE";
    state.openai_base_url = openaiBaseUrlInput.value.trim() || DEFAULT_OPENAI_BASE_URL;
    state.openai_model = (openaiModelSelect.value || openaiModelInput.value || "").trim();
    state.openai_timeout = Number(openaiTimeoutInput.value || 120);
    state.openai_server_type = normalizeOpenAIServerType(openaiServerTypeSelect.value);
    state.openai_lifecycle = normalizeOpenAILifecycle(openaiLifecycleSelect.value);
    state.openai_reasoning_effort = normalizeOpenAIReasoning(openaiReasoningSelect.value);
    state.ollama_host = hostInput.value || DEFAULT_OLLAMA_HOST;
    state.ollama_timeout = Number(ollamaTimeoutInput.value || 120);
    state.ollama_think = thinkInput.checked;
    state.unload_after = unloadInput.checked;
    state.max_tokens = Number(maxTokensInput.value || 768);
    state.temperature = Number(tempInput.value || 0.7);
    state.top_p = Number(topPInput.value || 0.9);
    state.top_k = Number(topKInput.value || 40);
    state.repeat_penalty = Number(repeatPenaltyInput.value || 1.05);
    state.ctx_size = Number(ctxInput.value || 8192);
    state.local_timeout = Number(localTimeoutInput.value || 180);
    state.memory_mode = memorySelect.value;
    state.reasoning = reasoningSelect.value;
    state.thinking_level = thinkingLevelSelect.value;
    state.thinking_budget = Number(thinkingBudgetInput.value || 2048);
    state.speculative_mode = speculativeSelect.value;
    state.mtp_draft_tokens = Number(mtpDraftTokensInput.value || 2);
    state.n_gpu_layers = Number(gpuLayersInput.value || 99);
    state.n_cpu_moe_layers = Number(cpuMoeLayersInput.value || 0);
    state.seed = Number(seedInput.value ?? -1);
    state.local_model = localModelSelect.value || "";
    state.local_mmproj = mmprojSelect.value || "none";
    state.local_system_prompt_preset = systemPresetSelect.value || "none";
    persistStandardProviderFromControls();
  }

  function syncPreview() {
    readFieldsIntoState();
    refreshThinkingControls();
    refreshAuditResult();
    const prompt = syncOutputWidgets(node, state, activeProfile());
    preview.textContent = prompt || "(Generate or type prompt output to preview here.)";
    updateOutputDocks();
  }

  function persistModelSelection() {
    if (isJsonXProfile()) {
      persistJsonXProviderFromControls();
      return;
    }
    storeModelSelection({
      backend: state.backend,
      gemini_model: state.gemini_model,
      openai_model: state.openai_model,
      ollama_model: state.ollama_model,
      local_model: state.local_model,
    });
  }

  function cachedOutput() {
    return state.last_generation || {
      prompt: widgetValue(node, "final_prompt", ""),
      positive: widgetValue(node, "generated_positive", ""),
      negative: widgetValue(node, "generated_negative", ""),
      target_model: widgetValue(node, "target_model", state.target_model),
      prompt_format: widgetValue(node, "prompt_format", state.prompt_format),
    };
  }

  function setPreviewButtonLabels() {
    positivePreviewBtn.textContent = dockIsOpen(node, "output_positive") ? "Hide positive" : "Show positive";
    negativePreviewBtn.textContent = dockIsOpen(node, "output_negative") ? "Hide negative" : "Show negative";
    const ideogramOpen = dockIsOpen(node, "ideogram");
    ideogramBtn.textContent = ideogramOpen ? "Hide layout" : "BBox layout";
    ideogramBtn.classList.toggle("active", ideogramOpen);
  }

  function updateOutputDocks() {
    const refs = node.__workflowXUapOutputRefs;
    if (!refs) return;
    const cached = cachedOutput();
    if (refs.positive?.view && document.body.contains(refs.positive.view)) {
      const promptFormat = cached.prompt_format || state.prompt_format;
      refs.positive.view.value = outputTextForState(state, cached.positive || "", promptFormat);
      refs.positive.prompt = outputTextForState(state, cached.prompt || "", promptFormat);
    } else if (refs.positive) {
      delete refs.positive;
    }
    if (refs.negative?.view && document.body.contains(refs.negative.view)) {
      const promptFormat = cached.prompt_format || state.prompt_format;
      refs.negative.view.value = cached.negative || "";
      refs.negative.prompt = outputTextForState(state, cached.prompt || "", promptFormat);
    } else if (refs.negative) {
      delete refs.negative;
    }
    setPreviewButtonLabels();
  }

  function setBusy(isBusy) {
    generateBtn.disabled = isBusy;
    generateBtn.textContent = isBusy ? "Generating..." : "Generate";
    cancelJsonXBtn.classList.toggle("workflowx-uap-hidden", !isBusy);
    cancelJsonXBtn.disabled = !isBusy;
  }

  function syncMemoryControls() {
    const memoryMode = memorySelect.value || "auto";
    gpuLayersInput.disabled = !["gpu_layers", "gpu_and_cpu_moe_layers"].includes(memoryMode);
    cpuMoeLayersInput.disabled = !["cpu_moe_layers", "gpu_and_cpu_moe_layers"].includes(memoryMode);
  }

  function measureVisibleContentHeight() {
    const liveWidth = Math.ceil(wrap.getBoundingClientRect().width || Math.max(320, (node.size?.[0] || 440) - 24));
    const clone = wrap.cloneNode(true);
    clone.style.cssText += [
      "position:fixed",
      "left:-100000px",
      "top:0",
      `width:${liveWidth}px`,
      "height:auto",
      "min-height:0",
      "max-height:none",
      "overflow:visible",
      "visibility:hidden",
      "pointer-events:none",
      "contain:none",
    ].join(";");
    document.body.appendChild(clone);
    const height = Math.ceil(Math.max(clone.scrollHeight, clone.getBoundingClientRect().height));
    clone.remove();
    return Math.max(160, height + 12);
  }

  function fitNode() {
    if (!node.__workflowXUapWidget) return;
    node.__workflowXUapWidgetHeight = measureVisibleContentHeight();
    markDirty();
  }

  function resizeNodeToVisibleContent() {
    if (!node.__workflowXUapWidget || node.__workflowXUapFitting) return;
    node.__workflowXUapFitting = true;
    try {
      fitNode();
      const width = node.size?.[0] || 440;
      const computed = node.computeSize?.();
      const targetHeight = Math.max(260, Math.ceil(computed?.[1] || node.__workflowXUapWidgetHeight + 80));
      if (Math.abs((node.size?.[1] || 0) - targetHeight) > 4) {
        node.setSize?.([width, targetHeight]);
      }
    } finally {
      node.__workflowXUapFitting = false;
    }
  }

  function scheduleVisibleContentResize() {
    // The browser applies a <details> open/close layout after its toggle event.
    // A second frame captures the compact height as well as the expanded one.
    requestAnimationFrame(() => {
      resizeNodeToVisibleContent();
      requestAnimationFrame(resizeNodeToVisibleContent);
    });
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
    const promptFormat = cached.prompt_format || state.prompt_format;
    const label = kind === "negative" ? "Negative" : "Positive";
    const dock = createDockWindow(node, key, `${label} Preview`, {
      width: 520,
      height: 440,
      matchNodeWidth: false,
    });
    const view = document.createElement("textarea");
    view.className = "workflowx-uap-dock-text";
    view.value = kind === "negative"
      ? cached.negative || ""
      : outputTextForState(state, cached.positive || "", promptFormat);
    view.readOnly = true;
    field(dock.body, label, view);
    node.__workflowXUapOutputRefs ||= {};
    node.__workflowXUapOutputRefs[kind] = {
      view,
      prompt: outputTextForState(state, cached.prompt || "", promptFormat),
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

  async function openJsonXMarkdownProfileSettings(requestedProfileKey = "") {
    let response;
    try {
      response = await fetchJsonChecked(`${JSONX_ROUTE}/reference_config`, {}, "JsonX Markdown settings");
      if (Number(response.current?.jsonx_reference_schema_version || 0) !== JSONX_REFERENCE_SCHEMA_VERSION) {
        throw new Error(
          `Unified JsonX reference schema mismatch (frontend ${JSONX_REFERENCE_SCHEMA_VERSION}, backend ${response.current?.jsonx_reference_schema_version || "missing"}). ` +
          "Restart ComfyUI and hard-refresh the browser.",
        );
      }
    } catch (error) {
      setStatus(`JsonX settings error: ${error.message}`, true);
      return;
    }

    const clone = (value) => JSON.parse(JSON.stringify(value));
    let savedBundle = clone(response.current);
    let draft = clone(savedBundle);
    const originalBundle = clone(response.original);
    let selectedKey = draft.manifest.profiles.some((profile) => profile.key === requestedProfileKey)
      ? requestedProfileKey
      : draft.manifest.profiles.some((profile) => profile.key === state.target_model)
        ? state.target_model
      : draft.manifest.profiles[0]?.key;
    let activeTab = "overview";
    let activeTemplate = "template_adaptive_ranked";
    let activeContract = "contract_stage_one_json";

    const backdrop = buildDom("div", "workflowx-uap-modal-backdrop");
    const modal = buildDom("div", "workflowx-uap-modal workflowx-uap-modal-v6");
    const head = buildDom("div", "workflowx-uap-modal-head");
    head.appendChild(buildDom("div", "workflowx-uap-modal-title", "Unified PrompterX · JsonX Profile Settings"));
    const close = buildDom("button", "workflowx-uap-btn", "×"); close.type = "button";
    close.title = "Close without saving editor changes";
    head.appendChild(close);

    const body = buildDom("div", "workflowx-uap-settings-body");
    const side = buildDom("aside", "workflowx-uap-settings-list");
    const search = createInput("search"); search.placeholder = "Search JsonX profiles";
    const sideActions = buildDom("div", "workflowx-uap-row");
    const add = buildDom("button", "workflowx-uap-btn", "Add");
    const duplicate = buildDom("button", "workflowx-uap-btn", "Duplicate");
    const remove = buildDom("button", "workflowx-uap-btn", "Delete");
    const resetOne = buildDom("button", "workflowx-uap-btn", "Reset profile");
    resetOne.title = "Immediately restore the selected built-in JsonX profile from reference/original/JsonX";
    for (const button of [add, duplicate, remove, resetOne]) { button.type = "button"; sideActions.appendChild(button); }
    const items = buildDom("div", "workflowx-uap-settings-items");
    side.appendChild(search); side.appendChild(sideActions); side.appendChild(items);
    const main = buildDom("main", "workflowx-uap-settings-form");
    const tabs = buildDom("div", "workflowx-uap-settings-tabs");
    const content = buildDom("div", "workflowx-uap-settings-page");
    main.appendChild(tabs); main.appendChild(content); body.appendChild(side); body.appendChild(main);

    const foot = buildDom("div", "workflowx-uap-modal-head");
    const statusText = buildDom("div", "workflowx-uap-status", "Runtime source: reference/current_use/JsonX");
    const revert = buildDom("button", "workflowx-uap-btn", "Revert");
    const exportBtn = buildDom("button", "workflowx-uap-btn", "Export JSON");
    const importBtn = buildDom("button", "workflowx-uap-btn", "Import JSON");
    const resetAll = buildDom("button", "workflowx-uap-btn", "Reset all defaults");
    resetAll.title = "Immediately restore all built-in JsonX profiles while preserving custom profiles";
    const save = buildDom("button", "workflowx-uap-btn primary", "Save");
    const importInput = document.createElement("input"); importInput.type = "file"; importInput.accept = ".json,application/json"; importInput.hidden = true;
    foot.appendChild(statusText);
    for (const button of [revert, exportBtn, importBtn, resetAll, save]) { button.type = "button"; foot.appendChild(button); }
    foot.appendChild(importInput);
    modal.appendChild(head); modal.appendChild(body); modal.appendChild(foot); backdrop.appendChild(modal); document.body.appendChild(backdrop);
    stopGraphEvents(modal);

    const tabDefinitions = [
      ["overview", "Overview"], ["paths", "Path Settings"], ["templates", "Templates"],
      ["presets", "Presets"], ["contracts", "Output Contracts"], ["preview", "Preview"],
    ];
    const originalKeys = new Set(originalBundle.manifest.profiles.map((profile) => profile.key));
    const currentProfile = () => draft.manifest.profiles.find((profile) => profile.key === selectedKey) || draft.manifest.profiles[0];
    const profilePath = (profile, semanticKey) => `${profile.folder}/${draft.manifest.file_map[semanticKey]}`;
    const getFile = (semanticKey, profile = currentProfile()) => draft.files[profilePath(profile, semanticKey)] ?? "";
    const setFile = (semanticKey, value, profile = currentProfile()) => { draft.files[profilePath(profile, semanticKey)] = value; };
    const setSelect = (select, entries, selected) => {
      setSelectOptions(select, entries.map(([value, label]) => ({ value, label })), selected);
      return select;
    };
    const uniqueKey = (base) => {
      const clean = String(base || "jsonx_custom").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "") || "jsonx_custom";
      const used = new Set(draft.manifest.profiles.map((profile) => profile.key));
      let value = clean; let index = 2; while (used.has(value)) value = `${clean}_${index++}`; return value;
    };
    const uniqueFolder = (base) => {
      const clean = String(base || "jsonx_custom").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "") || "jsonx_custom";
      const used = new Set(draft.manifest.profiles.map((profile) => profile.folder));
      let suffix = clean; let index = 2; while (used.has(`profiles/${suffix}`)) suffix = `${clean}_${index++}`; return `profiles/${suffix}`;
    };
    const addEditor = (label, semanticKey, rows = 20, condition = "") => {
      const card = buildDom("section", "workflowx-uap-settings-card");
      const cardHead = buildDom("div", "workflowx-uap-settings-card-head");
      cardHead.appendChild(buildDom("div", "workflowx-uap-settings-card-title", label));
      if (condition) cardHead.appendChild(buildDom("div", "workflowx-uap-condition-badge", condition));
      const area = createTextarea(rows); area.value = getFile(semanticKey); area.spellcheck = false;
      area.addEventListener("input", () => setFile(semanticKey, area.value));
      card.appendChild(cardHead); card.appendChild(area); content.appendChild(card); return area;
    };
    const friendly = (key) => String(key).replace(/^user_|^template_|^contract_/, "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());

    function renderList() {
      items.innerHTML = ""; const query = search.value.toLowerCase().trim();
      for (const peer of profiles.filter((profile) => profile.engine !== "jsonx")) {
        if (query && !`${peer.label} ${peer.key}`.toLowerCase().includes(query)) continue;
        const item = buildDom("button", "workflowx-uap-settings-item", peer.label || peer.key);
        item.type = "button";
        item.addEventListener("click", async () => {
          backdrop.remove();
          await openMarkdownProfileSettings("standard", peer.key);
        });
        items.appendChild(item);
      }
      for (const profile of draft.manifest.profiles) {
        if (query && !`${profile.label} ${profile.key}`.toLowerCase().includes(query)) continue;
        const item = buildDom("button", `workflowx-uap-settings-item${profile.key === selectedKey ? " active" : ""}`, profile.label || profile.key);
        item.type = "button"; item.addEventListener("click", () => { selectedKey = profile.key; activeTab = "overview"; renderAll(); }); items.appendChild(item);
      }
    }
    function renderTabs() {
      tabs.innerHTML = "";
      for (const [key, label] of tabDefinitions) {
        const button = buildDom("button", `workflowx-uap-settings-tab${activeTab === key ? " active" : ""}`, label);
        button.type = "button"; button.addEventListener("click", () => { activeTab = key; renderAll(); }); tabs.appendChild(button);
      }
    }
    function renderOverview(profile) {
      profile.defaults ||= defaultJsonXConfig();
      const grid = buildDom("div", "workflowx-uap-grid");
      const setupPresets = [
        ["adaptive_balanced", "Adaptive Balanced", { generation_profile: "adaptive", generation_mode: "fast", preset_context_mode: "optimized", template_use_presets: false, detail_level: "deep" }],
        ["adaptive_polished", "Adaptive Polished", { generation_profile: "adaptive", generation_mode: "refined", preset_context_mode: "optimized", template_use_presets: false, detail_level: "deep" }],
        ["adaptive_max", "Adaptive Max", { generation_profile: "adaptive", generation_mode: "refined", preset_context_mode: "full", template_use_presets: false, detail_level: "exhaustive" }],
        ["template_flex", "Template Flex", { generation_profile: "template_fill", generation_mode: "fast", preset_context_mode: "optimized", template_use_presets: false, detail_level: "deep" }],
        ["template_catalog", "Template Catalog", { generation_profile: "template_fill", generation_mode: "refined", preset_context_mode: "optimized", template_use_presets: true, detail_level: "deep" }],
        ["custom", "Custom", null],
      ];
      const controlledSetupKeys = ["generation_profile", "generation_mode", "preset_context_mode", "template_use_presets", "detail_level"];
      const matchingSetupPreset = () => setupPresets.find(([, , values]) => values && controlledSetupKeys.every((name) => profile.defaults[name] === values[name]))?.[0] || "custom";
      const key = createInput("text"); key.value = profile.key; key.disabled = originalKeys.has(profile.key);
      const label = createInput("text"); label.value = profile.label || "";
      const setupPreset = setSelect(createSelect(), setupPresets.map(([value, text]) => [value, text]), matchingSetupPreset());
      const format = setSelect(createSelect(), [["json", "JsonX JSON"], ["natural", "Natural language"]], profile.default_format);
      const generationProfile = setSelect(createSelect(), [["adaptive", "Adaptive — build a relevant structure"], ["template_fill", "Template Fill — fill a fixed structure"]], profile.defaults.generation_profile);
      const mode = setSelect(createSelect(), [["fast", "Fast — one JSON pass"], ["refined", "Refined — two JSON passes"]], profile.defaults.generation_mode);
      const contextMode = setSelect(createSelect(), [["optimized", "Ranked presets — Recommended"], ["full", "Full preset catalog"]], profile.defaults.preset_context_mode);
      const depth = setSelect(createSelect(), [["deep", "Deep"], ["exhaustive", "Exhaustive"]], profile.defaults.detail_level);
      const defaultRoute = setSelect(
        createSelect(),
        profile.enabled_generation_types.map((route) => [route, GENERATION_TYPE_MAP.get(route)?.label || route]),
        profile.default_generation_type,
      );
      const presets = document.createElement("input"); presets.type = "checkbox"; presets.checked = Boolean(profile.defaults.template_use_presets);
      const framing = document.createElement("input"); framing.type = "checkbox"; framing.checked = Boolean(profile.defaults.enable_framing_and_placement);
      const overviewField = (labelText, control, helpText = "") => {
        const holder = buildDom("div", "workflowx-uap-field");
        holder.appendChild(buildDom("label", "workflowx-uap-label", labelText));
        holder.appendChild(control);
        const help = buildDom("div", "workflowx-uap-field-help", helpText);
        holder.appendChild(help); grid.appendChild(holder);
        return { holder, help };
      };
      overviewField("Profile key", key, "Internal profile identifier.");
      overviewField("Display label", label, "Name shown in the node and profile list.");
      const setupPresetField = overviewField("JsonX setup preset", setupPreset);
      const formatField = overviewField("Default output format", format, "JSON returns the JsonX object. Natural converts validated JsonX in a required second pass.");
      const profileField = overviewField("JsonX construction method", generationProfile);
      const modeField = overviewField("Output processing", mode);
      const contextField = overviewField("Preset context", contextMode);
      const depthField = overviewField("Hierarchy depth", depth);
      overviewField("Default generation route", defaultRoute, "Text to Image writes from text; Image to Image can use connected references.");
      const presetHolder = buildDom("div", "workflowx-uap-field");
      const presetLabel = buildDom("label", "workflowx-uap-toggle"); presetLabel.appendChild(presets); presetLabel.appendChild(document.createTextNode("Include full presets in Template Fill")); presetHolder.appendChild(presetLabel);
      const presetHelp = buildDom("div", "workflowx-uap-field-help"); presetHolder.appendChild(presetHelp); grid.appendChild(presetHolder);
      const framingLabel = buildDom("label", "workflowx-uap-toggle"); framingLabel.appendChild(framing); framingLabel.appendChild(document.createTextNode("Framing and placement (3×3)")); grid.appendChild(framingLabel);
      content.appendChild(grid);
      const routeCard = buildDom("section", "workflowx-uap-settings-card"); routeCard.appendChild(buildDom("div", "workflowx-uap-settings-card-title", "Enabled generation routes"));
      for (const [route, routeLabel] of [["text_to_image", "Text to Image"], ["image_to_image", "Image to Image"]]) {
        const toggle = buildDom("label", "workflowx-uap-toggle"); const input = document.createElement("input"); input.type = "checkbox"; input.checked = profile.enabled_generation_types.includes(route);
        input.addEventListener("change", () => { if (input.checked && !profile.enabled_generation_types.includes(route)) profile.enabled_generation_types.push(route); if (!input.checked && profile.enabled_generation_types.length > 1) profile.enabled_generation_types = profile.enabled_generation_types.filter((item) => item !== route); if (!profile.enabled_generation_types.includes(profile.default_generation_type)) profile.default_generation_type = profile.enabled_generation_types[0]; renderAll(); });
        toggle.appendChild(input); toggle.appendChild(document.createTextNode(routeLabel)); routeCard.appendChild(toggle);
      }
      content.appendChild(routeCard);
      key.addEventListener("change", () => {
        const value = String(key.value || "").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
        if (value && !draft.manifest.profiles.some((item) => item !== profile && item.key === value)) {
          selectedKey = profile.key = value;
        }
        renderAll();
      });
      label.addEventListener("input", () => { profile.label = label.value; renderList(); });
      const setupPresetHelp = {
        adaptive_balanced: "Dynamic hierarchy · ranked presets · fast JSON processing · deep detail.",
        adaptive_polished: "Dynamic hierarchy · ranked presets · refined JSON processing · deep detail.",
        adaptive_max: "Dynamic hierarchy · full preset catalog · refined JSON processing · exhaustive detail.",
        template_flex: "Fixed fillable hierarchy · no preset catalog · fast JSON processing.",
        template_catalog: "Fixed fillable hierarchy · full preset catalog · refined JSON processing.",
        custom: "Manual combination of the settings below.",
      };
      const refreshSetupPresetHelp = () => {
        const naturalNote = format.value === "natural"
          ? " Natural output still uses its required two-pass conversion."
          : "";
        setupPresetField.help.textContent = `${setupPresetHelp[setupPreset.value] || setupPresetHelp.custom}${naturalNote}`;
      };
      const markSetupCustom = () => {
        setupPreset.value = "custom";
        refreshSetupPresetHelp();
      };
      const refreshDependencies = () => {
        const adaptive = generationProfile.value === "adaptive";
        const natural = format.value === "natural";
        const templateRefinedJson = !adaptive && !natural && mode.value === "refined";
        contextMode.disabled = !adaptive;
        contextField.holder.classList.toggle("is-disabled", !adaptive);
        contextField.help.textContent = adaptive
          ? (contextMode.value === "full"
            ? "Sends the complete preset catalog. Offers maximum coverage but uses much more context."
            : "Sends only preset entries ranked as relevant to the prompt. Smaller, faster, and recommended.")
          : "Only Adaptive uses preset context; Template Fill uses its fixed hierarchy and optional preset switch.";
        presets.disabled = adaptive;
        presetHolder.classList.toggle("is-disabled", adaptive);
        presetLabel.classList.toggle("is-disabled", adaptive);
        presetHelp.textContent = adaptive
          ? "Available only for Template Fill. Adaptive uses Ranked or Full preset context above."
          : (presets.checked
            ? "The complete preset catalog is supplied while the fixed hierarchy is filled."
            : "Template Fill uses the fixed blank hierarchy without the preset catalog.");
        mode.disabled = natural;
        modeField.holder.classList.toggle("is-disabled", natural);
        modeField.help.textContent = natural
          ? "Natural output always uses two passes: validated Stage 1 JSON, then prose conversion. The saved JSON mode is retained."
          : (mode.value === "refined"
            ? "Runs Stage 1 and a second JSON refinement pass."
            : "Returns validated Stage 1 JSON without a normal refinement pass.");
        depth.disabled = !adaptive && !templateRefinedJson;
        depthField.holder.classList.toggle("is-disabled", depth.disabled);
        depthField.help.textContent = depth.disabled
          ? "This setting does not affect the selected Template Fill pipeline."
          : (depth.value === "exhaustive"
            ? "Requests the maximum useful hierarchy detail."
            : "Requests a detailed hierarchy without forcing every possible branch.");
        profileField.help.textContent = adaptive
          ? "Builds a JsonX hierarchy dynamically from the request; it does not begin with every possible field."
          : "Starts from the fixed blank JsonX hierarchy, fills applicable leaves, then removes unused null leaves.";
        formatField.help.textContent = natural
          ? "Produces prose from validated Stage 1 JsonX using a required second model call."
          : "Produces the validated JsonX object. Fast or Refined processing can be selected below.";
        refreshSetupPresetHelp();
      };
      format.addEventListener("change", () => { profile.default_format = format.value; refreshDependencies(); });
      setupPreset.addEventListener("change", () => {
        const values = setupPresets.find(([value]) => value === setupPreset.value)?.[2];
        if (values) {
          Object.assign(profile.defaults, values);
          generationProfile.value = values.generation_profile;
          mode.value = values.generation_mode;
          contextMode.value = values.preset_context_mode;
          presets.checked = values.template_use_presets;
          depth.value = values.detail_level;
        }
        refreshDependencies();
      });
      generationProfile.addEventListener("change", () => { profile.defaults.generation_profile = generationProfile.value; markSetupCustom(); refreshDependencies(); });
      mode.addEventListener("change", () => { profile.defaults.generation_mode = mode.value; markSetupCustom(); refreshDependencies(); });
      contextMode.addEventListener("change", () => { profile.defaults.preset_context_mode = contextMode.value; markSetupCustom(); refreshDependencies(); });
      depth.addEventListener("change", () => { profile.defaults.detail_level = depth.value; markSetupCustom(); refreshDependencies(); });
      defaultRoute.addEventListener("change", () => { profile.default_generation_type = defaultRoute.value; });
      presets.addEventListener("change", () => { profile.defaults.template_use_presets = presets.checked; markSetupCustom(); refreshDependencies(); });
      framing.addEventListener("change", () => { profile.defaults.enable_framing_and_placement = framing.checked; });
      refreshDependencies();
    }
    function renderPaths() {
      const groups = [
        ["Generation routes", ["generation_text_to_image", "generation_image_to_image"]],
        ["Stage 1", ["stage_one_adaptive", "stage_one_template_fill"]],
        ["Stage 2", ["stage_two_json_refinement", "stage_two_natural_conversion"]],
        ["Repair", ["repair_json", "repair_natural"]],
        ["Image states", ["adaptive_image_with", "adaptive_image_without", "template_image_with", "template_image_without", "refinement_image_with", "refinement_image_without", "natural_image_with", "natural_image_without"]],
        ["Open-world and hierarchy", ["adaptive_open_world", "refinement_open_world", "depth_deep", "depth_exhaustive"]],
        ["Framing", ["framing_json_enabled", "framing_json_disabled", "framing_natural_enabled", "framing_natural_disabled"]],
        ["Template Fill state", ["template_presets_enabled", "template_presets_disabled", "template_refinement"]],
        ["Reference processing", ["reference_with_supported", "reference_without_supported", "reference_without_unsupported"]],
        ["User-message templates", ["user_stage_one", "user_json_refinement", "user_natural_conversion", "user_json_repair", "user_natural_repair"]],
      ];
      for (const [label, keys] of groups) {
        const details = buildDom("details", "workflowx-uap-settings-card");
        const summary = document.createElement("summary"); summary.textContent = label; details.appendChild(summary);
        for (const key of keys) {
          const holder = buildDom("div", "workflowx-uap-field"); holder.appendChild(buildDom("label", "", friendly(key)));
          const area = createTextarea(key.startsWith("user_") ? 8 : 14); area.value = getFile(key); area.spellcheck = false; area.addEventListener("input", () => setFile(key, area.value)); holder.appendChild(area); details.appendChild(holder);
        }
        content.appendChild(details);
      }
    }
    function renderTemplates() {
      const options = [
        ["template_adaptive_ranked", "Adaptive ranked context"], ["template_adaptive_full", "Adaptive full context"],
        ["template_fill_without_framing", "Template Fill hierarchy · framing disabled"], ["template_fill_with_framing", "Template Fill hierarchy · framing enabled"],
      ];
      const select = setSelect(createSelect(), options, activeTemplate); field(content, "Template", select);
      addEditor(options.find(([key]) => key === activeTemplate)?.[1] || "Template", activeTemplate, 38, "Exact editable payload carrier. Required tokens are validated on Save.");
      select.addEventListener("change", () => { activeTemplate = select.value; renderAll(); });
    }
    function renderPresets() {
      const stats = buildDom("div", "workflowx-uap-status"); content.appendChild(stats);
      const area = addEditor("Complete JsonX preset catalog", "presets_full", 44, "Raw JSON without a Markdown fence. Adaptive Full, Adaptive Ranked, and Template Fill use this same catalog.");
      const update = () => { try { const parsed = JSON.parse(area.value); const paths = (() => { let count = 0; const walk = (value) => { if (!value || typeof value !== "object" || Array.isArray(value)) return; const values = Object.values(value); if (values.length && values.every((item) => typeof item === "string")) { count += 1; return; } values.forEach(walk); }; walk(parsed); return count; })(); stats.textContent = `Valid JSON object · ${area.value.length.toLocaleString()} characters · ${paths.toLocaleString()} preset paths`; stats.classList.remove("error"); } catch (error) { stats.textContent = `Invalid preset JSON: ${error.message}`; stats.classList.add("error"); } };
      area.addEventListener("input", update); update();
    }
    function renderContracts() {
      const options = [
        ["contract_stage_one_json", "Stage 1 JSON"], ["contract_stage_two_json", "Refined Stage 2 JSON"],
        ["contract_stage_two_natural", "Natural Stage 2 prose"], ["contract_json_repair", "JSON repair"], ["contract_natural_repair", "Natural repair"],
      ];
      const select = setSelect(createSelect(), options, activeContract); field(content, "Stage contract", select);
      addEditor(options.find(([key]) => key === activeContract)?.[1] || "Output contract", activeContract, 24, "Appended last to the selected stage system prompt.");
      select.addEventListener("change", () => { activeContract = select.value; renderAll(); });
    }
    function renderPreview(profile) {
      const config = profile.key === state.target_model
        ? effectiveJsonXConfig()
        : { ...defaultJsonXConfig(), ...(profile.defaults || {}) };
      const controls = buildDom("div", "workflowx-uap-grid");
      const generationProfile = setSelect(createSelect(), [["adaptive", "Adaptive"], ["template_fill", "Template Fill"]], config.generation_profile);
      const output = setSelect(createSelect(), [["json", "JsonX JSON"], ["natural", "Natural language"]], state.prompt_format);
      const generationType = setSelect(createSelect(), profile.enabled_generation_types.map((key) => [key, GENERATION_TYPE_MAP.get(key)?.label || key]), state.generation_type);
      const images = createInput("number"); images.min = "0"; images.max = String(MAX_AUTHORING_IMAGES); images.value = String(connectedImages().length);
      const nsfw = document.createElement("input"); nsfw.type = "checkbox"; nsfw.checked = Boolean(state.nsfw_enabled);
      field(controls, "Generation profile", generationProfile); field(controls, "Output format", output); field(controls, "Generation route", generationType); field(controls, "Authoring media count", images);
      const nsfwLabel = buildDom("label", "workflowx-uap-toggle"); nsfwLabel.appendChild(nsfw); nsfwLabel.appendChild(document.createTextNode("Include shared Image NSFW block")); controls.appendChild(nsfwLabel); content.appendChild(controls);
      content.appendChild(buildDom("div", "workflowx-uap-status", "Preview uses the last saved current_use/JsonX files. Save draft edits before previewing them."));
      const stageOne = createTextarea(28); stageOne.readOnly = true; const stageOneUser = createTextarea(8); stageOneUser.readOnly = true;
      const stageTwo = createTextarea(22); stageTwo.readOnly = true; const stageTwoUser = createTextarea(8); stageTwoUser.readOnly = true;
      const repairs = createTextarea(18); repairs.readOnly = true; const routing = createTextarea(16); routing.readOnly = true;
      field(content, "Stage 1 · exact system text", stageOne); field(content, "Stage 1 · exact user text", stageOneUser);
      field(content, "Applicable Stage 2 · exact system text", stageTwo); field(content, "Applicable Stage 2 · exact user text", stageTwoUser);
      field(content, "Repair payloads", repairs); field(content, "Local routing only", routing);
      const refresh = buildDom("button", "workflowx-uap-btn primary", "Refresh preview"); refresh.type = "button"; content.appendChild(refresh);
      const update = async () => {
        try {
          const count = Math.max(0, Math.min(MAX_AUTHORING_IMAGES, Number(images.value || 0)));
          const selectedConfig = { ...config, generation_profile: generationProfile.value };
          const data = await fetchJsonChecked(`${JSONX_ROUTE}/instructions/preview`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
              ...selectedConfig, schema_version: FRONTEND_SCHEMA_VERSION, jsonx_reference_schema_version: JSONX_REFERENCE_SCHEMA_VERSION,
              target_model: profile.key, generation_type: generationType.value, output_format: output.value, nsfw_enabled: nsfw.checked,
              has_image: count > 0, images_b64: Array.from({ length: count }, (_value, index) => `preview-image-${index + 1}`),
              fields: { prompt_text: promptArea.value || "Example user prompt instructions", detail: detailSelect.value },
            }),
          }, "JsonX payload preview");
          stageOne.value = data.stage_one || ""; stageOneUser.value = data.user || ""; stageTwo.value = data.refinement || ""; stageTwoUser.value = data.stage_two_user || "";
          repairs.value = `JSON repair system:\n${data.json_repair || ""}\n\nJSON repair user:\n${data.json_repair_user || ""}\n\nNatural repair system:\n${data.natural_repair || ""}\n\nNatural repair user:\n${data.natural_repair_user || ""}`;
          routing.value = JSON.stringify({ profile: profile.key, generation_type: generationType.value, submitted_media: data.image_count, image_state: data.image_state, activated_files: data.activated_files, provider_parameters: { backend: providerBackend() }, preset_characters: data.full_preset_chars }, null, 2);
        } catch (error) { stageOne.value = `Preview error: ${error.message}`; stageOneUser.value = ""; stageTwo.value = ""; stageTwoUser.value = ""; repairs.value = ""; routing.value = ""; }
      };
      refresh.addEventListener("click", update); for (const control of [generationProfile, output, generationType, images, nsfw]) control.addEventListener("change", update); update();
    }
    function renderAll() {
      content.innerHTML = ""; renderList(); renderTabs(); const profile = currentProfile(); if (!profile) return;
      remove.disabled = originalKeys.has(profile.key); resetOne.disabled = !originalKeys.has(profile.key);
      if (activeTab === "overview") renderOverview(profile); else if (activeTab === "paths") renderPaths(); else if (activeTab === "templates") renderTemplates(); else if (activeTab === "presets") renderPresets(); else if (activeTab === "contracts") renderContracts(); else renderPreview(profile);
    }

    search.addEventListener("input", renderList);
    add.addEventListener("click", () => {
      const source = currentProfile() || draft.manifest.profiles[0];
      const key = uniqueKey("jsonx_custom"); const profile = clone(source); profile.key = key; profile.label = "JsonX Custom"; profile.folder = uniqueFolder(key); profile.builtin = false;
      const prefix = `${source.folder}/`; for (const [path, text] of Object.entries({ ...draft.files })) if (path.startsWith(prefix)) draft.files[`${profile.folder}/${path.slice(prefix.length)}`] = text;
      draft.manifest.profiles.push(profile); selectedKey = key; activeTab = "overview"; renderAll();
    });
    duplicate.addEventListener("click", () => {
      const source = currentProfile(); if (!source) return; const copy = clone(source); copy.key = uniqueKey(`${source.key}_copy`); copy.label = `${source.label} Copy`; copy.folder = uniqueFolder(copy.key); copy.builtin = false;
      const prefix = `${source.folder}/`; for (const [path, text] of Object.entries({ ...draft.files })) if (path.startsWith(prefix)) draft.files[`${copy.folder}/${path.slice(prefix.length)}`] = text;
      draft.manifest.profiles.push(copy); selectedKey = copy.key; activeTab = "overview"; renderAll();
    });
    remove.addEventListener("click", () => { const profile = currentProfile(); if (!profile || originalKeys.has(profile.key)) return; draft.manifest.profiles = draft.manifest.profiles.filter((item) => item !== profile); const prefix = `${profile.folder}/`; for (const path of Object.keys(draft.files)) if (path.startsWith(prefix)) delete draft.files[path]; selectedKey = draft.manifest.profiles[0]?.key; renderAll(); });
    resetOne.addEventListener("click", async () => { try { const data = await fetchJsonChecked(`${JSONX_ROUTE}/reference_config/reset_profile`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile_key: currentProfile()?.key }) }, "Reset JsonX profile"); savedBundle = clone(data.current); draft = clone(savedBundle); statusText.textContent = "JsonX profile restored from original."; renderAll(); } catch (error) { statusText.textContent = `Reset error: ${error.message}`; } });
    revert.addEventListener("click", async () => { try { const data = await fetchJsonChecked(`${JSONX_ROUTE}/reference_config`, {}, "Revert JsonX settings"); savedBundle = clone(data.current); draft = clone(savedBundle); statusText.textContent = "Unsaved changes discarded."; renderAll(); } catch (error) { statusText.textContent = `Revert error: ${error.message}`; } });
    exportBtn.addEventListener("click", async () => { try { const data = await fetchJsonChecked(`${JSONX_ROUTE}/reference_config`, {}, "Export JsonX settings"); const blob = new Blob([JSON.stringify(data.current, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `unified-jsonx-reference-v${JSONX_REFERENCE_SCHEMA_VERSION}.json`; anchor.click(); URL.revokeObjectURL(url); statusText.textContent = "Exported the last saved JsonX bundle."; } catch (error) { statusText.textContent = `Export error: ${error.message}`; } });
    importBtn.addEventListener("click", () => importInput.click());
    importInput.addEventListener("change", async () => { try { const imported = JSON.parse(await importInput.files?.[0]?.text()); if (Number(imported.jsonx_reference_schema_version || 0) !== JSONX_REFERENCE_SCHEMA_VERSION) throw new Error(`Imported bundle is not JsonX reference schema ${JSONX_REFERENCE_SCHEMA_VERSION}.`); draft = clone(imported); selectedKey = draft.manifest.profiles[0]?.key; statusText.textContent = "Import loaded as an unsaved draft. Click Save to apply it."; renderAll(); } catch (error) { statusText.textContent = `Import error: ${error.message}`; } importInput.value = ""; });
    resetAll.addEventListener("click", async () => { try { const data = await fetchJsonChecked(`${JSONX_ROUTE}/reference_config/reset_all`, { method: "POST" }, "Reset all JsonX profiles"); savedBundle = clone(data.current); draft = clone(savedBundle); statusText.textContent = "Built-in JsonX profiles restored; custom profiles preserved."; renderAll(); } catch (error) { statusText.textContent = `Reset error: ${error.message}`; } });
    save.addEventListener("click", async () => { save.disabled = true; try { const data = await fetchJsonChecked(`${JSONX_ROUTE}/reference_config`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) }, "Save JsonX Markdown profiles"); savedBundle = clone(data.current); draft = clone(savedBundle); clearProfileCache(); profiles = await loadProfiles(); profilesByKey = profileMap(profiles); if (profilesByKey.has(selectedKey)) state.target_model = selectedKey; refreshProfiles(); statusText.textContent = "Saved to reference/current_use/JsonX."; setStatus("JsonX Markdown settings saved."); renderAll(); } catch (error) { statusText.textContent = `Save error: ${error.message}`; } finally { save.disabled = false; } });
    close.addEventListener("click", () => backdrop.remove()); backdrop.addEventListener("mousedown", (event) => { if (event.target === backdrop) backdrop.remove(); }); renderAll();
  }

  async function openMarkdownProfileSettings(forceEngine = "", requestedProfileKey = "") {
    if (forceEngine === "jsonx" || (!forceEngine && isJsonXProfile())) {
      await openJsonXMarkdownProfileSettings(requestedProfileKey);
      return;
    }

    let config;
    try {
      config = await fetchJsonChecked(`${ROUTE}/reference_config`, {}, "Markdown profile settings");
      if (Number(config.reference_schema_version || 0) !== REFERENCE_SCHEMA_VERSION) {
        throw new Error(
          `Unified reference schema mismatch (frontend ${REFERENCE_SCHEMA_VERSION}, backend ${config.reference_schema_version || "missing"}). ` +
          "Restart ComfyUI and hard-refresh the browser.",
        );
      }
    } catch (error) {
      setStatus(`Profile settings error: ${error.message}`, true);
      return;
    }

    const clone = (value) => JSON.parse(JSON.stringify(value));
    let savedBundle = clone(config.current);
    let draft = clone(savedBundle);
    const originalBundle = clone(config.original);
    let selectedKey = draft.manifest.profiles.some((profile) => profile.key === requestedProfileKey)
      ? requestedProfileKey
      : draft.manifest.profiles.some((profile) => profile.key === state.target_model)
        ? state.target_model
      : draft.manifest.profiles[0]?.key;
    let editorMode = "profiles";
    let activeTab = "overview";
    let activePath = state.generation_type;
    let activeFormat = state.prompt_format;
    let activeNegative = Boolean(state.negative_enabled);

    const backdrop = buildDom("div", "workflowx-uap-modal-backdrop");
    const modal = buildDom("div", "workflowx-uap-modal workflowx-uap-modal-v6");
    const head = buildDom("div", "workflowx-uap-modal-head");
    const title = buildDom("div", "workflowx-uap-modal-title", "Unified PrompterX Profile Settings");
    const modeButtons = buildDom("div", "workflowx-uap-settings-segment");
    const profilesMode = buildDom("button", "active", "Profiles");
    const nsfwMode = buildDom("button", "", "Global Rules");
    const close = buildDom("button", "workflowx-uap-btn", "×");
    close.title = "Close without saving editor changes";
    for (const button of [profilesMode, nsfwMode, close]) button.type = "button";
    modeButtons.appendChild(profilesMode);
    modeButtons.appendChild(nsfwMode);
    head.appendChild(title);
    head.appendChild(modeButtons);
    head.appendChild(close);

    const body = buildDom("div", "workflowx-uap-settings-body");
    const side = buildDom("aside", "workflowx-uap-settings-list");
    const search = createInput("search");
    search.placeholder = "Search profiles";
    const sideActions = buildDom("div", "workflowx-uap-row");
    const add = buildDom("button", "workflowx-uap-btn", "Add");
    const duplicate = buildDom("button", "workflowx-uap-btn", "Duplicate");
    const remove = buildDom("button", "workflowx-uap-btn", "Delete");
    const resetOne = buildDom("button", "workflowx-uap-btn", "Reset profile");
    resetOne.title = "Immediately restore the selected built-in profile from reference/original";
    for (const button of [add, duplicate, remove, resetOne]) {
      button.type = "button";
      sideActions.appendChild(button);
    }
    const items = buildDom("div", "workflowx-uap-settings-items");
    side.appendChild(search);
    side.appendChild(sideActions);
    side.appendChild(items);

    const main = buildDom("main", "workflowx-uap-settings-form");
    const tabs = buildDom("div", "workflowx-uap-settings-tabs");
    const content = buildDom("div", "workflowx-uap-settings-page");
    main.appendChild(tabs);
    main.appendChild(content);
    body.appendChild(side);
    body.appendChild(main);

    const foot = buildDom("div", "workflowx-uap-modal-head");
    const status = buildDom("div", "workflowx-uap-status", "Runtime source: reference/current_use");
    const revert = buildDom("button", "workflowx-uap-btn", "Revert");
    const exportBtn = buildDom("button", "workflowx-uap-btn", "Export JSON");
    const importBtn = buildDom("button", "workflowx-uap-btn", "Import JSON");
    const resetAll = buildDom("button", "workflowx-uap-btn", "Reset all defaults");
    resetAll.title = "Immediately restore all built-in profiles while preserving custom profiles";
    const save = buildDom("button", "workflowx-uap-btn primary", "Save");
    const importInput = document.createElement("input");
    importInput.type = "file";
    importInput.accept = ".json,application/json";
    importInput.hidden = true;
    foot.appendChild(status);
    for (const button of [revert, exportBtn, importBtn, resetAll, save]) {
      button.type = "button";
      foot.appendChild(button);
    }
    foot.appendChild(importInput);
    modal.appendChild(head);
    modal.appendChild(body);
    modal.appendChild(foot);
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);
    stopGraphEvents(modal);

    const tabDefinitions = [
      ["overview", "Overview"],
      ["common", "Common Profile Rules"],
      ["paths", "Generation Paths"],
      ["references", "Reference Usage"],
      ["contracts", "Output Contracts"],
      ["preview", "Preview"],
    ];
    const originalKeys = new Set(originalBundle.manifest.profiles.map((profile) => profile.key));

    const currentProfile = () => draft.manifest.profiles.find((profile) => profile.key === selectedKey)
      || draft.manifest.profiles[0];
    const generationCatalog = () => draft.manifest.generation_types || {};
    const formatCatalog = () => draft.manifest.formats || {};
    const profilePath = (profile, relative) => `${profile.folder}/${relative}`;
    const getFile = (path) => Object.prototype.hasOwnProperty.call(draft.files, path) ? draft.files[path] : "";
    const setFile = (path, value) => { draft.files[path] = value; };
    const pathFile = (profile, type) => profilePath(profile, `split/${generationCatalog()[type]?.filename || `${type.replaceAll("_", "-")}.md`}`);
    const contractFile = (profile, format, negative) => {
      const prefix = formatCatalog()[format]?.contract_prefix || `${format}_output`;
      return profilePath(profile, `Supporting/${prefix}_${negative ? "with_negative" : "without_negative"}.md`);
    };
    const uniqueKey = (base) => {
      const normalized = String(base || "custom_model").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "") || "custom_model";
      const keys = new Set(draft.manifest.profiles.map((profile) => profile.key));
      let value = normalized;
      let index = 2;
      while (keys.has(value)) value = `${normalized}_${index++}`;
      return value;
    };
    const uniqueFolder = (base) => {
      const used = new Set(draft.manifest.profiles.map((profile) => profile.folder));
      const normalized = String(base || "Custom Model").replace(/[\\/:*?"<>|]/g, " ").replace(/\s+/g, " ").trim() || "Custom Model";
      let value = normalized;
      let index = 2;
      while (used.has(value)) value = `${normalized} ${index++}`;
      return value;
    };
    const addExactEditor = (label, path, rows = 24, condition = "") => {
      const card = buildDom("section", "workflowx-uap-settings-card");
      const cardHead = buildDom("div", "workflowx-uap-settings-card-head");
      cardHead.appendChild(buildDom("div", "workflowx-uap-settings-card-title", label));
      if (condition) cardHead.appendChild(buildDom("div", "workflowx-uap-condition-badge", condition));
      const area = createTextarea(rows);
      area.value = getFile(path);
      area.spellcheck = false;
      area.addEventListener("input", () => setFile(path, area.value));
      card.appendChild(cardHead);
      card.appendChild(area);
      content.appendChild(card);
      return area;
    };
    const setSelect = (select, entries, selected) => {
      setSelectOptions(select, entries.map(([value, label]) => ({ value, label })), selected);
      return select;
    };
    const sanitizedParams = (generationType, mediaCount) => {
      try {
        const images = Array.from({ length: Math.max(0, Number(mediaCount || 0)) }, (_value, index) => `preview-media-${index + 1}`);
        const payload = activeProviderPayload(false, images);
        delete payload.api_key;
        delete payload.image_b64;
        delete payload.images_b64;
        return payload;
      } catch (error) {
        return { provider: providerBackend(), configuration_warning: String(error.message || error), generation_type: generationType };
      }
    };

    function renderList() {
      items.innerHTML = "";
      const query = search.value.toLowerCase().trim();
      for (const profile of draft.manifest.profiles) {
        if (query && !`${profile.label} ${profile.key}`.toLowerCase().includes(query)) continue;
        const item = buildDom("button", `workflowx-uap-settings-item${profile.key === selectedKey ? " active" : ""}`);
        item.type = "button";
        item.textContent = profile.label || profile.key;
        item.addEventListener("click", () => {
          selectedKey = profile.key;
          activePath = profile.default_generation_type;
          activeFormat = profile.default_format;
          renderAll();
        });
        items.appendChild(item);
      }
      for (const peer of profiles.filter((profile) => profile.engine === "jsonx")) {
        if (query && !`${peer.label} ${peer.key}`.toLowerCase().includes(query)) continue;
        const item = buildDom("button", "workflowx-uap-settings-item", peer.label || peer.key);
        item.type = "button";
        item.addEventListener("click", async () => {
          backdrop.remove();
          await openMarkdownProfileSettings("jsonx", peer.key);
        });
        items.appendChild(item);
      }
    }

    function renderTabs() {
      tabs.innerHTML = "";
      for (const [key, label] of tabDefinitions) {
        const button = buildDom("button", `workflowx-uap-settings-tab${activeTab === key ? " active" : ""}`, label);
        button.type = "button";
        button.addEventListener("click", () => { activeTab = key; renderAll(); });
        tabs.appendChild(button);
      }
    }

    function renderOverview(profile) {
      const grid = buildDom("div", "workflowx-uap-grid");
      const key = createInput("text"); key.value = profile.key; key.disabled = originalKeys.has(profile.key);
      const label = createInput("text"); label.value = profile.label || "";
      const media = setSelect(createSelect(), [["image", "Image"], ["video", "Video"]], profile.media_type);
      const negative = document.createElement("input"); negative.type = "checkbox"; negative.checked = Boolean(profile.negative_supported);
      const defaultFormat = setSelect(
        createSelect(),
        profile.enabled_formats.map((format) => [format, formatCatalog()[format]?.label || format]),
        profile.default_format,
      );
      const defaultPath = setSelect(
        createSelect(),
        profile.enabled_generation_types.map((type) => [type, generationCatalog()[type]?.label || type]),
        profile.default_generation_type,
      );
      field(grid, "Profile key", key);
      field(grid, "Display label", label);
      field(grid, "Output medium", media);
      field(grid, "Default output format", defaultFormat);
      field(grid, "Default generation type", defaultPath);
      const negativeLabel = buildDom("label", "workflowx-uap-toggle");
      negativeLabel.appendChild(negative);
      negativeLabel.appendChild(document.createTextNode("Supports separate negative output"));
      grid.appendChild(negativeLabel);
      content.appendChild(grid);

      const formatRow = buildDom("div", "workflowx-uap-row");
      formatRow.appendChild(buildDom("strong", "", "Enabled output formats"));
      for (const [format, metadata] of Object.entries(formatCatalog())) {
        const toggle = buildDom("label", "workflowx-uap-toggle");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = profile.enabled_formats.includes(format);
        input.addEventListener("change", () => {
          if (input.checked && !profile.enabled_formats.includes(format)) profile.enabled_formats.push(format);
          if (!input.checked && profile.enabled_formats.length > 1) profile.enabled_formats = profile.enabled_formats.filter((item) => item !== format);
          if (!profile.enabled_formats.includes(profile.default_format)) profile.default_format = profile.enabled_formats[0];
          renderAll();
        });
        toggle.appendChild(input);
        toggle.appendChild(document.createTextNode(metadata.label || format));
        formatRow.appendChild(toggle);
      }
      content.appendChild(formatRow);

      const pathRow = buildDom("div", "workflowx-uap-row");
      pathRow.appendChild(buildDom("strong", "", "Enabled generation types"));
      for (const [type, metadata] of Object.entries(generationCatalog())) {
        const toggle = buildDom("label", "workflowx-uap-toggle");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = profile.enabled_generation_types.includes(type);
        input.addEventListener("change", () => {
          if (input.checked && !profile.enabled_generation_types.includes(type)) profile.enabled_generation_types.push(type);
          if (!input.checked && profile.enabled_generation_types.length > 1) profile.enabled_generation_types = profile.enabled_generation_types.filter((item) => item !== type);
          if (!profile.enabled_generation_types.includes(profile.default_generation_type)) profile.default_generation_type = profile.enabled_generation_types[0];
          renderAll();
        });
        toggle.appendChild(input);
        toggle.appendChild(document.createTextNode(metadata.label || type));
        pathRow.appendChild(toggle);
      }
      content.appendChild(pathRow);

      key.addEventListener("change", () => {
        const value = key.value.toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
        if (value && !draft.manifest.profiles.some((item) => item !== profile && item.key === value)) {
          selectedKey = profile.key = value;
          renderAll();
        }
      });
      label.addEventListener("input", () => { profile.label = label.value; renderList(); });
      media.addEventListener("change", () => { profile.media_type = media.value; });
      negative.addEventListener("change", () => { profile.negative_supported = negative.checked; });
      defaultFormat.addEventListener("change", () => { profile.default_format = defaultFormat.value; activeFormat = defaultFormat.value; });
      defaultPath.addEventListener("change", () => { profile.default_generation_type = defaultPath.value; activePath = defaultPath.value; });
    }

    function renderCommon(profile) {
      addExactEditor(
        "Common profile rules",
        profilePath(profile, "split/common.md"),
        32,
        "Included for every request using this profile.",
      );
    }

    function renderPaths(profile) {
      if (!profile.enabled_generation_types.includes(activePath)) activePath = profile.default_generation_type;
      const select = setSelect(
        createSelect(),
        profile.enabled_generation_types.map((type) => [type, generationCatalog()[type]?.label || type]),
        activePath,
      );
      field(content, "Generation type", select);
      addExactEditor(
        "Generation-type rules",
        pathFile(profile, activePath),
        32,
        "Included only when this generation type is selected. Missing packaged files intentionally open blank.",
      );
      select.addEventListener("change", () => { activePath = select.value; renderAll(); });
    }

    function renderReferences(profile) {
      const definitions = [
        ["with_reference_supported.md", "Reference supported · media connected", "Selected when the downstream type supports references and authoring media is connected."],
        ["without_reference_supported.md", "Reference supported · no media connected", "Selected when the downstream type supports references and no authoring media is connected."],
        ["without_reference_unsupported.md", "Reference unsupported downstream", "Selected for a downstream type that does not consume references, with or without authoring media."],
      ];
      for (const [filename, label, condition] of definitions) {
        addExactEditor(label, profilePath(profile, `Supporting/${filename}`), 16, condition);
      }
    }

    function renderContracts(profile) {
      if (!profile.enabled_formats.includes(activeFormat)) activeFormat = profile.default_format;
      if (!profile.negative_supported) activeNegative = false;
      const controls = buildDom("div", "workflowx-uap-grid");
      const format = setSelect(
        createSelect(),
        profile.enabled_formats.map((item) => [item, formatCatalog()[item]?.label || item]),
        activeFormat,
      );
      const negative = setSelect(createSelect(), [
        ["without", "Negative disabled"],
        ["with", "Negative enabled"],
      ], activeNegative ? "with" : "without");
      negative.disabled = !profile.negative_supported;
      field(controls, "Output format", format);
      field(controls, "Negative state", negative);
      content.appendChild(controls);
      addExactEditor(
        "Exact output contract",
        contractFile(profile, activeFormat, activeNegative && profile.negative_supported),
        28,
        "Exactly one profile-wide output contract is appended to the system message.",
      );
      format.addEventListener("change", () => { activeFormat = format.value; renderAll(); });
      negative.addEventListener("change", () => { activeNegative = negative.value === "with"; renderAll(); });
    }

    function renderGlobalNsfw() {
      content.appendChild(buildDom("div", "workflowx-uap-status", "These Markdown files are shared globally. NSFW rules join normal generation only when enabled; the audit block is sent alone only for a requested audit call."));
      addExactEditor("Image NSFW rules", "nsfw-image.md", 26, "Included for image-output generation types only when NSFW is enabled.");
      addExactEditor("Video NSFW rules", "nsfw-video.md", 26, "Included for video-output generation types only when NSFW is enabled.");
      addExactEditor("Prompt coherence audit", draft.manifest.audit_file || "audit.md", 26, "Used as the complete system message for Add audit pass or Audit only.");
    }

    function renderPreview(profile) {
      const controls = buildDom("div", "workflowx-uap-grid");
      if (!profile.enabled_generation_types.includes(activePath)) activePath = profile.default_generation_type;
      if (!profile.enabled_formats.includes(activeFormat)) activeFormat = profile.default_format;
      const path = setSelect(createSelect(), profile.enabled_generation_types.map((item) => [item, generationCatalog()[item]?.label || item]), activePath);
      const format = setSelect(createSelect(), profile.enabled_formats.map((item) => [item, formatCatalog()[item]?.label || item]), activeFormat);
      const imageCount = createInput("number"); imageCount.min = "0"; imageCount.max = String(MAX_AUTHORING_IMAGES); imageCount.value = String(connectedImages().length);
      const nsfw = document.createElement("input"); nsfw.type = "checkbox"; nsfw.checked = Boolean(state.nsfw_enabled);
      const negative = document.createElement("input"); negative.type = "checkbox"; negative.checked = Boolean(state.negative_enabled && profile.negative_supported); negative.disabled = !profile.negative_supported;
      field(controls, "Generation type", path);
      field(controls, "Output format", format);
      field(controls, "Authoring media count", imageCount);
      const nsfwLabel = buildDom("label", "workflowx-uap-toggle"); nsfwLabel.appendChild(nsfw); nsfwLabel.appendChild(document.createTextNode("Include NSFW block")); controls.appendChild(nsfwLabel);
      const negativeLabel = buildDom("label", "workflowx-uap-toggle"); negativeLabel.appendChild(negative); negativeLabel.appendChild(document.createTextNode("Generate negative")); controls.appendChild(negativeLabel);
      content.appendChild(controls);
      content.appendChild(buildDom("div", "workflowx-uap-status", "Preview uses the last saved current_use files—the same backend builder used by generation. Save draft edits before previewing them."));
      const system = createTextarea(28); system.readOnly = true;
      const user = createTextarea(8); user.readOnly = true;
      const media = createTextarea(4); media.readOnly = true;
      const routing = createTextarea(16); routing.readOnly = true;
      field(content, "Exact system text", system);
      field(content, "Exact user text", user);
      field(content, "Submitted authoring media", media);
      field(content, "Local routing only", routing);
      const refresh = buildDom("button", "workflowx-uap-btn primary", "Refresh preview"); refresh.type = "button"; content.appendChild(refresh);
      const update = async () => {
        try {
          const count = Math.max(0, Math.min(MAX_AUTHORING_IMAGES, Number(imageCount.value || 0)));
          const data = await fetchJsonChecked(`${ROUTE}/preview`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              schema_version: FRONTEND_SCHEMA_VERSION,
              reference_schema_version: REFERENCE_SCHEMA_VERSION,
              target_model: profile.key,
              prompt_format: format.value,
              generation_type: path.value,
              nsfw_enabled: nsfw.checked,
              negative_enabled: negative.checked,
              image_count: count,
              fields: { prompt_text: promptArea.value || "Example user prompt instructions", detail: detailSelect.value },
            }),
          }, "Markdown payload preview");
          system.value = data.system || "";
          user.value = data.user || "";
          media.value = data.image_count
            ? `${data.image_count} authoring media item${data.image_count === 1 ? "" : "s"} submitted separately.`
            : "No authoring media submitted.";
          routing.value = JSON.stringify({
            profile: profile.key,
            generation_type: data.generation_type,
            activated_files: data.activated_blocks || [],
            connected_media: data.connected_image_count,
            submitted_media: data.image_count,
            generation_parameters: sanitizedParams(path.value, count),
          }, null, 2);
        } catch (error) {
          system.value = `Preview error: ${error.message}`;
          user.value = "";
          media.value = "";
          routing.value = "";
        }
      };
      refresh.addEventListener("click", update);
      for (const control of [path, format, imageCount, nsfw, negative]) control.addEventListener("change", update);
      update();
    }

    function renderContent(profile) {
      content.innerHTML = "";
      if (activeTab === "overview") renderOverview(profile);
      else if (activeTab === "common") renderCommon(profile);
      else if (activeTab === "paths") renderPaths(profile);
      else if (activeTab === "references") renderReferences(profile);
      else if (activeTab === "contracts") renderContracts(profile);
      else renderPreview(profile);
    }

    function renderAll() {
      const globalMode = editorMode === "global";
      profilesMode.classList.toggle("active", !globalMode);
      nsfwMode.classList.toggle("active", globalMode);
      side.style.display = globalMode ? "none" : "flex";
      tabs.style.display = globalMode ? "none" : "flex";
      body.classList.toggle("global-rules-mode", globalMode);
      title.textContent = globalMode ? "Unified PrompterX Global Rules" : "Unified PrompterX Profile Settings";
      content.innerHTML = "";
      if (globalMode) {
        renderGlobalNsfw();
        return;
      }
      const profile = currentProfile();
      if (!profile) return;
      if (!profile.enabled_generation_types.includes(activePath)) activePath = profile.default_generation_type;
      if (!profile.enabled_formats.includes(activeFormat)) activeFormat = profile.default_format;
      renderList();
      renderTabs();
      renderContent(profile);
      remove.disabled = originalKeys.has(profile.key);
      resetOne.disabled = !originalKeys.has(profile.key);
    }

    profilesMode.addEventListener("click", () => { editorMode = "profiles"; renderAll(); });
    nsfwMode.addEventListener("click", () => { editorMode = "global"; renderAll(); });
    search.addEventListener("input", renderList);
    add.addEventListener("click", () => {
      const key = uniqueKey("custom_model");
      const folder = uniqueFolder("Custom Model");
      const profile = {
        key,
        label: "Custom Model",
        folder,
        media_type: "image",
        enabled_formats: ["natural"],
        default_format: "natural",
        enabled_generation_types: ["text_to_image"],
        default_generation_type: "text_to_image",
        negative_supported: true,
        builtin: false,
      };
      draft.manifest.profiles.push(profile);
      for (const relative of [
        "split/common.md",
        `split/${generationCatalog().text_to_image.filename}`,
        "Supporting/with_reference_supported.md",
        "Supporting/without_reference_supported.md",
        "Supporting/without_reference_unsupported.md",
        "Supporting/natural_output_without_negative.md",
        "Supporting/natural_output_with_negative.md",
        "Supporting/json_output_without_negative.md",
        "Supporting/json_output_with_negative.md",
      ]) setFile(`${folder}/${relative}`, "");
      selectedKey = key;
      activeTab = "overview";
      activePath = "text_to_image";
      activeFormat = "natural";
      renderAll();
    });
    duplicate.addEventListener("click", () => {
      const source = currentProfile();
      if (!source) return;
      const copy = clone(source);
      copy.key = uniqueKey(`${source.key}_copy`);
      copy.label = `${source.label} Copy`;
      copy.folder = uniqueFolder(`${source.folder} Copy`);
      copy.builtin = false;
      const prefix = `${source.folder}/`;
      for (const [path, text] of Object.entries({ ...draft.files })) {
        if (path.startsWith(prefix)) setFile(`${copy.folder}/${path.slice(prefix.length)}`, text);
      }
      draft.manifest.profiles.push(copy);
      selectedKey = copy.key;
      activeTab = "overview";
      renderAll();
    });
    remove.addEventListener("click", () => {
      const profile = currentProfile();
      if (!profile || originalKeys.has(profile.key)) return;
      draft.manifest.profiles = draft.manifest.profiles.filter((item) => item !== profile);
      const prefix = `${profile.folder}/`;
      for (const path of Object.keys(draft.files)) if (path.startsWith(prefix)) delete draft.files[path];
      selectedKey = draft.manifest.profiles[0]?.key;
      renderAll();
    });
    resetOne.addEventListener("click", async () => {
      const profile = currentProfile();
      if (!profile || !originalKeys.has(profile.key)) return;
      try {
        const data = await fetchJsonChecked(`${ROUTE}/reference_config/reset_profile`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile_key: profile.key }),
        }, "Reset profile");
        savedBundle = clone(data.current);
        draft = clone(savedBundle);
        status.textContent = `${profile.label} restored from original.`;
        renderAll();
      } catch (error) { status.textContent = `Reset error: ${error.message}`; }
    });
    revert.addEventListener("click", async () => {
      try {
        const data = await fetchJsonChecked(`${ROUTE}/reference_config`, {}, "Revert profiles");
        savedBundle = clone(data.current);
        draft = clone(savedBundle);
        if (!draft.manifest.profiles.some((profile) => profile.key === selectedKey)) selectedKey = draft.manifest.profiles[0]?.key;
        status.textContent = "Unsaved changes discarded.";
        renderAll();
      } catch (error) { status.textContent = `Revert error: ${error.message}`; }
    });
    exportBtn.addEventListener("click", async () => {
      try {
        const data = await fetchJsonChecked(`${ROUTE}/reference_config`, {}, "Export profiles");
        savedBundle = clone(data.current);
        const blob = new Blob([JSON.stringify(savedBundle, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `unified-prompterx-reference-v${REFERENCE_SCHEMA_VERSION}.json`;
        anchor.click();
        URL.revokeObjectURL(url);
        status.textContent = "Exported the last saved current_use bundle. Unsaved modal edits were not included.";
      } catch (error) {
        status.textContent = `Export error: ${error.message}`;
      }
    });
    importBtn.addEventListener("click", () => importInput.click());
    importInput.addEventListener("change", async () => {
      try {
        const imported = JSON.parse(await importInput.files?.[0]?.text());
        if (Number(imported.reference_schema_version || 0) !== REFERENCE_SCHEMA_VERSION) throw new Error(`Imported bundle is not reference schema ${REFERENCE_SCHEMA_VERSION}.`);
        draft = clone(imported);
        selectedKey = draft.manifest.profiles[0]?.key;
        status.textContent = "Import loaded as an unsaved draft. Click Save to apply it.";
        renderAll();
      } catch (error) { status.textContent = `Import error: ${error.message}`; }
      importInput.value = "";
    });
    resetAll.addEventListener("click", async () => {
      try {
        const data = await fetchJsonChecked(`${ROUTE}/reference_config/reset_all`, { method: "POST" }, "Reset all profiles");
        savedBundle = clone(data.current);
        draft = clone(savedBundle);
        if (!draft.manifest.profiles.some((profile) => profile.key === selectedKey)) selectedKey = draft.manifest.profiles[0]?.key;
        status.textContent = "Built-in profiles and global rule files restored; custom profiles preserved.";
        renderAll();
      } catch (error) { status.textContent = `Reset error: ${error.message}`; }
    });
    save.addEventListener("click", async () => {
      save.disabled = true;
      try {
        const data = await fetchJsonChecked(`${ROUTE}/reference_config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ bundle: draft }),
        }, "Save Markdown profiles");
        savedBundle = clone(data.current);
        draft = clone(savedBundle);
        clearProfileCache();
        profiles = await loadProfiles();
        profilesByKey = profileMap(profiles);
        if (profilesByKey.has(selectedKey)) state.target_model = selectedKey;
        refreshProfiles();
        status.textContent = "Saved to reference/current_use.";
        setStatus("Markdown profile settings saved.");
        renderAll();
      } catch (error) { status.textContent = `Save error: ${error.message}`; }
      finally { save.disabled = false; }
    });
    close.addEventListener("click", () => backdrop.remove());
    backdrop.addEventListener("mousedown", (event) => { if (event.target === backdrop) backdrop.remove(); });
    renderAll();
  }

  function normalizeBoxFromBbox(element, index) {
    const bbox = Array.isArray(element?.bbox) ? element.bbox : [80 + index * 40, 80 + index * 40, 320 + index * 40, 360 + index * 40];
    const order = bboxOrder(state.target_model);
    const xmin = clamp01(Number(order === "xy" ? bbox[0] : bbox[1]) / 1000);
    const ymin = clamp01(Number(order === "xy" ? bbox[1] : bbox[0]) / 1000);
    const xmax = clamp01(Number(order === "xy" ? bbox[2] : bbox[3]) / 1000);
    const ymax = clamp01(Number(order === "xy" ? bbox[3] : bbox[2]) / 1000);
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
    if (!isBboxLayoutTarget(state.target_model)) return;
    readFieldsIntoState();
    const targetLabel = bboxTargetConfig(state.target_model)?.label || activeProfile()?.label || "BBox";
    const dock = createDockWindow(node, "ideogram", `${targetLabel} bbox layout editor X`, { height: 470, matchNodeWidth: true });
    dock.dock.__workflowXOnClose = () => setPreviewButtonLabels();
    setPreviewButtonLabels();

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

    function activeBboxCaption() {
      const candidates = [];
      if (state.enable_bbox_json_input && state.connected_bbox_json_available) {
        candidates.push(state.connected_bbox_json || "");
      }
      if (state.last_generation?.target_model === state.target_model && state.last_generation?.prompt_format === "json") {
        candidates.push(state.last_generation.prompt);
        candidates.push(state.last_generation.positive);
      }
      candidates.push(widgetValue(node, "final_prompt", ""));
      candidates.push(state.final_prompt || "");
      candidates.push(widgetValue(node, "generated_positive", ""));
      candidates.push(state.generated_positive || "");
      candidates.push(state.ideogram_layout || "");
      for (const candidate of candidates) {
        const caption = parseCaptionText(candidate);
        if (hasCaptionContent(caption)) return caption;
      }
      return {};
    }

    const parsed = activeBboxCaption();
    const decomp = parsed.compositional_deconstruction || {};
    const sourceElements = Array.isArray(decomp.elements) ? decomp.elements : Array.isArray(parsed.elements) ? parsed.elements : [];
    const boxes = sourceElements.map(normalizeBoxFromBbox);
    let activeIndex = boxes.length ? 0 : -1;
    let drawing = null;
    let draggingBox = null;
    let inlineEditor = null;
    let layerMenu = null;
    let layerDismiss = null;
    let toolbarMenuDismiss = null;
    let highLevelDescription = parsed.high_level_description || state.prompt_text || "";
    let backgroundDescription = decomp.background || state.prompt_text || "";
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
    canvas.title = "Drag to draw, click to select, Alt-click to cycle overlapping regions, right-click for regions";
    canvas.tabIndex = 0;
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

    function closeToolbarMenus() {
      toolbarMenuDismiss?.();
      toolbarMenuDismiss = null;
      for (const item of [bgMenu, textMenu, templatesMenu]) {
        item.classList.add("workflowx-uap-hidden");
      }
    }

    function showMenu(menu, button) {
      const shouldOpen = menu.classList.contains("workflowx-uap-hidden");
      closeToolbarMenus();
      if (!shouldOpen) return;
      menu.classList.remove("workflowx-uap-hidden");
      const rect = button.getBoundingClientRect();
      menu.style.left = `${Math.max(4, Math.min(rect.left, window.innerWidth - 260))}px`;
      menu.style.top = `${Math.min(rect.bottom + 4, window.innerHeight - 180)}px`;
      toolbarMenuDismiss = armOutsideDismiss(menu, () => {
        menu.classList.add("workflowx-uap-hidden");
        toolbarMenuDismiss = null;
      }, button);
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
        closeToolbarMenus();
        closeLayerMenu();
        bgMenu.remove();
        textMenu.remove();
        templatesMenu.remove();
        inlineEditor?.remove();
        canvasResizeObserver?.disconnect?.();
        if (node.__workflowXUapRenderIdeogram === renderAll) node.__workflowXUapRenderIdeogram = null;
        if (node.__workflowXUapOnOverlayImageLoad) node.__workflowXUapOnOverlayImageLoad = null;
      };
    })();

    function buildCaption() {
      const toTargetBbox = (box) => {
        const xmin = Math.round(box.x * 1000);
        const ymin = Math.round(box.y * 1000);
        const xmax = Math.round((box.x + box.w) * 1000);
        const ymax = Math.round((box.y + box.h) * 1000);
        return bboxOrder(state.target_model) === "xy"
          ? [xmin, ymin, xmax, ymax]
          : [ymin, xmin, ymax, xmax];
      };
      const elements = boxes.map((box) => {
        const element = {
          type: box.type === "text" ? "text" : "obj",
          bbox: toTargetBbox(box),
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
        high_level_description: highLevelDescription || state.prompt_text || "",
        style_description: stylePalette.length ? {
          aesthetics: "",
          lighting: "",
          medium: state.detail || "",
          color_palette: stylePalette.map((color) => String(color).toUpperCase()),
        } : undefined,
        compositional_deconstruction: {
          background: backgroundDescription || state.prompt_text || "",
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
      const targetModel = isBboxLayoutTarget(state.target_model) ? state.target_model : "ideogram4";
      state.target_model = targetModel;
      if (enabledProfileFormats(activeProfile()).includes("json")) state.prompt_format = "json";
      targetSelect.value = targetModel;
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
        target_model: targetModel,
        prompt_format: "json",
        negative_enabled: Boolean(state.negative_enabled),
        source: "bbox_layout_apply",
        generated_at: new Date().toISOString(),
      };
      syncPreview();
      setStatus("BBox layout applied to output.");
    }

    function activeBox() {
      return boxes[activeIndex] || null;
    }

    function deleteActiveBox() {
      const box = activeBox();
      if (!box) return false;
      if (box.locked) {
        setStatus("Unlock the selected region before deleting it.", true);
        return false;
      }
      boxes.splice(activeIndex, 1);
      activeIndex = Math.min(activeIndex, boxes.length - 1);
      closeInlineEditor();
      closeLayerMenu();
      commitIdeogramState();
      renderAll();
      setStatus("Region deleted.");
      return true;
    }

    function boxColor(box) {
      return box?.palette?.find(Boolean) || box?.color || "#8c8c8c";
    }

    function boxLabel(box, index) {
      const main = box.type === "text" && box.text ? `"${box.text}"` : box.desc || "";
      return main || (box.type === "text" ? "(text)" : "(empty)");
    }

    function armOutsideDismiss(menu, onDismiss, anchor = null) {
      let active = true;
      const isAnchor = (target) => Boolean(anchor && (target === anchor || anchor.contains?.(target)));
      const disarm = () => {
        if (!active) return;
        active = false;
        document.removeEventListener("pointerdown", dismiss, true);
        document.removeEventListener("mousedown", dismiss, true);
        document.removeEventListener("keydown", onKey, true);
      };
      const dismiss = (event) => {
        if (!active) return;
        const target = event.target;
        if (menu.contains(target) || isAnchor(target)) return;
        disarm();
        onDismiss();
      };
      const onKey = (event) => {
        if (!active || event.key !== "Escape") return;
        disarm();
        onDismiss();
      };
      setTimeout(() => {
        if (!active) return;
        document.addEventListener("pointerdown", dismiss, true);
        document.addEventListener("mousedown", dismiss, true);
        document.addEventListener("keydown", onKey, true);
      }, 0);
      return disarm;
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
        if (box.locked) ctx.setLineDash([10, 6]);
        ctx.strokeRect(x, y, w, h);
        ctx.setLineDash([]);
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
          if (box.locked) {
            ctx.font = "18px sans-serif";
            ctx.fillText("locked", x + 8, Math.min(y + h - 12, y + 86));
          }
        }
        if (index === activeIndex && !box.locked) {
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
      const xmin = Math.round(box.x * width);
      const ymin = Math.round(box.y * height);
      const xmax = Math.round((box.x + box.w) * width);
      const ymax = Math.round((box.y + box.h) * height);
      return bboxOrder(state.target_model) === "xy" ? [xmin, ymin, xmax, ymax] : [ymin, xmin, ymax, xmax];
    }

    function boxToGrid(box) {
      const xmin = Math.round(box.x * 1000);
      const ymin = Math.round(box.y * 1000);
      const xmax = Math.round((box.x + box.w) * 1000);
      const ymax = Math.round((box.y + box.h) * 1000);
      return bboxOrder(state.target_model) === "xy" ? [xmin, ymin, xmax, ymax] : [ymin, xmin, ymax, xmax];
    }

    function parseOrderedBox(nums, width, height) {
      let xmin;
      let ymin;
      let xmax;
      let ymax;
      if (bboxOrder(state.target_model) === "xy") {
        [xmin, ymin, xmax, ymax] = nums;
      } else {
        [ymin, xmin, ymax, xmax] = nums;
      }
      ymin = Math.max(0, Math.min(height, ymin));
      ymax = Math.max(0, Math.min(height, ymax));
      xmin = Math.max(0, Math.min(width, xmin));
      xmax = Math.max(0, Math.min(width, xmax));
      if (ymin > ymax) [ymin, ymax] = [ymax, ymin];
      if (xmin > xmax) [xmin, xmax] = [xmax, xmin];
      return { xmin, ymin, xmax, ymax };
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
      const orderLabel = bboxOrderLabel(state.target_model);
      const pxField = makeBboxField(orderLabel, `Pixel bbox: ${orderLabel}`, () => {
        const nums = parseBboxNumbers(pxField);
        if (!nums) {
          pxField.value = boxToPx(box).join(", ");
          return;
        }
        const [width, height] = dims();
        const { xmin, ymin, xmax, ymax } = parseOrderedBox(nums, width, height);
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
      const gridField = makeBboxField(orderLabel, `Exported 0-1000 bbox: ${orderLabel}`, () => {
        const nums = parseBboxNumbers(gridField);
        if (!nums) {
          gridField.value = boxToGrid(box).join(", ");
          return;
        }
        const { xmin, ymin, xmax, ymax } = parseOrderedBox(nums.map((number) => Math.max(0, Math.min(1000, number))), 1000, 1000);
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

    function hitCandidates(point) {
      const handleX = Math.min(10 / Math.max(1, canvas.getBoundingClientRect().width), 0.04);
      const handleY = Math.min(10 / Math.max(1, canvas.getBoundingClientRect().height), 0.04);
      const handleHit = (pointValue, target, radius) => Math.abs(pointValue - target) <= radius;
      const candidates = [];
      for (let index = 0; index < boxes.length; index += 1) {
        const box = boxes[index];
        if (box.locked) continue;
        const x1 = box.x;
        const y1 = box.y;
        const x2 = box.x + box.w;
        const y2 = box.y + box.h;
        if (point.x < x1 - handleX || point.x > x2 + handleX || point.y < y1 - handleY || point.y > y2 + handleY) continue;
        const nearL = handleHit(point.x, x1, handleX);
        const nearR = handleHit(point.x, x2, handleX);
        const nearT = handleHit(point.y, y1, handleY);
        const nearB = handleHit(point.y, y2, handleY);
        let mode = "";
        if (nearL && nearT) mode = "resize-tl";
        else if (nearR && nearT) mode = "resize-tr";
        else if (nearL && nearB) mode = "resize-bl";
        else if (nearR && nearB) mode = "resize-br";
        else if (nearL && point.y >= y1 && point.y <= y2) mode = "resize-l";
        else if (nearR && point.y >= y1 && point.y <= y2) mode = "resize-r";
        else if (nearT && point.x >= x1 && point.x <= x2) mode = "resize-t";
        else if (nearB && point.x >= x1 && point.x <= x2) mode = "resize-b";
        else if (point.x >= x1 && point.x <= x2 && point.y >= y1 && point.y <= y2) mode = "move";
        if (mode) candidates.push({ index, mode });
      }
      return candidates;
    }

    function hitTest(point, cycle = false) {
      const candidates = hitCandidates(point);
      if (!candidates.length) return null;
      if (cycle && candidates.length > 1) {
        const ordered = [...candidates].sort((a, b) => a.index - b.index);
        const current = ordered.findIndex((item) => item.index === activeIndex);
        return ordered[(current + 1) % ordered.length];
      }
      const activeHandle = candidates.find((item) => item.index === activeIndex && item.mode !== "move");
      if (activeHandle) return activeHandle;
      return candidates[0];
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
      layerDismiss?.();
      layerDismiss = null;
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
        const lock = buildDom("button", `workflowx-uap-ideo-layer-btn${box.locked ? " on" : ""}`, box.locked ? "unlock" : "lock");
        const duplicate = buildDom("button", "workflowx-uap-ideo-layer-btn", "copy");
        const remove = buildDom("button", "workflowx-uap-ideo-layer-btn", "x");
        for (const button of [lock, duplicate, remove]) button.type = "button";
        lock.title = box.locked ? "Unlock this region for canvas editing" : "Lock this region against canvas editing";
        duplicate.title = "Duplicate this region";
        remove.title = box.locked ? "Unlock this region before removing it" : "Remove this region";
        remove.disabled = Boolean(box.locked);
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
      stopEditorEvents(menu);
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
      layerDismiss = armOutsideDismiss(menu, () => {
        closeLayerMenu();
      });
    }

    canvas.addEventListener("keydown", (event) => {
      if (!["Delete", "Backspace"].includes(event.key)) return;
      if (inlineEditor) return;
      event.preventDefault();
      event.stopPropagation();
      deleteActiveBox();
    });
    canvas.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      canvas.focus();
      closeInlineEditor();
      const point = eventPoint(event);
      const hit = hitTest(point, event.altKey);
      if (hit) {
        activeIndex = hit.index;
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
      if (state.enable_bbox_json_input && inputIsLinked(node, "bbox_json") && !state.connected_bbox_json_available) {
        setStatus("Connected bbox_json input is enabled but could not be read. Using cached output if available.", true);
      }
      const caption = activeBboxCaption();
      if (!hasCaptionContent(caption)) {
        setStatus("No BBox JSON available to sync.", true);
        return;
      }
      loadCaption(caption, false);
      setStatus("BBox layout synced.");
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

  function toggleIdeogramLayoutEditor() {
    if (dockIsOpen(node, "ideogram")) {
      closeDock(node, "ideogram");
      setPreviewButtonLabels();
      return;
    }
    openIdeogramLayoutEditor();
  }

  async function fetchGeminiModels() {
    const jsonx = isJsonXProfile();
    const apiKey = keyInput.value.trim();
    if (jsonx) {
      if (apiKey) localStorage.setItem(JSONX_GEMINI_KEY, apiKey);
      else localStorage.removeItem(JSONX_GEMINI_KEY);
    } else {
      state.gemini_key = apiKey;
      storeGeminiKey(apiKey);
    }
    if (!apiKey) {
      setStatus("Enter a Gemini API key first.", true);
      return;
    }
    fetchGeminiBtn.disabled = true;
    setStatus("Fetching Gemini models...");
    try {
      const response = await fetch(`${jsonx ? JSONX_ROUTE : ROUTE}/gemini/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, timeout: Number(timeoutInput.value || 120) }),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
      const selected = jsonx ? jsonxProviderSettings().gemini_model : state.gemini_model;
      fillModelSelect(geminiModelSelect, data.models, selected);
      if (!geminiModelSelect.value && geminiModelSelect.options.length) geminiModelSelect.selectedIndex = 0;
      if (jsonx) persistJsonXProviderFromControls();
      else state.gemini_model = geminiModelSelect.value;
      persistModelSelection();
      syncPreview();
      setStatus(`${data.models.length} Gemini models loaded.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchGeminiBtn.disabled = false;
      scheduleVisibleContentResize();
    }
  }

  async function fetchOpenaiModels() {
    const jsonx = isJsonXProfile();
    const baseUrl = openaiBaseUrlInput.value.trim() || DEFAULT_OPENAI_BASE_URL;
    const apiKey = openaiKeyInput.value.trim();
    if (jsonx) {
      if (apiKey) localStorage.setItem(JSONX_OPENAI_KEY, apiKey);
      else localStorage.removeItem(JSONX_OPENAI_KEY);
    } else {
      state.openai_base_url = baseUrl;
      state.openai_key = apiKey;
      storeOpenAIBaseUrl(baseUrl);
      storeOpenAIKey(apiKey);
    }
    fetchOpenaiBtn.disabled = true;
    setStatus("Fetching OpenAI-compatible models...");
    try {
      const data = await fetchJsonChecked(`${jsonx ? JSONX_ROUTE : ROUTE}/openai/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: baseUrl,
          api_key: apiKey,
          timeout: Number(openaiTimeoutInput.value || 120),
          server_type: normalizeOpenAIServerType(openaiServerTypeSelect.value),
        }),
      }, "Fetch OpenAI-compatible models");
      openaiDetectedServerType = normalizeOpenAIServerType(data.server_type || "generic");
      openaiModelsById = new Map((data.models || []).map((model) => [String(model.id || model.name || model), model]));
      openaiReasoningCapabilities = data.reasoning && typeof data.reasoning === "object" ? data.reasoning : {};
      const selected = jsonx ? jsonxProviderSettings().openai_model : state.openai_model;
      fillModelSelect(openaiModelSelect, data.models, selected);
      if (!openaiModelSelect.value && openaiModelSelect.options.length) openaiModelSelect.selectedIndex = 0;
      if (openaiModelSelect.value) openaiModelInput.value = "";
      syncOpenAIReasoningOptions();
      if (jsonx) persistJsonXProviderFromControls();
      else state.openai_model = openaiModelSelect.value || openaiModelInput.value;
      persistModelSelection();
      syncPreview();
      const detectedLabel = {
        generic: "Generic OpenAI-compatible",
        lm_studio: "LM Studio",
        unsloth: "Unsloth Studio",
      }[openaiDetectedServerType] || "OpenAI-compatible";
      setStatus(`${data.models.length} models loaded · ${detectedLabel}.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchOpenaiBtn.disabled = false;
      scheduleVisibleContentResize();
    }
  }

  async function fetchGrokModels() {
    const jsonx = isJsonXProfile();
    const apiKey = grokKeyInput.value.trim();
    if (!apiKey) {
      setStatus("Enter an xAI API key first.", true);
      return;
    }
    fetchGrokBtn.disabled = true;
    setStatus("Fetching xAI models...");
    try {
      const data = await fetchJsonChecked(`${jsonx ? JSONX_ROUTE : ROUTE}/grok/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, timeout: Number(grokTimeoutInput.value || 120) }),
      }, "Fetch xAI models");
      const previous = grokModelSelect.value || grokModelInput.value.trim();
      grokModelsById = new Map((data.models || []).map((item) => [String(item.id || item.name || item), item]));
      fillModelSelect(grokModelSelect, data.models || [], previous);
      const model = grokModelsById.get(grokModelSelect.value);
      grokCapabilityInfo.textContent = model
        ? `${model.vision ? "Vision input" : "Text input only"}${model.context_length ? ` · context ${model.context_length.toLocaleString()} tokens` : ""}`
        : "No language model selected.";
      syncGrokReasoningOptions();
      if (jsonx) persistJsonXProviderFromControls(); else persistStandardProviderFromControls();
      setStatus(`${(data.models || []).length} xAI models loaded.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchGrokBtn.disabled = false;
      scheduleVisibleContentResize();
    }
  }

  async function fetchDeepSeekModels() {
    const jsonx = isJsonXProfile();
    const apiKey = deepseekKeyInput.value.trim();
    if (!apiKey) {
      setStatus("Enter a DeepSeek API key first.", true);
      return;
    }
    fetchDeepSeekBtn.disabled = true;
    setStatus("Fetching DeepSeek models...");
    try {
      const data = await fetchJsonChecked(`${jsonx ? JSONX_ROUTE : ROUTE}/deepseek/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, timeout: Number(deepseekTimeoutInput.value || 120) }),
      }, "Fetch DeepSeek models");
      const previous = deepseekModelSelect.value || deepseekModelInput.value.trim();
      deepseekModelsById = new Map((data.models || []).map((item) => [String(item.id || item.name || item), item]));
      fillModelSelect(deepseekModelSelect, data.models || [], previous);
      if (deepseekModelSelect.value) deepseekModelInput.value = "";
      syncDeepSeekControls();
      if (jsonx) persistJsonXProviderFromControls(); else persistStandardProviderFromControls();
      setStatus(`${(data.models || []).length} DeepSeek models loaded.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchDeepSeekBtn.disabled = false;
      scheduleVisibleContentResize();
    }
  }

  async function fetchStudioModels(kind, controls) {
    const jsonx = isJsonXProfile();
    const label = kind === "lm_studio" ? "LM Studio" : "Unsloth Studio";
    controls.fetch.disabled = true;
    setStatus(`Fetching ${label} models...`);
    try {
      const data = await fetchJsonChecked(`${jsonx ? JSONX_ROUTE : ROUTE}/${kind}/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: controls.baseUrl.value.trim(),
          api_key: controls.key.value,
          timeout: Number(controls.timeout.value || 120),
        }),
      }, `Fetch ${label} models`);
      const previous = controls.model.value || controls.manualModel.value.trim();
      controls.modelsById = new Map((data.models || []).map((model) => {
        const augmented = kind === "unsloth" ? { ...(data.reasoning || {}), ...model } : model;
        return [String(model.id || model.name || model), augmented];
      }));
      fillModelSelect(controls.model, data.models || [], previous);
      const model = controls.modelsById.get(controls.model.value);
      const context = model?.active_context_length || model?.native_context_length || model?.max_context_length || model?.context_length;
      controls.capabilities.textContent = model
        ? `${model.vision === false ? "Text input only" : "Vision capability detected/unknown"}${context ? ` · active/native context ${Number(context).toLocaleString()} tokens` : ""}`
        : "No model selected.";
      const options = Array.isArray(model?.reasoning_options)
        ? model.reasoning_options
        : Array.isArray(data.reasoning?.options) ? data.reasoning.options : [];
      const reasoningChoices = openaiReasoningChoices.filter((item) => item.value === "default" || !options.length || options.includes(item.value));
      setSelectOptions(controls.reasoning, reasoningChoices, controls.reasoning.value || "default");
      controls.preserveThinkingSupported = Boolean(model?.preserve_thinking_supported ?? data.reasoning?.preserve_thinking_supported ?? false);
      if (kind === "unsloth") controls.preserveThinking.disabled = !controls.preserveThinkingSupported;
      if (jsonx) persistJsonXProviderFromControls(); else persistStandardProviderFromControls();
      setStatus(`${(data.models || []).length} ${label} models loaded.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      controls.fetch.disabled = false;
      scheduleVisibleContentResize();
    }
  }

  async function fetchOllamaModels() {
    const jsonx = isJsonXProfile();
    fetchOllamaBtn.disabled = true;
    setStatus("Fetching Ollama models...");
    try {
      const response = await fetch(`${jsonx ? JSONX_ROUTE : ROUTE}/ollama/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host: hostInput.value || DEFAULT_OLLAMA_HOST, timeout: Number(ollamaTimeoutInput.value || 120) }),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
      const selected = jsonx ? jsonxProviderSettings().ollama_model : state.ollama_model;
      fillModelSelect(ollamaModelSelect, data.models, selected);
      if (!ollamaModelSelect.value && ollamaModelSelect.options.length) ollamaModelSelect.selectedIndex = 0;
      if (jsonx) persistJsonXProviderFromControls();
      else state.ollama_model = ollamaModelSelect.value;
      persistModelSelection();
      syncPreview();
      setStatus(`${data.models.length} Ollama models loaded.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchOllamaBtn.disabled = false;
      scheduleVisibleContentResize();
    }
  }

  async function fetchLocalModels() {
    const jsonx = isJsonXProfile();
    fetchLocalBtn.disabled = true;
    setStatus("Refreshing local GGUF files...");
    try {
      if (jsonx) persistJsonXProviderFromControls();
      else storeAdditionalLocalModelPaths(localAdditionalPathsInput.value);
      const response = await fetch(`${jsonx ? JSONX_ROUTE : ROUTE}/local/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          additional_model_paths: additionalLocalModelPaths(localAdditionalPathsInput.value),
        }),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
      const selected = jsonx ? jsonxProviderSettings() : state;
      setSelectOptions(localModelSelect, data.models || [], selected.local_model);
      setSelectOptions(mmprojSelect, data.mmproj || ["none"], selected.local_mmproj);
      setSelectOptions(systemPresetSelect, data.system_prompts || ["none"], selected.local_system_prompt_preset);
      if (jsonx) persistJsonXProviderFromControls();
      else {
        state.local_model = localModelSelect.value || "";
        state.local_mmproj = mmprojSelect.value || "none";
        state.local_system_prompt_preset = systemPresetSelect.value || "none";
      }
      persistModelSelection();
      syncPreview();
      const skipped = Number(data.invalid_paths?.length || 0);
      setStatus(`Local model list refreshed${data.additional_roots ? ` · ${data.additional_roots} additional folder(s)` : ""}${skipped ? ` · ${skipped} missing/invalid path(s) skipped` : ""}.`, skipped > 0);
    } catch (error) {
      setStatus(`Error: ${error.message}`, true);
    } finally {
      fetchLocalBtn.disabled = false;
      scheduleVisibleContentResize();
    }
  }

  let activeGenerationId = "";

  function jsonxProviderSettings() {
    try {
      const legacy = JSON.parse(localStorage.getItem(JSONX_SETTINGS_KEY) || "{}");
      const browserSource = {
        ...(legacy && typeof legacy === "object" ? legacy : {}),
        ...loadProviderSettings("jsonx"),
      };
      const workflowSource = {};
      const source = {
        ...browserSource,
        ...workflowSource,
        local_options: {
          ...(browserSource.local_options && typeof browserSource.local_options === "object" ? browserSource.local_options : {}),
          ...(workflowSource.local_options && typeof workflowSource.local_options === "object" ? workflowSource.local_options : {}),
        },
        gemini_safety: {
          ...(browserSource.gemini_safety && typeof browserSource.gemini_safety === "object" ? browserSource.gemini_safety : {}),
          ...(workflowSource.gemini_safety && typeof workflowSource.gemini_safety === "object" ? workflowSource.gemini_safety : {}),
        },
      };
      const backend = PROVIDERS.some(([value]) => value === source.backend) ? source.backend : "gemini";
      const legacyModel = String(source.model || "");
      return {
        backend,
        gemini_model: source.gemini_model || (backend === "gemini" ? legacyModel : ""),
        gemini_timeout: Number(source.gemini_timeout || source.timeout || 180),
        openai_base_url: source.openai_base_url || DEFAULT_OPENAI_BASE_URL,
        openai_model: source.openai_model || (backend === "openai" ? legacyModel : ""),
        openai_timeout: Number(source.openai_timeout || source.timeout || 180),
        openai_server_type: normalizeOpenAIServerType(source.openai_server_type),
        openai_lifecycle: normalizeOpenAILifecycle(
          source.openai_lifecycle || (source.unload_after === true ? "unload_after" : "server_managed"),
        ),
        openai_reasoning_effort: normalizeOpenAIReasoning(source.openai_reasoning_effort),
        grok: {
          ...(source.grok || {}),
          api_key: loadDedicatedApiKey(JSONX_GROK_KEY, source.grok?.api_key),
        },
        deepseek: {
          ...(source.deepseek || {}),
          api_key: loadDedicatedApiKey(JSONX_DEEPSEEK_KEY, source.deepseek?.api_key),
        },
        lm_studio: { ...(source.lm_studio || {}) },
        unsloth: { ...(source.unsloth || {}) },
        ollama_host: source.ollama_host || DEFAULT_OLLAMA_HOST,
        ollama_model: source.ollama_model || (backend === "ollama" ? legacyModel : ""),
        ollama_timeout: Number(source.ollama_timeout || source.timeout || 180),
        ollama_think: Boolean(source.ollama_think ?? source.think ?? false),
        ollama_options: { ...(source.ollama_options || {}) },
        unload_after: source.unload_after !== false,
        local_model: source.local_model || (backend === "local" ? legacyModel : ""),
        local_timeout: Number(source.local_timeout || source.timeout || 180),
        additional_model_paths: String(source.additional_model_paths || ""),
        local_mmproj: source.local_mmproj || source.mmproj || "none",
        local_system_prompt_preset: source.local_system_prompt_preset || source.system_prompt_preset || "none",
        local_options: {
          max_tokens: 8192, temperature: 0.7, top_p: 0.9, top_k: 40, repeat_penalty: 1.05,
          ctx_size: 32768, memory_mode: "auto", n_gpu_layers: 99, n_cpu_moe_layers: 0,
          reasoning: "off", speculative_mode: "auto", mtp_draft_tokens: 2, seed: -1,
          ...(source.local_options && typeof source.local_options === "object" ? source.local_options : {}),
        },
        gemini_safety: {
          safety_harassment: "BLOCK_NONE", safety_hate_speech: "BLOCK_NONE",
          safety_sexual: "BLOCK_NONE", safety_dangerous: "BLOCK_NONE",
          ...(source.gemini_safety && typeof source.gemini_safety === "object" ? source.gemini_safety : {}),
        },
      };
    } catch { return { backend: "gemini", local_options: {}, gemini_safety: {} }; }
  }

  function saveJsonXProviderSettings(settings) {
    saveProviderSettings("jsonx", {
      ...settings,
      grok: withoutApiKey(settings?.grok),
      deepseek: withoutApiKey(settings?.deepseek),
    });
  }

  function isJsonXProfile(profile = activeProfile()) { return profile?.engine === "jsonx"; }

  function ensureSelectValue(select, value, label = value) {
    const clean = String(value || "");
    if (clean && !Array.from(select.options).some((item) => item.value === clean)) option(select, clean, label || clean);
    select.value = clean;
  }

  function providerBackend() {
    return isJsonXProfile() ? jsonxProviderSettings().backend : state.backend;
  }

  function applyActiveProviderSettingsToControls() {
    const discoveryScope = isJsonXProfile() ? "jsonx" : "standard";
    if (discoveryScope !== openaiDiscoveryScope) {
      openaiDiscoveryScope = discoveryScope;
      openaiDetectedServerType = "auto";
      openaiModelsById = new Map();
      openaiReasoningCapabilities = {};
    }
    if (!isJsonXProfile()) {
      keyInput.value = state.gemini_key || "";
      timeoutInput.value = String(state.gemini_timeout || 120);
      ensureSelectValue(geminiModelSelect, state.gemini_model);
      for (const [key] of GEMINI_SAFETY_FIELDS) geminiSafetySelects[key].value = state[key] || "BLOCK_NONE";
      openaiBaseUrlInput.value = state.openai_base_url || DEFAULT_OPENAI_BASE_URL;
      openaiKeyInput.value = state.openai_key || "";
      openaiTimeoutInput.value = String(state.openai_timeout || 120);
      openaiModelInput.value = state.openai_model || "";
      ensureSelectValue(openaiModelSelect, state.openai_model);
      openaiServerTypeSelect.value = "generic";
      openaiLifecycleSelect.value = normalizeOpenAILifecycle(state.openai_lifecycle);
      setSelectOptions(openaiReasoningSelect, openaiReasoningChoices, normalizeOpenAIReasoning(state.openai_reasoning_effort));
      hostInput.value = state.ollama_host || DEFAULT_OLLAMA_HOST;
      ollamaTimeoutInput.value = String(state.ollama_timeout || 120);
      ensureSelectValue(ollamaModelSelect, state.ollama_model);
      thinkInput.checked = Boolean(state.ollama_think);
      unloadInput.checked = state.unload_after !== false;
      for (const [key, input] of Object.entries(ollamaOptionInputs)) input.value = state.ollama_options?.[key] ?? "";
      localAdditionalPathsInput.value = loadStoredAdditionalLocalModelPaths();
      ensureSelectValue(localModelSelect, state.local_model);
      ensureSelectValue(mmprojSelect, state.local_mmproj || "none");
      ensureSelectValue(systemPresetSelect, state.local_system_prompt_preset || "none");
      localTimeoutInput.value = String(state.local_timeout || 180);
      maxTokensInput.value = String(state.max_tokens || 768);
      tempInput.value = String(state.temperature ?? 0.7);
      topPInput.value = String(state.top_p ?? 0.9);
      topKInput.value = String(state.top_k ?? 40);
      repeatPenaltyInput.value = String(state.repeat_penalty ?? 1.05);
      ctxInput.value = String(state.ctx_size || 8192);
      memorySelect.value = state.memory_mode || "auto";
      reasoningSelect.value = normalizeUnifiedReasoning(state.reasoning);
      thinkingLevelSelect.value = state.thinking_level || "default";
      thinkingBudgetInput.value = String(state.thinking_budget || 2048);
      refreshThinkingControls();
      speculativeSelect.value = state.speculative_mode || "auto";
      mtpDraftTokensInput.value = String(state.mtp_draft_tokens || 2);
      gpuLayersInput.value = String(state.n_gpu_layers ?? 99);
      cpuMoeLayersInput.value = String(state.n_cpu_moe_layers ?? 0);
      seedInput.value = String(state.seed ?? -1);
      applyExtendedProviderControls(state);
      syncMemoryControls();
      return;
    }
    const provider = jsonxProviderSettings();
    keyInput.value = localStorage.getItem(JSONX_GEMINI_KEY) || "";
    timeoutInput.value = String(provider.gemini_timeout || 180);
    ensureSelectValue(geminiModelSelect, provider.gemini_model);
    for (const [key] of GEMINI_SAFETY_FIELDS) geminiSafetySelects[key].value = provider.gemini_safety?.[key] || "BLOCK_NONE";
    openaiBaseUrlInput.value = provider.openai_base_url || DEFAULT_OPENAI_BASE_URL;
    openaiKeyInput.value = localStorage.getItem(JSONX_OPENAI_KEY) || "";
    openaiTimeoutInput.value = String(provider.openai_timeout || 180);
    openaiModelInput.value = provider.openai_model || "";
    ensureSelectValue(openaiModelSelect, provider.openai_model);
    openaiServerTypeSelect.value = "generic";
    openaiLifecycleSelect.value = normalizeOpenAILifecycle(provider.openai_lifecycle);
    setSelectOptions(openaiReasoningSelect, openaiReasoningChoices, normalizeOpenAIReasoning(provider.openai_reasoning_effort));
    hostInput.value = provider.ollama_host || DEFAULT_OLLAMA_HOST;
    ollamaTimeoutInput.value = String(provider.ollama_timeout || 180);
    ensureSelectValue(ollamaModelSelect, provider.ollama_model);
    thinkInput.checked = Boolean(provider.ollama_think);
    unloadInput.checked = provider.unload_after !== false;
    for (const [key, input] of Object.entries(ollamaOptionInputs)) input.value = provider.ollama_options?.[key] ?? "";
    localAdditionalPathsInput.value = provider.additional_model_paths || "";
    ensureSelectValue(localModelSelect, provider.local_model);
    ensureSelectValue(mmprojSelect, provider.local_mmproj || "none");
    ensureSelectValue(systemPresetSelect, provider.local_system_prompt_preset || "none");
    localTimeoutInput.value = String(provider.local_timeout || 180);
    const local = provider.local_options || {};
    maxTokensInput.value = String(local.max_tokens || 8192);
    tempInput.value = String(local.temperature ?? 0.7);
    topPInput.value = String(local.top_p ?? 0.9);
    topKInput.value = String(local.top_k ?? 40);
    repeatPenaltyInput.value = String(local.repeat_penalty ?? 1.05);
    ctxInput.value = String(local.ctx_size || 32768);
    memorySelect.value = local.memory_mode || "auto";
    reasoningSelect.value = normalizeUnifiedReasoning(local.reasoning || "off");
    thinkingLevelSelect.value = local.thinking_level || "default";
    thinkingBudgetInput.value = String(local.thinking_budget || 2048);
    refreshThinkingControls();
    speculativeSelect.value = local.speculative_mode || "auto";
    mtpDraftTokensInput.value = String(local.mtp_draft_tokens || 2);
    gpuLayersInput.value = String(local.n_gpu_layers ?? 99);
    cpuMoeLayersInput.value = String(local.n_cpu_moe_layers ?? 0);
    seedInput.value = String(local.seed ?? -1);
    applyExtendedProviderControls(provider);
    syncMemoryControls();
  }

  function applyExtendedProviderControls(source) {
    const grok = source?.grok || {};
    grokKeyInput.value = grok.api_key || "";
    ensureSelectValue(grokModelSelect, grok.model || "");
    grokModelInput.value = grok.manual_model || "";
    grokTimeoutInput.value = String(grok.timeout || 120);
    grokMaxTokensInput.value = grok.max_output_tokens ?? "";
    grokTemperatureInput.value = grok.temperature ?? "";
    grokTopPInput.value = grok.top_p ?? "";
    grokReasoningSelect.value = grok.reasoning_effort || "default";
    grokCacheSelect.value = grok.prompt_cache || "auto";
    const deepseek = source?.deepseek || {};
    deepseekKeyInput.value = deepseek.api_key || "";
    ensureSelectValue(deepseekModelSelect, deepseek.model || "");
    deepseekModelInput.value = deepseek.manual_model || "";
    deepseekTimeoutInput.value = String(deepseek.timeout || 120);
    deepseekMaxTokensInput.value = deepseek.max_tokens ?? "";
    deepseekThinkingSelect.value = deepseek.thinking || "default";
    deepseekReasoningSelect.value = deepseek.reasoning_effort || "default";
    deepseekTemperatureInput.value = deepseek.temperature ?? "";
    deepseekTopPInput.value = deepseek.top_p ?? "";
    deepseekImageDetailSelect.value = deepseek.image_detail || "default";
    syncDeepSeekControls();
    const applyStudio = (controls, values, fallbackUrl) => {
      values ||= {};
      controls.baseUrl.value = values.base_url || fallbackUrl;
      controls.key.value = values.api_key || "";
      ensureSelectValue(controls.model, values.model || "");
      controls.manualModel.value = values.manual_model || "";
      controls.timeout.value = String(values.timeout || 120);
      controls.lifecycle.value = values.lifecycle || "server_managed";
      controls.maxTokens.value = values.max_tokens ?? "";
      controls.context.value = values.context_length ?? "";
      controls.temperature.value = values.temperature ?? "";
      controls.topP.value = values.top_p ?? "";
      controls.topK.value = values.top_k ?? "";
      controls.minP.value = values.min_p ?? "";
      controls.repeatPenalty.value = values.repeat_penalty ?? "";
      controls.presencePenalty.value = values.presence_penalty ?? "";
      controls.reasoning.value = values.reasoning_effort || "default";
      controls.thinkingMode.value = values.thinking_mode || "default";
      controls.preserveThinking.checked = Boolean(values.preserve_thinking);
    };
    applyStudio(lmStudio, source?.lm_studio, "http://localhost:1234/v1");
    applyStudio(unsloth, source?.unsloth, "http://localhost:8000/v1");
  }

  function extendedProviderSettingsFromControls() {
    const studio = (controls) => ({
      base_url: controls.baseUrl.value.trim(),
      api_key: controls.key.value,
      model: controls.model.value || controls.manualModel.value.trim(),
      manual_model: controls.manualModel.value.trim(),
      timeout: Number(controls.timeout.value || 120),
      lifecycle: controls.lifecycle.value,
      max_tokens: optionalNumber(controls.maxTokens.value, true),
      context_length: optionalNumber(controls.context.value, true),
      temperature: optionalNumber(controls.temperature.value),
      top_p: optionalNumber(controls.topP.value),
      top_k: optionalNumber(controls.topK.value, true),
      min_p: optionalNumber(controls.minP.value),
      repeat_penalty: optionalNumber(controls.repeatPenalty.value),
      presence_penalty: optionalNumber(controls.presencePenalty.value),
      reasoning_effort: controls.reasoning.value || "default",
      thinking_mode: controls.thinkingMode.value || "default",
      preserve_thinking: controls.preserveThinking.checked,
    });
    return {
      grok: {
        api_key: grokKeyInput.value,
        model: grokModelSelect.value || grokModelInput.value.trim(),
        manual_model: grokModelInput.value.trim(),
        timeout: Number(grokTimeoutInput.value || 120),
        max_output_tokens: optionalNumber(grokMaxTokensInput.value, true),
        temperature: optionalNumber(grokTemperatureInput.value),
        top_p: optionalNumber(grokTopPInput.value),
        reasoning_effort: grokReasoningSelect.value || "default",
        prompt_cache: grokCacheSelect.value || "auto",
      },
      deepseek: {
        api_key: deepseekKeyInput.value,
        model: deepseekModelSelect.value || deepseekModelInput.value.trim(),
        manual_model: deepseekModelInput.value.trim(),
        timeout: Number(deepseekTimeoutInput.value || 120),
        max_tokens: optionalNumber(deepseekMaxTokensInput.value, true),
        thinking: deepseekThinkingSelect.value || "default",
        reasoning_effort: deepseekReasoningSelect.value || "default",
        temperature: optionalNumber(deepseekTemperatureInput.value),
        top_p: optionalNumber(deepseekTopPInput.value),
        image_detail: deepseekImageDetailSelect.value || "default",
      },
      lm_studio: studio(lmStudio),
      unsloth: studio(unsloth),
    };
  }

  function persistJsonXProviderFromControls(overrides = {}) {
    const previous = jsonxProviderSettings();
    const backend = overrides.backend || previous.backend || "gemini";
    const extended = extendedProviderSettingsFromControls();
    extended.grok.api_key = grokKeyDirty
      ? extended.grok.api_key
      : loadDedicatedApiKey(JSONX_GROK_KEY, extended.grok.api_key);
    extended.deepseek.api_key = deepseekKeyDirty
      ? extended.deepseek.api_key
      : loadDedicatedApiKey(JSONX_DEEPSEEK_KEY, extended.deepseek.api_key);
    if (grokKeyDirty) storeDedicatedApiKey(JSONX_GROK_KEY, extended.grok.api_key);
    if (deepseekKeyDirty) storeDedicatedApiKey(JSONX_DEEPSEEK_KEY, extended.deepseek.api_key);
    grokKeyDirty = false;
    deepseekKeyDirty = false;
    const provider = {
      ...previous,
      ...extended,
      backend,
      gemini_model: geminiModelSelect.value || previous.gemini_model || "",
      gemini_timeout: Number(timeoutInput.value || 180),
      gemini_safety: Object.fromEntries(GEMINI_SAFETY_FIELDS.map(([key]) => [key, geminiSafetySelects[key].value || "BLOCK_NONE"])),
      openai_base_url: openaiBaseUrlInput.value.trim() || DEFAULT_OPENAI_BASE_URL,
      openai_model: (openaiModelSelect.value || openaiModelInput.value || previous.openai_model || "").trim(),
      openai_timeout: Number(openaiTimeoutInput.value || 180),
      openai_server_type: normalizeOpenAIServerType(openaiServerTypeSelect.value),
      openai_lifecycle: normalizeOpenAILifecycle(openaiLifecycleSelect.value),
      openai_reasoning_effort: normalizeOpenAIReasoning(openaiReasoningSelect.value),
      ollama_host: hostInput.value.trim() || DEFAULT_OLLAMA_HOST,
      ollama_model: ollamaModelSelect.value || previous.ollama_model || "",
      ollama_timeout: Number(ollamaTimeoutInput.value || 180),
      ollama_think: thinkInput.checked,
      ollama_options: Object.fromEntries(Object.entries(ollamaOptionInputs).map(([key, input]) => [key, optionalNumber(input.value, input.dataset.integer === "1")])),
      unload_after: unloadInput.checked,
      local_model: localModelSelect.value || previous.local_model || "",
      local_timeout: Number(localTimeoutInput.value || 180),
      additional_model_paths: localAdditionalPathsInput.value.trim(),
      local_mmproj: mmprojSelect.value || "none",
      local_system_prompt_preset: systemPresetSelect.value || "none",
      local_options: {
        max_tokens: Number(maxTokensInput.value || 8192), temperature: Number(tempInput.value || 0.7),
        top_p: Number(topPInput.value || 0.9), top_k: Number(topKInput.value || 40),
        repeat_penalty: Number(repeatPenaltyInput.value || 1.05), ctx_size: Number(ctxInput.value || 32768),
        memory_mode: memorySelect.value || "auto", reasoning: reasoningSelect.value || "off",
        thinking_level: thinkingLevelSelect.value, thinking_budget: Number(thinkingBudgetInput.value || 2048),
        speculative_mode: speculativeSelect.value || "auto", mtp_draft_tokens: Number(mtpDraftTokensInput.value || 2),
        n_gpu_layers: Number(gpuLayersInput.value || 99), n_cpu_moe_layers: Number(cpuMoeLayersInput.value || 0),
        seed: Number(seedInput.value ?? -1),
      },
    };
    saveJsonXProviderSettings(provider);
    const geminiKey = keyInput.value.trim();
    const openaiKey = openaiKeyInput.value.trim();
    if (geminiKey) localStorage.setItem(JSONX_GEMINI_KEY, geminiKey); else localStorage.removeItem(JSONX_GEMINI_KEY);
    if (openaiKey) localStorage.setItem(JSONX_OPENAI_KEY, openaiKey); else localStorage.removeItem(JSONX_OPENAI_KEY);
    return provider;
  }

  function persistStandardProviderFromControls(overrides = {}) {
    const extended = extendedProviderSettingsFromControls();
    extended.grok.api_key = grokKeyDirty
      ? extended.grok.api_key
      : loadDedicatedApiKey(GROK_KEY_STORAGE_KEY, extended.grok.api_key);
    extended.deepseek.api_key = deepseekKeyDirty
      ? extended.deepseek.api_key
      : loadDedicatedApiKey(DEEPSEEK_KEY_STORAGE_KEY, extended.deepseek.api_key);
    if (grokKeyDirty) storeDedicatedApiKey(GROK_KEY_STORAGE_KEY, extended.grok.api_key);
    if (deepseekKeyDirty) storeDedicatedApiKey(DEEPSEEK_KEY_STORAGE_KEY, extended.deepseek.api_key);
    grokKeyDirty = false;
    deepseekKeyDirty = false;
    state.backend = overrides.backend || state.backend || "gemini";
    state.grok = extended.grok;
    state.deepseek = extended.deepseek;
    state.lm_studio = extended.lm_studio;
    state.unsloth = extended.unsloth;
    const saved = {
      backend: state.backend,
      gemini_model: geminiModelSelect.value || state.gemini_model || "",
      gemini_timeout: Number(timeoutInput.value || 120),
      safety_harassment: geminiSafetySelects.safety_harassment.value,
      safety_hate_speech: geminiSafetySelects.safety_hate_speech.value,
      safety_sexual: geminiSafetySelects.safety_sexual.value,
      safety_dangerous: geminiSafetySelects.safety_dangerous.value,
      openai_base_url: openaiBaseUrlInput.value.trim() || DEFAULT_OPENAI_BASE_URL,
      openai_model: openaiModelSelect.value || openaiModelInput.value.trim(),
      openai_timeout: Number(openaiTimeoutInput.value || 120),
      openai_lifecycle: openaiLifecycleSelect.value,
      openai_reasoning_effort: openaiReasoningSelect.value,
      ollama_host: hostInput.value.trim() || DEFAULT_OLLAMA_HOST,
      ollama_model: ollamaModelSelect.value || "",
      ollama_timeout: Number(ollamaTimeoutInput.value || 120),
      ollama_think: thinkInput.checked,
      ollama_options: Object.fromEntries(Object.entries(ollamaOptionInputs).map(([key, input]) => [key, optionalNumber(input.value, input.dataset.integer === "1")])),
      unload_after: unloadInput.checked,
      local_model: localModelSelect.value || "",
      local_timeout: Number(localTimeoutInput.value || 180),
      ...extended,
      grok: withoutApiKey(extended.grok),
      deepseek: withoutApiKey(extended.deepseek),
      thinking_level: thinkingLevelSelect.value,
      thinking_budget: Number(thinkingBudgetInput.value || 2048),
    };
    saveProviderSettings("standard", saved);
    return {
      ...saved,
      grok: extended.grok,
      deepseek: extended.deepseek,
    };
  }

  function connectedImages() {
    return Array.isArray(state.connected_images_b64)
      ? state.connected_images_b64.filter(Boolean)
      : (state.connected_image_b64 ? [state.connected_image_b64] : []);
  }

  function effectiveGenerationImages(generationType = state.generation_type, sourceImages = connectedImages()) {
    const connected = Array.isArray(sourceImages) ? sourceImages.filter(Boolean) : [];
    const rule = GENERATION_TYPE_MAP.get(generationType);
    const submitted = connected;
    return {
      connected,
      submitted,
      ignoredCount: 0,
      imageState: rule?.supportsImages
        ? (submitted.length ? "supported_with_image" : "supported_without_image")
        : (submitted.length ? "unsupported_with_image_guidance" : null),
      rule,
    };
  }

  function ignoredImageNotice(resolution) {
    if (!resolution?.ignoredCount) return "";
    const label = resolution.rule?.label || state.generation_type;
    return `${resolution.ignoredCount} connected image${resolution.ignoredCount === 1 ? "" : "s"} ignored for ${label}.`;
  }

  function validateSelectedGeneration(resolution = effectiveGenerationImages()) {
    const path = activeProfile()?.generation_paths?.[state.generation_type];
    if (!path) throw new Error("Select a supported generation type for the active profile.");
    const rule = resolution.rule || GENERATION_TYPE_MAP.get(state.generation_type);
    if (!rule) throw new Error(`Unknown generation type: ${state.generation_type}.`);
    const count = resolution.submitted.length;
    if (count > MAX_AUTHORING_IMAGES) {
      throw new Error(`Unified PrompterX accepts at most ${MAX_AUTHORING_IMAGES} authoring images; received ${count}.`);
    }
  }

  function activeProviderPayload(jsonx, images = effectiveGenerationImages().submitted) {
    const provider = jsonx ? persistJsonXProviderFromControls() : persistStandardProviderFromControls();
    const backend = provider.backend || state.backend;
    const payload = { backend };
    if (backend === "gemini") {
      payload.api_key = keyInput.value.trim();
      payload.model = geminiModelSelect.value;
      payload.timeout = Number(timeoutInput.value || 120);
      payload.gemini_safety = Object.fromEntries(GEMINI_SAFETY_FIELDS.map(([key]) => [key, geminiSafetySelects[key].value || "BLOCK_NONE"]));
      if (!payload.api_key || !payload.model) throw new Error("Set a Gemini API key and model first.");
    } else if (backend === "grok") {
      const settings = provider.grok || state.grok || extendedProviderSettingsFromControls().grok;
      payload.api_key = settings.api_key || "";
      payload.model = settings.model || settings.manual_model || "";
      payload.timeout = Number(settings.timeout || 120);
      payload.grok_max_output_tokens = settings.max_output_tokens;
      payload.grok_temperature = settings.temperature;
      payload.grok_top_p = settings.top_p;
      payload.grok_reasoning_effort = settings.reasoning_effort || "default";
      payload.grok_prompt_cache = settings.prompt_cache || "auto";
      payload.model_capabilities = grokModelsById.get(payload.model) || {};
      if (!payload.api_key || !payload.model) throw new Error("Set an xAI API key and Grok language model first.");
      if (images.length && payload.model_capabilities.vision === false) throw new Error("The selected Grok model does not accept image input.");
    } else if (backend === "deepseek") {
      const settings = provider.deepseek || state.deepseek || extendedProviderSettingsFromControls().deepseek;
      payload.api_key = settings.api_key || "";
      payload.model = settings.model || settings.manual_model || "";
      payload.timeout = Number(settings.timeout || 120);
      payload.deepseek_max_tokens = settings.max_tokens;
      payload.deepseek_thinking = settings.thinking || "default";
      payload.deepseek_reasoning_effort = settings.reasoning_effort || "default";
      payload.deepseek_temperature = settings.temperature;
      payload.deepseek_top_p = settings.top_p;
      payload.deepseek_image_detail = settings.image_detail || "default";
      payload.model_capabilities = deepseekModelsById.get(payload.model) || {
        vision: deepseekModelSupportsVision(payload.model),
      };
      if (!payload.api_key || !payload.model) throw new Error("Set a DeepSeek API key and model first.");
      if (images.length && payload.model_capabilities.vision !== true) {
        throw new Error(`The selected DeepSeek model '${payload.model}' does not accept image input.`);
      }
    } else if (["openai", "lm_studio", "unsloth"].includes(backend)) {
      if (backend === "openai") {
        payload.base_url = openaiBaseUrlInput.value.trim() || DEFAULT_OPENAI_BASE_URL;
        payload.api_key = openaiKeyInput.value.trim();
        payload.model = openaiModelSelect.value || openaiModelInput.value.trim();
        payload.timeout = Number(openaiTimeoutInput.value || 120);
        payload.openai_lifecycle = openaiLifecycleSelect.value;
        payload.openai_reasoning_effort = openaiReasoningSelect.value || "default";
      } else {
        const controls = backend === "lm_studio" ? lmStudio : unsloth;
        const settings = provider[backend] || extendedProviderSettingsFromControls()[backend];
        payload.base_url = settings.base_url;
        payload.api_key = settings.api_key || "";
        payload.model = settings.model || settings.manual_model || "";
        payload.timeout = Number(settings.timeout || 120);
        payload.openai_lifecycle = settings.lifecycle || "server_managed";
        payload.openai_reasoning_effort = settings.thinking_mode === "off"
          ? "none"
          : settings.thinking_mode === "on" && (settings.reasoning_effort || "default") === "default"
            ? "on"
            : settings.reasoning_effort || "default";
        payload.model_capabilities = controls.modelsById.get(payload.model) || {};
        if (images.length && payload.model_capabilities.vision === false) {
          throw new Error(`The selected ${backend === "lm_studio" ? "LM Studio" : "Unsloth Studio"} model does not accept image input.`);
        }
        payload.provider_options = backend === "lm_studio" ? {
          max_output_tokens: settings.max_tokens,
          context_length: settings.context_length,
          temperature: settings.temperature,
          top_p: settings.top_p,
          top_k: settings.top_k,
          min_p: settings.min_p,
          repeat_penalty: settings.repeat_penalty,
        } : {
          max_new_tokens: settings.max_tokens,
          temperature: settings.temperature,
          top_p: settings.top_p,
          top_k: settings.top_k,
          min_p: settings.min_p,
          repetition_penalty: settings.repeat_penalty,
          presence_penalty: settings.presence_penalty,
          preserve_thinking: controls.preserveThinkingSupported ? settings.preserve_thinking : undefined,
        };
      }
      if (!payload.model) throw new Error(`Set a ${PROVIDERS.find(([key]) => key === backend)?.[1] || backend} model first.`);
    } else if (backend === "ollama") {
      payload.host = hostInput.value.trim() || DEFAULT_OLLAMA_HOST;
      payload.model = ollamaModelSelect.value;
      payload.timeout = Number(ollamaTimeoutInput.value || 120);
      payload.think = thinkInput.checked;
      payload.unload_after = unloadInput.checked;
      payload.ollama_options = Object.fromEntries(Object.entries(ollamaOptionInputs).map(([key, input]) => [key, optionalNumber(input.value, input.dataset.integer === "1")]));
      if (!payload.model) throw new Error("Fetch and select an Ollama model first.");
    } else if (backend === "local") {
      payload.model = localModelSelect.value;
      payload.timeout = Number(localTimeoutInput.value || 180);
      payload.mmproj = mmprojSelect.value || "none";
      payload.additional_model_paths = additionalLocalModelPaths(localAdditionalPathsInput.value);
      payload.local_options = {
        max_tokens: Number(maxTokensInput.value || 768), temperature: Number(tempInput.value || 0.7),
        top_p: Number(topPInput.value || 0.9), top_k: Number(topKInput.value || 40),
        repeat_penalty: Number(repeatPenaltyInput.value || 1.05), ctx_size: Number(ctxInput.value || 8192),
        memory_mode: memorySelect.value, n_gpu_layers: Number(gpuLayersInput.value || 99),
        n_cpu_moe_layers: Number(cpuMoeLayersInput.value || 0), reasoning: reasoningSelect.value,
        reasoning_budget: thinkingBudget(),
        speculative_mode: speculativeSelect.value, mtp_draft_tokens: Number(mtpDraftTokensInput.value || 2),
        seed: Number(seedInput.value ?? -1), timeout: Number(localTimeoutInput.value || 180),
      };
      if (!payload.model) throw new Error("Refresh and select a local GGUF model first.");
      if (images.length && (!payload.mmproj || payload.mmproj === "none")) {
        throw new Error("Connected authoring images require a compatible vision mmproj for the selected local GGUF model.");
      }
    }
    return payload;
  }


  async function refreshGeneralPresets() {
    refreshPresetsBtn.disabled = true;
    const selected = generalPresetSelect.value || state.general_preset || "none";
    try {
      const data = await fetchJsonChecked(`${ROUTE}/general/presets`, {}, "Fetch presets");
      const names = ["none", ...(data.presets || [])];
      if (!names.includes(selected)) names.push(selected);
      setSelectOptions(generalPresetSelect, names, state.general_preset || selected, (value) => value === "none" ? "None" : value);
    } catch (error) { setStatus(error.message, true); }
    finally { refreshPresetsBtn.disabled = false; scheduleVisibleContentResize(); }
  }

  function generalRequest() {
    if (profileLoadError || backendSchemaVersion !== FRONTEND_SCHEMA_VERSION) throw new Error(profileLoadError || "Restart ComfyUI and hard-refresh the browser.");
    const auditOnly = state.audit_mode === "audit_only";
    const images = auditOnly ? [] : connectedImages();
    if (images.length > MAX_AUTHORING_IMAGES) throw new Error("General accepts at most nine connected images.");
    const connected = !auditOnly && state.enable_text_input && state.connected_raw_prompt_text_available ? String(state.connected_raw_prompt_text || "") : "";
    if (state.enable_text_input && !connected.trim()) setStatus("Connected text is unavailable; using Prompt instructions.");
    if (auditOnly && !state.prompt_text.trim()) throw new Error("Enter Prompt instructions before using Audit only.");
    if (!auditOnly && !connected.trim() && !state.prompt_text.trim() && !images.length) throw new Error("Enter a prompt or connect an image.");
    return {
      ...activeProviderPayload(false, images), schema_version: FRONTEND_SCHEMA_VERSION,
      general_schema_version: GENERAL_SCHEMA_VERSION, target_model: "general",
      preset: state.general_preset || "none", images_b64: images,
      fields: { prompt_text: state.prompt_text, raw_prompt_text: connected },
      refresh_vram: Boolean(state.refresh_vram),
      audit_mode: state.audit_mode || "none",
    };
  }

  async function previewGeneral() {
    readFieldsIntoState();
    generalPreviewBtn.disabled = true;
    try {
      const payload = generalRequest();
      const data = await fetchJsonChecked(`${ROUTE}/general/preview`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)}, "Preview General");
      const backdrop = buildDom("div", "workflowx-uap-modal-backdrop");
      const modal = buildDom("div", "workflowx-uap-modal");
      const head = buildDom("div", "workflowx-uap-modal-head");
      head.appendChild(buildDom("strong", "", "General — exact payload preview"));
      const close = buildDom("button", "workflowx-uap-btn", "Close");
      close.onclick = () => backdrop.remove();
      head.appendChild(close);
      modal.appendChild(head);
      const content = buildDom("div", "workflowx-uap-settings-page");
      for (const [label, text] of [["System instructions (empty when no preset)",data.system_prompt],["User text",data.user_prompt]]) {
        const area = createTextarea(10); area.value = text; area.readOnly = true; field(content,label,area);
      }
      for (const src of data.images_b64 || []) {
        const image = document.createElement("img"); image.src = src.startsWith("data:") ? src : `data:image/png;base64,${src}`; image.style.maxWidth = "180px"; content.appendChild(image);
      }
      const parameters = Object.fromEntries(Object.entries(payload).filter(([key]) => ["backend","model","timeout","local_options","provider_options","think"].includes(key) || /^(grok|deepseek)_/.test(key)));
      const local = createTextarea(8); local.readOnly = true; local.value = JSON.stringify({...data.local_routing,parameters},null,2); field(content,"Local routing only",local);
      modal.appendChild(content); backdrop.appendChild(modal); document.body.appendChild(backdrop); stopGraphEvents(modal);
    } catch (error) { setStatus(error.message, true); }
    finally { generalPreviewBtn.disabled = false; }
  }

  function logGenerationFailure(error) {
    const text = String(error?.message || "").toLowerCase();
    if (text.includes("cancelled") || text.includes("canceled")) return;
    const reason = /content|safety|moderation|policy/.test(text) ? "The provider rejected the request under its content or safety rules."
      : /billing|credit|spending limit/.test(text) ? "Check account credits and spending limits."
      : /\b401\b|authentication failed|invalid api key/.test(text) ? "Check the API key and server access."
      : /\b403\b|denied access|permission/.test(text) ? "The provider denied access; check model/team permissions."
      : /memory|allocation/.test(text) ? "Reduce context/output tokens or increase CPU offloading."
      : /context|too many tokens/.test(text) ? "The model context may be exceeded; review input and context settings."
      : /vision|mmproj|image input/.test(text) ? "Select an image-capable model and compatible mmproj where required."
      : /timeout|timed out/.test(text) ? "Check the server or increase Timeout."
      : /connection|unreachable/.test(text) ? "Check the server address and that it is running."
      : /model.*(unavailable|not found)|404/.test(text) ? "Refresh the model list and select an available model."
      : "Check model and provider settings, then try again.";
    console.warn(`[Unified PrompterX] Generation failed. ${reason} Previous output kept.`);
  }

  async function generateGeneral() {
    let payload;
    try { payload = generalRequest(); } catch (error) { setStatus(error.message,true); logGenerationFailure(error); return; }
    activeGenerationId = `uap-general-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    payload.generation_id = activeGenerationId;
    setBusy(true); setStatus("Generating...");
    try {
      const data = await fetchJsonChecked(`${ROUTE}/general/generate`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}, "Generate General");
      state.generated_positive = data.positive; state.generated_negative = ""; state.final_prompt = data.prompt;
      state.last_generation = {positive:data.positive,negative:"",prompt:data.prompt,target_model:"general",prompt_format:"natural",negative_enabled:false,generated_at:new Date().toISOString(),audit:data.audit||null};
      syncPreview();
      const audit = data.audit || {};
      if (audit.status === "failed") setStatus(`Audit failed; ${state.audit_mode === "audit_only" ? "textbox prompt" : "generated prompt"} retained: ${audit.error}`, true);
      else if (audit.status === "completed") setStatus(audit.changed
        ? (state.audit_mode === "audit_only" ? "Prompt audited and refined." : "Prompt generated and refined by audit.")
        : (state.audit_mode === "audit_only" ? "Audit complete; no changes needed." : "Prompt generated; audit found no changes needed."));
      else setStatus("Generation complete.");
    } catch (error) { logGenerationFailure(error); setStatus(error.message,true); }
    finally { activeGenerationId = ""; setBusy(false); }
  }

  async function generateJsonXPrompt() {
    const jsonx = effectiveJsonXConfig();
    const rawPromptText = state.enable_text_input && state.connected_raw_prompt_text_available
      ? String(state.connected_raw_prompt_text || "").trim()
      : "";
    const textInputLinked = inputIsLinked(node, "raw_prompt_text");
    const textInputWarning = state.enable_text_input && (!textInputLinked || !rawPromptText)
      ? "Connected raw_prompt_text is enabled but missing or unreadable; using Prompt instructions."
      : "";
    const imageResolution = effectiveGenerationImages();
    const images = imageResolution.submitted;
    const ignoredNotice = ignoredImageNotice(imageResolution);
    if (!rawPromptText && !String(state.prompt_text || "").trim() && !images.length) {
      setStatus(textInputWarning || `${ignoredNotice ? `${ignoredNotice} ` : ""}Enter Prompt instructions or select an image-assisted generation type.`, true);
      return;
    }
    if (profileLoadError || backendSchemaVersion !== FRONTEND_SCHEMA_VERSION || backendJsonXReferenceSchemaVersion !== JSONX_REFERENCE_SCHEMA_VERSION) {
      setStatus(profileLoadError || "Unified schema mismatch. Restart ComfyUI and hard-refresh the browser.", true);
      return;
    }
    try { validateSelectedGeneration(imageResolution); } catch (error) { setStatus(error.message, true); return; }
    let providerPayload;
    try { providerPayload = activeProviderPayload(true, images); } catch (error) { setStatus(error.message, true); return; }
    activeGenerationId=`uap-jsonx-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const fields={prompt_text:state.prompt_text,detail:state.detail,raw_prompt_text:rawPromptText};
    const generationMode=state.prompt_format==="natural"?"refined":(jsonx.generation_mode||"fast");
    const payload={...jsonx,...providerPayload,schema_version:FRONTEND_SCHEMA_VERSION,jsonx_reference_schema_version:JSONX_REFERENCE_SCHEMA_VERSION,target_model:state.target_model,generation_type:state.generation_type,nsfw_enabled:Boolean(state.nsfw_enabled),generation_id:activeGenerationId,fields,image_b64:images[0]||"",images_b64:images,output_format:state.prompt_format,generation_mode:generationMode,refresh_vram:Boolean(state.refresh_vram)};
    setBusy(true);setStatus([textInputWarning, ignoredNotice, "Generating Unified JsonX..."].filter(Boolean).join(" "), Boolean(textInputWarning));
try{const response=await fetch(`${JSONX_ROUTE}/generate`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok||data.error)throw Object.assign(new Error(data.error||`HTTP ${response.status}`),{data});state.generated_positive=data.positive||data.prompt||"";state.generated_negative=data.negative||"";state.final_prompt=data.prompt||"";state.negative_enabled=Boolean(state.generated_negative);state.jsonx={diagnostics:data.diagnostics||null};state.last_generation={prompt:state.final_prompt,positive:state.generated_positive,negative:state.generated_negative,target_model:state.target_model,prompt_format:state.prompt_format,negative_enabled:state.negative_enabled,generated_at:new Date().toISOString()};syncPreview();setStatus(`${ignoredNotice ? `${ignoredNotice} ` : ""}Unified JsonX generated · ${data.output_format||state.prompt_format} · ${data.generation_profile||"adaptive"}${data.natural_fallback?" · used canonical JsonX prose fallback.":"."}`);}catch(error){logGenerationFailure(error);const diagnostics=error.data?.diagnostics||{error:error.message};state.jsonx={diagnostics};syncPreview();const reasons=[diagnostics.initial_error&&`Initial: ${diagnostics.initial_error}`,diagnostics.repair_error&&`Repair: ${diagnostics.repair_error}`].filter(Boolean).join(" · ");setStatus(`Error: ${String(error.message).replace(/(?:[.\s]*Previous output kept\.)+$/i, "").replace(/\.$/, "")}${reasons?` ${reasons}`:""}. Previous output kept.`,true);}finally{activeGenerationId="";setBusy(false);}
  }

  async function generatePrompt() {
    if (state.target_model === "general") { readFieldsIntoState(); return generateGeneral(); }
    if (isJsonXProfile()) { readFieldsIntoState(); return generateJsonXPrompt(); }
    readFieldsIntoState();
    const auditOnly = state.audit_mode === "audit_only";
    const rawPromptText = state.enable_text_input && state.connected_raw_prompt_text_available
      ? String(state.connected_raw_prompt_text || "").trim()
      : "";
    const textInputLinked = inputIsLinked(node, "raw_prompt_text");
    const textInputWarning = !auditOnly && state.enable_text_input && (!textInputLinked || !state.connected_raw_prompt_text_available || !rawPromptText)
      ? "Connected raw_prompt_text is enabled but missing or unreadable; using Prompt instructions."
      : "";
    const imageResolution = auditOnly ? { connected: [], submitted: [], ignoredCount: 0, imageState: null, rule: GENERATION_TYPE_MAP.get(state.generation_type) } : effectiveGenerationImages();
    const images = imageResolution.submitted;
    const ignoredNotice = ignoredImageNotice(imageResolution);
    const linkedImageCount = linkedReferenceImageInputNames(node).length;
    const hasTextSeed = Boolean((auditOnly ? "" : rawPromptText) || String(state.prompt_text || "").trim());
    const hasConnectedImage = images.length > 0;
    const hasUnresolvedConnectedImage = Boolean(
      linkedImageCount > imageResolution.connected.length
    );
    if (!hasTextSeed && !hasConnectedImage) {
      setStatus(
        textInputWarning
          ? `${textInputWarning} Enter Prompt instructions or connect a readable raw_prompt_text input.`
          : ignoredNotice
          ? `${ignoredNotice} Enter Prompt instructions or select an image-assisted generation type.`
          : hasUnresolvedConnectedImage
          ? "Connected image has no preview yet. Run or refresh the upstream image node first."
          : "Enter Prompt instructions or connect an image.",
        true,
      );
      return;
    }

    if (profileLoadError || backendSchemaVersion !== FRONTEND_SCHEMA_VERSION || backendReferenceSchemaVersion !== REFERENCE_SCHEMA_VERSION) {
      setStatus(profileLoadError || "Unified schema mismatch. Restart ComfyUI and hard-refresh the browser.", true);
      return;
    }
    if (!auditOnly) {
      try { validateSelectedGeneration(imageResolution); } catch (error) { setStatus(error.message, true); return; }
    }
    let providerPayload;
    try { providerPayload = activeProviderPayload(false, images); } catch (error) { setStatus(error.message, true); return; }
    activeGenerationId = `uap-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    const payload = {
      ...providerPayload,
      schema_version: FRONTEND_SCHEMA_VERSION,
      reference_schema_version: REFERENCE_SCHEMA_VERSION,
      generation_id: activeGenerationId,
      target_model: state.target_model,
      prompt_format: state.prompt_format,
      generation_type: state.generation_type,
      nsfw_enabled: Boolean(state.nsfw_enabled),
      negative_enabled: state.negative_enabled,
      audit_mode: state.audit_mode || "none",
      refresh_vram: state.refresh_vram,
      image_b64: images[0] || "",
      images_b64: images,
      fields: {
        prompt_text: state.prompt_text,
        detail: state.detail,
        raw_prompt_text: rawPromptText,
        bbox_layout: isBboxLayoutTarget(state.target_model) ? state.ideogram_layout : "",
        ideogram_layout: isBboxLayoutTarget(state.target_model) ? state.ideogram_layout : "",
        ideogram_palette: isBboxLayoutTarget(state.target_model) ? state.ideogram_palette : "",
      },
    };

    persistModelSelection();
    setBusy(true);
    setStatus([textInputWarning, ignoredNotice, "Generating..."].filter(Boolean).join(" "), Boolean(textInputWarning));
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
        audit: data.audit || null,
      };
      syncPreview();
      const audit = data.audit || {};
      if (audit.status === "failed") {
        setStatus(`${ignoredNotice ? `${ignoredNotice} ` : ""}Audit failed; ${state.audit_mode === "audit_only" ? "textbox prompt" : "generated prompt"} retained: ${audit.error}`, true);
      } else if (audit.status === "completed") {
        setStatus(`${ignoredNotice ? `${ignoredNotice} ` : ""}${audit.changed
          ? (state.audit_mode === "audit_only" ? "Prompt audited and refined." : "Prompt generated and refined by audit.")
          : (state.audit_mode === "audit_only" ? "Audit complete; no changes needed." : "Prompt generated; audit found no changes needed.")}`);
      } else {
        setStatus(`${ignoredNotice ? `${ignoredNotice} ` : ""}Prompt generated.`);
      }
    } catch (error) {
      syncPreview();
      logGenerationFailure(error);
      setStatus(`Error: ${String(error.message).replace(/(?:[.\s]*Previous output kept\.)+$/i, "").replace(/\.$/, "")}. Previous output kept.`, true);
    } finally {
      activeGenerationId = "";
      setBusy(false);
    }
  }

  node.__workflowXUapGenerateOnQueue = async () => {
    if (state.working_mode !== "on_queue") return false;
    if (activeGenerationId) throw new Error("Unified Prompter generation is already in progress; wait before queueing.");
    const previousGeneration = state.last_generation;
    setStatus("Workflow queued · generating prompt before submission...");
    await generatePrompt();
    if (state.last_generation === previousGeneration) {
      throw new Error(status.textContent || "Unified Prompter could not generate a prompt for this queue.");
    }
    return true;
  };
  unifiedQueueNodes.add(node);

  const stateInputs = [
    targetSelect,
    formatSelect,
    generationTypeSelect,
    providerSelect,
    promptArea,
    detailSelect,
    auditSelect,
    workingModeSelect,
    ideogramLayoutArea,
    ideogramPaletteInput,
    bboxJsonInput,
    rawTextInput,
    timeoutInput,
    ...Object.values(geminiSafetySelects),
    openaiBaseUrlInput,
    openaiModelInput,
    openaiTimeoutInput,
    openaiServerTypeSelect,
    openaiLifecycleSelect,
    openaiReasoningSelect,
    hostInput,
    ollamaTimeoutInput,
    thinkInput,
    unloadInput,
    ...Object.values(ollamaOptionInputs),
    localModelSelect,
    mmprojSelect,
    systemPresetSelect,
    localAdditionalPathsInput,
    localTimeoutInput,
    maxTokensInput,
    tempInput,
    topPInput,
    topKInput,
    repeatPenaltyInput,
    ctxInput,
    memorySelect,
    reasoningSelect,
    thinkingLevelSelect,
    thinkingBudgetInput,
    generalPresetSelect,
    speculativeSelect,
    mtpDraftTokensInput,
    gpuLayersInput,
    cpuMoeLayersInput,
    seedInput,
    negativeInput,
    refreshVramInput,
    disablePaletteInput,
    nsfwInput,
  grokKeyInput, grokModelSelect, grokModelInput, grokTimeoutInput, grokMaxTokensInput,
    grokTemperatureInput, grokTopPInput, grokReasoningSelect, grokCacheSelect,
    deepseekKeyInput, deepseekModelSelect, deepseekModelInput, deepseekTimeoutInput,
    deepseekMaxTokensInput, deepseekThinkingSelect, deepseekReasoningSelect,
    deepseekTemperatureInput, deepseekTopPInput, deepseekImageDetailSelect,
    ...[lmStudio, unsloth].flatMap((item) => [
      item.baseUrl, item.key, item.model, item.manualModel, item.timeout, item.lifecycle,
      item.maxTokens, item.context, item.temperature, item.topP, item.topK, item.minP,
      item.repeatPenalty, item.presencePenalty, item.reasoning, item.thinkingMode, item.preserveThinking,
    ]),
  ];
  for (const input of stateInputs) {
    input.addEventListener("input", syncPreview);
    input.addEventListener("change", syncPreview);
  }

  function restoreWorkflowStateFromWidgets() {
    const runtimeState = {
      connected_image_b64: state.connected_image_b64,
      connected_images_b64: state.connected_images_b64,
      connected_image_url: state.connected_image_url,
      connected_image_urls: state.connected_image_urls,
      connected_image_available: state.connected_image_available,
      connected_image_count: state.connected_image_count,
      connected_bbox_json: state.connected_bbox_json,
      connected_bbox_json_available: state.connected_bbox_json_available,
      connected_raw_prompt_text: state.connected_raw_prompt_text,
      connected_raw_prompt_text_available: state.connected_raw_prompt_text_available,
    };
    Object.assign(state, defaultState(node), runtimeState);
    ensureSelectValue(generalPresetSelect, state.general_preset || "none");
    state.gemini_key = loadStoredGeminiKey();
    state.openai_key = loadStoredOpenAIKey();

    promptArea.value = state.prompt_text;
    detailSelect.value = state.detail;
    auditSelect.value = state.audit_mode || "none";
    refreshAuditHelp();
    workingModeSelect.value = state.working_mode || "on_generate";
    refreshWorkingModeHelp();
    nsfwInput.checked = Boolean(state.nsfw_enabled);
    negativeInput.checked = Boolean(state.negative_enabled);
    bboxJsonInput.checked = Boolean(state.enable_bbox_json_input);
    rawTextInput.checked = Boolean(state.enable_text_input);
    refreshVramInput.checked = Boolean(state.refresh_vram);
    disablePaletteInput.checked = Boolean(state.disable_color_palette);
    ideogramLayoutArea.value = state.ideogram_layout;
    ideogramPaletteInput.value = state.ideogram_palette;
    modelSettingsDetails.open = Boolean(state.model_settings_open);

    refreshProfiles();
    syncPreview();
    requestAnimationFrame(resizeNodeToVisibleContent);
  }
  node.__workflowXUapRestoreState = restoreWorkflowStateFromWidgets;

  targetSelect.addEventListener("change", () => {
    state.target_model = targetSelect.value;
    state.final_prompt = "";
    refreshFormats();
  });
  formatSelect.addEventListener("change", () => {
    state.prompt_format = formatSelect.value;
    state.final_prompt = "";
    refreshFormats();
  });
  generationTypeSelect.addEventListener("change", () => {
    state.generation_type = generationTypeSelect.value;
    syncPreview();
  });
  auditSelect.addEventListener("change", () => {
    state.audit_mode = auditSelect.value || "none";
    refreshAuditHelp();
    generateBtn.textContent = state.audit_mode === "audit_only" ? "Audit prompt" : "Generate";
    syncPreview();
    scheduleVisibleContentResize();
  });
  workingModeSelect.addEventListener("change", () => {
    state.working_mode = workingModeSelect.value || "on_generate";
    refreshWorkingModeHelp();
    syncPreview();
  });
  nsfwInput.addEventListener("change", () => {
    state.nsfw_enabled = nsfwInput.checked;
    syncPreview();
  });
  negativeInput.addEventListener("change", () => {
    state.negative_enabled = negativeInput.checked;
    state.final_prompt = "";
    syncPreview();
  });
  refreshVramInput.addEventListener("change", () => {
    state.refresh_vram = refreshVramInput.checked;
    syncPreview();
  });
  disablePaletteInput.addEventListener("change", () => {
    state.disable_color_palette = disablePaletteInput.checked;
    syncPreview();
  });
  modelSettingsDetails.addEventListener("toggle", () => {
    state.model_settings_open = modelSettingsDetails.open;
    syncPreview();
    scheduleVisibleContentResize();
  });
  const selectBackend = (backend) => {
    if (isJsonXProfile()) persistJsonXProviderFromControls({ backend });
    else {
      persistStandardProviderFromControls({ backend });
      persistModelSelection();
    }
    refreshBackends();
    syncPreview();
  };
  providerSelect.addEventListener("change", () => selectBackend(providerSelect.value));
  grokModelSelect.addEventListener("change", () => {
    if (grokModelSelect.value) grokModelInput.value = "";
    syncGrokReasoningOptions();
    syncPreview();
  });
  grokModelInput.addEventListener("input", () => {
    if (grokModelInput.value.trim()) grokModelSelect.value = "";
    syncGrokReasoningOptions();
    syncPreview();
  });
  deepseekModelSelect.addEventListener("change", () => {
    if (deepseekModelSelect.value) deepseekModelInput.value = "";
    syncDeepSeekControls();
    syncPreview();
  });
  deepseekModelInput.addEventListener("input", () => {
    if (deepseekModelInput.value.trim()) deepseekModelSelect.value = "";
    syncDeepSeekControls();
    syncPreview();
  });
  deepseekThinkingSelect.addEventListener("change", () => {
    syncDeepSeekControls();
    syncPreview();
  });
  keyInput.addEventListener("input", () => {
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else {
      state.gemini_key = keyInput.value;
      storeGeminiKey(state.gemini_key);
    }
  });
  openaiKeyInput.addEventListener("input", () => {
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else {
      state.openai_key = openaiKeyInput.value;
      storeOpenAIKey(state.openai_key);
    }
  });
  openaiBaseUrlInput.addEventListener("input", () => {
    openaiDetectedServerType = "auto";
    openaiModelsById = new Map();
    openaiReasoningCapabilities = {};
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else {
      state.openai_base_url = openaiBaseUrlInput.value.trim() || DEFAULT_OPENAI_BASE_URL;
      storeOpenAIBaseUrl(state.openai_base_url);
    }
  });
  geminiModelSelect.addEventListener("change", () => {
    if (!isJsonXProfile()) state.gemini_model = geminiModelSelect.value;
    persistModelSelection();
    syncPreview();
  });
  openaiModelSelect.addEventListener("change", () => {
    if (openaiModelSelect.value) openaiModelInput.value = "";
    syncOpenAIReasoningOptions();
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else state.openai_model = openaiModelSelect.value;
    persistModelSelection();
    syncPreview();
  });
  openaiModelInput.addEventListener("input", () => {
    if (openaiModelInput.value.trim()) openaiModelSelect.value = "";
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else state.openai_model = openaiModelInput.value.trim();
    persistModelSelection();
    syncPreview();
  });
  openaiServerTypeSelect.addEventListener("change", () => {
    openaiDetectedServerType = normalizeOpenAIServerType(openaiServerTypeSelect.value);
    openaiModelsById = new Map();
    openaiReasoningCapabilities = {};
    syncOpenAIReasoningOptions();
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else state.openai_server_type = normalizeOpenAIServerType(openaiServerTypeSelect.value);
    syncPreview();
  });
  openaiLifecycleSelect.addEventListener("change", () => {
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else state.openai_lifecycle = normalizeOpenAILifecycle(openaiLifecycleSelect.value);
    syncPreview();
  });
  openaiReasoningSelect.addEventListener("change", () => {
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else state.openai_reasoning_effort = normalizeOpenAIReasoning(openaiReasoningSelect.value);
    syncPreview();
  });
  ollamaModelSelect.addEventListener("change", () => {
    if (!isJsonXProfile()) state.ollama_model = ollamaModelSelect.value;
    persistModelSelection();
    syncPreview();
  });
  localModelSelect.addEventListener("change", () => {
    if (!isJsonXProfile()) state.local_model = localModelSelect.value || "";
    persistModelSelection();
    syncPreview();
  });
  localAdditionalPathsInput.addEventListener("change", () => {
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else storeAdditionalLocalModelPaths(localAdditionalPathsInput.value);
  });
  unloadInput.addEventListener("change", () => {
    if (isJsonXProfile()) persistJsonXProviderFromControls();
    else state.unload_after = unloadInput.checked;
    syncPreview();
  });
  memorySelect.addEventListener("change", syncMemoryControls);
  fetchGeminiBtn.addEventListener("click", fetchGeminiModels);
  fetchOpenaiBtn.addEventListener("click", fetchOpenaiModels);
  fetchGrokBtn.addEventListener("click", fetchGrokModels);
  fetchDeepSeekBtn.addEventListener("click", fetchDeepSeekModels);
  lmStudio.fetch.addEventListener("click", () => fetchStudioModels("lm_studio", lmStudio));
  unsloth.fetch.addEventListener("click", () => fetchStudioModels("unsloth", unsloth));
  fetchOllamaBtn.addEventListener("click", fetchOllamaModels);
  fetchLocalBtn.addEventListener("click", fetchLocalModels);
  positivePreviewBtn.addEventListener("click", () => toggleOutputPreview("positive"));
  negativePreviewBtn.addEventListener("click", () => toggleOutputPreview("negative"));
  ideogramBtn.addEventListener("click", toggleIdeogramLayoutEditor);
  modelSettingsBtn.addEventListener("click", openMarkdownProfileSettings);
  presetsBtn.addEventListener("click", openPromptPresets);
  generalPreviewBtn.addEventListener("click", previewGeneral);
  refreshPresetsBtn.addEventListener("click", refreshGeneralPresets);
  thinkingLevelSelect.addEventListener("change", scheduleVisibleContentResize);
  cancelJsonXBtn.addEventListener("click", async () => {
    if (!activeGenerationId) return;
    cancelJsonXBtn.disabled = true;
    cancelJsonXBtn.textContent = "Cancelling...";
    try {
      await fetch(`${isJsonXProfile() ? JSONX_ROUTE : ROUTE}/cancel`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ generation_id: activeGenerationId }),
      });
    } finally {
      cancelJsonXBtn.textContent = "Cancel";
    }
  });
  generateBtn.addEventListener("click", generatePrompt);

  const setConnectedImageDataUrls = (dataUrls, urls = []) => {
    const clean = (Array.isArray(dataUrls) ? dataUrls : []).filter(Boolean);
    state.connected_images_b64 = clean;
    state.connected_image_b64 = clean[0] || "";
    state.connected_image_available = clean.length > 0;
    state.connected_image_count = clean.length;
    state.connected_image_urls = (Array.isArray(urls) ? urls : []).filter(Boolean);
    state.connected_image_url = state.connected_image_urls[0] || "";
    syncPreview();
  };

  const canvasToDataUrl = (canvas) => {
    try {
      return canvas.toDataURL("image/png");
    } catch (error) {
      console.warn("[WorkflowX Unified Autoprompter] Could not convert connected image to base64", error);
      return "";
    }
  };

  const imageToDataUrl = (img) => {
    try {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth || img.width || 1;
      canvas.height = img.naturalHeight || img.height || 1;
      canvas.getContext("2d")?.drawImage(img, 0, 0);
      return canvasToDataUrl(canvas);
    } catch (error) {
      console.warn("[WorkflowX Unified Autoprompter] Could not capture connected image", error);
      return "";
    }
  };

  const setOverlayImage = (src) => {
    if (!src) {
      node.__workflowXUapOverlayImage = null;
      node.__workflowXUapOnOverlayImageLoad?.(null);
      node.__workflowXUapRenderIdeogram?.();
      return;
    }
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      node.__workflowXUapOverlayImage = img;
      node.__workflowXUapOnOverlayImageLoad?.(img);
      node.__workflowXUapRenderIdeogram?.();
    };
    img.onerror = () => {
      node.__workflowXUapOverlayImage = null;
      node.__workflowXUapOnOverlayImageLoad?.(null);
      node.__workflowXUapRenderIdeogram?.();
    };
    img.src = src;
  };

  const sourceToDataUrl = (source) => new Promise((resolve) => {
    if (!source) {
      resolve("");
    } else if (source.isVideo && source.videoEl) {
      captureVideoFrame(source.videoEl, (canvas) => resolve(canvasToDataUrl(canvas)));
    } else if (source.url && !source.isVideo) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(imageToDataUrl(img));
      img.onerror = () => resolve("");
      img.src = source.url;
    } else {
      resolve("");
    }
  });

  let referenceImageLoadToken = 0;
  const unwatchImageInput = watchReferenceImageInputs(node, async (sources) => {
    const token = ++referenceImageLoadToken;
    const linkedCount = linkedReferenceImageInputNames(node).length;
    if (!sources?.length) {
      setConnectedImageDataUrls([]);
      setOverlayImage("");
      if (linkedCount) setStatus("Connected image references have no preview yet. Run or refresh upstream image nodes first.", true);
      return;
    }
    const dataUrls = await Promise.all(sources.map(sourceToDataUrl));
    if (token !== referenceImageLoadToken) return;
    const clean = dataUrls.filter(Boolean);
    setConnectedImageDataUrls(clean, sources.map((source) => source.url || ""));
    setOverlayImage(clean[0] || sources[0]?.url || "");
    if (!clean.length && linkedCount) {
      setStatus("Connected image references could not be loaded.", true);
    } else if (clean.length < linkedCount) {
      setStatus(`${clean.length} of ${linkedCount} connected image references loaded. Unreadable refs were skipped.`, true);
    } else if (clean.length) {
      setStatus(`${clean.length} connected image reference${clean.length === 1 ? "" : "s"} loaded.`);
    }
  });
  const unwatchBBoxJsonInput = watchTextInput(node, "bbox_json", (source) => {
    state.connected_bbox_json = source?.value || "";
    state.connected_bbox_json_available = Boolean(source?.available);
    if (state.enable_bbox_json_input && source?.connected && !source.available) {
      setStatus("Connected bbox_json input could not be read; Sync will use cached output if available.", true);
    }
    syncPreview();
  });
  const unwatchRawPromptTextInput = watchTextInput(node, "raw_prompt_text", (source) => {
    state.connected_raw_prompt_text = source?.value || "";
    state.connected_raw_prompt_text_available = Boolean(source?.available);
    if (state.enable_text_input && source?.connected && !source.available) {
      setStatus("Connected raw_prompt_text input could not be read; generation will use Prompt instructions.", true);
    }
    syncPreview();
  });

  node.__workflowXUapWidgetHeight = NODE_MIN_WIDGET_HEIGHT;
  node.__workflowXUapRoot = wrap;
  node.__workflowXUapWidget = node.addDOMWidget("unified_autoprompter_x", "Unified Autoprompter X", wrap, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => node.__workflowXUapWidgetHeight || NODE_MIN_WIDGET_HEIGHT,
  });
  node.resizable = true;

  chainCallback(node, "onRemoved", () => {
    unwatchImageInput?.();
    unwatchBBoxJsonInput?.();
    unwatchRawPromptTextInput?.();
    closeDock(node, "output_positive");
    closeDock(node, "output_negative");
    closeDock(node, "ideogram");
    tagSuggestions.remove();
    node.__workflowXUapRestoreState = null;
    node.__workflowXUapGenerateOnQueue = null;
    unifiedQueueNodes.delete(node);
  });

  loadProfiles().then((loadedProfiles) => {
    profiles = loadedProfiles;
    profilesByKey = profileMap(profiles);
    profilesLoaded = true;
    refreshProfiles();
    refreshBackends();
    syncPreview();
    if (profileLoadError) setStatus(profileLoadError, true);
    else if (providerBackend() === "local") setTimeout(fetchLocalModels, 0);
    refreshPromptPresets().catch((error) => setStatus(`Presets error: ${error.message}`, true));
    requestAnimationFrame(resizeNodeToVisibleContent);
  });
}

app.registerExtension({
  name: "WorkflowX.UnifiedAutoprompterX",

  setup() {
    installQueueGenerationHooks();
  },

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== TARGET_NODE) return;

    chainCallback(nodeType.prototype, "onNodeCreated", function workflowXUnifiedCreated() {
      // Workflow nodes receive their serialized widget values during configure.
      // Deferring setup prevents the custom UI from reading and persisting defaults
      // before ComfyUI has restored the hidden ui_state widget.
      setTimeout(() => setupUnifiedAutoprompter(this), 0);
    });

    chainCallback(nodeType.prototype, "onConfigure", function workflowXUnifiedConfigured() {
      setTimeout(() => {
        if (this.__workflowXUnifiedAutoprompterReady) this.__workflowXUapRestoreState?.();
        else setupUnifiedAutoprompter(this);
      }, 0);
    });
  },
});
