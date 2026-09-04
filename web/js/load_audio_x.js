import { app } from "/scripts/app.js";
import { injectAudioXState, LOAD_AUDIO_X_DEFAULTS, movedRangeStart, normalizeAudioXState, selectedRange, timelineDragMode } from "./load_audio_x_state.mjs";

const NODE = "WorkflowX_LoadAudioX";
const API = "/workflowx_configurator/load_audio_x";
const ACCENT = "#ef476f";
const DEFAULT_NODE_WIDTH = 340;
const instances = new Set();
let cssReady = false;
let previewNonce = 0;
let restoringNodeIds = new Set();

function installCSS() {
  if (cssReady) return;
  cssReady = true;
  const style = document.createElement("style");
  style.textContent = `
  .workflowx-lax{width:100%;height:auto;container-type:inline-size;display:flex;flex-direction:column;gap:5px;padding:6px 8px 7px;box-sizing:border-box;color:#e5e7eb;background:linear-gradient(145deg,#1a171d,#111318);font:11px ui-sans-serif,system-ui,sans-serif;overflow:hidden}
  .workflowx-lax *{box-sizing:border-box}.workflowx-lax button,.workflowx-lax select,.workflowx-lax input{height:26px;min-width:0;border:1px solid #4b4650;border-radius:5px;background:#242129;color:#eee;font:inherit}.workflowx-lax button{cursor:pointer}.workflowx-lax button:hover{border-color:${ACCENT}}
  .workflowx-lax-top{display:grid;grid-template-columns:minmax(0,1fr) auto auto auto;gap:4px}.workflowx-lax-top select{padding:0 5px}.workflowx-lax-top button{padding:0 8px}.workflowx-lax-repair{color:#ffd166!important}
  .workflowx-lax-wave{position:relative;height:112px;min-height:84px;border:1px solid #413b46;border-radius:6px;background:#0b0d12;overflow:hidden;touch-action:none}.workflowx-lax-wave canvas{display:block;width:100%;height:100%}.workflowx-lax-wave audio{position:absolute;isolation:isolate;left:6px;right:6px;bottom:4px;width:calc(100% - 12px);height:27px;opacity:1;background:#383838;border-radius:999px;box-shadow:0 0 0 4px #0b0d12}
  .workflowx-lax-time{display:grid;grid-template-columns:auto minmax(72px,160px) auto minmax(72px,160px);gap:4px;align-items:center;justify-content:start}.workflowx-lax-time label,.workflowx-lax-label{color:#9992a0}.workflowx-lax-time input{width:100%;padding:0 6px}.workflowx-lax-mode{display:grid;grid-template-columns:repeat(3,max-content);gap:4px;justify-content:center}.workflowx-lax-mode button{padding:0 12px}.workflowx-lax-mode button.active{border-color:${ACCENT};background:#6b263a}.workflowx-lax-convert{display:grid;grid-template-columns:repeat(2,minmax(140px,250px));gap:4px;justify-content:start}.workflowx-lax-field{display:grid;grid-template-columns:58px minmax(0,1fr);align-items:center;gap:4px}.workflowx-lax-field select{width:100%;padding:0 5px}
  .workflowx-lax-status{height:38px;min-height:38px;max-height:38px;padding:5px 7px;border:1px solid #37333d;border-radius:5px;background:#18161b;color:#aeb4c0;line-height:1.3;overflow:auto;white-space:pre-wrap;scrollbar-width:thin}.workflowx-lax-status.warn{border-color:#796225;color:#ffd166}.workflowx-lax-status.error{border-color:#853448;color:#ff8fab}
  .workflowx-lax-popup{position:fixed;z-index:100001;width:min(390px,calc(100vw - 20px));max-height:min(680px,calc(100vh - 20px));overflow:auto;padding:10px;border:1px solid #5b505e;border-radius:8px;background:#211e24;color:#eee;box-shadow:0 18px 60px #000b;font:12px ui-sans-serif,system-ui,sans-serif}.workflowx-lax-popup[hidden]{display:none}.workflowx-lax-popup details{border:1px solid #423c46;border-radius:5px;margin:0 0 7px;background:#19171c}.workflowx-lax-popup summary{padding:8px;cursor:pointer;color:#ff8fab;font-weight:700}.workflowx-lax-popup-body{display:grid;gap:7px;padding:0 8px 9px}.workflowx-lax-popup-row{display:grid;grid-template-columns:126px minmax(0,1fr);gap:8px;align-items:center}.workflowx-lax-popup input,.workflowx-lax-popup select{width:100%;height:28px;border:1px solid #4b4650;border-radius:4px;background:#28242b;color:#eee;padding:0 6px}.workflowx-lax-checks{display:grid;grid-template-columns:1fr 1fr;gap:5px}.workflowx-lax-checks label{display:flex;gap:5px;align-items:center}.workflowx-lax-checks input{width:auto;height:auto}.workflowx-lax-detail{white-space:pre-wrap;color:#aaa;font:10px ui-monospace,monospace}.workflowx-lax-wired{color:#70d6ff;font-size:10px}
  @container (max-width:280px){.workflowx-lax-top{grid-template-columns:minmax(0,1fr) auto auto}.workflowx-lax-repair{grid-column:1/-1}.workflowx-lax-convert{grid-template-columns:1fr}.workflowx-lax-time{grid-template-columns:auto minmax(0,1fr)}.workflowx-lax-mode{grid-template-columns:repeat(3,minmax(0,1fr))}.workflowx-lax-mode button{padding:0 3px}.workflowx-lax-wave{height:100px}}
  `;
  document.head.append(style);
}

