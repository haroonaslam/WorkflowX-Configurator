import { app } from "/scripts/app.js";
import { openLoadImageXPicker, installLoadImageXBrowserCSS } from "./load_image_x.js";
import { viewURL } from "./load_image_x_helpers.mjs";
import {
  DEFAULT_ADV_STATE,
  clearCropForImageChange,
  computeOutputDimensions,
  normalizeAdvState,
  normalizedRect,
  pixelRectFromState,
  snapCropRect,
} from "./load_image_x_adv_helpers.mjs";

const ACCENT = "#7aa2f7";
const MIN_WIDTH = 380;
const PREVIEW_FLOOR = 170;
const SNAP_OPTIONS = [0, 8, 16, 32, 64];
const MODE_OPTIONS = [
  ["off", "Off"], ["max_mp", "Max MP"], ["longest_side", "Longest side"],
  ["scale_factor", "Scale by x"], ["fit_inside", "Fit inside"],
  ["cover", "Crop to fill"], ["match_ratio", "Match ratio"], ["pad", "Pad"],
];
const RESAMPLE_OPTIONS = [
  ["auto", "Auto"], ["nearest", "Nearest"], ["bilinear", "Bilinear"],
  ["bicubic", "Bicubic"], ["lanczos", "Lanczos"],
];
const RATIO_OPTIONS = [
  ["1:1", 1, 1], ["16:9", 16, 9], ["9:16", 9, 16], ["2:1", 2, 1],
  ["3:2", 3, 2], ["2:3", 2, 3], ["4:3", 4, 3], ["3:4", 3, 4],
  ["4:5", 4, 5], ["21:9", 21, 9], ["5:4", 5, 4], ["custom", null, null],
];
const ANCHORS = [
  "top-left", "top", "top-right", "left", "center", "right",
  "bottom-left", "bottom", "bottom-right",
];

let cssInstalled = false;

