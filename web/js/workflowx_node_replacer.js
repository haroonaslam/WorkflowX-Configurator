import { app } from "../../scripts/app.js";
import { $el } from "../../scripts/ui.js";

const EXTENSION_NAME = "Comfy.WorkflowXNodeReplacer";
const MENU_LABEL = "WorkflowX: Replace node...";
const CATALOG = new Map();
const WILDCARD_TYPES = new Set(["*", "any", "ANY", "WILDCARD", "undefined"]);

let activeDialog = null;
let toastTimer = null;

function getGraph() {
  return app.graph || app.canvas?.graph;
}

function getCanvas() {
  return app.canvas;
}

function markDirty() {
  getCanvas()?.setDirty?.(true, true);
  getGraph()?.setDirtyCanvas?.(true, true);
}

function nodeClass(node) {
  return node?.comfyClass || node?.constructor?.comfyClass || node?.type || node?.constructor?.type || "";
}

function nodeDisplayName(nodeData, nodeTypeDef) {
  return nodeData?.display_name || nodeTypeDef?.title || nodeTypeDef?.type || nodeData?.name || "Unknown node";
}

function registerCatalogEntry(nodeTypeDef, nodeData) {
  const className = nodeData?.name || nodeTypeDef?.comfyClass || nodeTypeDef?.type;
  if (!className) return;

  CATALOG.set(className, {
    className,
    displayName: nodeDisplayName(nodeData, nodeTypeDef),
    category: nodeData?.category || "Other",
  });
}

function splitTypes(type) {
  if (type == null) return ["*"];
  if (Array.isArray(type)) return type.flatMap(splitTypes);
  return String(type)
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function typeKey(type) {
  return String(type || "").trim();
}

function isWildcardType(type) {
  return splitTypes(type).some((part) => WILDCARD_TYPES.has(part) || WILDCARD_TYPES.has(part.toUpperCase()));
}

function compatibleTypes(leftType, rightType) {
  const left = splitTypes(leftType);
  const right = splitTypes(rightType);
  if (isWildcardType(leftType) || isWildcardType(rightType)) return true;

  const rightKeys = new Set(right.map((part) => typeKey(part).toUpperCase()));
  return left.some((part) => rightKeys.has(typeKey(part).toUpperCase()));
}

function cloneValue(value) {
  if (typeof structuredClone === "function") {
    try {
      return structuredClone(value);
    } catch {
      // Fall through to JSON clone below.
    }
  }

  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return value;
  }
}

function copyVisualState(oldNode, newNode) {
  newNode.pos = [Number(oldNode.pos?.[0] || 0), Number(oldNode.pos?.[1] || 0)];
  if (oldNode.color !== undefined) newNode.color = oldNode.color;
  if (oldNode.bgcolor !== undefined) newNode.bgcolor = oldNode.bgcolor;
  if (oldNode.mode !== undefined) newNode.mode = oldNode.mode;
  if (oldNode.flags) newNode.flags = { ...newNode.flags, ...cloneValue(oldNode.flags) };

  const oldDefaultTitle = oldNode.constructor?.title || oldNode.type || nodeClass(oldNode);
  if (oldNode.title && oldNode.title !== oldDefaultTitle) {
    newNode.title = oldNode.title;
  }
}

function copyWidgetValues(oldNode, newNode) {
  const oldWidgets = new Map((oldNode.widgets || []).map((widget) => [widget.name, widget]));
  let copied = 0;

  for (const widget of newNode.widgets || []) {
    const oldWidget = oldWidgets.get(widget.name);
    if (!oldWidget) continue;

    widget.value = cloneValue(oldWidget.value);
    copied += 1;

    try {
      widget.callback?.call(widget, widget.value, getCanvas(), newNode, getCanvas()?.graph_mouse);
    } catch (error) {
      console.warn("[WorkflowX] Could not apply copied widget value", widget.name, error);
    }
  }

  return copied;
}

function copySize(oldNode, newNode) {
  const oldSize = oldNode.size || [];
  const newSize = newNode.size || [];
  const width = Math.max(Number(oldSize[0] || 0), Number(newSize[0] || 0));
  const height = Math.max(Number(oldSize[1] || 0), Number(newSize[1] || 0));
  if (width > 0 && height > 0) newNode.size = [width, height];
}

