import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { logicalGraphs, graphNodes } from "./key_config_graph.mjs";
import {
  RUN_TARGET, SEGMENT_RUN, TARGET_PROPERTY, createSegmentRunner,
  outputTargets, outputLabel, selectedOutput,
} from "./segment_run_x_state.mjs";

let runner;
const rootGraph = () => app.rootGraph ?? app.graph;

function panel(node, name, height) {
  const content = document.createElement("div");
  content.className = "workflowx-segment-panel";
  content.style.minHeight = `${height - 16}px`;
  for (const event of ["pointerdown", "pointerup", "click", "wheel"]) {
    content.addEventListener(event, (e) => e.stopPropagation());
  }
  content.addEventListener("keydown", (event) => {
    if (!event.ctrlKey && !event.metaKey) event.stopPropagation();
  });
  node.addDOMWidget(name, "custom", content, {
    serialize: false, hideOnZoom: false, margin: 8, getMinHeight: () => height,
  });
  return content;
}

function attachTarget(node) {
  const content = panel(node, "segment_run_target", 50);
  const select = document.createElement("select");
  select.setAttribute("aria-label", "Output node");
  content.append(select);
  select.addEventListener("change", () => {
    const target = outputTargets(rootGraph()).find(({ executionId }) => executionId === select.value);
    if (!target) return;
    const root = rootGraph();
    root.beforeChange?.();
    app.canvas?.emitBeforeChange?.();
    try {
      node.properties[TARGET_PROPERTY] = { executionId: target.executionId, type: target.node.type };
    } finally {
      root.afterChange?.();
      app.canvas?.emitAfterChange?.();
    }
  });
  let previous;
  return () => {
    if (!node.graph) return;
    select.disabled = runner?.busy ?? false;
    const targets = outputTargets(rootGraph());
    const selected = selectedOutput(rootGraph(), node);
    const signature = JSON.stringify([targets.map((entry) => [entry.executionId, outputLabel(entry)]),
      node.properties[TARGET_PROPERTY]]);
    if (signature === previous) return;
    previous = signature;
    const placeholder = new Option(node.properties[TARGET_PROPERTY] && !selected
      ? "Output missing. Choose an output…" : "Choose an output…", "");
    placeholder.disabled = true;
    select.replaceChildren(placeholder, ...targets.map((entry) => new Option(outputLabel(entry), entry.executionId)));
    select.value = selected?.executionId ?? "";
  };
}

function attachDashboard(node) {
  const content = panel(node, "segment_run_controls", 78);
  const rendered = new Map();
  const empty = document.createElement("div");
  empty.textContent = "Add a Run TargetX and choose an output.";
  return () => {
    if (!node.graph) return;
    const records = logicalGraphs(rootGraph()).flatMap(({ graph, path }) =>
      graphNodes(graph).filter((marker) => marker.type === RUN_TARGET).map((marker) => ({ marker, path })));
    for (const [marker, row] of rendered) {
      if (!records.some((record) => record.marker === marker)) {
        row.container.remove();
        rendered.delete(marker);
      }
    }
    if (!records.length) {
      if (!empty.parentNode) content.append(empty);
      return;
    }
    empty.remove();
    for (const { marker, path } of records) {
      let row = rendered.get(marker);
      if (!row) {
        const container = document.createElement("div");
        container.className = "workflowx-segment-row";
        const text = document.createElement("span");
        const title = document.createElement("span");
        const output = document.createElement("small");
        const state = document.createElement("small");
        text.append(title, output, state);
        const button = document.createElement("button");
        button.textContent = "▶";
        button.title = "Run";
        button.setAttribute("aria-label", "Run selected output");
        button.type = "button";
        button.addEventListener("click", () => {
          runner.run(marker).catch((error) => {
            state.textContent = error.message;
          });
        });
        container.append(text, button);
        content.append(container);
        row = { container, title, output, state, button };
        rendered.set(marker, row);
      }
      const target = selectedOutput(rootGraph(), marker);
      const title = [...path, marker.title || "Run TargetX"].join(" / ");
      if (row.title.textContent !== title) row.title.textContent = title;
      const output = target ? outputLabel(target) : "Choose an output in Run TargetX";
      if (row.output.textContent !== output) row.output.textContent = output;
      const state = runner?.status(marker) ?? "Ready";
      if (row.state.textContent !== state) {
        row.state.textContent = state;
        row.state.title = state;
      }
      row.button.disabled = !target || !runner || runner.busy;
    }
  };
}

function styles() {
  if (document.getElementById("workflowx-segment-run-style")) return;
  const style = document.createElement("style");
  style.id = "workflowx-segment-run-style";
  style.textContent = `
    .workflowx-segment-panel { box-sizing:border-box; contain:size; height:100%; overflow:auto;
      padding:4px; color:var(--input-text,#ddd); font:12px sans-serif; }
    .workflowx-segment-panel select { width:100%; min-width:0; padding:4px; color:inherit;
      background:var(--comfy-input-bg,#272727); border:1px solid var(--border-color,#666); border-radius:4px; }
    .workflowx-segment-row { display:flex; gap:8px; align-items:center; min-height:48px; padding:3px 0; }
    .workflowx-segment-row > span { flex:1; min-width:0; }
    .workflowx-segment-row span > span, .workflowx-segment-row small { display:block; overflow:hidden;
      text-overflow:ellipsis; white-space:nowrap; }
    .workflowx-segment-row small { opacity:.75; }
    .workflowx-segment-row button { flex:none; padding:4px 8px; border:1px solid var(--border-color,#666);
      color:inherit; background:var(--comfy-input-bg,#272727); border-radius:4px; cursor:pointer; }
    .workflowx-segment-row button:disabled { opacity:.45; cursor:default; }
  `;
  document.head.append(style);
}

app.registerExtension({
  name: "WorkflowX.SegmentRunX",
  registerCustomNodes() {
    styles();
    const { LGraphNode, LiteGraph } = globalThis;
    for (const [type, title, attach, size] of [
      [RUN_TARGET, "Run TargetX", attachTarget, [270, 68]],
      [SEGMENT_RUN, SEGMENT_RUN, attachDashboard, [290, 96]],
    ]) {
      class SegmentController extends LGraphNode {
        static title = title;
        isVirtualNode = true;

        constructor(label = title) {
          super(label);
          this.widgets_up = true;
          this.setSize([...size]);
        }

        onAdded() {
          this.refreshSegment ??= attach(this);
          this.refreshSegment();
          this.segmentTimer = setInterval(this.refreshSegment, 250);
        }

        onRemoved() {
          clearInterval(this.segmentTimer);
        }
      }
      LiteGraph.registerNodeType(type, SegmentController);
      SegmentController.category = "WorkflowX";
    }
  },
  beforeRegisterVueAppNodeDefs(defs) {
    const marker = defs.find((entry) => entry.name === RUN_TARGET);
    if (marker) marker.display_name = "Run TargetX";
  },
  setup() {
    runner = createSegmentRunner({ app, api });
    const load = app.loadGraphData;
    app.loadGraphData = function () {
      runner.abandon();
      return load.apply(this, arguments);
    };
    window.addEventListener("beforeunload", () => runner.abandon());
  },
  afterConfigureGraph() {
    runner?.recover();
  },
});