function installCSS() {
  if (cssInstalled) return;
  cssInstalled = true;
  const style = document.createElement("style");
  style.textContent = `
    .workflowx-lixa {
      --lixa-accent:${ACCENT}; width:100%; height:100%; min-height:0; box-sizing:border-box;
      padding:4px 8px 8px; display:flex; flex-direction:column; gap:7px; overflow:hidden;
      color:#d9dce2; font:11px ui-sans-serif,system-ui,sans-serif; letter-spacing:0;
    }
    .workflowx-lixa *, .workflowx-lixa *::before, .workflowx-lixa *::after { box-sizing:border-box; }
    .workflowx-lixa button, .workflowx-lixa input, .workflowx-lixa select { font:inherit; letter-spacing:0; }
    .workflowx-lixa-browse { height:36px; flex:none; border:1px solid #5876a4; border-radius:4px;
      background:#263952; color:#f2f6ff; cursor:pointer; font-weight:650; }
    .workflowx-lixa-browse:hover { border-color:var(--lixa-accent); background:#304b6d; }
    .workflowx-lixa-modes { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:5px; flex:none; }
    .workflowx-lixa-chip, .workflowx-lixa-toggle, .workflowx-lixa-segment button, .workflowx-lixa-ratio,
    .workflowx-lixa-command, .workflowx-lixa-swap {
      min-width:0; height:30px; border:1px solid #4b5058; border-radius:4px; background:#202226;
      color:#c0c4ca; cursor:pointer; padding:0 6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    }
    .workflowx-lixa-chip:hover, .workflowx-lixa-toggle:hover, .workflowx-lixa-segment button:hover,
    .workflowx-lixa-ratio:hover, .workflowx-lixa-command:hover, .workflowx-lixa-swap:hover {
      border-color:var(--lixa-accent); color:#fff;
    }
    .workflowx-lixa-chip.active, .workflowx-lixa-toggle.active, .workflowx-lixa-segment button.active,
    .workflowx-lixa-ratio.active { border-color:var(--lixa-accent); background:#385a86; color:#fff; }
    .workflowx-lixa-panel { flex:none; padding:8px; border:1px solid #3e4249; border-radius:4px;
      background:#24262a; display:flex; flex-direction:column; gap:7px; }
    .workflowx-lixa-row { min-width:0; min-height:30px; display:flex; align-items:center; justify-content:center; gap:6px; }
    .workflowx-lixa-label { color:#9298a1; font-size:9px; text-transform:uppercase; white-space:nowrap; }
    .workflowx-lixa-field { min-width:0; flex:1; display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:5px; }
    .workflowx-lixa-number { width:100%; min-width:52px; height:30px; border:1px solid #4b5058; border-radius:4px;
      background:#17191c; color:#edf1f7; text-align:center; outline:none; }
    .workflowx-lixa-number:focus { border-color:var(--lixa-accent); }
    .workflowx-lixa-quick { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:4px; }
    .workflowx-lixa-quick .workflowx-lixa-chip { height:27px; padding:0 3px; font-size:9px; }
    .workflowx-lixa-swap { width:30px; flex:none; color:var(--lixa-accent); font-size:14px; padding:0; }
    .workflowx-lixa-aspect { width:38px; height:28px; flex:none; display:grid; place-items:center; }
    .workflowx-lixa-aspect-shape { display:block; max-width:30px; max-height:21px; border:1px solid var(--lixa-accent);
      background:rgba(122,162,247,.13); border-radius:2px; }
    .workflowx-lixa-segment { display:grid; grid-template-columns:1fr 1fr; gap:4px; }
    .workflowx-lixa-anchors { width:92px; display:grid; grid-template-columns:repeat(3,1fr); gap:4px; margin:0 auto; }
    .workflowx-lixa-anchor { height:20px; border:1px solid #4b5058; border-radius:3px; background:#191b1f; cursor:pointer; }
    .workflowx-lixa-anchor.active { border-color:var(--lixa-accent); background:#557caf; }
    .workflowx-lixa-ratios { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:4px; }
    .workflowx-lixa-ratio { height:35px; padding:2px 3px; display:flex; flex-direction:column; align-items:center;
      justify-content:center; gap:2px; font-size:8px; }
    .workflowx-lixa-ratio-shape { display:block; border:1px solid currentColor; opacity:.8; min-width:7px; min-height:5px; }
    .workflowx-lixa-padgrid { display:grid; grid-template-columns:minmax(70px,1fr) minmax(80px,1fr) minmax(70px,1fr);
      grid-template-rows:30px 30px 30px; align-items:center; gap:5px; }
    .workflowx-lixa-padgrid .top { grid-column:2; grid-row:1; } .workflowx-lixa-padgrid .left { grid-column:1; grid-row:2; }
    .workflowx-lixa-padgrid .center { grid-column:2; grid-row:2; } .workflowx-lixa-padgrid .right { grid-column:3; grid-row:2; }
    .workflowx-lixa-padgrid .bottom { grid-column:2; grid-row:3; }
    .workflowx-lixa-color { width:100%; height:30px; padding:2px; border:1px solid #4b5058; border-radius:4px; background:#17191c; }
    .workflowx-lixa-padfooter { display:grid; grid-template-columns:1fr auto 1fr; gap:6px; align-items:center; }
    .workflowx-lixa-live { color:var(--lixa-accent); font-weight:650; text-align:center; }
    .workflowx-lixa-snaprow { height:28px; flex:none; display:flex; align-items:center; justify-content:center; gap:5px; }
    .workflowx-lixa-snaprow .workflowx-lixa-chip { width:34px; height:26px; padding:0; font-size:9px; }
    .workflowx-lixa-resample { height:32px; flex:none; display:grid; grid-template-columns:31px 1fr 31px; gap:5px; }
    .workflowx-lixa-resample button, .workflowx-lixa-resample select { border:1px solid #4b5058; border-radius:4px;
      background:#202226; color:#d9dce2; cursor:pointer; }
    .workflowx-lixa-resample button { color:var(--lixa-accent); }
    .workflowx-lixa-toggles { height:32px; flex:none; display:grid; grid-template-columns:1fr 1fr; gap:6px; }
    .workflowx-lixa-preview { min-height:${PREVIEW_FLOOR}px; flex:1 1 ${PREVIEW_FLOOR}px; position:relative; overflow:hidden;
      background:#141518; border:1px solid #343840; border-radius:3px; }
    .workflowx-lixa-preview canvas { width:100%; height:100%; display:block; touch-action:none; }
    .workflowx-lixa-port-card { position:absolute; left:12px; top:38px; right:142px; height:88px; z-index:5;
      pointer-events:none; display:flex; align-items:center; justify-content:center; gap:11px; border:1px solid #434a55;
      border-radius:5px; background:#25282d; box-shadow:inset 0 1px rgba(255,255,255,.025); color:#d9dce2; }
    .workflowx-lixa-port-card-label { color:#969da7; font-size:9px; text-transform:uppercase; }
    .workflowx-lixa-port-card-size { color:var(--lixa-accent); font-weight:700; font-size:15px; }
    .workflowx-lixa-port-card-shape { display:block; border:1px solid var(--lixa-accent); background:rgba(122,162,247,.12); border-radius:2px; }
    .lg-node.workflowx-lixa-host .image-preview { display:none !important; min-height:0 !important; height:0 !important; }
  `;
  document.head.appendChild(style);
}

function hideWidget(widget) {
  if (!widget) return;
  if (!widget._workflowxOriginalType) widget._workflowxOriginalType = widget.type;
  widget.hidden = true;
  widget.type = "hidden";
  widget.options = { ...(widget.options || {}), hidden: true };
  widget.draw = () => {};
  widget.computeSize = () => [0, -4];
  widget.computeLayoutSize = () => ({ minHeight: 0, maxHeight: 0, minWidth: 0 });
}

function button(text, className = "workflowx-lixa-chip") {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  element.textContent = text;
  return element;
}

function numericInput(value, { min = 0, max = 16384, step = 1, title = "", onCommit }) {
  const input = document.createElement("input");
  input.type = "number";
  input.className = "workflowx-lixa-number";
  input.value = String(value);
  input.min = String(min);
  input.max = String(max);
  input.step = String(step);
  input.title = title;
  const commit = () => {
    const number = Math.max(min, Math.min(max, Number(input.value)));
    if (!Number.isFinite(number)) return;
    input.value = String(number);
    onCommit(number);
  };
  input.addEventListener("change", commit);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); commit(); input.blur(); }
  });
  return input;
}

function isAdvancedNode(node) {
  return node?.comfyClass === "WorkflowX_LoadImageXAdv" || node?.type === "WorkflowX_LoadImageXAdv";
}