function collectInputLinks(node) {
  const graph = getGraph();
  const links = [];

  (node.inputs || []).forEach((input, slot) => {
    if (input?.link == null) return;
    const link = graph?.links?.[input.link];
    const originNode = graph?.getNodeById?.(link?.origin_id);
    if (!link || !originNode || originNode === node) return;

    links.push({
      oldSlot: slot,
      name: input.name,
      type: input.type,
      originType: originNode.outputs?.[link.origin_slot]?.type,
      originNode,
      originSlot: link.origin_slot,
    });
  });

  return links;
}

function collectOutputLinks(node) {
  const graph = getGraph();
  const outputs = [];

  (node.outputs || []).forEach((output, slot) => {
    const links = [];
    for (const linkId of output?.links || []) {
      const link = graph?.links?.[linkId];
      const targetNode = graph?.getNodeById?.(link?.target_id);
      if (!link || !targetNode || targetNode === node) continue;

      links.push({
        targetNode,
        targetSlot: link.target_slot,
        targetType: targetNode.inputs?.[link.target_slot]?.type,
      });
    }

    if (links.length) {
      outputs.push({
        oldSlot: slot,
        name: output.name,
        type: output.type,
        links,
      });
    }
  });

  return outputs;
}

function inputLinkCompatible(oldSlot, newSlot) {
  return compatibleTypes(oldSlot.originType || oldSlot.type, newSlot?.type);
}

function outputLinkCompatible(oldSlot, newSlot) {
  if (!compatibleTypes(oldSlot.type, newSlot?.type)) return false;
  return oldSlot.links.every((link) => compatibleTypes(newSlot?.type, link.targetType || oldSlot.type));
}

function mapSlots(oldSlots, newSlots, isCompatible = (oldSlot, newSlot) => compatibleTypes(oldSlot.type, newSlot?.type)) {
  const mapped = new Map();
  const usedNewSlots = new Set();

  for (const oldSlot of oldSlots) {
    const match = newSlots.find(
      (slot, index) =>
        !usedNewSlots.has(index) &&
        slot?.name === oldSlot.name &&
        isCompatible(oldSlot, slot),
    );

    if (match) {
      const index = newSlots.indexOf(match);
      mapped.set(oldSlot.oldSlot, index);
      usedNewSlots.add(index);
    }
  }

  for (const oldSlot of oldSlots) {
    if (mapped.has(oldSlot.oldSlot)) continue;

    const index = newSlots.findIndex(
      (slot, newSlot) => !usedNewSlots.has(newSlot) && isCompatible(oldSlot, slot),
    );

    if (index !== -1) {
      mapped.set(oldSlot.oldSlot, index);
      usedNewSlots.add(index);
    }
  }

  return mapped;
}

function reconnectInputs(oldInputLinks, newNode) {
  const inputMap = mapSlots(oldInputLinks, newNode.inputs || [], inputLinkCompatible);
  let kept = 0;

  for (const link of oldInputLinks) {
    const newSlot = inputMap.get(link.oldSlot);
    if (newSlot == null) continue;
    link.originNode.connect(link.originSlot, newNode, newSlot);
    kept += 1;
  }

  return { kept, skipped: oldInputLinks.length - kept };
}

function reconnectOutputs(oldOutputLinks, newNode) {
  const outputMap = mapSlots(oldOutputLinks, newNode.outputs || [], outputLinkCompatible);
  let kept = 0;
  let total = 0;

  for (const output of oldOutputLinks) {
    total += output.links.length;
    const newSlot = outputMap.get(output.oldSlot);
    if (newSlot == null) continue;

    for (const link of output.links) {
      newNode.connect(newSlot, link.targetNode, link.targetSlot);
      kept += 1;
    }
  }

  return { kept, skipped: total - kept };
}

function showToast(message) {
  clearTimeout(toastTimer);
  document.getElementById("workflowx-node-replacer-toast")?.remove();

  const toast = $el("div.workflowx-node-replacer-toast", {
    id: "workflowx-node-replacer-toast",
    textContent: message,
    parent: document.body,
  });

  toastTimer = setTimeout(() => toast.remove(), 3600);
}

