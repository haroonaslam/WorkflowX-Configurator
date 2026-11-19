import { app } from "../../scripts/app.js";
import { installAutogrowLayoutHooks } from "./workflowx_autogrow_layout.mjs";

const TYPE = "WorkflowXPromptAssemblerX";
const DISABLED_LINKS = "workflowx_prompt_disabled_links";
const PROMPT_NAME = /^prompts\.(prompt_\d+)$/;

function promptRows(node) {
  const disabled = new Set(node.properties[DISABLED_LINKS] ?? []);
  return node.inputs.flatMap((input, slot) => {
    const match = PROMPT_NAME.exec(input.name);
    if (!match || input.link == null) return [];
    const link = String(input.link);
    return [{ name: match[1], slot, link, checked: !disabled.has(link) }];
  });
}

function storeToggle(node, name, checked) {
  const rows = promptRows(node);
  const row = rows.find((entry) => entry.name === name);
  if (!node.graph || !row || row.checked === checked) return;
  const graph = node.graph.rootGraph ?? node.graph;
  const canvas = app.canvas;
  graph.beforeChange?.();
  canvas?.emitBeforeChange?.();
  try {
    node.properties[DISABLED_LINKS] = rows
      .filter((entry) => !(entry === row ? checked : entry.checked))
      .map((entry) => entry.link);
  } finally {
    graph.afterChange?.();
    canvas?.emitAfterChange?.();
    graph.setDirtyCanvas?.(true, true);
  }
}

function installStyles() {
  if (document.getElementById("workflowx-prompt-assembler-style")) return;
  const style = document.createElement("style");
  style.id = "workflowx-prompt-assembler-style";
  style.textContent = `
    .workflowx-assembler-switches { box-sizing:border-box; contain:size; height:100%; min-height:32px;
      overflow:auto; padding:2px 5px; color:var(--input-text, #ddd); font:12px sans-serif; }
    .workflowx-assembler-switches label { display:flex; align-items:center; justify-content:space-between;
      gap:5px; min-height:27px; }
    .workflowx-assembler-switches label span { min-width:0; overflow:hidden; text-overflow:ellipsis;
      white-space:nowrap; }
    .workflowx-assembler-switches input { appearance:none; flex:none; width:28px; height:16px; margin:0;
      border-radius:10px; border:1px solid #888; background:var(--comfy-input-bg, #333);
      display:grid; align-items:center; padding:2px; cursor:pointer; }
    .workflowx-assembler-switches input::before { content:""; width:10px; height:10px;
      border-radius:50%; background:currentColor; }
    .workflowx-assembler-switches input:checked { justify-items:end; background:#39744c; color:#fff; }
    .workflowx-assembler-switches input:disabled { opacity:.45; cursor:default; }
  `;
  document.head.append(style);
}

function attachPromptSwitches(node) {
  const backing = node.widgets?.find((widget) => widget.name === "disabled_slots");
  if (!backing) return;
  backing.hidden = true;
  backing.serialize = false;
  backing.serializeValue = () => JSON.stringify(promptRows(node).filter(({ checked }) => !checked).map(({ name }) => name));

  installStyles();
  const list = document.createElement("div");
  list.className = "workflowx-assembler-switches";
  for (const event of ["pointerdown", "pointerup", "click", "wheel"]) {
    list.addEventListener(event, (e) => e.stopPropagation());
  }
  list.addEventListener("keydown", (event) => {
    if (!event.ctrlKey && !event.metaKey) event.stopPropagation();
  });
  node.addDOMWidget("workflowx_prompt_switches", "custom", list, {
    serialize: false,
    hideOnZoom: false,
    margin: 8,
    getMinHeight: () => 48,
  });
  node.setSize(node.computeSize());

  const labels = new Map();
  function refresh() {
    if (!node.graph) return;
    const rows = promptRows(node);
    const names = new Set(rows.map(({ name }) => name));
    for (const [name, label] of labels) {
      if (names.has(name)) continue;
      label.remove();
      labels.delete(name);
    }
    rows.forEach((row, index) => {
      let label = labels.get(row.name);
      if (!label) {
        label = document.createElement("label");
        const caption = document.createElement("span");
        const toggle = document.createElement("input");
        toggle.type = "checkbox";
        toggle.setAttribute("role", "switch");
        toggle.addEventListener("change", () => {
          storeToggle(node, row.name, toggle.checked);
          refresh();
        });
        label.append(caption, toggle);
        labels.set(row.name, label);
      }
      if (list.children[index] !== label) list.insertBefore(label, list.children[index] ?? null);
      const link = node.getInputLink(row.slot);
      const source = link && node.graph.getNodeById(link.origin_id);
      const port = !source && link ? node.graph.inputs?.[link.origin_slot] : null;
      const title = source?.title || source?.constructor?.title || port?.label || port?.name || "Connected input";
      const caption = label.firstElementChild;
      if (caption.textContent !== title) {
        caption.textContent = title;
        caption.title = title;
      }
      label.lastElementChild.checked = row.checked;
    });
  }

  let timer;
  const added = node.onAdded;
  node.onAdded = function () {
    const result = added?.apply(this, arguments);
    timer = setInterval(refresh, 150);
    return result;
  };
  const removed = node.onRemoved;
  node.onRemoved = function () {
    clearInterval(timer);
    return removed?.apply(this, arguments);
  };
  const serialized = node.onSerialize;
  node.onSerialize = function (data) {
    serialized?.apply(this, arguments);
    if (!this.graph || !data.properties) return;
    const disabled = promptRows(this).filter(({ checked }) => !checked).map(({ link }) => link);
    if (disabled.length) data.properties[DISABLED_LINKS] = disabled;
    else delete data.properties[DISABLED_LINKS];
  };
}

app.registerExtension({
  name: "WorkflowX.PromptAssemblerX",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name === TYPE) installAutogrowLayoutHooks(nodeType.prototype);
  },
  nodeCreated(node) {
    if (node.type === TYPE || node.comfyClass === TYPE) attachPromptSwitches(node);
  },
});