function createAdvancedUI(node, imageWidget, stateWidget) {
  installCSS();
  installLoadImageXBrowserCSS();

  const root = document.createElement("div");
  root.className = "workflowx-lixa";
  const browse = button("Browse Thumbnails", "workflowx-lixa-browse");
  browse.title = "Browse images in ComfyUI input folders";
  const modes = document.createElement("div");
  modes.className = "workflowx-lixa-modes";
  const outputSnap = document.createElement("div");
  outputSnap.className = "workflowx-lixa-snaprow";
  const resample = document.createElement("div");
  resample.className = "workflowx-lixa-resample";
  const toggles = document.createElement("div");
  toggles.className = "workflowx-lixa-toggles";
  const cropSnap = document.createElement("div");
  cropSnap.className = "workflowx-lixa-snaprow";
  const preview = document.createElement("div");
  preview.className = "workflowx-lixa-preview";
  const canvas = document.createElement("canvas");
  preview.appendChild(canvas);
  root.append(browse, modes, outputSnap, resample, toggles, preview);

  const ui = {
    root, source: null, sourcePath: "", imageBox: null, drag: null, panel: null,
    loadSequence: 0, state: normalizeAdvState(stateWidget.value || DEFAULT_ADV_STATE),
    widget: null, resizeObserver: null, imagePoll: null, portalCard: null,
    output: { width: 0, height: 0 }, pendingBrowserSelection: false, disposed: false,
  };

  function markChanged() {
    node.graph?.setDirtyCanvas?.(true, true);
    node.setDirtyCanvas?.(true, true);
    node.graph?.change?.();
  }

  function fixedContentHeight() {
    const children = [...root.children].filter((child) => child !== preview && child.offsetParent !== null);
    const content = children.reduce((sum, child) => sum + Math.ceil(child.offsetHeight || child.getBoundingClientRect().height || 0), 0);
    return Math.max(0, content + Math.max(0, children.length) * 7 + 12);
  }

  function minimumHeight() {
    return Math.max(330, fixedContentHeight() + PREVIEW_FLOOR);
  }

  function resizeForContent(previousFixed = null) {
    requestAnimationFrame(() => {
      if (ui.disposed) return;
      const currentFixed = fixedContentHeight();
      if (previousFixed !== null && Number.isFinite(previousFixed)) {
        const delta = currentFixed - previousFixed;
        if (Math.abs(delta) > 1) {
          const height = Math.max(Number(node.size?.[1]) || 0, minimumHeight() + 42);
          node.setSize?.([Math.max(MIN_WIDTH, Number(node.size?.[0]) || MIN_WIDTH), Math.max(minimumHeight() + 42, height + delta)]);
        }
      }
      ui.widget?.callback?.();
      node.setDirtyCanvas?.(true, true);
      drawPreview();
    });
  }

  function commitState(next, { render = true, resize = false } = {}) {
    const previousFixed = resize ? fixedContentHeight() : null;
    ui.state = normalizeAdvState(next);
    stateWidget.value = JSON.stringify(ui.state);
    stateWidget.callback?.(stateWidget.value);
    markChanged();
    if (render) renderControls();
    updateOutput();
    drawPreview();
    if (resize) resizeForContent(previousFixed);
  }

  function aspectShape(width, height, className = "workflowx-lixa-aspect-shape") {
    const shape = document.createElement("span");
    shape.className = className;
    const ratio = Math.max(0.2, Math.min(5, Number(width) / Math.max(1, Number(height))));
    if (ratio >= 1) {
      shape.style.width = "30px";
      shape.style.height = `${Math.max(6, 30 / ratio)}px`;
    } else {
      shape.style.height = "21px";
      shape.style.width = `${Math.max(6, 21 * ratio)}px`;
    }
    return shape;
  }

  function updateCardElement(card) {
    if (!card) return;
    const size = card.querySelector(".workflowx-lixa-port-card-size");
    const shape = card.querySelector(".workflowx-lixa-port-card-shape");
    const { width, height } = ui.output;
    size.textContent = width && height ? `${width} x ${height}` : "- x -";
    const ratio = width && height ? width / height : 1;
    if (ratio >= 1) {
      shape.style.width = "31px";
      shape.style.height = `${Math.max(7, 31 / ratio)}px`;
    } else {
      shape.style.height = "25px";
      shape.style.width = `${Math.max(7, 25 * ratio)}px`;
    }
  }

  function makePortCard() {
    const card = document.createElement("div");
    card.className = "workflowx-lixa-port-card";
    const label = document.createElement("span");
    label.className = "workflowx-lixa-port-card-label";
    label.textContent = "Output";
    const shape = document.createElement("span");
    shape.className = "workflowx-lixa-port-card-shape";
    const size = document.createElement("span");
    size.className = "workflowx-lixa-port-card-size";
    card.append(label, shape, size);
    updateCardElement(card);
    return card;
  }

  function mountNodes2Card() {
    if (ui.disposed || ui.portalCard?.isConnected) return;
    const host = root.closest?.(".lg-node");
    if (!host) return;
    host.classList.add("workflowx-lixa-host");
    ui.portalCard = makePortCard();
    host.appendChild(ui.portalCard);
  }

  function updateOutput() {
    if (!ui.source) ui.output = { width: 0, height: 0 };
    else ui.output = computeOutputDimensions(ui.source.naturalWidth, ui.source.naturalHeight, ui.state);
    updateCardElement(ui.portalCard);
    node._workflowxLixaOutput = ui.output;
    node.setDirtyCanvas?.(true, true);
  }

  function labeledRow(labelText, ...children) {
    const row = document.createElement("div");
    row.className = "workflowx-lixa-row";
    if (labelText) {
      const label = document.createElement("span");
      label.className = "workflowx-lixa-label";
      label.textContent = labelText;
      row.appendChild(label);
    }
    row.append(...children);
    return row;
  }

  function field(labelText, input) {
    const wrapper = document.createElement("label");
    wrapper.className = "workflowx-lixa-field";
    const label = document.createElement("span");
    label.className = "workflowx-lixa-label";
    label.textContent = labelText;
    wrapper.append(label, input);
    return wrapper;
  }

  function dimensionsRow(widthKey, heightKey) {
    const width = numericInput(ui.state[widthKey], {
      min: 8, max: 16384, step: 8, title: "Width in pixels",
      onCommit: (value) => commitState({ ...ui.state, [widthKey]: value }),
    });
    const height = numericInput(ui.state[heightKey], {
      min: 8, max: 16384, step: 8, title: "Height in pixels",
      onCommit: (value) => commitState({ ...ui.state, [heightKey]: value }),
    });
    const swap = button("<>", "workflowx-lixa-swap");
    swap.title = "Swap width and height";
    swap.addEventListener("click", () => commitState({
      ...ui.state, [widthKey]: ui.state[heightKey], [heightKey]: ui.state[widthKey],
    }, { render: true }));
    const aspect = document.createElement("span");
    aspect.className = "workflowx-lixa-aspect";
    aspect.appendChild(aspectShape(ui.state[widthKey], ui.state[heightKey]));
    return labeledRow("", field("W", width), swap, field("H", height), aspect);
  }

  function quickPanel(label, key, values, suffix, options) {
    const panel = document.createElement("div");
    panel.className = "workflowx-lixa-panel";
    const quick = document.createElement("div");
    quick.className = "workflowx-lixa-quick";
    for (const value of values) {
      const item = button(`${value}${suffix}`);
      item.classList.toggle("active", Number(ui.state[key]) === value);
      item.addEventListener("click", () => commitState({ ...ui.state, [key]: value }));
      quick.appendChild(item);
    }
    const input = numericInput(ui.state[key], {
      ...options, onCommit: (value) => commitState({ ...ui.state, [key]: value }),
    });
    panel.append(quick, labeledRow(label, input));
    return panel;
  }

  function renderModePanel() {
    ui.panel?.remove();
    ui.panel = null;
    if (ui.state.mode === "off") return;
    if (ui.state.mode === "max_mp") {
      ui.panel = quickPanel("Megapixels", "max_mp", [0.25, 0.5, 1, 2, 4, 8], " MP", { min: 0.01, max: 64, step: 0.01 });
    } else if (ui.state.mode === "longest_side") {
      ui.panel = quickPanel("Longest side", "longest_side", [512, 768, 1024, 1280, 1536, 2048], "", { min: 8, max: 16384, step: 8 });
    } else if (ui.state.mode === "scale_factor") {
      ui.panel = quickPanel("Scale factor", "scale_factor", [0.25, 0.5, 1, 2, 3, 4], "x", { min: 0.01, max: 8, step: 0.01 });
    } else if (ui.state.mode === "fit_inside") {
      ui.panel = document.createElement("div");
      ui.panel.className = "workflowx-lixa-panel";
      ui.panel.appendChild(dimensionsRow("fit_w", "fit_h"));
    } else if (ui.state.mode === "cover") {
      ui.panel = document.createElement("div");
      ui.panel.className = "workflowx-lixa-panel";
      ui.panel.appendChild(dimensionsRow("cover_w", "cover_h"));
      const segment = document.createElement("div");
      segment.className = "workflowx-lixa-segment";
      for (const [id, label] of [["fill", "Fill"], ["crop", "Crop"]]) {
        const item = button(label);
        item.classList.toggle("active", ui.state.cover_action === id);
        item.addEventListener("click", () => commitState({ ...ui.state, cover_action: id }));
        segment.appendChild(item);
      }
      const anchors = document.createElement("div");
      anchors.className = "workflowx-lixa-anchors";
      for (const anchor of ANCHORS) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "workflowx-lixa-anchor";
        item.title = anchor.replaceAll("-", " ");
        item.classList.toggle("active", ui.state.crop_anchor === anchor);
        item.addEventListener("click", () => commitState({ ...ui.state, crop_anchor: anchor }));
        anchors.appendChild(item);
      }
      ui.panel.append(segment, anchors);
    } else if (ui.state.mode === "match_ratio") {
      ui.panel = document.createElement("div");
      ui.panel.className = "workflowx-lixa-panel";
      const ratios = document.createElement("div");
      ratios.className = "workflowx-lixa-ratios";
      for (const [id, width, height] of RATIO_OPTIONS) {
        const item = button(id === "custom" ? "Custom" : id, "workflowx-lixa-ratio");
        if (id !== "custom") item.appendChild(aspectShape(width, height, "workflowx-lixa-ratio-shape"));
        const text = document.createElement("span");
        text.textContent = id === "custom" ? "Custom" : id;
        item.appendChild(text);
        item.classList.toggle("active", ui.state.ratio_preset === id);
        item.addEventListener("click", () => {
          const next = { ...ui.state, ratio_preset: id };
          if (id !== "custom") Object.assign(next, { ratio_w: width, ratio_h: height });
          commitState(next, { render: true, resize: true });
        });
        ratios.appendChild(item);
      }
      ui.panel.appendChild(ratios);
      if (ui.state.ratio_preset === "custom") ui.panel.appendChild(dimensionsRow("ratio_w", "ratio_h"));
    } else if (ui.state.mode === "pad") {
      ui.panel = document.createElement("div");
      ui.panel.className = "workflowx-lixa-panel";
      const grid = document.createElement("div");
      grid.className = "workflowx-lixa-padgrid";
      for (const [key, className, title] of [
        ["pad_top", "top", "Top"], ["pad_left", "left", "Left"],
        ["pad_right", "right", "Right"], ["pad_bottom", "bottom", "Bottom"],
      ]) {
        const input = numericInput(ui.state[key], {
          min: 0, max: 8192, step: 1, title: `${title} padding`,
          onCommit: (value) => commitState({ ...ui.state, [key]: value }),
        });
        input.classList.add(className);
        grid.appendChild(input);
      }
      const color = document.createElement("input");
      color.type = "color";
      color.className = "workflowx-lixa-color center";
      color.value = /^#[0-9a-f]{6}$/i.test(ui.state.pad_color) ? ui.state.pad_color : "#808080";
      color.title = "Padding fill color";
      color.addEventListener("input", () => commitState({ ...ui.state, pad_color: color.value }, { render: false }));
      grid.appendChild(color);
      const footer = document.createElement("div");
      footer.className = "workflowx-lixa-padfooter";
      const reset = button("Reset", "workflowx-lixa-command");
      reset.addEventListener("click", () => commitState({
        ...ui.state, pad_top: 0, pad_bottom: 0, pad_left: 0, pad_right: 0,
      }));
      const live = document.createElement("span");
      live.className = "workflowx-lixa-live";
      live.textContent = ui.output.width ? `${ui.output.width} x ${ui.output.height}` : "- x -";
      footer.append(reset, live, document.createElement("span"));
      ui.panel.append(grid, footer);
    }
    if (ui.panel) modes.after(ui.panel);
  }

  function renderSnapRow(container, labelText, key) {
    container.replaceChildren();
    const label = document.createElement("span");
    label.className = "workflowx-lixa-label";
    label.textContent = labelText;
    container.appendChild(label);
    for (const value of SNAP_OPTIONS) {
      const item = button(value === 0 ? "Off" : String(value));
      item.classList.toggle("active", Number(ui.state[key]) === value);
      item.title = value ? `Constrain dimensions to multiples of ${value}` : "Disable snapping";
      item.addEventListener("click", () => {
        const next = { ...ui.state, [key]: value };
        if (key === "crop_snap" && ui.source && ui.state.crop_rect) {
          const current = pixelRectFromState(ui.source.naturalWidth, ui.source.naturalHeight, { ...ui.state, crop_snap: 0 });
          const snapped = snapCropRect(current, ui.source.naturalWidth, ui.source.naturalHeight, value, "top-left");
          next.crop_rect = normalizedRect(snapped, ui.source.naturalWidth, ui.source.naturalHeight);
        }
        commitState(next);
      });
      container.appendChild(item);
    }
  }

  function renderControls() {
    modes.replaceChildren();
    for (const [id, label] of MODE_OPTIONS) {
      const item = button(label);
      item.classList.toggle("active", ui.state.mode === id);
      item.addEventListener("click", () => commitState({ ...ui.state, mode: id }, { render: true, resize: true }));
      modes.appendChild(item);
    }
    renderModePanel();
    renderSnapRow(outputSnap, "Output Snap", "output_snap");

    resample.replaceChildren();
    const previous = button("<");
    previous.title = "Previous resampling filter";
    const select = document.createElement("select");
    select.title = "Resampling filter";
    for (const [id, label] of RESAMPLE_OPTIONS) {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = `Resample: ${label}`;
      option.selected = ui.state.resample === id;
      select.appendChild(option);
    }
    const next = button(">");
    next.title = "Next resampling filter";
    const shiftResample = (direction) => {
      const index = RESAMPLE_OPTIONS.findIndex(([id]) => id === ui.state.resample);
      const selected = RESAMPLE_OPTIONS[(index + direction + RESAMPLE_OPTIONS.length) % RESAMPLE_OPTIONS.length][0];
      commitState({ ...ui.state, resample: selected });
    };
    previous.addEventListener("click", () => shiftResample(-1));
    next.addEventListener("click", () => shiftResample(1));
    select.addEventListener("change", () => commitState({ ...ui.state, resample: select.value }));
    resample.append(previous, select, next);

    toggles.replaceChildren();
    const cropToggle = button(`Crop: ${ui.state.crop_enabled ? "On" : "Off"}`, "workflowx-lixa-toggle");
    cropToggle.classList.toggle("active", ui.state.crop_enabled);
    cropToggle.addEventListener("click", () => commitState(
      { ...ui.state, crop_enabled: !ui.state.crop_enabled }, { render: true, resize: true },
    ));
    const upscaleToggle = button(`Upscaling: ${ui.state.allow_upscale ? "On" : "Off"}`, "workflowx-lixa-toggle");
    upscaleToggle.classList.toggle("active", ui.state.allow_upscale);
    upscaleToggle.addEventListener("click", () => commitState({ ...ui.state, allow_upscale: !ui.state.allow_upscale }));
    toggles.append(cropToggle, upscaleToggle);

    if (ui.state.crop_enabled) {
      renderSnapRow(cropSnap, "Crop Snap", "crop_snap");
      if (!cropSnap.isConnected) preview.before(cropSnap);
    } else cropSnap.remove();
    updateOutput();
  }

  function canvasPoint(event) {
    const bounds = canvas.getBoundingClientRect();
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
  }

  function sourcePoint(point) {
    if (!ui.source || !ui.imageBox) return null;
    const box = ui.imageBox;
    if (point.x < box.x || point.y < box.y || point.x > box.x + box.width || point.y > box.y + box.height) return null;
    return {
      x: Math.round((point.x - box.x) / box.width * ui.source.naturalWidth),
      y: Math.round((point.y - box.y) / box.height * ui.source.naturalHeight),
    };
  }

  function screenCropRect() {
    if (!ui.source || !ui.imageBox) return null;
    const rect = pixelRectFromState(ui.source.naturalWidth, ui.source.naturalHeight, ui.state);
    if (!rect) return null;
    return {
      x: ui.imageBox.x + rect.x / ui.source.naturalWidth * ui.imageBox.width,
      y: ui.imageBox.y + rect.y / ui.source.naturalHeight * ui.imageBox.height,
      w: rect.w / ui.source.naturalWidth * ui.imageBox.width,
      h: rect.h / ui.source.naturalHeight * ui.imageBox.height,
      source: rect,
    };
  }

  function hitCrop(point) {
    const rect = screenCropRect();
    if (!rect) return { mode: "new" };
    const handles = {
      "top-left": [rect.x, rect.y], "top-right": [rect.x + rect.w, rect.y],
      "bottom-left": [rect.x, rect.y + rect.h], "bottom-right": [rect.x + rect.w, rect.y + rect.h],
    };
    for (const [corner, [x, y]] of Object.entries(handles)) {
      if (Math.abs(point.x - x) <= 10 && Math.abs(point.y - y) <= 10) return { mode: "resize", corner };
    }
    if (point.x >= rect.x && point.x <= rect.x + rect.w && point.y >= rect.y && point.y <= rect.y + rect.h) return { mode: "move" };
    return { mode: "new" };
  }

  function drawPreview() {
    const bounds = canvas.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    const pixelWidth = Math.max(1, Math.round(bounds.width * ratio));
    const pixelHeight = Math.max(1, Math.round(bounds.height * ratio));
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) { canvas.width = pixelWidth; canvas.height = pixelHeight; }
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, bounds.width, bounds.height);
    context.fillStyle = "#141518";
    context.fillRect(0, 0, bounds.width, bounds.height);
    ui.imageBox = null;
    if (!ui.source) return;
    const factor = Math.min(bounds.width / ui.source.naturalWidth, bounds.height / ui.source.naturalHeight);
    const width = ui.source.naturalWidth * factor;
    const height = ui.source.naturalHeight * factor;
    const x = (bounds.width - width) / 2;
    const y = (bounds.height - height) / 2;
    ui.imageBox = { x, y, width, height };
    context.drawImage(ui.source, x, y, width, height);
    if (!ui.state.crop_enabled) return;
    const crop = screenCropRect();
    if (!crop) return;
    context.save();
    context.fillStyle = "rgba(0,0,0,.58)";
    context.beginPath();
    context.rect(x, y, width, height);
    context.rect(crop.x, crop.y, crop.w, crop.h);
    context.fill("evenodd");
    context.strokeStyle = ACCENT;
    context.lineWidth = 2;
    context.strokeRect(crop.x, crop.y, crop.w, crop.h);
    context.fillStyle = ACCENT;
    for (const [handleX, handleY] of [[crop.x, crop.y], [crop.x + crop.w, crop.y], [crop.x, crop.y + crop.h], [crop.x + crop.w, crop.y + crop.h]]) {
      context.fillRect(handleX - 4, handleY - 4, 8, 8);
    }
    const text = `${crop.source.w} x ${crop.source.h}`;
    context.font = "600 11px ui-sans-serif,system-ui,sans-serif";
    const textWidth = context.measureText(text).width;
    const pillX = Math.max(x + 3, Math.min(crop.x + crop.w / 2 - textWidth / 2 - 7, x + width - textWidth - 17));
    const pillY = crop.y > y + 24 ? crop.y - 22 : crop.y + 5;
    context.fillStyle = "rgba(20,20,20,.9)";
    context.fillRect(pillX, pillY, textWidth + 14, 18);
    context.fillStyle = "#eef4ff";
    context.fillText(text, pillX + 7, pillY + 13);
    context.restore();
  }

  function acceptLoadedImage(image, selected, reason) {
    const oldSize = ui.source ? [ui.source.naturalWidth, ui.source.naturalHeight] : null;
    const newSize = [image.naturalWidth, image.naturalHeight];
    if (reason === "browser" || (oldSize && (oldSize[0] !== newSize[0] || oldSize[1] !== newSize[1]))) {
      commitState(clearCropForImageChange(ui.state), { render: true, resize: false });
    }
    ui.source = image;
    ui.sourcePath = selected;
    node.imgs = [image];
    node.imageIndex = 0;
    updateOutput();
    drawPreview();
    node.setDirtyCanvas?.(true, true);
  }

  function loadSelectedImage(reason = "external") {
    const selected = String(imageWidget.value || "");
    const sequence = ++ui.loadSequence;
    if (!selected) {
      ui.source = null;
      ui.sourcePath = "";
      node.imgs = [];
      updateOutput();
      drawPreview();
      return;
    }
    const image = new Image();
    image.onload = () => { if (sequence === ui.loadSequence) acceptLoadedImage(image, selected, reason); };
    image.onerror = () => {
      if (sequence !== ui.loadSequence) return;
      ui.source = null;
      ui.sourcePath = selected;
      updateOutput();
      drawPreview();
    };
    image.src = viewURL({ path: selected, version: String(Date.now()) });
  }

  browse.addEventListener("click", () => openLoadImageXPicker(node, imageWidget, {
    loadNativePreview: false,
    beforeSelect: () => { ui.pendingBrowserSelection = true; },
    onEmpty: () => loadSelectedImage("browser"),
  }));

  canvas.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || !event.isPrimary || !ui.state.crop_enabled || !ui.source) return;
    const point = canvasPoint(event);
    const source = sourcePoint(point);
    if (!source) return;
    const hit = hitCrop(point);
    const current = pixelRectFromState(ui.source.naturalWidth, ui.source.naturalHeight, ui.state);
    ui.drag = { hit, start: source, current, moved: false };
    canvas.setPointerCapture(event.pointerId);
    event.preventDefault();
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!ui.state.crop_enabled || !ui.source) { canvas.style.cursor = "default"; return; }
    const point = canvasPoint(event);
    if (!ui.drag) {
      const hit = hitCrop(point);
      canvas.style.cursor = hit.mode === "move" ? "grab" : hit.mode === "resize" ? "nwse-resize" : "crosshair";
      return;
    }
    const source = sourcePoint({
      x: Math.max(ui.imageBox.x, Math.min(ui.imageBox.x + ui.imageBox.width, point.x)),
      y: Math.max(ui.imageBox.y, Math.min(ui.imageBox.y + ui.imageBox.height, point.y)),
    });
    if (!source) return;
    const drag = ui.drag;
    drag.moved ||= Math.abs(source.x - drag.start.x) + Math.abs(source.y - drag.start.y) > 1;
    let rect = drag.current;
    let fixedCorner = "top-left";
    if (drag.hit.mode === "new") {
      rect = {
        x: Math.min(drag.start.x, source.x), y: Math.min(drag.start.y, source.y),
        w: Math.max(1, Math.abs(source.x - drag.start.x)), h: Math.max(1, Math.abs(source.y - drag.start.y)),
      };
      fixedCorner = `${source.y < drag.start.y ? "bottom" : "top"}-${source.x < drag.start.x ? "right" : "left"}`;
    } else if (drag.hit.mode === "move" && drag.current) {
      rect = {
        ...drag.current,
        x: Math.max(0, Math.min(ui.source.naturalWidth - drag.current.w, drag.current.x + source.x - drag.start.x)),
        y: Math.max(0, Math.min(ui.source.naturalHeight - drag.current.h, drag.current.y + source.y - drag.start.y)),
      };
    } else if (drag.hit.mode === "resize" && drag.current) {
      const opposite = {
        "top-left": { x: drag.current.x + drag.current.w, y: drag.current.y + drag.current.h, fixed: "bottom-right" },
        "top-right": { x: drag.current.x, y: drag.current.y + drag.current.h, fixed: "bottom-left" },
        "bottom-left": { x: drag.current.x + drag.current.w, y: drag.current.y, fixed: "top-right" },
        "bottom-right": { x: drag.current.x, y: drag.current.y, fixed: "top-left" },
      }[drag.hit.corner];
      rect = { x: Math.min(source.x, opposite.x), y: Math.min(source.y, opposite.y),
        w: Math.max(1, Math.abs(source.x - opposite.x)), h: Math.max(1, Math.abs(source.y - opposite.y)) };
      fixedCorner = opposite.fixed;
    }
    if (drag.hit.mode !== "move") rect = snapCropRect(rect, ui.source.naturalWidth, ui.source.naturalHeight, ui.state.crop_snap, fixedCorner);
    ui.state = { ...ui.state, crop_rect: normalizedRect(rect, ui.source.naturalWidth, ui.source.naturalHeight) };
    drawPreview();
    event.preventDefault();
  });

  canvas.addEventListener("pointerup", (event) => {
    if (!ui.drag) return;
    const drag = ui.drag;
    ui.drag = null;
    if (drag.hit.mode === "new" && !drag.moved && drag.current) commitState({ ...ui.state, crop_rect: null });
    else commitState(ui.state, { render: false });
    canvas.releasePointerCapture?.(event.pointerId);
    event.preventDefault();
  });
  canvas.addEventListener("pointercancel", () => { ui.drag = null; });
  root.addEventListener("contextmenu", (event) => {
    const graphCanvas = app.canvasEl || app.canvas?.canvas;
    event.preventDefault();
    event.stopPropagation();
    const ContextMenu = window.LiteGraph?.ContextMenu;
    const options = app.canvas?.getNodeMenuOptions?.(node);
    if (ContextMenu && Array.isArray(options)) {
      new ContextMenu(options, { event, title: node.type, extra: node });
      return;
    }
    if (!graphCanvas) return;
    const pointer = {
      button: 2,
      clientX: event.clientX,
      clientY: event.clientY,
      pointerId: 1,
      isPrimary: true,
    };
    graphCanvas.dispatchEvent(new PointerEvent("pointerdown", pointer));
    window.setTimeout(() => graphCanvas.dispatchEvent(new PointerEvent("pointerup", pointer)));
  });

  ui.resizeObserver = new ResizeObserver(() => { mountNodes2Card(); drawPreview(); });
  ui.resizeObserver.observe(preview);

  let lastImage = String(imageWidget.value || "");
  const originalImageCallback = imageWidget.callback;
  imageWidget.callback = function (value) {
    const result = originalImageCallback?.apply(this, arguments);
    const selected = String(value ?? imageWidget.value ?? "");
    const reason = ui.pendingBrowserSelection ? "browser" : "external";
    ui.pendingBrowserSelection = false;
    lastImage = selected;
    loadSelectedImage(reason);
    return result;
  };

  ui.imagePoll = window.setInterval(() => {
    if (ui.disposed) return;
    for (const widget of node.widgets || []) {
      const name = String(widget?.name || "").toLowerCase();
      if (widget !== ui.widget && (widget === imageWidget || widget === stateWidget || name === "upload" || name.includes("image_preview"))) {
        hideWidget(widget);
      }
    }
    const selected = String(imageWidget.value || "");
    if (selected !== lastImage) {
      lastImage = selected;
      loadSelectedImage("external");
      return;
    }
    const nativeImage = node.imgs?.[0];
    if (nativeImage && nativeImage !== ui.source && nativeImage.complete && nativeImage.naturalWidth) {
      acceptLoadedImage(nativeImage, selected, "external");
    }
    mountNodes2Card();
  }, 250);

  const originalConfigure = node.onConfigure;
  node.onConfigure = function () {
    const result = originalConfigure?.apply(this, arguments);
    queueMicrotask(() => {
      ui.state = normalizeAdvState(stateWidget.value);
      lastImage = String(imageWidget.value || "");
      renderControls();
      loadSelectedImage("reload");
      resizeForContent();
    });
    return result;
  };

  ui.dispose = () => {
    ui.disposed = true;
    ui.resizeObserver?.disconnect();
    window.clearInterval(ui.imagePoll);
    ui.portalCard?.remove();
    root.closest?.(".lg-node")?.classList.remove("workflowx-lixa-host");
  };
  ui.minimumHeight = minimumHeight;
  ui.drawPreview = drawPreview;
  ui.updateCard = updateCardElement;
  renderControls();
  loadSelectedImage("reload");
  return ui;
}