function allNodes(graph, seen = new Set()) {
  if (!graph || seen.has(graph)) return [];
  seen.add(graph);
  const nodes = [...(graph._nodes || [])];
  const nestedValues = (value) => !value ? [] : Array.isArray(value) ? value : value instanceof Map ? [...value.values()] : typeof value === "object" ? Object.values(value) : [];
  for (const node of [...nodes]) {
    for (const nested of [node.subgraph, ...nestedValues(node.subgraphs), ...nestedValues(node._subgraphs)]) nodes.push(...allNodes(nested, seen));
  }
  return nodes;
}

function installPromptInjection() {
  if (app.__workflowXAudioXPromptInjection || typeof app.graphToPrompt !== "function") return;
  app.__workflowXAudioXPromptInjection = true;
  const original = app.graphToPrompt.bind(app);
  app.graphToPrompt = async function (...args) {
    const result = await original(...args);
    const byId = new Map(allNodes(app.graph).map((node) => [String(node.id), node]));
    for (const [id, entry] of Object.entries(result?.output || {})) {
      if (entry?.class_type !== NODE) continue;
      const node = byId.get(String(id)) || [...instances].find((item) => String(item.id) === String(id));
      injectAudioXState(entry, node?.properties?.workflowxLoadAudioXState || LOAD_AUDIO_X_DEFAULTS);
    }
    return result;
  };
}

function element(tag, className = "", text = "") {
  const item = document.createElement(tag); item.className = className; item.textContent = text; return item;
}
function optionSelect(values, value, change) {
  const select = document.createElement("select");
  for (const item of values) select.append(new Option(item.label || item, item.value ?? item));
  select.value = value; select.onchange = () => change(select.value); return select;
}
function numeric(value, min, max, step, change) {
  const input = document.createElement("input"); input.type = "number"; input.value = value; input.min = min; input.max = max; input.step = step;
  input.onchange = () => change(Number(input.value)); return input;
}
function displaySeconds(value) {
  const rounded = Math.round((Number(value) || 0) * 1000) / 1000;
  return Object.is(rounded, -0) ? "0" : String(rounded);
}
function popupRow(label, control) { const row = element("label", "workflowx-lax-popup-row"); row.append(element("span", "", label), control); return row; }
function viewURL(preview) {
  if (!preview?.filename) return "";
  const query = new URLSearchParams(preview);
  // Preview files are deliberately overwritten per node. Give every rewrite a
  // new URL so the browser cannot reuse an older (or previously silent) file.
  query.set("workflowx_cache", `${Date.now()}-${++previewNonce}`);
  return `/view?${query}`;
}
function compactWarning(value) { const lines=String(value||"").split(/\r?\n/).filter(Boolean); return lines.length ? `${lines[0]}${lines.length>1?` (+${lines.length-1} more)`:""}` : ""; }

