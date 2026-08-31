import { app } from "/scripts/app.js";
import { createGraphDock } from "./workflowx_graph_dock.mjs";
import {
  DEFAULT_VIDEO_STATE,
  clearForVideoChange,
  computeOutputDimensions,
  isNativeVideoPreviewWidgetName,
  normalizeTrimRange,
  normalizeVideoState,
  normalizedRect,
  pixelRectFromState,
  requestedOutputsFromPrompt,
  snapCropRect,
  videoViewURL,
  withRequestedOutputsState,
} from "./load_video_x_adv_helpers.mjs";

const NODE_NAME = "WorkflowX_LoadVideoXAdv";
const ACCENT = "#7aa2f7";
const SNAP_OPTIONS = [0, 8, 16, 32, 64];
const MODES = [
  ["off", "Off"], ["max_mp", "Max MP"], ["longest_side", "Longest side"],
  ["scale_factor", "Scale by x"], ["fit_inside", "Fit inside"], ["cover", "Crop to fill"],
  ["match_ratio", "Match ratio"], ["pad", "Pad"],
];
let cssInstalled = false;

function installCSS() {
  if (cssInstalled) return;
  cssInstalled = true;
  const style = document.createElement("style");
  style.textContent = `
    .workflowx-lvxa{display:flex;flex-direction:column;gap:7px;width:100%;height:100%;padding:4px 8px 8px;
      color:#d9dce2;font:11px ui-sans-serif,system-ui,sans-serif;box-sizing:border-box;overflow:hidden}
    .workflowx-lvxa *{box-sizing:border-box}.workflowx-lvxa button,.workflowx-lvxa input,.workflowx-lvxa select{font:inherit}
    .workflowx-lvxa-summary{display:grid;grid-template-columns:1fr 1fr;gap:6px}.workflowx-lvxa-card{height:54px;
      display:flex;flex-direction:column;align-items:center;justify-content:center;border:1px solid #454b55;border-radius:5px;background:#24272c}
    .workflowx-lvxa-card small{color:#9299a3;text-transform:uppercase;font-size:8px}.workflowx-lvxa-size{color:${ACCENT};font-size:14px;font-weight:700}
    .workflowx-lvxa button,.workflowx-lvxa select,.workflowx-lvxa input{min-width:0;height:29px;border:1px solid #4b5058;
      border-radius:4px;background:#1d1f23;color:#d9dce2}.workflowx-lvxa button{cursor:pointer}.workflowx-lvxa button:hover{border-color:${ACCENT};color:#fff}
    .workflowx-lvxa button.workflowx-lvxa-card{height:54px}
    .workflowx-lvxa .active{border-color:${ACCENT};background:#385a86;color:#fff}.workflowx-lvxa-modes{display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));gap:4px}.workflowx-lvxa-panel{padding:7px;background:#24262a;border:1px solid #3d4148;border-radius:4px}
    .workflowx-lvxa-row{display:flex;align-items:center;gap:5px}.workflowx-lvxa-row label{color:#949ba5;white-space:nowrap}.workflowx-lvxa-row input,
      .workflowx-lvxa-row select{flex:1;text-align:center;padding:0 5px}.workflowx-lvxa-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}
    .workflowx-lvxa-snap{display:flex;justify-content:center;align-items:center;gap:4px}.workflowx-lvxa-snap button{width:34px;padding:0;font-size:9px}
    .workflowx-lvxa-toggles{display:grid;grid-template-columns:1fr 1fr;gap:5px}
    .workflowx-lvxa-native-crop{position:absolute;inset:0;width:100%;height:100%;z-index:5;pointer-events:none}
    .workflowx-lvxa-native-crop-surface{position:absolute;inset:0;z-index:6;touch-action:none}
    .workflowx-lvxa-help{position:absolute;left:50%;top:8px;z-index:7;max-width:calc(100% - 24px);padding:3px 7px;border-radius:3px;
      background:#000b;color:#e1e6ee;font-size:10px;line-height:1.25;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
      pointer-events:none;transform:translateX(-50%)}
    .workflowx-lvxa-timeline{height:100%;display:grid;grid-template-rows:minmax(0,1fr) 104px 24px 32px 38px;gap:8px;padding:9px;background:#181a1e}
    .workflowx-lvxa-player{width:100%;height:100%;min-height:0;background:#08090b;object-fit:contain}.workflowx-lvxa-strip{position:relative;min-height:78px;
      border:1px solid #4a4f57;border-radius:4px;overflow:hidden;background:#111;touch-action:none}.workflowx-lvxa-strip canvas{width:100%;height:100%;display:block}
    .workflowx-lvxa-trim-shade,.workflowx-lvxa-trim-selection,.workflowx-lvxa-trim-playhead{position:absolute;top:0;bottom:0;pointer-events:none}
    .workflowx-lvxa-trim-shade{background:#0009}.workflowx-lvxa-trim-selection{border:2px solid ${ACCENT};background:#7aa2f71a;pointer-events:auto;cursor:grab}
    .workflowx-lvxa-trim-selection:active{cursor:grabbing}.workflowx-lvxa-trim-handle{position:absolute;top:-2px;bottom:-2px;width:18px;
      padding:0;border:0;border-radius:3px;background:${ACCENT};cursor:ew-resize;touch-action:none;z-index:4}
    .workflowx-lvxa-trim-handle::after{content:"";position:absolute;left:7px;top:35%;width:3px;height:30%;border-left:1px solid #fff;border-right:1px solid #fff}
    .workflowx-lvxa-trim-handle.start{left:-9px}.workflowx-lvxa-trim-handle.end{right:-9px}.workflowx-lvxa-trim-playhead{width:2px;background:#ff755f;z-index:3}
    .workflowx-lvxa-scrubber{width:100%;height:24px;accent-color:${ACCENT}}
    .workflowx-lvxa-duration{display:grid;grid-template-columns:auto minmax(90px,150px) auto;gap:8px;align-items:center;color:#aeb5bf}
    .workflowx-lvxa-duration input{width:100%;height:29px;border:1px solid #4b5058;border-radius:4px;background:#111318;color:#fff;padding:0 8px}
    .workflowx-lvxa-duration small{color:#7f8792;text-transform:uppercase;font-size:9px}
    .workflowx-lvxa-readout{display:flex;align-items:center;gap:7px}.workflowx-lvxa-readout button:first-child{width:38px;flex:none}
    .workflowx-lvxa-readout button:not(:first-child){width:auto;padding:0 10px}.workflowx-lvxa-readout span{flex:1;text-align:center;color:#c8cdd5;font-variant-numeric:tabular-nums}
  `;
  document.head.appendChild(style);
}

