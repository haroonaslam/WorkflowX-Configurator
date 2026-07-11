import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const ROUTE = "/workflowx_configurator/remote_image";
const NODES = new Map([
  ["WorkflowX_KieImageAPI", "kie"],
  ["WorkflowX_AtlasImageAPI", "atlas"],
]);
const IMAGE_RE = /^image_(\d+)$/;
const MAX_IMAGES = 14;
const MAX_LOG_LINES = 150;
let catalogsPromise;

function installStyles() {
  if (document.getElementById("workflowx-remote-image-styles")) return;
  const style = document.createElement("style");
  style.id = "workflowx-remote-image-styles";
  style.textContent = `
    .workflowx-remote-image { box-sizing:border-box; width:100%; min-width:520px; color:#d7dde5; font:13px/1.35 Inter,system-ui,sans-serif; background:#0d1115; border:1px solid #27313a; border-radius:10px; padding:12px; overflow:auto; }
    .workflowx-ri-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:10px; }
    .workflowx-ri-title { font-size:15px; font-weight:700; color:#f0f4f8; }
    .workflowx-ri-badges { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
    .workflowx-ri-badge { border:1px solid #3b4b59; border-radius:999px; padding:2px 8px; color:#b9c6d2; background:#151c22; font-size:11px; }
    .workflowx-ri-badge[data-level='success'] { color:#a9e7c3; border-color:#2d7650; }
    .workflowx-ri-badge[data-level='warning'] { color:#ffd28a; border-color:#876225; }
    .workflowx-ri-badge[data-level='error'] { color:#ffaaa7; border-color:#8e3c3a; }
    .workflowx-ri-card { border:1px solid #28333c; border-radius:9px; background:#101519; padding:10px; margin-top:9px; }
    .workflowx-ri-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:9px 12px; }
    .workflowx-ri-wide { grid-column:1/-1; }
    .workflowx-ri-field { min-width:0; display:flex; flex-direction:column; gap:4px; }
    .workflowx-ri-label { color:#aeb8c2; font-size:12px; }
    .workflowx-ri-field input,.workflowx-ri-field select,.workflowx-ri-field textarea { box-sizing:border-box; width:100%; color:#e5eaf0; background:#0b0f12; border:1px solid #35424d; border-radius:7px; padding:8px 9px; outline:none; }
    .workflowx-ri-field textarea { min-height:88px; resize:vertical; }
    .workflowx-ri-field input:focus,.workflowx-ri-field select:focus,.workflowx-ri-field textarea:focus { border-color:#65a9d5; box-shadow:0 0 0 1px #65a9d544; }
    .workflowx-ri-check { min-height:34px; flex-direction:row; align-items:center; gap:8px; padding-top:18px; }
    .workflowx-ri-check input { width:auto; accent-color:#60a8d1; }
    .workflowx-ri-actions { display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }
    .workflowx-ri-actions button { border:1px solid #405462; border-radius:7px; background:#18232b; color:#e2e9ef; padding:7px 11px; cursor:pointer; }
    .workflowx-ri-actions button.primary { background:#e9eef3; color:#111820; border-color:#e9eef3; font-weight:700; }
    .workflowx-ri-actions button.warn { border-color:#8a6328; color:#ffd495; }
    .workflowx-ri-actions button.danger { border-color:#84403d; color:#ffb0ac; }
    .workflowx-ri-actions button:disabled { opacity:.42; cursor:not-allowed; }
    .workflowx-ri-note { color:#8f9aa5; font-size:11px; margin-top:7px; }
    .workflowx-ri-log { height:132px; overflow:auto; white-space:pre-wrap; user-select:text; background:#080b0e; border:1px solid #26313a; border-radius:7px; padding:8px; color:#9fb0bd; font:11px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace; }
    .workflowx-ri-log .warning { color:#e6bd79; } .workflowx-ri-log .error { color:#ef9692; } .workflowx-ri-log .success { color:#8fd0aa; }
    @media (max-width:560px) { .workflowx-ri-grid { grid-template-columns:1fr; } .workflowx-ri-wide { grid-column:auto; } }
  `;
  document.head.appendChild(style);
}

