import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const CODEX_DEFAULT = "Use Codex setting";
const IMAGE_SOCKET = /^image_([1-9][0-9]*)$/;
const MINIMUM_WIDTH = 320;
const INITIAL_EDITOR_SPACE = 48;
let catalogRequest;

function loadCatalog() {
  catalogRequest ??= api.fetchApi("/workflowx_configurator/codex/models").then(async (response) => {
    const catalog = await response.json();
    if (!response.ok) throw new Error(catalog.error);
    return catalog;
  }).catch((error) => {
    catalogRequest = undefined;
    throw error;
  });
  return catalogRequest;
}

function syncModelWidgets(node, modelChanged = false) {
  const catalog = node.codexCatalog;
  const model = node.widgets?.find((widget) => widget.name === "model");
  const effort = node.widgets?.find((widget) => widget.name === "reasoning_effort");
  if (!catalog || !model || !effort) return;
  const hasImages = node.inputs?.some((input) => IMAGE_SOCKET.test(input.name) && input.link != null);
  model.options.values = [CODEX_DEFAULT, ...Object.keys(catalog.models).filter(
    (name) => !hasImages || catalog.models[name].acceptsImages,
  )];
  const selected = model.value === CODEX_DEFAULT ? catalog.defaultModel : model.value;
  effort.options.values = [CODEX_DEFAULT, ...(catalog.models[selected]?.efforts ?? [])];
  if (modelChanged && !effort.options.values.includes(effort.value)) {
    effort.value = CODEX_DEFAULT;
  }
  node.setDirtyCanvas(true, true);
}

function syncImageInputs(node) {
  const slots = (node.inputs ?? []).filter((input) => IMAGE_SOCKET.test(input.name));
  const oldCount = slots.length;
  const oldSize = [...node.size];
  const oldMinimum = node.computeSize();
  if (!slots.length) {
    slots.push(node.addInput("image_1", "IMAGE"));
  } else {
    // Keep one spare socket at the end without renumbering connected sockets.
    while (slots.length > 1 && slots.at(-1).link == null && slots.at(-2).link == null) {
      node.removeInput(node.inputs.indexOf(slots.pop()));
    }
    const last = slots.at(-1);
    if (last.link != null) {
      const number = Number(last.name.match(IMAGE_SOCKET)[1]);
      slots.push(node.addInput(`image_${number + 1}`, "IMAGE"));
    }
  }
  if (slots.length !== oldCount) {
    // LiteGraph can recompute the node's size on socket changes. Preserve
    // the user's width and the extra height above the widget minimum.
    const minimum = node.computeSize();
    node.setSize([
      Math.max(oldSize[0], minimum[0]),
      minimum[1] + Math.max(0, oldSize[1] - oldMinimum[1]),
    ]);
  }
}

function scheduleSync(node) {
  if (node.codexImageSyncScheduled) return;
  node.codexImageSyncScheduled = true;
  queueMicrotask(() => {
    node.codexImageSyncScheduled = false;
    syncImageInputs(node);
    syncModelWidgets(node);
  });
}

app.registerExtension({
  name: "WorkflowX.CodeX",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "CodeX") return;
    const originalComputeSize = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (...args) {
      const size = originalComputeSize.apply(this, args);
      size[0] = Math.max(size[0], MINIMUM_WIDTH);
      return size;
    };
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function (...args) {
      const result = originalCreated?.apply(this, args);
      const minimum = this.computeSize();
      this.setSize([
        Math.max(this.size[0], minimum[0]),
        Math.max(this.size[1], minimum[1] + INITIAL_EDITOR_SPACE),
      ]);
      const model = this.widgets?.find((widget) => widget.name === "model");
      if (model) {
        const originalCallback = model.callback;
        model.callback = (...callbackArgs) => {
          const value = originalCallback?.apply(model, callbackArgs);
          syncModelWidgets(this, true);
          return value;
        };
      }
      loadCatalog().then((catalog) => {
        this.codexCatalog = catalog;
        syncModelWidgets(this);
      }).catch((error) => console.warn("[CodeX] Could not load models:", error));
      return result;
    };
    const originalConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (...args) {
      const result = originalConfigure?.apply(this, args);
      scheduleSync(this);
      // A workflow saved before the controls existed may retain a shorter
      // widget area. Keep larger saved sizes and grow undersized nodes.
      queueMicrotask(() => {
        const minimum = this.computeSize();
        if (this.size[0] < minimum[0] || this.size[1] < minimum[1]) {
          this.setSize([Math.max(this.size[0], minimum[0]), Math.max(this.size[1], minimum[1])]);
        }
      });
      return result;
    };

    const originalConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (slotType, ...args) {
      const result = originalConnectionsChange?.call(this, slotType, ...args);
      if (slotType === 1) scheduleSync(this);
      return result;
    };
  },
});