function button(text, title = "") {
  const element = document.createElement("button");
  element.type = "button"; element.textContent = text; element.title = title;
  return element;
}

function field(value, options, commit) {
  const input = document.createElement("input");
  input.type = options.type || "number"; input.value = String(value);
  if (options.min != null) input.min = String(options.min);
  if (options.max != null) input.max = String(options.max);
  if (options.step != null) input.step = String(options.step);
  input.addEventListener("change", () => commit(input.type === "color" ? input.value : Number(input.value)));
  return input;
}

function row(labelText, ...elements) {
  const element = document.createElement("div"); element.className = "workflowx-lvxa-row";
  const label = document.createElement("label"); label.textContent = labelText;
  element.append(label, ...elements); return element;
}

function hideWidget(widget) {
  if (!widget) return;
  widget.hidden = true; widget.type = "hidden";
  if (widget.element) widget.element.style.display = "none";
  if (widget.videoEl) widget.videoEl.style.display = "none";
  widget.computeSize = () => [0, -4];
  widget.computeLayoutSize = () => ({ minHeight: 0, maxHeight: 0, minWidth: 0 });
  widget.draw = () => {};
}

function findNativeVideoPreview(node, root) {
  const legacyWidget = (node.widgets || []).find((widget) => {
    const name = String(widget.name || "").toLowerCase();
    const video = widget.videoEl || widget.videoElement || widget.element?.querySelector?.("video");
    return isNativeVideoPreviewWidgetName(name) && video;
  });
  if (legacyWidget) return { widget: legacyWidget, videoEl: legacyWidget.videoEl || legacyWidget.videoElement || legacyWidget.element?.querySelector?.("video") };

  // Current ComfyUI renders native VIDEO outputs as a Vue VideoPreview, not a
  // LiteGraph widget. Resolve it from this node's DOM host instead of assuming
  // it exists in node.widgets.
  const nodeHost = root?.closest?.("[data-node-id]")
    || (node.id != null ? document.querySelector(`[data-node-id="${node.id}"]`) : null);
  const video = nodeHost?.querySelector?.(".video-preview video, video[data-testid='video-preview']");
  return video ? { videoEl: video, element: video.parentElement, vueOutput: true } : null;
}

function upstreamSeconds(node) {
  const inputIndex = node.inputs?.findIndex((input) => input.name === "seconds") ?? -1;
  const linkId = inputIndex >= 0 ? node.inputs[inputIndex]?.link : null;
  const link = linkId != null ? app.graph?.links?.[linkId] : null;
  const origin = link ? app.graph?.getNodeById?.(link.origin_id) : null;
  if (!origin) return null;
  const candidates = [origin._pixLiveSeconds, origin._workflowxLiveSeconds,
    origin.widgets?.find((widget) => ["seconds", "value", "number"].includes(String(widget.name).toLowerCase()))?.value];
  for (const candidate of candidates) {
    const value = Number(candidate);
    if (Number.isFinite(value) && value > 0) return value;
  }
  return null;
}

function installPromptMask() {
  if (app.__workflowXVideoOutputMaskPatched || typeof app.graphToPrompt !== "function") return;
  app.__workflowXVideoOutputMaskPatched = true;
  const original = app.graphToPrompt.bind(app);
  app.graphToPrompt = async function (...args) {
    const result = await original(...args);
    const output = result?.output || {};
    for (const [id, entry] of Object.entries(output)) {
      if (entry?.class_type !== NODE_NAME) continue;
      const requested = requestedOutputsFromPrompt(output, id);
      entry.inputs ||= {};
      entry.inputs.workflowx_state = withRequestedOutputsState(entry.inputs.workflowx_state, requested);
    }
    return result;
  };
}