function installCanvasBehavior(node, ui) {
  const originalDrawBackground = node.onDrawBackground;
  node.onDrawBackground = function () {
    const images = this.imgs;
    if (images?.length) this.imgs = [];
    try { return originalDrawBackground?.apply(this, arguments); }
    finally { if (images?.length) this.imgs = images; }
  };

  const originalDrawForeground = node.onDrawForeground;
  node.onDrawForeground = function (context) {
    const result = originalDrawForeground?.apply(this, arguments);
    if (this.flags?.collapsed || ui.portalCard?.isConnected) return result;
    const width = Math.max(120, (Number(this.size?.[0]) || MIN_WIDTH) - 154);
    const height = 84;
    const x = 10;
    const y = 8;
    context.save();
    context.fillStyle = "#25282d";
    context.strokeStyle = "#434a55";
    context.lineWidth = 1;
    context.beginPath();
    context.roundRect(x, y, width, height, 5);
    context.fill();
    context.stroke();
    const output = this._workflowxLixaOutput || { width: 0, height: 0 };
    const label = output.width ? `${output.width} x ${output.height}` : "- x -";
    context.fillStyle = "#969da7";
    context.font = "9px sans-serif";
    context.textAlign = "right";
    context.fillText("OUTPUT", x + width / 2 - 6, y + 28);
    const ratio = output.width && output.height ? output.width / output.height : 1;
    const shapeWidth = ratio >= 1 ? 27 : Math.max(7, 18 * ratio);
    const shapeHeight = ratio >= 1 ? Math.max(7, 27 / ratio) : 18;
    context.strokeStyle = ACCENT;
    context.fillStyle = "rgba(122,162,247,.12)";
    context.fillRect(x + width / 2 + 8, y + 20 - shapeHeight / 2, shapeWidth, shapeHeight);
    context.strokeRect(x + width / 2 + 8, y + 20 - shapeHeight / 2, shapeWidth, shapeHeight);
    context.fillStyle = ACCENT;
    context.font = "bold 15px sans-serif";
    context.textAlign = "center";
    context.fillText(label, x + width / 2, y + 58);
    context.restore();
    return result;
  };
}

