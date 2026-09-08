import { audioOnlyInputs } from "./voice_changer_x_matching.mjs";

const LABELS = {
  pitch_shift: "Pitch · semitones",
  formant_shift: "Formant · semitones",
  timbre: "Timbre · dB/octave",
  breathiness: "Breathiness · %",
  pitch_variation: "Pitch variation · %",
  output_gain: "Output gain · dB",
};

export function normalizeValue(raw, spec, previous) {
  if (String(raw).trim() === "" || !Number.isFinite(Number(raw))) return previous;
  const value = Math.min(spec.max, Math.max(spec.min, Number(raw)));
  const decimals = Math.max(0, Math.round(-Math.log10(spec.step)));
  return Number((Math.round(value / spec.step) * spec.step).toFixed(decimals));
}

export function mountVoiceControls(node, definitions, matchReference) {
  const root = document.createElement("div");
  root.className = "workflowx-voice-controls";
  root.style.cssText = "box-sizing:border-box;width:100%;padding:8px 10px;color:var(--input-text,#ddd);font:12px sans-serif;display:flex;flex-direction:column;gap:10px;";
  const rows = [];
  let revision = 0, disposed = false, busy = false;
  let editing = false;
  const begin = () => {
    if (!editing) {
      node.graph?.beforeChange?.();
      node.graph?.canvasAction?.(canvas => canvas.emitBeforeChange?.());
      editing = true;
    }
  };
  const end = () => {
    if (editing) {
      editing = false;
      node.graph?.afterChange?.();
      node.graph?.canvasAction?.(canvas => canvas.emitAfterChange?.());
    }
  };
  const sync = () => {
    for (const { name, widget, slider, number } of rows) {
      if (document.activeElement !== number) number.value = String(widget.value);
      slider.value = String(widget.value);
      if (widget.type !== "converted-widget") {
        widget.computeSize = () => [0, -4];
        widget.draw = () => {};
      }
    }
  };
  const commit = (row, raw) => {
    const value = normalizeValue(raw, row.spec, row.widget.value);
    if (value !== row.widget.value) {
      begin();
      revision++;
      const previous = row.widget.value;
      row.widget.value = value;
      row.widget.callback?.call(row.widget, value, node.graph?.canvas, node);
      node.onWidgetChanged?.(row.name, value, previous, row.widget);
      node.setDirtyCanvas?.(true, true);
    }
    row.slider.value = row.number.value = String(row.widget.value);
  };
  for (const [name, [, spec]] of Object.entries(definitions)) {
    if (!(name in LABELS)) continue;
    const widget = node.widgets?.find(item => item.name === name);
    if (!widget) continue;
    const group = document.createElement("label");
    group.title = spec.tooltip || "";
    group.style.cssText = "display:flex;flex-direction:column;gap:4px;";
    const caption = document.createElement("span");
    caption.textContent = LABELS[name];
    const line = document.createElement("div");
    line.style.cssText = "display:flex;align-items:center;gap:8px;";
    const slider = document.createElement("input");
    slider.type = "range";
    slider.style.cssText = "flex:1;min-width:0;accent-color:#ce7894;";
    const number = document.createElement("input");
    number.type = "number";
    number.style.cssText = "box-sizing:border-box;width:82px;background:var(--comfy-input-bg,#222);color:inherit;border:1px solid var(--border-color,#555);border-radius:4px;padding:4px;";
    for (const input of [slider, number]) {
      input.min = spec.min; input.max = spec.max; input.step = spec.step;
      input.setAttribute("aria-label", LABELS[name]);
      input.addEventListener("pointerdown", event => event.stopPropagation());
    }
    const row = { name, widget, spec, slider, number };
    slider.addEventListener("input", () => commit(row, slider.value));
    for (const event of ["change", "pointerup", "pointercancel", "blur"]) slider.addEventListener(event, end);
    number.addEventListener("change", () => { commit(row, number.value); end(); });
    number.addEventListener("keydown", event => { event.stopPropagation(); if (event.key === "Enter") number.blur(); });
    line.append(slider, number); group.append(caption, line); root.append(group); rows.push(row);
  }
  const reset = document.createElement("button");
  reset.type = "button"; reset.textContent = "Reset all";
  reset.title = "Restore all six voice controls to their neutral defaults.";
  reset.style.cssText = "padding:5px;border:1px solid var(--border-color,#555);border-radius:4px;background:var(--comfy-input-bg,#222);color:inherit;cursor:pointer;";
  reset.addEventListener("click", () => { revision++; for (const row of rows) commit(row, row.spec.default); end(); sync(); status.textContent = "Controls reset. Queue to preview."; });
  const match = document.createElement("button");
  match.type = "button"; match.textContent = "Match Reference";
  match.title = "Analyze the connected source and reference voices, then fill the sliders with approximate matching settings.";
  match.style.cssText = reset.style.cssText + "border-color:#ce7894;";
  const status = document.createElement("div");
  status.setAttribute("role", "status");
  status.style.cssText = "height:44px;min-height:44px;overflow:auto;white-space:pre-wrap;line-height:1.35;color:#b8b8bd;";
  status.textContent = "Connect reference audio, then Match Reference. Queue to preview.";
  match.addEventListener("click", async () => {
    if (busy || !matchReference) return;
    const started = revision;
    const startedValues = rows.map(row => row.widget.value);
    busy = true; match.disabled = true; match.textContent = "Matching…";
    status.textContent = "Queued source/reference analysis…";
    try {
      const report = await matchReference(node, () => disposed);
      if (disposed) return;
      if (started !== revision || rows.some((row, index) => row.widget.value !== startedValues[index])) throw new Error("Controls changed during matching; estimates were not applied. Match again when ready.");
      // Validate the whole response before changing a single widget.
      if (!rows.every(row => Number.isFinite(report.settings?.[row.name]))) throw new Error("Reference analysis returned incomplete settings.");
      for (const row of rows) commit(row, report.settings[row.name]);
      end(); sync();
      const pitch = report.source && report.reference ? `Pitch ${report.source.median_pitch_hz.toFixed(0)} → ${report.reference.median_pitch_hz.toFixed(0)} Hz. ` : "";
      status.textContent = `${pitch}Approximate match applied. Fine-tune and queue to preview.${report.warnings?.length ? "\n" + report.warnings.join("\n") : ""}`;
    } catch (error) {
      if (!disposed) status.textContent = error?.message || String(error);
    } finally {
      end(); busy = false;
      if (!disposed) { match.disabled = false; match.textContent = "Match Reference"; }
    }
  });
  const actions = document.createElement("div");
  actions.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:8px;";
  actions.append(match, reset); root.append(actions, status);
  const domWidget = node.addDOMWidget("voice_changer_controls", "custom", root, { serialize: false, hideOnZoom: false });
  domWidget.computeSize = () => [320, 395];
  domWidget.computeLayoutSize = () => ({ minWidth: 320, minHeight: 395, maxHeight: 395 });
  for (const hook of ["onWidgetChanged", "onDrawForeground"]) {
    const original = node[hook];
    node[hook] = function (...args) { const result = original?.apply(this, args); sync(); return result; };
  }
  const configured = node.onConfigure;
  node.onConfigure = function (...args) { const result = configured?.apply(this, args); revision++; audioOnlyInputs(this); sync(); return result; };
  const connections = node.onConnectionsChange;
  node.onConnectionsChange = function (...args) { revision++; return connections?.apply(this, args); };
  const removed = node.onRemoved;
  node.onRemoved = function (...args) { disposed = true; end(); return removed?.apply(this, args); };
  audioOnlyInputs(node);
  sync();
  node.setSize?.([Math.max(340, node.size?.[0] || 0), Math.max(470, node.size?.[1] || 0)]);
  return { root, rows, reset, match, status, sync };
}