function catalogs() {
  catalogsPromise ||= fetch(`${ROUTE}/catalogs`).then((response) => {
    if (!response.ok) throw new Error(`Catalog request failed (${response.status})`);
    return response.json();
  }).then((payload) => payload.providers || {});
  return catalogsPromise;
}

function nativeWidget(node, name) { return (node.widgets || []).find((entry) => entry.name === name) || null; }
function setNative(node, name, value) {
  const item = nativeWidget(node, name);
  if (!item) return;
  item.value = value;
  try { item.callback?.call(item, value, app.canvas, node, app.canvas?.graph_mouse); } catch {}
}
function hideNativeWidgets(node) {
  for (const item of node.widgets || []) {
    if (item.type === "converted-widget") continue;
    item.hidden = true;
    item.computeSize ||= () => [0, -4];
    item.computeSize = () => [0, -4];
  }
}

function imageNumbers(node) {
  return (node.inputs || []).map((input) => IMAGE_RE.exec(String(input.name || ""))).filter(Boolean).map((match) => Number(match[1])).sort((a, b) => a - b);
}
function inputIndex(node, name) { return (node.inputs || []).findIndex((input) => input.name === name); }
function linked(node, number) { const index = inputIndex(node, `image_${number}`); return index >= 0 && node.inputs[index].link != null; }
function referenceCount(node) { return imageNumbers(node).filter((number) => linked(node, number)).length; }
function syncImageSockets(node) {
  let numbers = imageNumbers(node);
  if (!numbers.length) { node.addInput("image_1", "IMAGE"); numbers = [1]; }
  while (numbers.length > 1) {
    const last = numbers.at(-1); const previous = numbers.at(-2);
    if (linked(node, last) || linked(node, previous)) break;
    const index = inputIndex(node, `image_${last}`); if (index >= 0) node.removeInput(index);
    numbers = imageNumbers(node);
  }
  const last = numbers.at(-1);
  if (last < MAX_IMAGES && linked(node, last)) node.addInput(`image_${last + 1}`, "IMAGE");
  if (node.__workflowxRemoteRenderProfile) node.__workflowxRemoteRenderProfile(false);
  else node.__workflowxRemoteRefreshMode?.();
  node.setDirtyCanvas?.(true, true);
}

function el(tag, className, text) {
  const item = document.createElement(tag); if (className) item.className = className; if (text != null) item.textContent = text; return item;
}
function field(label, control, wide = false) {
  const wrap = el("label", `workflowx-ri-field${wide ? " workflowx-ri-wide" : ""}`);
  wrap.append(el("span", "workflowx-ri-label", label), control); return wrap;
}
function selectControl(options, value, changed) {
  const control = el("select");
  for (const option of options) { const item = el("option", "", String(option)); item.value = String(option); control.append(item); }
  control.value = String(value ?? options[0] ?? ""); control.addEventListener("change", () => changed(control.value)); return control;
}
function inputControl(type, value, changed, attributes = {}) {
  const control = el("input"); control.type = type; control.value = value ?? "";
  for (const [key, item] of Object.entries(attributes)) if (item != null && item !== "any") control[key] = item;
  control.addEventListener("change", () => changed(type === "number" ? Number(control.value) : control.value)); return control;
}
function checkboxControl(value, changed) {
  const control = el("input"); control.type = "checkbox"; control.checked = !!value; control.addEventListener("change", () => changed(control.checked)); return control;
}

