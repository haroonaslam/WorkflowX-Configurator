import { graphNodes, logicalGraphs } from "./key_config_graph.mjs";
import { installAutogrowLayoutHooks } from "./workflowx_autogrow_layout.mjs";

export const QUICK_TOGGLE = "Quick ToggleX";
export const TOGGLE_CONTROLLER = "WorkflowXToggleXController";
export const TOGGLE_SELECTION = "workflowx_toggle_selection";
const CHOICE = /^choices\.input\d+$/;
const MIN_PANEL_HEIGHT = 58;
const DEFAULT_PANEL_SIZE = [234, 76];

function nodeTitle(node, fallback) {
  return String(node?.title || node?.constructor?.title || fallback);
}

export function toggleChoices(node) {
  if (!node.graph) return [];
  const choices = (node.inputs ?? []).flatMap((input, index) => {
    if (!CHOICE.test(input.name) || input.link == null) return [];
    const link = node.getInputLink?.(index);
    if (!link) return [];
    const source = node.graph.getNodeById(link.origin_id);
    const port = node.graph.inputs?.[link.origin_slot];
    return [{
      name: input.name,
      link: String(link.id),
      source: String(link.origin_id),
      slot: link.origin_slot,
      title: nodeTitle(source, port?.label || port?.name || "Subgraph input"),
      output: source?.outputs?.[link.origin_slot]?.label || source?.outputs?.[link.origin_slot]?.name,
    }];
  });
  const titles = new Map();
  for (const choice of choices) titles.set(choice.title, (titles.get(choice.title) ?? 0) + 1);
  return choices.map((choice) => ({
    ...choice,
    label: titles.get(choice.title) === 1 ? choice.title
      : `${choice.title} · ${choice.output || `Output ${choice.slot + 1}`} · #${choice.source}`,
  }));
}

function selectedChoice(node, choices = toggleChoices(node)) {
  const selected = node.properties?.[TOGGLE_SELECTION];
  return choices.find(({ link, source, slot }) =>
    link === selected?.link && source === selected?.source && slot === selected?.slot);
}

export function toggleRows(root) {
  return logicalGraphs(root).flatMap(({ graph, path, isRoot }) =>
    graphNodes(graph).filter((node) => node.type === TOGGLE_CONTROLLER).map((node) => {
      const choices = toggleChoices(node);
      return {
        key: JSON.stringify([isRoot ? null : graph.uuid ?? graph.id, String(node.id)]),
        node,
        title: nodeTitle(node, "ToggleX Controller"),
        path: path.join(" / "),
        choices,
        selected: selectedChoice(node, choices)?.link ?? "",
      };
    }));
}

export function selectToggleInput(root, canvas, node, linkId) {
  const choice = toggleChoices(node).find(({ link }) => link === linkId);
  if (!choice || selectedChoice(node)?.link === choice.link) return;
  root.beforeChange?.();
  canvas?.emitBeforeChange?.();
  try {
    const { link, source, slot } = choice;
    node.properties[TOGGLE_SELECTION] = { link, source, slot };
  } finally {
    root.afterChange?.();
    canvas?.emitAfterChange?.();
    root.setDirtyCanvas?.(true, true);
  }
}

export function installToggleControllerHooks(proto) {
  installAutogrowLayoutHooks(proto);
  const original = proto.onSerialize;
  proto.onSerialize = function (data) {
    original?.apply(this, arguments);
    if (this.graph && data.properties && !selectedChoice(this)) {
      delete data.properties[TOGGLE_SELECTION];
    }
  };
}

export function pruneToggleInputs(promptResult, inventory) {
  const output = promptResult?.output;
  if (!output) return promptResult;
  for (const { node, executionId } of inventory.instances) {
    const prompt = output[executionId];
    if (node.type !== TOGGLE_CONTROLLER || prompt?.class_type !== TOGGLE_CONTROLLER) continue;
    const selected = selectedChoice(node)?.name;
    for (const name of Object.keys(prompt.inputs)) {
      if (CHOICE.test(name) && name !== selected) delete prompt.inputs[name];
    }
  }
  return promptResult;
}

function dashboardStyle() {
  if (document.getElementById("workflowx-quick-toggle-style")) return;
  const style = document.createElement("style");
  style.id = "workflowx-quick-toggle-style";
  style.textContent = `
    .workflowx-toggle-list { box-sizing:border-box; contain:size; height:100%; min-height:44px; overflow:auto; padding:4px;
      color:var(--input-text, #ddd); font:12px sans-serif; }
    .workflowx-toggle-row { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1.25fr);
      align-items:center; gap:8px; min-height:32px; padding:2px 0; }
    .workflowx-toggle-title, .workflowx-toggle-path { display:block; overflow:hidden;
      text-overflow:ellipsis; white-space:nowrap; }
    .workflowx-toggle-path, .workflowx-toggle-empty { opacity:.72; }
    .workflowx-toggle-path { font-size:10px; }
    .workflowx-toggle-select { min-width:0; width:100%; font:inherit; padding:4px;
      color:inherit; background:var(--comfy-input-bg, #272727); border:1px solid var(--border-color, #666);
      border-radius:4px; }
  `;
  document.head.append(style);
}

