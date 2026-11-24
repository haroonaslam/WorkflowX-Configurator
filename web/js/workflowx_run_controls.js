import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { buildGraphInventory } from "./key_config_graph.mjs";
import { outputLabel } from "./segment_run_x_state.mjs";
import { STOP, SOURCE, TARGET, SELECT, SOURCES, LOADERS, buildControls, upstream } from "./workflowx_run_controls_state.mjs";

const root = () => app.rootGraph ?? app.graph;
const records = () => buildGraphInventory(root()).instances;
const identity = (r) => ({ executionId: r.executionId, type: r.node.type });
let rgthree;
const applied = new Set();

function picker(node, panel, label, property, filter) {
  const caption = document.createElement("label");
  caption.textContent = label;
  const select = document.createElement("select");
  select.setAttribute("aria-label", label);
  caption.append(select); panel.append(caption);
  select.addEventListener("change", () => {
    const selected = records().find((r) => r.executionId === select.value);
    root().beforeChange?.();
    node.properties[property] = selected ? identity(selected) : null;
    root().afterChange?.();
  });
  let signature;
  return () => {
    const entries = records().filter(filter);
    const next = JSON.stringify([entries.map((r) => [r.executionId, outputLabel(r)]), node.properties[property]]);
    if (signature === next) return;
    signature = next;
    const current = node.properties[property];
    const selected = entries.find((r) => r.executionId === current?.executionId && r.node.type === current?.type);
    select.replaceChildren(new Option(current && !selected ? "Selection missing…" : "Choose a node…", ""),
      ...entries.map((r) => new Option(outputLabel(r), r.executionId)));
    select.value = selected?.executionId ?? "";
  };
}

function attach(node) {
  const panel = document.createElement("div");
  panel.className = "workflowx-run-control-panel";
  for (const event of ["pointerdown", "pointerup", "click", "wheel", "keydown"]) panel.addEventListener(event, (e) => e.stopPropagation());
  const refresh = [];
  if (node.type === TARGET) refresh.push(picker(node, panel, "Image SourceX", "workflowx_source", (r) => r.node.type === SOURCE));
  refresh.push(picker(node, panel, node.type === STOP ? "Stop after" : node.type === SOURCE ? "Image from" : "Copy to", SELECT,
    (r) => node.type === STOP ? !r.node.isVirtualNode && !["WorkflowX_RunControls", "WorkflowX_ImageTransferLoader", "WorkflowX_ImageTransferLoaderAdv"].includes(r.node.type)
      : (node.type === SOURCE ? SOURCES : LOADERS).has(r.node.type)));
  if (node.type === TARGET) {
    const mode = document.createElement("select");
    mode.setAttribute("aria-label", "Transfer timing");
    mode.append(new Option("Prepare next run", "next_run"), new Option("Use in this run", "same_run"));
    mode.value = node.properties.workflowx_transfer_mode ?? "next_run";
    mode.addEventListener("change", () => {
      root().beforeChange?.(); node.properties.workflowx_transfer_mode = mode.value; root().afterChange?.();
    });
    panel.append(mode);
    refresh.push(() => { mode.value = node.properties.workflowx_transfer_mode ?? "next_run"; });
  }
  const status = document.createElement("small");
  status.textContent = node.type === STOP ? "Normal runs only" : "First image · preserves loader mode";
  node._workflowxRunControlStatus = status;
  panel.append(status);
  const height = node.type === TARGET ? 155 : 65;
  node.addDOMWidget("workflowx_run_control", "custom", panel, {
    serialize: false, hideOnZoom: false, margin: 8, getMinHeight: () => height,
  });
  return () => refresh.forEach((fn) => fn());
}

function receive(record) {
  const key = `${record.prompt_id}:${record.id}`;
  if (applied.has(key) || record.workflow !== (root()?.id ?? root()?.uuid)) return;
  const target = records().find((r) => r.executionId === record.target && r.node.type === record.target_type)?.node;
  if (!target) return;
  if (record.completed_at && Number(target.properties.workflowx_transfer_received_at ?? 0) >= record.completed_at) return;
  // No mode check: a muted/bypassed loader is still a valid image mailbox.
  if (target.workflowxReceiveImage) target.workflowxReceiveImage(record.image);
  else {
    const widget = target.widgets?.find((w) => w.name === "image");
    if (!widget) return;
    const selected = `${record.image.subfolder}/${record.image.name} [temp]`;
    if (Array.isArray(widget.options?.values) && !widget.options.values.includes(selected)) widget.options.values.push(selected);
    widget.value = selected;
    widget.callback?.(selected);
    const image = new Image();
    image.onload = () => { target.imgs = [image]; target.setDirtyCanvas?.(true, true); };
    image.src = api.apiURL(`/view?filename=${encodeURIComponent(record.image.name)}&subfolder=${encodeURIComponent(record.image.subfolder)}&type=temp`);
  }
  applied.add(key);
  if (record.completed_at) target.properties.workflowx_transfer_received_at = record.completed_at;
  target.setDirtyCanvas?.(true, true);
  root().change?.();
  const marker = records().find((r) => r.executionId === record.id && r.node.type === TARGET)?.node;
  if (marker?._workflowxRunControlStatus) marker._workflowxRunControlStatus.textContent = "Image copied · loader mode preserved";
}

async function recoverHistory(promptId) {
  const response = await api.fetchApi(promptId ? `/history/${encodeURIComponent(promptId)}` : "/history?max_items=30");
  if (!response.ok) return;
  for (const history of Object.values(await response.json())) {
    for (const output of Object.values(history.outputs ?? {})) {
      for (const record of output.workflowx_transfers ?? []) receive(record);
    }
  }
}

