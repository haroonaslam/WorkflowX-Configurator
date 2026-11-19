import { graphGroups, graphNodes, intersects, logicalGraphs } from "./key_config_graph.mjs";

export const QUICK_MODES = [
  { type: "WorkflowXQuickMute", title: "Quick MuteX", mode: 2 },
  { type: "WorkflowXQuickBypass", title: "Quick BypassX", mode: 4 },
];

const TARGETS = "workflowx_quick_targets";
const ACTIVE = 0;
const MIN_LIST_HEIGHT = 54;
const DEFAULT_SIZE = [220, 72];
const lastKnownLabels = new WeakMap();

export function isQuickModeController(node) {
  return QUICK_MODES.some(({ type }) => node?.type === type);
}

function targetEntries(controller) {
  const value = controller.properties?.[TARGETS];
  return Array.isArray(value)
    ? value.filter((ref) => ref && (typeof ref.nodeId === "string" || typeof ref.groupId === "string"))
    : [];
}

function graphId(graph) {
  return String(graph?.uuid ?? graph?.id ?? "");
}

function titleOf(node) {
  return String(node.title || node.constructor.title || node.type || (node.nodes ? "Group" : "Node"));
}

function sameTarget(a, b) {
  return a.graphId === b.graphId && a.groupId === b.groupId && a.nodeId === b.nodeId && a.type === b.type;
}

function changeGraph(graph, canvas, change) {
  graph.beforeChange?.();
  canvas?.emitBeforeChange?.();
  try {
    change();
  } finally {
    graph.afterChange?.();
    canvas?.emitAfterChange?.();
    graph.setDirtyCanvas?.(true, true);
  }
}

function placeController(graph, controller, anchor) {
  const [x, y] = anchor.pos;
  controller.pos = [x + (anchor.size?.[0] ?? 0) + 32, y];
  const [width, height] = controller.size;
  const neighbors = graphNodes(graph);
  const placement = { pos: [controller.pos[0], y - 36], size: [width, height + 72] };
  while (neighbors.some((node) => intersects(placement, node))) {
    placement.pos[1] += height + 44;
  }
  controller.pos[1] = placement.pos[1] + 36;
}

export function addQuickTarget(graph, target, spec, createNode, canvas) {
  const location = logicalGraphs(graph).find((entry) => entry.graph === target.graph);
  const isGroup = graphGroups(location?.graph).includes(target);
  if (!location || (!isGroup && !graphNodes(location.graph).includes(target)) || isQuickModeController(target)) {
    throw new Error("This target is outside the current workflow.");
  }
  if (target.id == null) throw new Error("This target has no saved ID.");
  const id = location.isRoot ? null : graphId(location.graph);
  if (id === "") throw new Error("This subgraph has no saved ID.");
  const ref = {
    graphId: id,
    ...(isGroup ? { groupId: String(target.id) } : { nodeId: String(target.id), type: target.type }),
    title: titleOf(target),
    path: location.path.join(" / "),
  };
  const controllers = graphNodes(graph).filter((node) => node.type === spec.type);
  const existing = controllers.find((node) => targetEntries(node).some((entry) => sameTarget(entry, ref)));
  if (existing) return { controller: existing, added: false };

  const controller = controllers[0] ?? createNode(spec.type);
  if (!controller) throw new Error(`${spec.title} could not be created.`);
  changeGraph(graph, canvas, () => {
    if (!controllers.length) {
      placeController(graph, controller, location.rootNode ?? target);
      graph.add(controller);
    }
    controller.properties[TARGETS] = [...targetEntries(controller), ref];
  });
  return { controller, added: true };
}

export function quickTargetRows(graph, controller) {
  const refs = targetEntries(controller);
  if (!refs.length) return [];
  const locations = new Map([[null, { graph, path: [] }]]);
  if (refs.some((ref) => ref.graphId !== null)) {
    for (const location of logicalGraphs(graph)) {
      if (!location.isRoot) locations.set(graphId(location.graph), location);
    }
  }
  return refs.map((ref) => {
    const location = locations.get(ref.graphId);
    const targetGraph = location?.graph;
    const group = ref.groupId === undefined ? undefined
      : graphGroups(targetGraph).find((candidate) => String(candidate.id) === ref.groupId);
    const target = ref.nodeId === undefined ? undefined : targetGraph?.getNodeById?.(ref.nodeId)
      ?? graphNodes(targetGraph).find((candidate) => String(candidate.id) === ref.nodeId);
    const node = target?.type === ref.type ? target : undefined;
    const entity = group ?? node;
    const lastKnown = lastKnownLabels.get(ref);
    const title = entity ? titleOf(entity) : lastKnown?.title ?? ref.title ?? (ref.groupId === undefined ? "Node" : "Group");
    const path = location?.path.join(" / ") ?? lastKnown?.path ?? ref.path ?? "";
    if (entity && (title !== lastKnown?.title || path !== lastKnown?.path)) {
      lastKnownLabels.set(ref, { title, path });
    }
    return { ref, node, group, title, path };
  });
}