function addDashboard(node, getRootGraph, getCanvas) {
  dashboardStyle();
  const list = document.createElement("div");
  list.className = "workflowx-toggle-list";
  for (const event of ["pointerdown", "pointerup", "click", "wheel"]) {
    list.addEventListener(event, (e) => e.stopPropagation());
  }
  list.addEventListener("keydown", (event) => {
    if (!event.ctrlKey && !event.metaKey) event.stopPropagation();
  });
  node.addDOMWidget("workflowx_toggle_dashboard", "custom", list, {
    serialize: false,
    hideOnZoom: false,
    margin: 8,
    getMinHeight: () => MIN_PANEL_HEIGHT,
  });
  const rendered = new Map();
  const empty = document.createElement("div");
  empty.className = "workflowx-toggle-empty";

  function refresh(force = false) {
    const root = getRootGraph();
    if (!node.graph || (!force && (!list.isConnected || getCanvas()?.graph !== node.graph))) return;
    const onMainCanvas = node.graph === root;
    const rows = onMainCanvas ? toggleRows(root) : [];
    const keys = new Set(rows.map(({ key }) => key));
    for (const [key, row] of rendered) {
      if (!keys.has(key)) {
        row.label.remove();
        rendered.delete(key);
      }
    }
    if (!rows.length) {
      empty.textContent = onMainCanvas ? "Add a ToggleX Controller to this workflow." : "Use Quick ToggleX on the main canvas.";
      if (!empty.parentNode) list.append(empty);
      return;
    }
    empty.remove();
    rows.forEach((record, index) => {
      let row = rendered.get(record.key);
      if (!row) {
        const label = document.createElement("label");
        label.className = "workflowx-toggle-row";
        const caption = document.createElement("span");
        const title = document.createElement("span");
        title.className = "workflowx-toggle-title";
        const path = document.createElement("span");
        path.className = "workflowx-toggle-path";
        const select = document.createElement("select");
        select.className = "workflowx-toggle-select";
        caption.append(title, path);
        label.append(caption, select);
        row = { label, title, path, select };
        rendered.set(record.key, row);
        select.addEventListener("change", () => {
          const currentRoot = getRootGraph();
          const current = toggleRows(currentRoot).find(({ key }) => key === record.key);
          if (current) selectToggleInput(currentRoot, getCanvas(), current.node, select.value);
          refresh(true);
        });
      }
      if (list.children[index] !== row.label) list.insertBefore(row.label, list.children[index] ?? null);
      if (row.title.textContent !== record.title) row.title.textContent = record.title;
      if (row.path.textContent !== record.path) row.path.textContent = record.path;
      row.label.title = [record.path, record.title].filter(Boolean).join(" / ");
      const options = JSON.stringify(record.choices.map(({ link, label }) => [link, label]));
      if (options !== row.options) {
        const placeholder = new Option(record.choices.length ? "Select an input" : "No connected inputs", "");
        placeholder.disabled = true;
        row.select.replaceChildren(placeholder, ...record.choices.map(({ label, link }) => new Option(label, link)));
        row.select.disabled = !record.choices.length;
        row.options = options;
      }
      if (row.select.value !== record.selected) row.select.value = record.selected;
    });
  }

  return refresh;
}

export function registerQuickToggleDashboard(getRootGraph, getCanvas) {
  const { LiteGraph, LGraphNode } = globalThis;
  if (!LiteGraph || !LGraphNode || LiteGraph.registered_node_types[QUICK_TOGGLE]) return;
  class QuickToggleDashboard extends LGraphNode {
    static title = QUICK_TOGGLE;
    isVirtualNode = true;

    constructor(title = QUICK_TOGGLE) {
      super(title);
      this.widgets_up = true;
      this.setSize([...DEFAULT_PANEL_SIZE]);
    }

    onAdded() {
      this.refreshToggleDashboard ??= addDashboard(this, getRootGraph, getCanvas);
      this.refreshToggleDashboard(true);
      this.quickToggleTimer = setInterval(this.refreshToggleDashboard, 250);
    }

    onRemoved() {
      clearInterval(this.quickToggleTimer);
    }
  }
  LiteGraph.registerNodeType(QUICK_TOGGLE, QuickToggleDashboard);
  QuickToggleDashboard.category = "WorkflowX";
}