function upstreamSeconds(node) {
  const index = node.inputs?.findIndex((input) => input.name === "seconds") ?? -1;
  const linkId = index >= 0 ? node.inputs[index]?.link : null;
  const link = linkId != null ? app.graph?.links?.[linkId] : null;
  const origin = link ? app.graph?.getNodeById?.(link.origin_id) : null;
  if (!origin) return null;
  const candidate = [origin._pixLiveSeconds, origin._workflowxLiveSeconds, origin.widgets?.find((widget) => ["seconds", "value", "number"].includes(String(widget.name).toLowerCase()))?.value]
    .map(Number).find((value) => Number.isFinite(value) && value >= 0);
  return candidate ?? null;
}

function createGear(ui, anchor) {
  const popup = element("div", "workflowx-lax-popup"); popup.hidden = true; popup.tabIndex = -1; document.body.append(popup);
  const section = (title, open = false) => { const details = document.createElement("details"); details.open = open; const summary = document.createElement("summary"); summary.textContent = title; const body = element("div", "workflowx-lax-popup-body"); details.append(summary, body); popup.append(details); return body; };
  const bound = [];
  const commitControl = (key, control) => { bound.push([key, control]); control.addEventListener("change", () => ui.commit({ ...ui.state, [key]: control.type === "checkbox" ? control.checked : control.type === "number" ? Number(control.value) : control.value }, false)); return control; };

  const recovery = section("Recovery & diagnostics", true);
  recovery.append(popupRow("Recovery mode", commitControl("repair_mode", optionSelect([{"label":"Safe automatic", "value":"auto"}, {"label":"Off", "value":"off"}], ui.state.repair_mode, () => {}))));
  ui.detail = element("div", "workflowx-lax-detail", "No file inspected yet."); recovery.append(ui.detail);

  const filters = section("Cleanup & filter presets"); const checks = element("div", "workflowx-lax-checks");
  const filterControls = [];
  for (const name of ["Denoise light", "De-click", "High-pass rumble cut", "Low-pass hiss cut", "De-esser light", "Presence boost", "Warmth", "Brightness", "Speech clarity", "Stereo widen", "Noise gate", "Voice compressor"]) {
    const label = document.createElement("label"), checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.checked = ui.state.filters.includes(name);
    checkbox.onchange = () => ui.commit({ ...ui.state, filters: checkbox.checked ? [...new Set([...ui.state.filters, name])] : ui.state.filters.filter((item) => item !== name) }, false);
    filterControls.push([name, checkbox]);
    label.append(checkbox, document.createTextNode(name)); checks.append(label);
  }
  filters.append(checks);

  const level = section("Gain, normalization & limiter");
  level.append(popupRow("Gain (dB)", commitControl("gain_db", numeric(ui.state.gain_db, -24, 24, .1, () => {}))));
  level.append(popupRow("Normalize", commitControl("normalize", optionSelect(["Off", "Peak", "EBU R128"], ui.state.normalize, () => {}))));
  level.append(popupRow("Target LUFS", commitControl("target_lufs", numeric(ui.state.target_lufs, -30, -5, .5, () => {}))));
  const limiter = document.createElement("input"); limiter.type = "checkbox"; limiter.checked = ui.state.limiter; level.append(popupRow("Limiter", commitControl("limiter", limiter)));

  const timing = section("Silence trim & fades");
  const trim = document.createElement("input"); trim.type = "checkbox"; trim.checked = ui.state.trim_silence; timing.append(popupRow("Trim edge silence", commitControl("trim_silence", trim)));
  timing.append(popupRow("Threshold (dB)", commitControl("silence_threshold_db", numeric(ui.state.silence_threshold_db, -90, -10, 1, () => {}))));
  timing.append(popupRow("Minimum silence", commitControl("minimum_silence", numeric(ui.state.minimum_silence, 0, 10, .01, () => {}))));
  timing.append(popupRow("Fade in (s)", commitControl("fade_in", numeric(ui.state.fade_in, 0, 60, .01, () => {}))));
  timing.append(popupRow("Fade out (s)", commitControl("fade_out", numeric(ui.state.fade_out, 0, 60, .01, () => {}))));

  const saving = section("Output destination");
  const save = document.createElement("input"); save.type = "checkbox"; save.checked = ui.state.save_output; saving.append(popupRow("Permanent save", commitControl("save_output", save)));
  const prefix = document.createElement("input"); prefix.type = "text"; prefix.value = ui.state.filename_prefix; saving.append(popupRow("Filename prefix", commitControl("filename_prefix", prefix)));

  const close = () => { popup.hidden = true; document.removeEventListener("pointerdown", away, true); document.removeEventListener("keydown", keys, true); };
  const position = () => { const rect = anchor.getBoundingClientRect(), width = Math.min(390, innerWidth - 20), left = Math.max(10, Math.min(innerWidth - width - 10, rect.right - width)); popup.style.left = `${left}px`; popup.style.top = `${Math.max(10, Math.min(innerHeight - Math.min(680, popup.scrollHeight) - 10, rect.bottom + 5))}px`; };
  const away = (event) => { if (!popup.contains(event.target) && event.target !== anchor) close(); };
  const keys = (event) => { if (event.key === "Escape") close(); };
  anchor.onclick = (event) => { event.stopPropagation(); if (!popup.hidden) return close(); popup.hidden = false; position(); popup.focus(); document.addEventListener("pointerdown", away, true); document.addEventListener("keydown", keys, true); };
  ui.closeGear = () => { close(); popup.remove(); };
  ui.syncGear = () => { for (const [key, control] of bound) { if (control.type === "checkbox") control.checked = ui.state[key] === true; else control.value = ui.state[key]; } for (const [name, control] of filterControls) control.checked = ui.state.filters.includes(name); };
  ui.syncGear();
  return popup;
}