function groupMembers(group) {
  // Match native group membership without its recompute step, which sorts the graph's groups.
  const [x, y, width, height] = group.boundingRect ?? [...group.pos, ...group.size];
  return graphNodes(group.graph).filter((node) => {
    if (isQuickModeController(node)) return false;
    const [left, top, w, h] = node.boundingRect ?? [...node.pos, ...node.size];
    const cx = left + w / 2;
    const cy = top + h / 2;
    return cx >= x && cx <= x + width && cy >= y && cy <= y + height;
  });
}

export function setQuickTargetMode(graph, controller, ref, mode, enabled, canvas) {
  const row = quickTargetRows(graph, controller).find((entry) => sameTarget(entry.ref, ref));
  const targets = row?.group ? groupMembers(row.group) : row?.node ? [row.node] : [];
  const nextMode = enabled ? ACTIVE : mode;
  const changed = targets.filter((target) => target.mode !== nextMode);
  if (!changed.length) return;
  changeGraph(graph, canvas, () => {
    for (const target of changed) {
      if (target.changeMode) target.changeMode(nextMode);
      else target.mode = nextMode;
    }
    (row.group ?? row.node).graph?.setDirtyCanvas?.(true, true);
  });
}

export function removeQuickTarget(graph, controller, ref, canvas) {
  const refs = targetEntries(controller);
  const remaining = refs.filter((entry) => !sameTarget(entry, ref));
  if (refs.length === remaining.length) return;
  changeGraph(graph, canvas, () => {
    controller.properties[TARGETS] = remaining;
  });
}

function element(tag, className, content) {
  const item = document.createElement(tag);
  item.className = className;
  if (content) item.textContent = content;
  return item;
}

function installStyles() {
  if (document.getElementById("workflowx-quick-mode-style")) return;
  const style = document.createElement("style");
  style.id = "workflowx-quick-mode-style";
  style.textContent = `
    .workflowx-quick-list { box-sizing:border-box; contain:size; height:100%; min-height:40px; overflow:auto; padding:4px;
      color:var(--input-text, #ddd); font:12px sans-serif; }
    .workflowx-quick-row { display:flex; align-items:center; gap:6px; min-height:28px; padding:2px 0; }
    .workflowx-quick-label { flex:1; display:flex; align-items:center; gap:6px; min-width:0; }
    .workflowx-quick-name, .workflowx-quick-path { display:block; overflow:hidden; text-overflow:ellipsis;
      white-space:nowrap; }
    .workflowx-quick-text { flex:1; min-width:0; }
    .workflowx-quick-path, .workflowx-quick-empty { opacity:.72; }
    .workflowx-quick-path { font-size:10px; }
    .workflowx-quick-toggle { appearance:none; flex:none; width:28px; height:16px; margin:0;
      border-radius:10px; border:1px solid #888; background:var(--comfy-input-bg, #333);
      display:grid; align-items:center; padding:2px; cursor:pointer; }
    .workflowx-quick-toggle::before { content:""; width:10px; height:10px; border-radius:50%;
      background:currentColor; }
    .workflowx-quick-toggle:checked { justify-items:end; background:#39744c; color:#fff; }
    .workflowx-quick-toggle:indeterminate { justify-items:center; color:#e2aa58; }
    .workflowx-quick-toggle:disabled { opacity:.45; cursor:default; }
    .workflowx-quick-remove { font:inherit; padding:2px 5px; border:0; border-radius:3px;
      color:inherit; background:transparent; cursor:pointer; }
    .workflowx-quick-remove:hover { background:var(--comfy-input-bg, #333); }
  `;
  document.head.append(style);
}