app.registerExtension({
  name: "WorkflowX.RunControls",
  registerCustomNodes() {
    const style = document.createElement("style");
    style.textContent = `.workflowx-run-control-panel { box-sizing:border-box; contain:size; height:100%; overflow:auto; padding:4px; color:var(--input-text,#ddd); font:12px sans-serif; }
      .workflowx-run-control-panel label { display:block; margin-bottom:5px; }
      .workflowx-run-control-panel select { display:block; box-sizing:border-box; width:100%; min-width:0; padding:4px; color:inherit; background:var(--comfy-input-bg,#272727); border:1px solid var(--border-color,#666); border-radius:4px; }
      .workflowx-run-control-panel small { display:block; margin-top:4px; opacity:.7; }`;
    document.head.append(style);
    for (const type of [STOP, SOURCE, TARGET]) {
      class Controller extends globalThis.LGraphNode {
        static title = type;
        isVirtualNode = true;
        constructor(title = type) { super(title); this.resizable = true; this.setSize([260, type === TARGET ? 175 : 85]); }
        onAdded() { this.refreshControls ??= attach(this); this.refreshControls(); this.controlsTimer = setInterval(this.refreshControls, 400); }
        onRemoved() { clearInterval(this.controlsTimer); }
      }
      globalThis.LiteGraph.registerNodeType(type, Controller);
      Controller.category = "WorkflowX";
    }
  },
  async setup() {
    // rgthree's output filter runs before the final /prompt request. Read its
    // explicit queue intent rather than guessing from an upstream closure.
    try { ({ rgthree } = await import("/extensions/rgthree-comfy/rgthree.js")); } catch { /* optional extension */ }
    const fetch = api.fetchApi;
    api.fetchApi = async function (route, options, ...args) {
      if (route !== "/prompt" || options?.method !== "POST" || !options.body) return fetch.call(this, route, options, ...args);
      const body = JSON.parse(options.body);
      const inventory = records();
      if (!inventory.some((r) => [STOP, SOURCE, TARGET].includes(r.node.type))) return fetch.call(this, route, options, ...args);
      const graph = root();
      const workflow = body.extra_data?.extra_pnginfo?.workflow;
      if (workflow && workflow.id !== (graph.id ?? graph.uuid)) return fetch.call(this, route, options, ...args);
      const selective = !!body.partial_execution_targets?.length || !!rgthree?.queueNodeIds?.length;
      const outputIds = inventory.filter((r) => body.prompt[r.executionId] &&
        (r.node.constructor.nodeData?.output_node || r.node.constructor.output_node)).map((r) => r.executionId);
      const originallyReachable = new Set(outputIds.flatMap((id) => [...upstream(body.prompt, id)]));
      const find = (selection) => inventory.find((r) => r.executionId === selection?.executionId && r.node.type === selection?.type);
      const active = (r) => r && ![2, 4].includes(r.node.mode) && !r.ancestors.some(({ node }) => [2, 4].includes(node.mode));
      // A same-run destination needs the source's upstream closure even during
      // selected-output queues. Never force a muted source into a normal run.
      for (const marker of inventory.filter((r) => r.node.type === TARGET && active(r))) {
        const target = find(marker.node.properties?.[SELECT]);
        const targetId = LOADERS.has(target?.node.type) ? target.executionId : null;
        const sourceMarker = find(marker.node.properties?.workflowx_source);
        if (sourceMarker?.node.type !== SOURCE || !active(sourceMarker)) continue;
        const source = find(sourceMarker.node.properties?.[SELECT]);
        const sourceId = SOURCES.has(source?.node.type) ? source.executionId : null;
        if (!sourceId || !targetId || marker.node.properties.workflowx_transfer_mode !== "same_run" || !body.prompt[targetId]) continue;
        if (selective && !originallyReachable.has(targetId)) continue;
        if (!body.prompt[sourceId] && app.workflowxCompileSegment) {
          if (!selective && !active(source)) continue;
          const compiled = await app.workflowxCompileSegment(graph, sourceId);
          for (const id of upstream(compiled.result.output, sourceId)) body.prompt[id] ??= compiled.result.output[id];
        }
      }
      if (root() !== graph) throw new Error("Workflow changed while preparing Image TargetX. Queue again.");
      const control = buildControls(body.prompt, inventory, { selective, outputIds, workflow: graph.id ?? graph.uuid, nonce: crypto.randomUUID() });
      if (control && body.partial_execution_targets) body.partial_execution_targets.push(control);
      return fetch.call(this, route, { ...options, body: JSON.stringify(body) }, ...args);
    };
    api.addEventListener("workflowx_image_transfer", ({ detail }) => receive(detail));
    api.addEventListener("workflowx_stopped", ({ detail }) => {
      if (detail.workflow !== (root()?.id ?? root()?.uuid)) return;
      for (const { node } of records()) {
        if (node.type === STOP && node.properties[SELECT]?.executionId === detail.node && node._workflowxRunControlStatus) {
          node._workflowxRunControlStatus.textContent = "Stopped after selected node";
        }
      }
    });
    api.addEventListener("execution_success", ({ detail }) => recoverHistory(detail.prompt_id).catch(console.warn));
    api.addEventListener("reconnected", () => recoverHistory().catch(console.warn));
  },
  afterConfigureGraph() { recoverHistory().catch(console.warn); },
});