function attachAdvancedUI(node) {
  if (!isAdvancedNode(node) || node._workflowxLoadImageXAdvSetup) return;
  node._workflowxLoadImageXAdvSetup = true;
  queueMicrotask(() => {
    const imageWidget = node.widgets?.find((widget) => widget.name === "image");
    const stateWidget = node.widgets?.find((widget) => widget.name === "workflowx_state");
    if (!imageWidget || !stateWidget) { node._workflowxLoadImageXAdvSetup = false; return; }
    hideWidget(imageWidget);
    hideWidget(stateWidget);
    for (const widget of node.widgets || []) {
      const name = String(widget?.name || "").toLowerCase();
      if (widget !== imageWidget && widget !== stateWidget && (name === "upload" || name.includes("image_preview"))) hideWidget(widget);
    }
    node.inputs = [];
    const ui = createAdvancedUI(node, imageWidget, stateWidget);
    const widget = node.addDOMWidget("workflowx_load_image_x_adv", "custom", ui.root, {
      getMinHeight: () => ui.minimumHeight(), getMaxHeight: () => Infinity, margin: 0, serialize: false,
    });
    widget.computeLayoutSize = () => ({ minHeight: ui.minimumHeight(), maxHeight: Infinity, minWidth: MIN_WIDTH });
    ui.widget = widget;
    installCanvasBehavior(node, ui);

    const originalRemoved = node.onRemoved;
    node.onRemoved = function () {
      ui.dispose();
      return originalRemoved?.apply(this, arguments);
    };

    requestAnimationFrame(() => {
      const width = Math.max(MIN_WIDTH, Number(node.size?.[0]) || MIN_WIDTH);
      const computed = node.computeSize?.() || [width, ui.minimumHeight() + 42];
      node.setSize?.([width, Math.max(Number(computed[1]) || 0, ui.minimumHeight() + 42)]);
      ui.drawPreview();
      node.setDirtyCanvas?.(true, true);
    });
  });
}

app.registerExtension({
  name: "WorkflowX.LoadImageXAdv",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== "WorkflowX_LoadImageXAdv") return;
    nodeType.prototype.onConnectInput = () => false;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalCreated?.apply(this, arguments);
      attachAdvancedUI(this);
      return result;
    };
  },
  nodeCreated(node) { attachAdvancedUI(node); },
  loadedGraphNode(node) { attachAdvancedUI(node); },
});