function attachList(controller, mode, getRootGraph, getCanvas) {
  installStyles();
  const list = element("div", "workflowx-quick-list");
  for (const event of ["pointerdown", "pointerup", "click", "wheel"]) {
    list.addEventListener(event, (e) => e.stopPropagation());
  }
  list.addEventListener("keydown", (event) => {
    if (!event.ctrlKey && !event.metaKey) event.stopPropagation();
  });
  controller.addDOMWidget("workflowx_quick_targets", "custom", list, {
    serialize: false,
    hideOnZoom: false,
    margin: 8,
    getMinHeight: () => MIN_LIST_HEIGHT,
  });

  let previous;
  function refresh(force = false) {
    const graph = controller.graph;
    if (!graph || (!force && !list.isConnected)) return;
    const onMainCanvas = graph === getRootGraph();
    const rows = (onMainCanvas ? quickTargetRows(graph, controller) : []).map((row) => {
      const members = row.group ? groupMembers(row.group) : row.node ? [row.node] : [];
      const current = members[0]?.mode;
      return { ...row, missing: !row.group && !row.node, empty: !members.length,
        mixed: members.some((member) => member.mode !== current), active: current === ACTIVE };
    });
    const view = rows.map(({ ref, title, path, missing, empty, mixed, active }) =>
      [ref.graphId, ref.groupId, ref.nodeId, ref.type, title, path, missing, empty, mixed, active]);
    const signature = JSON.stringify([onMainCanvas, view]);
    if (signature === previous) return;
    previous = signature;

    const focused = list.contains(document.activeElement) ? document.activeElement : null;
    const focusKey = focused?.dataset.quickControl;
    const scrollTop = list.scrollTop;
    list.replaceChildren();
    if (!rows.length) {
      const message = onMainCanvas ? "Right-click a node or group to add it here." : "Use this controller on the main canvas.";
      list.append(element("div", "workflowx-quick-empty", message));
      return;
    }
    for (const { ref, title, path, missing, empty, mixed, active } of rows) {
      const key = JSON.stringify([ref.graphId, ref.groupId, ref.nodeId, ref.type]);
      const row = element("div", "workflowx-quick-row");
      const label = element("label", "workflowx-quick-label");
      const text = element("span", "workflowx-quick-text");
      text.append(element("span", "workflowx-quick-name", missing ? `${title} (missing)` : title));
      if (path) text.append(element("span", "workflowx-quick-path", path));
      text.title = path ? `${title} — ${path}` : title;
      const toggle = element("input", "workflowx-quick-toggle");
      toggle.type = "checkbox";
      toggle.dataset.quickControl = `toggle:${key}`;
      if (ref.groupId === undefined) toggle.setAttribute("role", "switch");
      toggle.checked = active && !mixed;
      toggle.indeterminate = mixed;
      toggle.disabled = empty;
      if (mixed) toggle.title = "Mixed modes. Click to enable all group members.";
      else if (empty && !missing) toggle.title = "No nodes in group";
      toggle.addEventListener("change", () => {
        setQuickTargetMode(graph, controller, ref, mode, toggle.checked, getCanvas());
        refresh(true);
      });
      label.append(text, toggle);
      const remove = element("button", "workflowx-quick-remove", "×");
      remove.type = "button";
      remove.dataset.quickControl = `remove:${key}`;
      remove.setAttribute("aria-label", `Remove ${title} from this list`);
      remove.title = "Remove from list";
      remove.addEventListener("click", () => {
        removeQuickTarget(graph, controller, ref, getCanvas());
        refresh(true);
      });
      row.append(label, remove);
      list.append(row);
      if (toggle.dataset.quickControl === focusKey) toggle.focus();
      if (remove.dataset.quickControl === focusKey) remove.focus();
    }
    list.scrollTop = scrollTop;
  }

  return refresh;
}

export function registerQuickModeNodes(getRootGraph, getCanvas) {
  const { LiteGraph, LGraphNode } = globalThis;
  if (!LiteGraph || !LGraphNode) return;
  for (const spec of QUICK_MODES) {
    if (LiteGraph.registered_node_types[spec.type]) continue;
    class QuickModeController extends LGraphNode {
      static title = spec.title;
      isVirtualNode = true;

      constructor(title = spec.title) {
        super(title);
        this.properties[TARGETS] = [];
        this.widgets_up = true;
        this.setSize([...DEFAULT_SIZE]);
      }

      onAdded() {
        this.refreshQuickTargets ??= attachList(this, spec.mode, getRootGraph, getCanvas);
        this.refreshQuickTargets(true);
        this.quickModeTimer = setInterval(this.refreshQuickTargets, 250);
      }

      onRemoved() {
        clearInterval(this.quickModeTimer);
      }

      onSerialize(data) {
        const saved = data.properties?.[TARGETS];
        if (!this.graph || !Array.isArray(saved) || !saved.length) return;
        const labels = quickTargetRows(this.graph, this);
        for (const ref of saved) {
          const label = labels.find((row) => sameTarget(row.ref, ref));
          if (label) Object.assign(ref, { title: label.title, path: label.path });
        }
      }
    }
    LiteGraph.registerNodeType(spec.type, QuickModeController);
    QuickModeController.category = "WorkflowX";
  }
}