function createUI(node) {
  installCSS();
  node.properties ||= {};
  const ui = { node, state: normalizeAudioXState(node.properties.workflowxLoadAudioXState), metadata: null, disposed: false, dragging: null, layoutHeight: 350, fitFrame: 0 };
  const root = element("div", "workflowx-lax"); ui.root = root;
  const top = element("div", "workflowx-lax-top"), picker = document.createElement("select"), upload = element("button", "", "Upload"), gear = element("button", "", "⚙"), repair = element("button", "workflowx-lax-repair", "Repair");
  picker.title = "Select audio or video from ComfyUI input"; top.append(picker, upload, gear, repair);
  const wave = element("div", "workflowx-lax-wave"), canvas = document.createElement("canvas"), player = document.createElement("audio"); player.controls = true; player.preload = "metadata"; wave.append(canvas, player); ui.canvas = canvas; ui.player = player;
  const time = element("div", "workflowx-lax-time"), start = numeric(ui.state.start, 0, 86400, .001, (value) => ui.commit({ ...ui.state, start: value })), length = numeric(ui.state.length, 0, 86400, .001, (value) => ui.commit({ ...ui.state, length: value }));
  time.append(element("label", "", "Start"), start, element("label", "", "Length"), length); ui.start = start; ui.length = length;
  const mode = element("div", "workflowx-lax-mode"), whole = element("button", "", "Whole file"), fixed = element("button", "", "Use length"), short = element("button", "", "Short: silence"); mode.append(whole, fixed, short);
  const convert = element("div", "workflowx-lax-convert");
  const addSelect = (label, key, values) => { const row = element("label", "workflowx-lax-field"); row.append(element("span", "workflowx-lax-label", label), optionSelect(values, ui.state[key], (value) => ui.commit({ ...ui.state, [key]: value }))); convert.append(row); return row; };
  addSelect("Format", "format", [{label:"WAV",value:"wav"},{label:"MP3",value:"mp3"}]);
  const quality = addSelect("WAV depth", "wav_depth", ["16-bit","24-bit","32-bit float"]); ui.quality = quality;
  addSelect("Channels", "channels", ["Source","Mono","Stereo"]); addSelect("Rate", "sample_rate", ["Source","8 kHz","16 kHz","22.05 kHz","24 kHz","32 kHz","44.1 kHz","48 kHz","96 kHz"]);
  const status = element("div", "workflowx-lax-status", "Choose an audio or video file."); ui.status = status;
  root.append(top, wave, time, mode, convert, status);
  createGear(ui, gear);

  ui.fitToContent = (resizeNode = false) => {
    if (ui.fitFrame) cancelAnimationFrame(ui.fitFrame);
    ui.fitFrame = requestAnimationFrame(() => {
      ui.fitFrame = 0;
      if (ui.disposed || !root.isConnected) return;
      const needed = Math.max(260, Math.ceil(root.scrollHeight));
      ui.layoutHeight = needed;
      if (resizeNode) ui.widget?.callback?.();
      if (resizeNode && node.__workflowXLoadAudioXRestored !== true) {
        requestAnimationFrame(() => {
          if (ui.disposed || node.__workflowXLoadAudioXRestored === true) return;
          const computed = node.computeSize?.() || [DEFAULT_NODE_WIDTH, needed + 64];
          node.setSize?.([DEFAULT_NODE_WIDTH, Number(computed[1]) || needed + 64]);
        });
      }
      node.setDirtyCanvas?.(true, true);
      node.graph?.setDirtyCanvas?.(true, true);
    });
  };

  ui.commit = (next, render = true) => { ui.state = normalizeAudioXState(next); node.properties.workflowxLoadAudioXState = ui.state; node.graph?.change?.(); node.graph?.setDirtyCanvas?.(true, true); if (render) ui.render(); ui.draw(); };
  ui.render = () => {
    start.value = displaySeconds(ui.state.start); length.value = displaySeconds(ui.state.length);
    const wired = upstreamSeconds(node); length.disabled = wired !== null || ui.state.when_unwired === "whole";
    whole.classList.toggle("active", ui.state.when_unwired === "whole" && wired === null); fixed.classList.toggle("active", ui.state.when_unwired === "length" && wired === null);
    fixed.textContent = wired !== null ? `Wired: ${wired.toFixed(3)} s` : "Use length";
    short.textContent = `Short: ${ui.state.when_short}`;
    const qualitySelect = quality.querySelector("select"); quality.querySelector("span").textContent = ui.state.format === "mp3" ? "Bitrate" : "WAV depth";
    qualitySelect.replaceChildren(...(ui.state.format === "mp3" ? ["64k","96k","128k","160k","192k","256k","320k"] : ["16-bit","24-bit","32-bit float"]).map((value) => new Option(value, value)));
    qualitySelect.value = ui.state.format === "mp3" ? ui.state.mp3_bitrate : ui.state.wav_depth;
    qualitySelect.onchange = () => ui.commit({ ...ui.state, [ui.state.format === "mp3" ? "mp3_bitrate" : "wav_depth"]: qualitySelect.value });
    ui.syncGear?.();
  };
  whole.onclick = () => ui.commit({ ...ui.state, when_unwired: "whole" }); fixed.onclick = () => ui.commit({ ...ui.state, when_unwired: "length" }); short.onclick = () => ui.commit({ ...ui.state, when_short: ui.state.when_short === "loop" ? "silence" : "loop" });

  ui.draw = () => {
    const rect = canvas.getBoundingClientRect(), dpr = devicePixelRatio || 1, width = Math.max(1, Math.round(rect.width * dpr)), height = Math.max(1, Math.round(rect.height * dpr)); if (canvas.width !== width) canvas.width = width; if (canvas.height !== height) canvas.height = height;
    const ctx = canvas.getContext("2d"); ctx.clearRect(0,0,width,height); ctx.fillStyle="#0b0d12"; ctx.fillRect(0,0,width,height); const peaks = ui.metadata?.peaks || [], mid = (height - 30*dpr)/2;
    ctx.strokeStyle="#ef476f"; ctx.lineWidth=Math.max(1,dpr); ctx.beginPath(); peaks.forEach((peak,index) => { const x=index/Math.max(1,peaks.length-1)*width,y=peak*mid*.82; ctx.moveTo(x,mid-y);ctx.lineTo(x,mid+y); });ctx.stroke();
    const range=selectedRange(ui.state,ui.metadata?.duration||0,upstreamSeconds(node)), total=ui.metadata?.duration||1, sx=range.start/total*width, ex=range.end/total*width; ctx.fillStyle="#0008";ctx.fillRect(0,0,sx,height-30*dpr);ctx.fillRect(ex,0,width-ex,height-30*dpr);ctx.strokeStyle="#ffd166";ctx.lineWidth=2*dpr;ctx.strokeRect(sx,1,Math.max(1,ex-sx),height-30*dpr-2);ctx.fillStyle="#ffd166";ctx.fillRect(sx-3*dpr,0,6*dpr,height-30*dpr);ctx.fillRect(ex-3*dpr,0,6*dpr,height-30*dpr);
    if (player.duration && Number.isFinite(player.currentTime)) { ctx.fillStyle="#70d6ff";ctx.fillRect(player.currentTime/Math.max(player.duration,.001)*width,0,2*dpr,height-30*dpr); }
  };
  canvas.addEventListener("pointerdown", (event) => {
    if (!ui.metadata?.duration) return;
    event.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    const wired = upstreamSeconds(node);
    const range = selectedRange(ui.state, ui.metadata.duration, wired);
    ui.dragging = {
      mode: timelineDragMode(ratio, range.start / ui.metadata.duration, range.end / ui.metadata.duration, rect.width, wired !== null),
      pointerSeconds: ratio * ui.metadata.duration,
      start: range.start,
      length: range.length,
    };
    canvas.setPointerCapture?.(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!ui.dragging || !ui.metadata?.duration) return;
    const rect = canvas.getBoundingClientRect();
    const seconds = Math.max(0, Math.min(ui.metadata.duration, (event.clientX - rect.left) / rect.width * ui.metadata.duration));
    const wired = upstreamSeconds(node);
    const range = selectedRange(ui.state, ui.metadata.duration, wired);
    if (ui.dragging.mode === "move") {
      const nextStart = movedRangeStart(ui.dragging.start, ui.dragging.length, seconds - ui.dragging.pointerSeconds, ui.metadata.duration);
      ui.commit({ ...ui.state, start: nextStart });
    } else if (wired !== null) {
      const nextStart = movedRangeStart(range.start, range.length, seconds - (ui.dragging.mode === "start" ? range.start : range.end), ui.metadata.duration);
      ui.commit({ ...ui.state, start: nextStart });
    } else if (ui.dragging.mode === "start") {
      ui.commit({ ...ui.state, start: Math.min(seconds, range.end), length: Math.max(0, range.end - seconds), when_unwired: "length" });
    } else {
      ui.commit({ ...ui.state, length: Math.max(0, seconds - range.start), when_unwired: "length" });
    }
  });
  const stopDrag=()=>{ui.dragging=null}; canvas.addEventListener("pointerup",stopDrag);canvas.addEventListener("pointercancel",stopDrag);canvas.addEventListener("lostpointercapture",stopDrag); player.addEventListener("timeupdate",ui.draw);
  player.addEventListener("play",()=>{const range=selectedRange(ui.state,ui.metadata?.duration||player.duration,upstreamSeconds(node));if(player.currentTime<range.start||player.currentTime>=range.end)player.currentTime=range.start;});
  player.addEventListener("timeupdate",()=>{const range=selectedRange(ui.state,ui.metadata?.duration||player.duration,upstreamSeconds(node));if(!player.paused&&range.end>range.start&&player.currentTime>=range.end)player.pause();});

  // Status text changes repeatedly while probing/repairing. Keep those updates
  // inside a fixed-height scroller so loading media never resizes the node.
  ui.setStatus = (text, kind="") => { status.textContent=text; status.className=`workflowx-lax-status ${kind}`; };
  ui.applyAnalysis = (data) => { ui.metadata=data; player.pause(); player.src=viewURL(data.preview); player.load(); const warning=[compactWarning(data.warning),data.repair&&data.repair!=="none"?`Recovery: ${data.repair}`:""].filter(Boolean).join(" · "); ui.setStatus(`${data.codec || "audio"} · ${data.sample_rate} Hz · ${data.channels} ch · ${Number(data.duration).toFixed(3)} s${warning?` · ${warning}`:""}`,warning?"warn":""); if(ui.detail)ui.detail.textContent=JSON.stringify({container:data.container,codec:data.codec,rate:data.sample_rate,channels:data.channels,duration:data.duration,repair:data.repair,warning:data.warning},null,2); ui.draw(); };
  ui.inspect = async (doRepair=false) => { if(!ui.state.file)return; ui.setStatus(doRepair?"Running bounded repair…":"Inspecting audio…"); try { const response=await fetch(`${API}/${doRepair?"repair":"analyze"}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({file:ui.state.file,node_id:node.id})}); const data=await response.json(); if(!response.ok||!data.ok){ ui.metadata=null;ui.setStatus(data.detail||data.error||`HTTP ${response.status}`,data.recoverable?"warn":"error");if(ui.detail)ui.detail.textContent=JSON.stringify(data,null,2);ui.draw();return;}ui.applyAnalysis(data); } catch(error){ui.setStatus(String(error),"error");} };
  repair.onclick=()=>ui.inspect(true);

  ui.refreshFiles = async () => { const response=await fetch(`${API}/files`,{cache:"no-store"}), data=await response.json(), files=data.files||[]; picker.replaceChildren(new Option("Select input media…",""),...files.map((file)=>new Option(file,file))); picker.value=ui.state.file; };
  picker.onchange=()=>{ui.commit({...ui.state,file:picker.value,start:0});ui.inspect(false)};
  upload.onclick=()=>{const input=document.createElement("input");input.type="file";input.accept="audio/*,video/*,.m4a,.3ga,.amr,.awb,.opus";input.onchange=async()=>{const file=input.files?.[0];if(!file)return;ui.setStatus("Uploading…");const form=new FormData();form.append("image",file,file.name);form.append("type","input");form.append("overwrite","false");try{const response=await fetch("/upload/image",{method:"POST",body:form}),data=await response.json();if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);const selected=[data.subfolder,data.name].filter(Boolean).join("/");await ui.refreshFiles();picker.value=selected;ui.commit({...ui.state,file:selected,start:0});ui.inspect(false);}catch(error){ui.setStatus(`Upload failed: ${error}`,"error");}};input.click();};
  ui.restore=()=>{ui.state=normalizeAudioXState(node.properties.workflowxLoadAudioXState);node.properties.workflowxLoadAudioXState=ui.state;ui.render();ui.lastWiredSeconds=upstreamSeconds(node);ui.fitToContent();ui.refreshFiles().then(()=>{picker.value=ui.state.file;if(ui.state.file)ui.inspect(false)}).catch((error)=>ui.setStatus(String(error),"error"));};
  ui.poll=setInterval(()=>{if(!ui.disposed){const wired=upstreamSeconds(node);if(wired!==ui.lastWiredSeconds){ui.lastWiredSeconds=wired;ui.render();}ui.draw();}},350); ui.resize=new ResizeObserver(ui.draw);ui.resize.observe(root);
  ui.dispose=()=>{ui.disposed=true;clearInterval(ui.poll);if(ui.fitFrame)cancelAnimationFrame(ui.fitFrame);ui.resize.disconnect();ui.closeGear?.();instances.delete(node);};
  ui.restore(); return ui;
}

function attach(node) {
  if (node.comfyClass !== NODE && node.type !== NODE) return;
  if (restoringNodeIds.has(String(node.id))) node.__workflowXLoadAudioXRestored = true;
  if (node.__workflowXLoadAudioXUI || node.__workflowXLoadAudioXPending) return;
  node.__workflowXLoadAudioXPending = true;
  instances.add(node);
  queueMicrotask(() => {
    node.__workflowXLoadAudioXPending = false;
    if (node.__workflowXLoadAudioXUI) return;
    try {
      const ui = createUI(node); node.__workflowXLoadAudioXUI = ui;
      const widget = node.addDOMWidget("workflowx_load_audio_x", "custom", ui.root, {
        serialize: false, hideOnZoom: false,
        getMinHeight: () => ui.layoutHeight,
        getMaxHeight: () => ui.layoutHeight,
        margin: 0,
      });
      widget.computeLayoutSize = () => ({ minHeight: ui.layoutHeight, maxHeight: ui.layoutHeight, minWidth: 260 });
      ui.widget = widget;
      ui.fitToContent(node.__workflowXLoadAudioXRestored !== true);
      const configured = node.onConfigure;
      node.onConfigure = function () { const result = configured?.apply(this, arguments); queueMicrotask(ui.restore); return result; };
      const executed = node.onExecuted;
      node.onExecuted = function (message) {
        const result = executed?.apply(this, arguments), data = message?.workflowx_load_audio_x?.[0];
        if (data) ui.setStatus(`${data.codec} ${data.source_sample_rate} Hz/${data.source_channels} ch → ${data.format.toUpperCase()} ${data.sample_rate} Hz/${data.channels} ch · ${displaySeconds(data.duration)} s · ${data.saved ? "saved" : "temporary"}\n${data.path}${data.warning ? `\n${compactWarning(data.warning)}` : ""}`, data.warning ? "warn" : "");
        return result;
      };
      const removed = node.onRemoved;
      node.onRemoved = function () { ui.dispose(); node.__workflowXLoadAudioXUI = null; return removed?.apply(this, arguments); };
    } catch (error) {
      node.__workflowXLoadAudioXUI = null;
      instances.delete(node);
      console.error("[WorkflowX Load AudioX] UI attachment failed", error);
    }
  });
}

function attachExistingNodes() {
  for (const node of allNodes(app.graph)) {
    if (node.comfyClass === NODE || node.type === NODE) {
      node.__workflowXLoadAudioXRestored = true;
    }
    attach(node);
  }
}

function attachCreatedNode(node) {
  if (!restoringNodeIds.has(String(node?.id))) node.__workflowXLoadAudioXRestored = false;
  attach(node);
}

installPromptInjection();
app.registerExtension({
  name:"WorkflowX.LoadAudioX",
  setup(){ installPromptInjection(); setTimeout(attachExistingNodes, 0); },
  beforeConfigureGraph(graphData){ restoringNodeIds = new Set((graphData?.nodes || []).map((node) => String(node.id))); },
  beforeRegisterNodeDef(nodeType,nodeData){if(nodeData?.name!==NODE)return;const created=nodeType.prototype.onNodeCreated;nodeType.prototype.onNodeCreated=function(){const result=created?.apply(this,arguments);attach(this);return result}},
  nodeCreated:attachCreatedNode,
  loadedGraphNode:attach,
  afterConfigureGraph(){ queueMicrotask(() => { attachExistingNodes(); restoringNodeIds.clear(); }); },
});