async function pendingRecord(provider, nodeId) {
  const response = await fetch(`${ROUTE}/pending/${provider}/${encodeURIComponent(nodeId)}`);
  if (!response.ok) throw new Error(`Pending lookup failed (${response.status})`); return response.json();
}
async function requestCancel(node, provider, mode) {
  const warning = mode === "continue"
    ? "Stop local work, forget retrieval tracking, and continue the graph with a black placeholder? An already-submitted provider task may still run and incur charges."
    : "Stop local work and preserve any submitted task for Force Retrieve? The current workflow execution will end.";
  if (!window.confirm(warning)) return;
  const response = await fetch(`${ROUTE}/cancel/${provider}/${encodeURIComponent(node.id)}`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ mode }) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || `HTTP ${response.status}`);
}
async function forceRetrieve(node, provider) {
  const state = await pendingRecord(provider, node.id);
  if (!state.pending) throw new Error("No pending task is stored for this node.");
  setNative(node, "retrieval_mode", "force_retrieve"); await app.queuePrompt(0, 1);
}
async function forgetPending(node, provider) {
  if (!window.confirm("Forget this local pending record? This does not cancel provider-side work or charges.")) return;
  const response = await fetch(`${ROUTE}/pending/${provider}/${encodeURIComponent(node.id)}`, { method:"DELETE" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`); setNative(node, "retrieval_mode", "generate");
}

function buildPanel(node, provider, profiles) {
  installStyles(); hideNativeWidgets(node);
  const root = el("div", "workflowx-remote-image");
  const head = el("div", "workflowx-ri-head"); head.append(el("div", "workflowx-ri-title", `${provider === "kie" ? "Kie" : "Atlas"} Image API X`));
  const badges = el("div", "workflowx-ri-badges"); const modeBadge = el("span", "workflowx-ri-badge"); const statusBadge = el("span", "workflowx-ri-badge", "Ready"); badges.append(modeBadge, statusBadge); head.append(badges); root.append(head);
  const identity = el("div", "workflowx-ri-card workflowx-ri-grid"); root.append(identity);
  const generation = el("div", "workflowx-ri-card workflowx-ri-grid"); root.append(generation);
  const execution = el("div", "workflowx-ri-card workflowx-ri-grid"); root.append(execution);
  const actions = el("div", "workflowx-ri-actions"); root.append(actions);
  root.append(el("div", "workflowx-ri-note", "Cancellation is local only. Kie and Atlas do not expose a canonical provider-side cancel endpoint; submitted work may continue and incur charges."));
  const log = el("div", "workflowx-ri-log"); root.append(el("div", "workflowx-ri-card", "")); root.lastElementChild.append(log);
  const lines = [];
  const addLog = (message, level = "info") => {
    const row = el("div", level, `[${new Date().toLocaleTimeString()}] ${message}`); log.append(row); lines.push(row);
    while (lines.length > MAX_LOG_LINES) lines.shift().remove(); log.scrollTop = log.scrollHeight;
    statusBadge.textContent = message.length > 34 ? `${message.slice(0, 31)}...` : message; statusBadge.dataset.level = level;
  };
  node.__workflowxRemoteLog = addLog;

  const model = selectControl(profiles.map((item) => item.id), nativeWidget(node, "model")?.value, (value) => { setNative(node, "model", value); renderProfile(true); });
  model.dataset.widget = "model";
  for (const option of model.options) option.textContent = profiles.find((item) => item.id === option.value)?.label || option.value;
  const key = inputControl("password", nativeWidget(node, "api_key")?.value, (value) => setNative(node, "api_key", value)); key.autocomplete = "off"; key.dataset.widget = "api_key";
  identity.append(field("Model", model), field(`${provider === "kie" ? "Kie" : "Atlas"} API Key (environment fallback supported)`, key));
  const prompt = el("textarea"); prompt.dataset.widget = "prompt"; prompt.value = nativeWidget(node, "prompt")?.value || ""; prompt.addEventListener("input", () => setNative(node, "prompt", prompt.value)); identity.append(field("Prompt", prompt, true));

  function currentProfile() { return profiles.find((item) => item.id === model.value) || profiles[0]; }
  function setDefault(control, reset) {
    const item = nativeWidget(node, control.widget); if (!item) return;
    const options = control.options || [];
    let value = reset ? control.default : item.value;
    if (options.length && !options.map(String).includes(String(value))) value = control.default ?? options[0];
    if (control.widget === "thinking_mode" && typeof value === "object") value = value.thinking === "enabled";
    setNative(node, control.widget, value);
  }
  function addControl(control) {
    const hasRefs = referenceCount(node) > 0;
    if (control.send_rules?.includes("t2i_only") && hasRefs) return;
    if (control.send_rules?.includes("i2i_only") && !hasRefs) return;
    setDefault(control, false); const name = control.widget; const value = nativeWidget(node, name)?.value;
    if (name === "seed") {
      const enabled = checkboxControl(nativeWidget(node, "seed_enabled")?.value, (checked) => { setNative(node, "seed_enabled", checked); renderProfile(false); }); enabled.dataset.widget = "seed_enabled";
      const wrap = el("label", "workflowx-ri-field workflowx-ri-check"); wrap.append(enabled, el("span", "workflowx-ri-label", "Use Fixed Seed")); generation.append(wrap);
      if (!enabled.checked) return;
    }
    if (control.type === "boolean") {
      const check = checkboxControl(value, (next) => setNative(node, name, next)); check.dataset.widget = name; const wrap = el("label", "workflowx-ri-field workflowx-ri-check"); wrap.append(check, el("span", "workflowx-ri-label", control.label)); generation.append(wrap); return;
    }
    let input;
    if (control.options?.length) input = selectControl(control.options, value, (next) => setNative(node, name, next));
    else input = inputControl(control.type === "integer" || control.type === "number" ? "number" : "text", value, (next) => setNative(node, name, next), { min:control.minimum, max:control.maximum, step:control.step });
    input.dataset.widget = name; generation.append(field(control.label, input));
  }
  function resizePanel() { requestAnimationFrame(() => { const height = Math.min(940, Math.max(610, root.scrollHeight + 92)); node.setSize?.([Math.max(560, node.size?.[0] || 0), height]); node.__workflowxRemoteWidgetHeight = height - 82; node.setDirtyCanvas?.(true, true); }); }
  function renderProfile(reset = false) {
    const profile = currentProfile(); generation.replaceChildren();
    for (const control of profile.controls || []) { if (reset) setDefault(control, true); addControl(control); }
    if (profile.custom_size) {
      if (reset) setNative(node, "custom_size_enabled", false);
      const enabled = checkboxControl(nativeWidget(node, "custom_size_enabled")?.value, (checked) => { setNative(node, "custom_size_enabled", checked); renderProfile(false); });
      const wrap = el("label", "workflowx-ri-field workflowx-ri-check"); wrap.append(enabled, el("span", "workflowx-ri-label", "Custom Output Size")); generation.append(wrap);
      if (enabled.checked) {
        const spec = profile.custom_size; generation.append(
          ...(spec.supports_auto ? (() => { const auto=checkboxControl(nativeWidget(node,"custom_size_auto")?.value,(checked)=>{setNative(node,"custom_size_auto",checked);renderProfile(false);}); auto.dataset.widget="custom_size_auto"; const item=el("label","workflowx-ri-field workflowx-ri-check"); item.append(auto,el("span","workflowx-ri-label","Use Provider Auto Size")); return [item]; })() : []),
          ...(!spec.supports_auto || !nativeWidget(node,"custom_size_auto")?.value ? [
            field("Custom Width", inputControl("number", nativeWidget(node, "custom_width")?.value, (v) => setNative(node, "custom_width", v), { min:spec.min_edge || spec.width_height_step || 64, max:spec.max_edge || 4096, step:spec.width_height_step || 1 })),
            field("Custom Height", inputControl("number", nativeWidget(node, "custom_height")?.value, (v) => setNative(node, "custom_height", v), { min:spec.min_edge || spec.width_height_step || 64, max:spec.max_edge || 4096, step:spec.width_height_step || 1 }))
          ] : [])
        );
      }
    } else { setNative(node, "custom_size_enabled", false); setNative(node, "custom_size_auto", false); }
    refreshMode(); resizePanel();
  }
  function refreshMode() {
    const count = referenceCount(node); const profile = currentProfile(); modeBadge.textContent = `${count ? "I2I" : "T2I"} · ${count}/${profile.max_references} refs`;
    modeBadge.dataset.level = count > profile.max_references ? "error" : "success";
  }
  node.__workflowxRemoteRefreshMode = refreshMode;
  node.__workflowxRemoteRenderProfile = renderProfile;

  const timeout = inputControl("number", nativeWidget(node, "timeout_seconds")?.value, (v) => setNative(node, "timeout_seconds", v), { min:30, max:3600, step:1 });
  const poll = inputControl("number", nativeWidget(node, "poll_interval_seconds")?.value, (v) => setNative(node, "poll_interval_seconds", v), { min:2, max:60, step:1 });
  const maxEdge = inputControl("number", nativeWidget(node, "reference_max_edge")?.value, (v) => setNative(node, "reference_max_edge", v), { min:512, max:8192, step:64 });
  const payloadCheck = checkboxControl(nativeWidget(node, "show_payload")?.value, (v) => setNative(node, "show_payload", v)); const payloadWrap = el("label", "workflowx-ri-field workflowx-ri-check"); payloadWrap.append(payloadCheck, el("span", "workflowx-ri-label", "Log Request Payload"));
  execution.append(field("Timeout Seconds (parks task)", timeout), field("Poll Interval Seconds", poll), field("Reference Resize Max Edge", maxEdge), payloadWrap);

  const button = (label, className, action) => { const item = el("button", className, label); item.addEventListener("click", async () => { try { await action(); } catch (error) { addLog(String(error), "error"); } }); actions.append(item); return item; };
  button("Queue Generation", "primary", async () => { setNative(node, "retrieval_mode", "generate"); await app.queuePrompt(0, 1); });
  const stopContinue = button("Stop & Continue", "danger", () => requestCancel(node, provider, "continue"));
  const stopRetrieve = button("Stop & Retrieve Later", "warn", () => requestCancel(node, provider, "retrieve"));
  button("Force Retrieve", "", () => forceRetrieve(node, provider));
  button("Forget Pending", "", async () => { await forgetPending(node, provider); addLog("Local pending record removed.", "warning"); });
  const setRunning = (running) => { stopContinue.disabled = !running; stopRetrieve.disabled = !running; };
  setRunning(false); node.__workflowxRemoteSetRunning = setRunning;
  renderProfile(false); addLog("Model contract loaded. Ready.");
  node.__workflowxRemoteWidgetHeight = 650;
  node.__workflowxRemoteWidget = node.addDOMWidget("workflowx_remote_image", "Remote Image API", root, { serialize:false, hideOnZoom:false, getMinHeight:() => node.__workflowxRemoteWidgetHeight || 650 });
  node.resizable = true; resizePanel();
}

api.addEventListener("workflowx.remote_image.status", (event) => {
  const detail = event.detail || event; const node = app.graph?._nodes?.find((item) => String(item.id) === String(detail.node_id));
  if (!node || !node.__workflowxRemoteLog) return;
  node.__workflowxRemoteLog(detail.message || detail.phase, detail.level || (detail.phase === "completed" ? "success" : "info"));
  const terminal = ["completed", "failed", "timeout", "cancelled", "parked"].includes(detail.phase); node.__workflowxRemoteSetRunning?.(!terminal);
});

app.registerExtension({
  name: "WorkflowX.RemoteImageAPI.RichUI",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const provider = NODES.get(nodeData.name); if (!provider) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = created?.apply(this, arguments); syncImageSockets(this);
      catalogs().then((all) => buildPanel(this, provider, all[provider] || [])).catch((error) => console.warn("[WorkflowX Remote Image]", error)); return result;
    };
    const connections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (slotType) { const result = connections?.apply(this, arguments); if (slotType === 1) syncImageSockets(this); return result; };
    const configured = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () { const result = configured?.apply(this, arguments); syncImageSockets(this); return result; };
    const executed = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) { const result = executed?.apply(this, arguments); if (message?.pending?.[0] === false) setNative(this, "retrieval_mode", "generate"); this.__workflowxRemoteSetRunning?.(false); return result; };
  },
});