function createTimeline(ui) {
  if (ui.dock?.element?.isConnected) return;
  const content = document.createElement("div"); content.className = "workflowx-lvxa-timeline";
  const player = document.createElement("video"); player.className = "workflowx-lvxa-player"; player.controls = true; player.preload = "metadata";
  const strip = document.createElement("div"); strip.className = "workflowx-lvxa-strip";
  const canvas = document.createElement("canvas");
  const leftShade = document.createElement("div"); leftShade.className = "workflowx-lvxa-trim-shade";
  const rightShade = document.createElement("div"); rightShade.className = "workflowx-lvxa-trim-shade";
  const selection = document.createElement("div"); selection.className = "workflowx-lvxa-trim-selection";
  const startHandle = button("", "Drag trim start"); startHandle.className = "workflowx-lvxa-trim-handle start"; startHandle.setAttribute("aria-label", "Trim start");
  const endHandle = button("", "Drag trim end"); endHandle.className = "workflowx-lvxa-trim-handle end"; endHandle.setAttribute("aria-label", "Trim end");
  const playhead = document.createElement("div"); playhead.className = "workflowx-lvxa-trim-playhead";
  selection.append(startHandle, endHandle); strip.append(canvas, leftShade, rightShade, selection, playhead);
  const scrubber = document.createElement("input"); scrubber.className = "workflowx-lvxa-scrubber"; scrubber.type = "range"; scrubber.min = "0"; scrubber.max = "1000"; scrubber.step = "1"; scrubber.value = "0"; scrubber.title = "Video playhead";
  const durationRow = document.createElement("div"); durationRow.className = "workflowx-lvxa-duration";
  const durationLabel = document.createElement("label"); durationLabel.textContent = "Selection seconds";
  const durationInput = document.createElement("input"); durationInput.type = "number"; durationInput.min = "0.001"; durationInput.step = "0.001";
  const durationMode = document.createElement("small"); durationRow.append(durationLabel, durationInput, durationMode);
  const readout = document.createElement("div"); readout.className = "workflowx-lvxa-readout";
  const selectionPlay = button("▶", "Play selection");
  const label = document.createElement("span");
  readout.append(selectionPlay, label); content.append(player, strip, scrubber, durationRow, readout);
  const timeline = { player, canvas, label, thumbnails: [], sampler: null, token: 0 };
  ui.timeline = timeline;

  selectionPlay.onclick = () => {
    const range = ui.range();
    if (player.currentTime < range.start || player.currentTime >= Math.min(ui.metadata.duration, range.end)) player.currentTime = range.start;
    player.play();
  };
  player.addEventListener("timeupdate", () => {
    const range = ui.range();
    if (player.currentTime >= Math.min(ui.metadata.duration, range.end) && !player.paused) {
      player.pause(); player.currentTime = range.start;
    }
    const nativeVideo = ui.nativeVideo?.();
    if (nativeVideo && Number.isFinite(player.currentTime)) nativeVideo.currentTime = Math.min(player.currentTime, Math.max(0, ui.metadata.duration - .001));
    draw();
  });

  function sizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const w = Math.max(1, Math.round(rect.width * ratio)); const h = Math.max(1, Math.round(rect.height * ratio));
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    return { w, h, ratio };
  }
  function draw() {
    const { w, h } = sizeCanvas(); const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, w, h); ctx.fillStyle = "#111"; ctx.fillRect(0, 0, w, h);
    const cell = timeline.thumbnails.length ? w / timeline.thumbnails.length : w;
    timeline.thumbnails.forEach((image, index) => {
      const targetX = index * cell; const scale = Math.max(cell / image.width, h / image.height);
      const sw = cell / scale; const sh = h / scale;
      ctx.drawImage(image, (image.width - sw) / 2, (image.height - sh) / 2, sw, sh, targetX, 0, cell + 1, h);
    });
    const duration = Math.max(.001, ui.metadata.duration || 0);
    const range = ui.range(); const startPercent = Math.max(0, Math.min(100, range.start / duration * 100)); const endPercent = Math.max(startPercent, Math.min(100, range.end / duration * 100));
    leftShade.style.left = "0"; leftShade.style.width = `${startPercent}%`;
    rightShade.style.left = `${endPercent}%`; rightShade.style.right = "0";
    selection.style.left = `${startPercent}%`; selection.style.width = `${Math.max(.15, endPercent - startPercent)}%`;
    playhead.style.left = `${Math.max(0, Math.min(100, player.currentTime / duration * 100))}%`;
    scrubber.value = String(Math.round(Math.max(0, Math.min(1, player.currentTime / duration)) * 1000));
    const wired = Boolean(ui.secondsConnected?.()); durationInput.disabled = wired;
    durationInput.max = String(Math.max(.001, ui.metadata.duration || .001)); durationInput.step = String(Math.max(.001, 1 / Math.max(1, ui.metadata.fps || 1)));
    if (document.activeElement !== durationInput) durationInput.value = (range.end - range.start).toFixed(3);
    durationMode.textContent = wired ? "wired" : "editable";
    label.textContent = `${range.start.toFixed(3)}s (${Math.round(range.start * ui.metadata.fps)}f)  —  ${range.end.toFixed(3)}s (${Math.round(range.end * ui.metadata.fps)}f)  ·  ${(range.end - range.start).toFixed(3)}s`;
  }
  function pointerTime(event) {
    const rect = strip.getBoundingClientRect(); const duration = Math.max(.001, ui.metadata.duration);
    return Math.max(0, Math.min(duration, (event.clientX - rect.left) / rect.width * duration));
  }
  function setPlayhead(time) {
    const duration = Math.max(.001, ui.metadata.duration);
    time = Math.max(0, Math.min(duration, time));
    player.currentTime = time;
    const nativeVideo = ui.nativeVideo?.();
    if (nativeVideo) nativeVideo.currentTime = time;
    draw();
  }
  function beginRangeDrag(event, mode) {
    if (event.button !== 0) return;
    event.preventDefault(); event.stopPropagation();
    const target = event.currentTarget; const pointerId = event.pointerId;
    const original = ui.range(); const anchor = pointerTime(event); const length = original.end - original.start;
    let finished = false;
    const finish = (finalEvent) => {
      if (finished) return; finished = true;
      target.removeEventListener("pointermove", move); target.removeEventListener("pointerup", finish); target.removeEventListener("pointercancel", finish); target.removeEventListener("lostpointercapture", finish);
      if (target.hasPointerCapture?.(pointerId)) target.releasePointerCapture(pointerId);
      finalEvent?.stopPropagation?.();
    };
    const move = (next) => {
      if ((next.buttons & 1) === 0) { finish(next); return; }
      const time = pointerTime(next); const current = ui.range();
      if (mode === "start") ui.setRange(time, current.end, "start");
      else if (mode === "end") ui.setRange(current.start, time, "end");
      else {
        const duration = Math.max(0, ui.metadata.duration || 0); let start = original.start + time - anchor;
        start = Math.max(0, Math.min(Math.max(0, duration - length), start));
        ui.setRange(start, start + length, "start");
      }
      draw();
    };
    target.addEventListener("pointermove", move); target.addEventListener("pointerup", finish); target.addEventListener("pointercancel", finish); target.addEventListener("lostpointercapture", finish);
    target.setPointerCapture?.(pointerId);
  }
  startHandle.addEventListener("pointerdown", (event) => beginRangeDrag(event, "start"));
  endHandle.addEventListener("pointerdown", (event) => beginRangeDrag(event, "end"));
  selection.addEventListener("pointerdown", (event) => { if (!event.target.closest(".workflowx-lvxa-trim-handle")) beginRangeDrag(event, "selection"); });
  strip.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest(".workflowx-lvxa-trim-selection")) return;
    event.preventDefault(); setPlayhead(pointerTime(event));
  });
  scrubber.addEventListener("input", () => {
    const duration = Math.max(.001, ui.metadata.duration);
    setPlayhead(Number(scrubber.value) / 1000 * duration);
  });
  durationInput.addEventListener("change", () => {
    if (ui.secondsConnected?.()) return;
    const value = Math.max(.001, Number(durationInput.value) || 0); const range = ui.range();
    ui.setRange(range.start, range.start + value, "start"); draw();
  });

  async function buildFilmstrip() {
    const token = ++timeline.token; timeline.thumbnails = []; draw();
    if (!ui.sourceURL || !ui.metadata.duration) return;
    const sampler = document.createElement("video"); sampler.muted = true; sampler.preload = "auto"; sampler.src = ui.sourceURL; timeline.sampler = sampler;
    await new Promise((resolve, reject) => { sampler.onloadedmetadata = resolve; sampler.onerror = reject; }).catch(() => null);
    const count = Math.max(4, Math.min(14, Math.floor(canvas.clientWidth / 72) || 8));
    for (let index = 0; index < count && token === timeline.token; index += 1) {
      sampler.currentTime = Math.min(ui.metadata.duration - .001, (index + .5) / count * ui.metadata.duration);
      await new Promise((resolve) => { sampler.onseeked = resolve; setTimeout(resolve, 1200); });
      if (!sampler.videoWidth) continue;
      const image = document.createElement("canvas"); image.width = 144; image.height = Math.max(54, Math.round(144 * sampler.videoHeight / sampler.videoWidth));
      image.getContext("2d").drawImage(sampler, 0, 0, image.width, image.height); timeline.thumbnails.push(image); draw();
    }
    sampler.removeAttribute("src"); sampler.load();
  }
  timeline.load = () => {
    player.src = ui.sourceURL || ""; player.load(); buildFilmstrip(); draw();
  };
  timeline.draw = draw;
  timeline.resizeObserver = new ResizeObserver(draw); timeline.resizeObserver.observe(strip);
  timeline.dispose = () => { timeline.token += 1; timeline.resizeObserver.disconnect(); player.pause(); player.removeAttribute("src"); timeline.sampler?.removeAttribute("src"); };
  ui.dock = createGraphDock({ app, node: ui.node, ownerElement: ui.root, propertyKey: "workflowx_video_timeline_dock", title: "Load VideoX Adv · Timeline", content,
    onClose: () => { timeline.dispose(); ui.dock = null; ui.timeline = null; } });
  timeline.load();
}