function replaceNode(oldNode, targetClass) {
  const graph = getGraph();
  const liteGraph = globalThis.LiteGraph;
  if (!graph || !liteGraph?.createNode) {
    showToast("WorkflowX replace failed: graph is not ready.");
    return;
  }

  const newNode = liteGraph.createNode(targetClass);
  if (!newNode) {
    showToast(`WorkflowX replace failed: ${targetClass} could not be created.`);
    return;
  }

  const oldInputLinks = collectInputLinks(oldNode);
  const oldOutputLinks = collectOutputLinks(oldNode);

  let newNodeAdded = false;
  let oldNodeRemoved = false;

  try {
    graph.beforeChange?.();
    copyVisualState(oldNode, newNode);
    graph.add(newNode, false);
    newNodeAdded = true;
    const copiedWidgets = copyWidgetValues(oldNode, newNode);
    copySize(oldNode, newNode);

    const inputResult = reconnectInputs(oldInputLinks, newNode);
    const outputResult = reconnectOutputs(oldOutputLinks, newNode);

    graph.remove(oldNode);
    oldNodeRemoved = true;
    graph.afterChange?.();
    markDirty();

    const kept = inputResult.kept + outputResult.kept;
    const skipped = inputResult.skipped + outputResult.skipped;
    const widgetText = copiedWidgets ? `, ${copiedWidgets} widget values copied` : "";
    showToast(`Replaced node: ${kept} links kept, ${skipped} skipped${widgetText}.`);
  } catch (error) {
    console.error("[WorkflowX] Node replacement failed", error);
    if (newNodeAdded && !oldNodeRemoved) {
      try {
        graph.remove(newNode);
      } catch (cleanupError) {
        console.warn("[WorkflowX] Could not clean up failed replacement node", cleanupError);
      }
    }
    graph.afterChange?.();
    markDirty();
    showToast(`WorkflowX replace failed: ${error?.message || error}`);
  }
}

function catalogItemsFor(currentClass) {
  return Array.from(CATALOG.values())
    .filter((item) => item.className !== currentClass)
    .sort((left, right) => {
      const categoryCompare = left.category.localeCompare(right.category);
      if (categoryCompare !== 0) return categoryCompare;
      return left.displayName.localeCompare(right.displayName);
    });
}