function createVideoUI(node, videoWidget, stateWidget) {
  installCSS();
  const root = document.createElement("div"); root.className = "workflowx-lvxa";
  const summary = document.createElement("div"); summary.className = "workflowx-lvxa-summary";
  const dimensionCard = document.createElement("div"); dimensionCard.className = "workflowx-lvxa-card";
  const dimensionLabel = document.createElement("small"); dimensionLabel.textContent = "Output";
  const dimensionValue = document.createElement("div"); dimensionValue.className = "workflowx-lvxa-size"; dimensionValue.textContent = "— × —";
  dimensionCard.append(dimensionLabel, dimensionValue);
  const timelineButton = button("Open Timeline", "Open the floating trim editor"); timelineButton.className = "workflowx-lvxa-card";
  summary.append(dimensionCard, timelineButton);
  const modeButtons = document.createElement("div"); modeButtons.className = "workflowx-lvxa-modes";
  const panel = document.createElement("div"); panel.className = "workflowx-lvxa-panel";
  const outputSnap = document.createElement("div"); outputSnap.className = "workflowx-lvxa-snap";
  const resampleRow = document.createElement("div"); resampleRow.className = "workflowx-lvxa-row";
  const toggles = document.createElement("div"); toggles.className = "workflowx-lvxa-toggles";
  const cropSnap = document.createElement("div"); cropSnap.className = "workflowx-lvxa-snap";
  const canvas = document.createElement("canvas"); const cropSurface = document.createElement("div"); cropSurface.className = "workflowx-lvxa-native-crop-surface";
  const help = document.createElement("div"); help.className = "workflowx-lvxa-help"; help.textContent = "Enable crop, then drag on video";
  canvas.className = "workflowx-lvxa-native-crop";
  root.append(summary, modeButtons, panel, outputSnap, resampleRow, toggles, cropSnap);

  const ui = {
    node, root, canvas, cropSurface, help, sourceURL: "", metadata: { width: 0, height: 0, duration: 0, fps: 30 },
    state: normalizeVideoState(stateWidget.value || DEFAULT_VIDEO_STATE), drag: null, dock: null, timeline: null,
    disposed: false, poll: null, resizeObserver: null, nativePreviewWidget: null, overlayHost: null, overlayPointerHandler: null,
  };
  ui.nativeVideo = () => ui.nativePreviewWidget?.videoEl || null;
  ui.setExecutionStatus = (status) => {
    if (!status) return;
    if (status.wired && Number(status.requested_duration) > 0) ui.executedSeconds = Number(status.requested_duration);
    const notices = [];
    if (status.short) notices.push(`Available ${Number(status.actual_duration || 0).toFixed(3)}s of requested ${Number(status.requested_duration || 0).toFixed(3)}s`);
    if (status.has_audio === false && status.requested_outputs?.includes("audio")) notices.push("Source has no audio");
    help.textContent = notices.join(" · ") || "Enable crop, then drag on video";
  };
  ui.attachNativeOverlay = () => {
    const nativeWidget = findNativeVideoPreview(node, root);
    const video = nativeWidget?.videoEl; const host = video?.parentElement;
    if (!video || !host) return false;
    ui.nativePreviewWidget = nativeWidget;
    let changed = false;
    if (ui.overlayHost !== host || canvas.parentElement !== host) {
      if (ui.overlayHost && ui.overlayPointerHandler) ui.overlayHost.removeEventListener("pointermove", ui.overlayPointerHandler);
      canvas.remove(); cropSurface.remove(); help.remove(); ui.overlayHost = host; changed = true;
      if (getComputedStyle(host).position === "static") host.style.position = "relative";
      host.append(canvas, cropSurface, help);
      ui.overlayPointerHandler = (event) => {
        if (ui.drag) return;
        const rect = video.getBoundingClientRect();
        cropSurface.style.pointerEvents = event.clientY >= rect.bottom - 44 ? "none" : "auto";
      };
      host.addEventListener("pointermove", ui.overlayPointerHandler);
      ui.resizeObserver?.observe?.(host);
    }
    if (!video.__workflowxCropOverlayListener) {
      video.__workflowxCropOverlayListener = true;
      video.addEventListener("loadedmetadata", () => ui.drawPreview?.());
    }
    if (changed) ui.drawPreview?.();
    return true;
  };
  const secondsConnected = () => {
    const input = node.inputs?.find((candidate) => candidate.name === "seconds");
    return input?.link != null;
  };
  ui.secondsConnected = secondsConnected;
  ui.fixedSeconds = () => upstreamSeconds(node) ?? (secondsConnected() ? ui.executedSeconds ?? null : null);
  function markChanged() { node.graph?.change?.(); node.graph?.setDirtyCanvas?.(true, true); node.setDirtyCanvas?.(true, true); }
  ui.layoutHeight = 310;
  ui.reflow = () => {
    if (ui.reflowFrame) cancelAnimationFrame(ui.reflowFrame);
    ui.reflowFrame = requestAnimationFrame(() => {
      ui.reflowFrame = 0;
      if (ui.disposed || !root.isConnected) return;
      const visible = [...root.children].filter((child) => getComputedStyle(child).display !== "none");
      const style = getComputedStyle(root); const gap = Number.parseFloat(style.rowGap || style.gap) || 0;
      const padding = (Number.parseFloat(style.paddingTop) || 0) + (Number.parseFloat(style.paddingBottom) || 0);
      // offsetHeight is expressed in layout pixels. getBoundingClientRect() is
      // transformed by the graph zoom, which made a 279 px controls panel look
      // only ~148 px tall at 53% zoom and caused its final row to be clipped.
      const needed = Math.max(260, Math.ceil(padding + visible.reduce((sum, child) => sum + child.offsetHeight, 0) + Math.max(0, visible.length - 1) * gap));
      const delta = needed - ui.layoutHeight; ui.layoutHeight = needed;
      ui.widget?.callback?.();
      if (!ui.widget || Math.abs(delta) < 1) { node.setDirtyCanvas?.(true, true); return; }
      const width = Math.max(410, Number(node.size?.[0]) || 410); const height = Math.max(520, (Number(node.size?.[1]) || 720) + delta);
      node.setSize?.([width, height]); node.setDirtyCanvas?.(true, true);
    });
  };
  ui.commit = (next, render = true) => {
    ui.state = normalizeVideoState(next); stateWidget.value = JSON.stringify(ui.state); stateWidget.callback?.(stateWidget.value);
    markChanged(); if (render) renderControls(); updateDimensions(); ui.drawPreview(); ui.timeline?.draw?.();
  };
  ui.range = () => normalizeTrimRange(ui.metadata, ui.state, ui.fixedSeconds());
  ui.setRange = (start, end, moved) => {
    const fixed = ui.fixedSeconds();
    let next = { ...ui.state, trim_start: start, trim_end: end };
    const normalized = normalizeTrimRange(ui.metadata, next, fixed, moved);
    next = { ...next, trim_start: normalized.start, trim_end: normalized.end };
    ui.commit(next, false);
  };

  function updateDimensions() {
    const result = computeOutputDimensions(ui.metadata.width || 0, ui.metadata.height || 0, ui.state);
    dimensionValue.textContent = result.width && result.height ? `${result.width} × ${result.height}` : "— × —";
  }
  function addInput(label, key, options = {}) {
    const input = field(ui.state[key], options, (value) => ui.commit({ ...ui.state, [key]: value })); panel.append(row(label, input));
  }
  function twoInputs(label, leftKey, rightKey, options = {}) {
    const grid = document.createElement("div"); grid.className = "workflowx-lvxa-grid";
    grid.append(field(ui.state[leftKey], options, (value) => ui.commit({ ...ui.state, [leftKey]: value })),
      field(ui.state[rightKey], options, (value) => ui.commit({ ...ui.state, [rightKey]: value })));
    panel.append(row(label, grid));
  }
  function renderPanel() {
    panel.replaceChildren(); panel.style.display = ui.state.mode === "off" ? "none" : "block";
    if (ui.state.mode === "max_mp") addInput("Megapixels", "max_mp", { min: .01, max: 64, step: .05 });
    else if (ui.state.mode === "longest_side") addInput("Longest side", "longest_side", { min: 8, max: 16384 });
    else if (ui.state.mode === "scale_factor") addInput("Scale", "scale_factor", { min: .01, max: 8, step: .05 });
    else if (ui.state.mode === "fit_inside") twoInputs("Width × height", "fit_w", "fit_h", { min: 8, max: 16384 });
    else if (ui.state.mode === "cover") {
      twoInputs("Width × height", "cover_w", "cover_h", { min: 8, max: 16384 });
      const action = document.createElement("select");
      for (const [value, text] of [["fill", "Scale + crop"], ["crop", "Crop only"]]) { const option = new Option(text, value); action.append(option); }
      action.value = ui.state.cover_action; action.onchange = () => ui.commit({ ...ui.state, cover_action: action.value }); panel.append(row("Action", action));
      const anchor = document.createElement("select");
      for (const value of ["top-left", "top", "top-right", "left", "center", "right", "bottom-left", "bottom", "bottom-right"]) anchor.append(new Option(value, value));
      anchor.value = ui.state.crop_anchor; anchor.onchange = () => ui.commit({ ...ui.state, crop_anchor: anchor.value }); panel.append(row("Anchor", anchor));
    } else if (ui.state.mode === "match_ratio") {
      const preset = document.createElement("select");
      for (const value of ["1:1", "16:9", "9:16", "2:1", "3:2", "2:3", "4:3", "3:4", "4:5", "21:9", "5:4", "custom"]) preset.append(new Option(value, value));
      preset.value = ui.state.ratio_preset || "custom";
      preset.onchange = () => {
        if (preset.value === "custom") ui.commit({ ...ui.state, ratio_preset: "custom" });
        else { const [ratioW, ratioH] = preset.value.split(":").map(Number); ui.commit({ ...ui.state, ratio_preset: preset.value, ratio_w: ratioW, ratio_h: ratioH }); }
      };
      panel.append(row("Preset", preset));
      if (preset.value === "custom") twoInputs("Ratio", "ratio_w", "ratio_h", { min: .01, max: 100, step: .01 });
    }
    else if (ui.state.mode === "pad") {
      twoInputs("Left / right", "pad_left", "pad_right", { min: 0, max: 8192 });
      twoInputs("Top / bottom", "pad_top", "pad_bottom", { min: 0, max: 8192 });
      const color = field(ui.state.pad_color, { type: "color" }, (value) => ui.commit({ ...ui.state, pad_color: value })); panel.append(row("Color", color));
    }
  }
  function renderControls() {
    modeButtons.replaceChildren();
    for (const [value, text] of MODES) { const item = button(text); item.classList.toggle("active", ui.state.mode === value); item.onclick = () => ui.commit({ ...ui.state, mode: value }); modeButtons.append(item); }
    renderPanel();
    outputSnap.replaceChildren(); const label = document.createElement("label"); label.textContent = "OUTPUT SNAP"; outputSnap.append(label);
    for (const snap of SNAP_OPTIONS) { const item = button(snap ? String(snap) : "Off"); item.classList.toggle("active", ui.state.output_snap === snap); item.onclick = () => ui.commit({ ...ui.state, output_snap: snap }); outputSnap.append(item); }
    resampleRow.replaceChildren(); const resampleLabel = document.createElement("label"); resampleLabel.textContent = "Resample";
    const resample = document.createElement("select");
    for (const value of ["auto", "nearest", "bilinear", "bicubic", "lanczos"]) resample.append(new Option(value[0].toUpperCase() + value.slice(1), value));
    resample.value = ui.state.resample; resample.onchange = () => ui.commit({ ...ui.state, resample: resample.value }); resampleRow.append(resampleLabel, resample);
    toggles.replaceChildren(); const crop = button(`Crop: ${ui.state.crop_enabled ? "On" : "Off"}`); crop.classList.toggle("active", ui.state.crop_enabled);
    crop.onclick = () => ui.commit({ ...ui.state, crop_enabled: !ui.state.crop_enabled });
    const upscale = button(`Upscaling: ${ui.state.allow_upscale ? "On" : "Off"}`); upscale.classList.toggle("active", ui.state.allow_upscale);
    upscale.onclick = () => ui.commit({ ...ui.state, allow_upscale: !ui.state.allow_upscale }); toggles.append(crop, upscale);
    cropSnap.replaceChildren(); cropSnap.style.display = ui.state.crop_enabled ? "flex" : "none"; const cropLabel = document.createElement("label"); cropLabel.textContent = "CROP SNAP"; cropSnap.append(cropLabel);
    for (const snap of SNAP_OPTIONS) { const item = button(snap ? String(snap) : "Off"); item.classList.toggle("active", ui.state.crop_snap === snap); item.onclick = () => ui.commit({ ...ui.state, crop_snap: snap }); cropSnap.append(item); }
    cropSurface.style.pointerEvents = "auto";
    cropSurface.style.cursor = ui.state.crop_enabled ? "crosshair" : "default";
    help.textContent = ui.state.crop_enabled ? "Drag to draw or adjust crop" : "Enable crop, then drag on video";
    ui.reflow();
  }

  function canvasMetrics() {
    const rect = canvas.getBoundingClientRect(); const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(rect.width * ratio)); const height = Math.max(1, Math.round(rect.height * ratio));
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    const nativeVideo = ui.nativeVideo();
    const sourceW = ui.metadata.width || nativeVideo?.videoWidth || 1; const sourceH = ui.metadata.height || nativeVideo?.videoHeight || 1;
    const scale = Math.min(canvas.width / sourceW, canvas.height / sourceH);
    return { sourceW, sourceH, scale, x: (canvas.width - sourceW * scale) / 2, y: (canvas.height - sourceH * scale) / 2, ratio };
  }
  ui.drawPreview = () => {
    if (!canvas.isConnected) return;
    const metric = canvasMetrics(); const ctx = canvas.getContext("2d"); ctx.clearRect(0, 0, canvas.width, canvas.height);
    const crop = pixelRectFromState(metric.sourceW, metric.sourceH, ui.state);
    if (crop) {
      const x = metric.x + crop.x * metric.scale, y = metric.y + crop.y * metric.scale, w = crop.w * metric.scale, h = crop.h * metric.scale;
      ctx.fillStyle = "rgba(0,0,0,.5)"; ctx.fillRect(metric.x, metric.y, metric.sourceW * metric.scale, y - metric.y); ctx.fillRect(metric.x, y + h, metric.sourceW * metric.scale, metric.y + metric.sourceH * metric.scale - y - h); ctx.fillRect(metric.x, y, x - metric.x, h); ctx.fillRect(x + w, y, metric.x + metric.sourceW * metric.scale - x - w, h);
      ctx.strokeStyle = ACCENT; ctx.lineWidth = 2 * metric.ratio; ctx.strokeRect(x, y, w, h);
      ctx.fillStyle = ACCENT;
      for (const [hx, hy] of [[x, y], [x + w, y], [x, y + h], [x + w, y + h]]) ctx.fillRect(hx - 4 * metric.ratio, hy - 4 * metric.ratio, 8 * metric.ratio, 8 * metric.ratio);
    }
  };

  function sourcePoint(event) {
    const rect = canvas.getBoundingClientRect(); const metric = canvasMetrics(); const sx = canvas.width / rect.width, sy = canvas.height / rect.height;
    return { x: Math.max(0, Math.min(metric.sourceW, ((event.clientX - rect.left) * sx - metric.x) / metric.scale)), y: Math.max(0, Math.min(metric.sourceH, ((event.clientY - rect.top) * sy - metric.y) / metric.scale)), metric };
  }
  function hitCrop(point) {
    const current = pixelRectFromState(point.metric.sourceW, point.metric.sourceH, ui.state);
    if (!current) return { mode: "new", current: null };
    const threshold = 12 * point.metric.ratio / Math.max(.001, point.metric.scale);
    const corners = {
      "top-left": [current.x, current.y], "top-right": [current.x + current.w, current.y],
      "bottom-left": [current.x, current.y + current.h], "bottom-right": [current.x + current.w, current.y + current.h],
    };
    for (const [corner, [x, y]] of Object.entries(corners)) {
      if (Math.abs(point.x - x) <= threshold && Math.abs(point.y - y) <= threshold) return { mode: "resize", corner, current };
    }
    if (point.x >= current.x && point.x <= current.x + current.w && point.y >= current.y && point.y <= current.y + current.h) return { mode: "move", current };
    return { mode: "new", current };
  }
  cropSurface.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || !event.isPrimary) return;
    event.preventDefault(); event.stopPropagation();
    if (!ui.state.crop_enabled) return;
    const point = sourcePoint(event);
    ui.drag = { startX: point.x, startY: point.y, ...hitCrop(point), moved: false, pointerId: event.pointerId }; cropSurface.setPointerCapture?.(event.pointerId);
  });
  cropSurface.addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); });
  cropSurface.addEventListener("pointermove", (event) => {
    if (!ui.state.crop_enabled) return;
    if (ui.drag && (event.buttons & 1) === 0) { finishCrop(event); return; }
    const point = sourcePoint(event);
    if (!ui.drag) {
      const hit = hitCrop(point); cropSurface.style.cursor = hit.mode === "move" ? "grab" : hit.mode === "resize" ? "nwse-resize" : "crosshair"; return;
    }
    const drag = ui.drag; drag.moved ||= Math.abs(point.x - drag.startX) + Math.abs(point.y - drag.startY) > 1;
    let rect; let fixedCorner = "top-left";
    if (drag.mode === "move" && drag.current) {
      rect = { ...drag.current,
        x: Math.max(0, Math.min(point.metric.sourceW - drag.current.w, drag.current.x + point.x - drag.startX)),
        y: Math.max(0, Math.min(point.metric.sourceH - drag.current.h, drag.current.y + point.y - drag.startY)) };
    } else if (drag.mode === "resize" && drag.current) {
      const opposite = {
        "top-left": { x: drag.current.x + drag.current.w, y: drag.current.y + drag.current.h, fixed: "bottom-right" },
        "top-right": { x: drag.current.x, y: drag.current.y + drag.current.h, fixed: "bottom-left" },
        "bottom-left": { x: drag.current.x + drag.current.w, y: drag.current.y, fixed: "top-right" },
        "bottom-right": { x: drag.current.x, y: drag.current.y, fixed: "top-left" },
      }[drag.corner];
      rect = { x: Math.min(point.x, opposite.x), y: Math.min(point.y, opposite.y), w: Math.max(1, Math.abs(point.x - opposite.x)), h: Math.max(1, Math.abs(point.y - opposite.y)) };
      fixedCorner = opposite.fixed;
    } else {
      rect = { x: Math.min(drag.startX, point.x), y: Math.min(drag.startY, point.y), w: Math.max(1, Math.abs(point.x - drag.startX)), h: Math.max(1, Math.abs(point.y - drag.startY)) };
      fixedCorner = `${point.y < drag.startY ? "bottom" : "top"}-${point.x < drag.startX ? "right" : "left"}`;
    }
    if (drag.mode !== "move") rect = snapCropRect(rect, point.metric.sourceW, point.metric.sourceH, ui.state.crop_snap, fixedCorner);
    ui.state = normalizeVideoState({ ...ui.state, crop_rect: normalizedRect(rect, point.metric.sourceW, point.metric.sourceH) }); stateWidget.value = JSON.stringify(ui.state); updateDimensions(); ui.drawPreview();
  });
  const finishCrop = (event) => {
    if (!ui.drag) return; const drag = ui.drag; ui.drag = null;
    if (cropSurface.hasPointerCapture?.(drag.pointerId)) cropSurface.releasePointerCapture(drag.pointerId);
    if (drag.mode === "new" && !drag.moved && drag.current) ui.state = normalizeVideoState({ ...ui.state, crop_rect: null });
    stateWidget.value = JSON.stringify(ui.state); stateWidget.callback?.(stateWidget.value); markChanged(); updateDimensions(); ui.drawPreview();
  };
  cropSurface.addEventListener("pointerup", finishCrop); cropSurface.addEventListener("pointercancel", finishCrop); cropSurface.addEventListener("lostpointercapture", finishCrop);
  timelineButton.onclick = () => createTimeline(ui);

  let lastVideo = "";
  async function loadVideo(reason = "external") {
    const selected = String(videoWidget.value || ""); if (!selected) return;
    if (reason !== "restore") ui.state = clearForVideoChange(ui.state);
    stateWidget.value = JSON.stringify(ui.state);
    const token = selected;
    try {
      const response = await fetch(`/workflowx_configurator/load_video_x/metadata?path=${encodeURIComponent(selected)}`); const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`); if (String(videoWidget.value || "") !== token) return;
      ui.metadata = data; ui.sourceURL = videoViewURL(selected, data.version); ui.attachNativeOverlay();
      const range = normalizeTrimRange(data, ui.state, ui.fixedSeconds()); ui.state = normalizeVideoState({ ...ui.state, trim_start: range.start, trim_end: range.end }); stateWidget.value = JSON.stringify(ui.state);
      updateDimensions(); renderControls(); ui.timeline?.load?.(); ui.drawPreview();
    } catch (error) { dimensionValue.textContent = "Video error"; console.warn("[WorkflowX Load VideoX Adv]", error); }
  }
  const originalVideoCallback = videoWidget.callback;
  videoWidget.callback = function (value) {
    const result = originalVideoCallback?.apply(this, arguments); const selected = String(value ?? videoWidget.value ?? "");
    if (selected !== lastVideo) { lastVideo = selected; loadVideo("change"); } return result;
  };
  ui.poll = window.setInterval(() => {
    if (ui.disposed) return; const selected = String(videoWidget.value || "");
    ui.attachNativeOverlay();
    if (selected !== lastVideo) { lastVideo = selected; loadVideo("change"); }
    const fixed = ui.fixedSeconds(); if (fixed !== ui.lastFixed) { ui.lastFixed = fixed; const range = ui.range(); ui.state.trim_start = range.start; ui.state.trim_end = range.end; stateWidget.value = JSON.stringify(ui.state); ui.timeline?.draw?.(); }
  }, 300);
  ui.resizeObserver = new ResizeObserver(() => { ui.drawPreview(); ui.timeline?.draw?.(); }); ui.resizeObserver.observe(root);
  ui.dispose = () => {
    ui.disposed = true; clearInterval(ui.poll); if (ui.reflowFrame) cancelAnimationFrame(ui.reflowFrame); ui.resizeObserver.disconnect(); ui.dock?.close?.();
    if (ui.overlayHost && ui.overlayPointerHandler) ui.overlayHost.removeEventListener("pointermove", ui.overlayPointerHandler);
    canvas.remove(); cropSurface.remove(); help.remove();
  };
  ui.restore = () => {
    ui.state = normalizeVideoState(stateWidget.value || DEFAULT_VIDEO_STATE); renderControls();
    lastVideo = String(videoWidget.value || ""); if (lastVideo) loadVideo("restore"); else { updateDimensions(); ui.drawPreview(); }
  };
  ui.restore();
  return ui;
}

function attach(node) {
  if ((node.comfyClass !== NODE_NAME && node.type !== NODE_NAME) || node.__workflowXLoadVideoAdvReady) return;
  node.__workflowXLoadVideoAdvReady = true;
  queueMicrotask(() => {
    const videoWidget = node.widgets?.find((widget) => widget.name === "video"); const stateWidget = node.widgets?.find((widget) => widget.name === "workflowx_state");
    if (!videoWidget || !stateWidget) { node.__workflowXLoadVideoAdvReady = false; return; }
    hideWidget(stateWidget); const ui = createVideoUI(node, videoWidget, stateWidget);
    // Keep the controls at their measured content height.  The native video
    // preview is a separate ComfyUI DOM widget and should be the only flexible
    // area when the node is resized; allowing both widgets to flex lets the
    // preview consume the crop-snap row and visually overlap the controls.
    const widget = node.addDOMWidget("workflowx_load_video_x_adv", "custom", ui.root, { serialize: false, getMinHeight: () => ui.layoutHeight, getMaxHeight: () => ui.layoutHeight, margin: 0 });
    widget.computeLayoutSize = () => ({ minHeight: ui.layoutHeight, maxHeight: ui.layoutHeight, minWidth: 390 });
    ui.widget = widget; ui.attachNativeOverlay();
    const currentHeight = Number(node.size?.[1]) || 720;
    node.setSize?.([Math.max(410, Number(node.size?.[0]) || 410), Math.max(620, Math.min(1120, currentHeight))]);
    ui.reflow();
    const configured = node.onConfigure;
    node.onConfigure = function () { const result = configured?.apply(this, arguments); queueMicrotask(ui.restore); return result; };
    const executed = node.onExecuted;
    node.onExecuted = function (message) {
      const result = executed?.apply(this, arguments);
      queueMicrotask(ui.attachNativeOverlay);
      ui.setExecutionStatus(message?.workflowx_load_video_x_adv?.[0]);
      return result;
    };
    const removed = node.onRemoved; node.onRemoved = function () { ui.dispose(); return removed?.apply(this, arguments); };
  });
}

installPromptMask();
app.registerExtension({
  name: "WorkflowX.LoadVideoXAdv",
  setup() { installPromptMask(); },
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_NAME) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () { const result = created?.apply(this, arguments); attach(this); return result; };
  },
  nodeCreated: attach,
  loadedGraphNode: attach,
});