function matchesQuery(item, query) {
  if (!query) return true;
  const haystack = `${item.displayName} ${item.className} ${item.category}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((part) => haystack.includes(part));
}

function closeDialog() {
  activeDialog?.remove();
  activeDialog = null;
}

function createDialogStyles() {
  if (document.getElementById("workflowx-node-replacer-style")) return;

  $el("style", {
    id: "workflowx-node-replacer-style",
    textContent: `
.workflowx-node-replacer-overlay {
  align-items: center;
  background: rgba(0, 0, 0, .52);
  bottom: 0;
  display: flex;
  justify-content: center;
  left: 0;
  position: fixed;
  right: 0;
  top: 0;
  z-index: 10000;
}
.workflowx-node-replacer-dialog {
  background: var(--comfy-menu-bg, #181a20);
  border: 1px solid var(--border-color, #3c3f45);
  border-radius: 8px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, .45);
  color: var(--fg-color, #e7e9ee);
  display: flex;
  flex-direction: column;
  max-height: min(720px, 82vh);
  max-width: min(760px, 92vw);
  min-height: 420px;
  overflow: hidden;
  width: 680px;
}
.workflowx-node-replacer-header {
  border-bottom: 1px solid var(--border-color, #3c3f45);
  display: flex;
  gap: 10px;
  padding: 12px;
}
.workflowx-node-replacer-search {
  background: var(--comfy-input-bg, #101217);
  border: 1px solid var(--border-color, #3c3f45);
  border-radius: 6px;
  color: var(--fg-color, #e7e9ee);
  flex: 1;
  font: inherit;
  min-width: 0;
  padding: 9px 11px;
}
.workflowx-node-replacer-close {
  background: var(--comfy-input-bg, #101217);
  border: 1px solid var(--border-color, #3c3f45);
  border-radius: 6px;
  color: var(--fg-color, #e7e9ee);
  cursor: pointer;
  height: 38px;
  width: 38px;
}
.workflowx-node-replacer-results {
  overflow: auto;
  padding: 8px;
}
.workflowx-node-replacer-row {
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  display: grid;
  gap: 3px;
  grid-template-columns: minmax(0, 1fr) auto;
  padding: 9px 10px;
}
.workflowx-node-replacer-row:hover,
.workflowx-node-replacer-row.active {
  background: color-mix(in srgb, var(--comfy-input-bg, #101217) 72%, #38bdf8 16%);
  border-color: color-mix(in srgb, var(--border-color, #3c3f45) 70%, #38bdf8 30%);
}
.workflowx-node-replacer-name,
.workflowx-node-replacer-category,
.workflowx-node-replacer-class {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflowx-node-replacer-name {
  font-weight: 600;
}
.workflowx-node-replacer-category,
.workflowx-node-replacer-class {
  color: color-mix(in srgb, var(--fg-color, #e7e9ee) 62%, transparent);
  font-size: 12px;
}
.workflowx-node-replacer-empty {
  color: color-mix(in srgb, var(--fg-color, #e7e9ee) 68%, transparent);
  padding: 24px 12px;
  text-align: center;
}
.workflowx-node-replacer-toast {
  background: var(--comfy-menu-bg, #181a20);
  border: 1px solid var(--border-color, #3c3f45);
  border-radius: 6px;
  bottom: 24px;
  box-shadow: 0 12px 38px rgba(0, 0, 0, .35);
  color: var(--fg-color, #e7e9ee);
  left: 50%;
  max-width: min(760px, 90vw);
  padding: 10px 14px;
  position: fixed;
  transform: translateX(-50%);
  z-index: 10001;
}
`,
    parent: document.head,
  });
}

function openReplaceDialog(sourceNode) {
  createDialogStyles();
  closeDialog();

  const currentClass = nodeClass(sourceNode);
  const allItems = catalogItemsFor(currentClass);
  let visibleItems = allItems;
  let activeIndex = 0;

  const overlay = $el("div.workflowx-node-replacer-overlay", { parent: document.body });
  const dialog = $el("div.workflowx-node-replacer-dialog", { parent: overlay });
  const header = $el("div.workflowx-node-replacer-header", { parent: dialog });
  const search = $el("input.workflowx-node-replacer-search", {
    placeholder: "Search replacement nodes",
    value: "",
    parent: header,
  });
  const close = $el("button.workflowx-node-replacer-close", {
    textContent: "x",
    title: "Close",
    parent: header,
  });
  const results = $el("div.workflowx-node-replacer-results", { parent: dialog });

  activeDialog = overlay;

  function choose(item) {
    if (!item) return;
    closeDialog();
    replaceNode(sourceNode, item.className);
  }

  function syncActiveRowClasses() {
    results.querySelectorAll(".workflowx-node-replacer-row").forEach((row, index) => {
      row.classList.toggle("active", index === activeIndex);
    });
  }

  function render() {
    results.replaceChildren();
    if (!visibleItems.length) {
      $el("div.workflowx-node-replacer-empty", { textContent: "No matching nodes", parent: results });
      return;
    }

    visibleItems.slice(0, 120).forEach((item, index) => {
      const row = $el("div.workflowx-node-replacer-row", {
        className: `workflowx-node-replacer-row${index === activeIndex ? " active" : ""}`,
        parent: results,
      });
      $el("div.workflowx-node-replacer-name", { textContent: item.displayName, parent: row });
      $el("div.workflowx-node-replacer-category", { textContent: item.category, parent: row });
      $el("div.workflowx-node-replacer-class", { textContent: item.className, parent: row });
      row.addEventListener("mouseenter", () => {
        activeIndex = index;
        syncActiveRowClasses();
      });
      row.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        choose(item);
      });
    });
  }

  function updateFilter() {
    visibleItems = allItems.filter((item) => matchesQuery(item, search.value));
    activeIndex = 0;
    render();
  }

  close.addEventListener("click", closeDialog);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeDialog();
  });
  search.addEventListener("input", updateFilter);
  search.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog();
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, visibleItems.length - 1);
      render();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      render();
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      choose(visibleItems[activeIndex]);
    }
  });

  render();
  requestAnimationFrame(() => search.focus());
}

function installMenuHandler(nodeTypeDef) {
  const proto = nodeTypeDef?.prototype;
  if (!proto || proto.__workflowXNodeReplacerMenu) return;

  const originalGetExtraMenuOptions = proto.getExtraMenuOptions;
  proto.getExtraMenuOptions = function workflowXGetExtraMenuOptions(_, options) {
    const result = originalGetExtraMenuOptions?.apply(this, arguments);
    if (!Array.isArray(options)) return result;

    if (options.length && options[options.length - 1] !== null) options.push(null);
    options.push({
      content: MENU_LABEL,
      callback: () => openReplaceDialog(this),
    });

    return result;
  };
  proto.__workflowXNodeReplacerMenu = true;
}

app.registerExtension({
  name: EXTENSION_NAME,
  beforeRegisterNodeDef(nodeTypeDef, nodeData) {
    registerCatalogEntry(nodeTypeDef, nodeData);
    installMenuHandler(nodeTypeDef);
  },
});
