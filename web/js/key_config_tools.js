import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "key_config_tools.group_configurator";

const CONFIGURATOR_TYPE = "KVGC_GroupConfigurator";
const SELECTOR_TYPE = "KVGC_ConfigSelector";
const GET_TYPES = Object.freeze({
  KVGC_GetInt: "Int",
  KVGC_GetFloat: "Float",
  KVGC_GetString: "String",
  KVGC_GetText: "Text",
  KVGC_GetBoolean: "Boolean",
});
const SET_TYPES_BY_GET_TYPE = Object.freeze({
  KVGC_GetInt: "KVGC_SetInt",
  KVGC_GetFloat: "KVGC_SetFloat",
  KVGC_GetString: "KVGC_SetString",
  KVGC_GetText: "KVGC_SetText",
  KVGC_GetBoolean: "KVGC_SetBoolean",
});

const MODES = Object.freeze({
  Active: 0,
  Mute: 2,
  Bypass: 4,
});

const MODE_NAMES = Object.freeze(Object.keys(MODES));

function getGraph() {
  return app.graph;
}

function getCanvas() {
  return app.canvas;
}

function markCanvasDirty() {
  const canvas = getCanvas();
  if (canvas?.setDirty) {
    canvas.setDirty(true, true);
    return;
  }
  getGraph()?.setDirtyCanvas?.(true, true);
}

function findWidget(node, name) {
  return node?.widgets?.find((widget) => widget.name === name);
}

function getWidgetValue(node, name, fallback = "") {
  const widget = findWidget(node, name);
  return widget ? widget.value : fallback;
}

function setWidgetValue(node, name, value) {
  const widget = findWidget(node, name);
  if (!widget) return false;

  widget.value = value;
  if (!widget.__workflowXInternalWrite) {
    widget.callback?.(value, app.canvas, node, app.canvas?.graph_mouse);
  }
  node.setDirtyCanvas?.(true, true);
  markCanvasDirty();
  return true;
}

function setWidgetValueSilently(node, name, value) {
  const widget = findWidget(node, name);
  if (!widget) return false;

  widget.__workflowXInternalWrite = true;
  setWidgetValue(node, name, value);
  widget.__workflowXInternalWrite = false;
  return true;
}

function allNodes() {
  return getGraph()?._nodes ?? [];
}

function allGroups() {
  return getGraph()?._groups ?? [];
}

function groupTitle(group) {
  return String(group?.title ?? "").trim();
}

function uniqueGroupTitles() {
  return [...new Set(allGroups().map(groupTitle).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  );
}

function nodeType(node) {
  return node?.comfyClass ?? node?.type;
}

function isConfigurator(node) {
  return nodeType(node) === CONFIGURATOR_TYPE;
}

function isSelector(node) {
  return nodeType(node) === SELECTOR_TYPE;
}

function isGetNode(node) {
  return Object.hasOwn(GET_TYPES, nodeType(node));
}

function configsByName() {
  const configs = new Map();
  for (const node of allNodes().filter(isConfigurator)) {
    const name = String(getWidgetValue(node, "config_name", "")).trim();
    if (!name) continue;
    configs.set(name, {
      node,
      modes: readConfigModes(node),
    });
  }
  return configs;
}

function readConfigModes(node) {
  const raw = String(getWidgetValue(node, "config_json", "{}") || "{}");
  try {
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

function writeConfigModes(node, modes) {
  const widget = findWidget(node, "config_json");
  if (widget) {
    widget.__workflowXInternalWrite = true;
  }
  setWidgetValue(node, "config_json", JSON.stringify(modes));
  if (widget) {
    widget.__workflowXInternalWrite = false;
  }
}

function nodeBounds(node) {
  const [x, y] = node.pos ?? [0, 0];
  const [w, h] = node.size ?? [0, 0];
  return { x, y, w, h };
}

function groupBounds(group) {
  const [x, y] = group.pos ?? [0, 0];
  const [w, h] = group.size ?? [0, 0];
  return { x, y, w, h };
}

function intersects(a, b) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function nodeInsideGroup(node, group) {
  if (isConfigurator(node) || isSelector(node)) return false;
  return intersects(nodeBounds(node), groupBounds(group));
}

function applyModeToGroup(groupName, modeName) {
  if (!MODE_NAMES.includes(modeName)) return 0;

  let changed = 0;
  const mode = MODES[modeName];
  for (const group of allGroups()) {
    if (groupTitle(group) !== groupName) continue;

    for (const node of allNodes()) {
      if (!nodeInsideGroup(node, group)) continue;
      if (node.mode === mode) continue;

      node.mode = mode;
      node.setDirtyCanvas?.(true, true);
      changed += 1;
    }
  }
  return changed;
}

function applyConfig(configName) {
  const config = configsByName().get(String(configName || "").trim());
  if (!config) return false;

  for (const [groupName, modeName] of Object.entries(config.modes)) {
    applyModeToGroup(groupName, modeName);
  }

  markCanvasDirty();
  return true;
}

function stableStringify(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }

  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }

  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
    .join(",")}}`;
}

function digestResolvedValue(typeName, key, configName, value) {
  const payload = {
    config: String(configName || ""),
    key: String(key || "").trim(),
    type: typeName,
    value,
  };
  return `workflowx:${stableStringify(payload)}`;
}

function selectedConfigFromSelectors() {
  const selectors = allNodes()
    .filter(isSelector)
    .map((node) => ({ id: Number(node.id ?? 0), value: selectedConfigName(node) }))
    .filter((entry) => entry.value);
  selectors.sort((a, b) => a.id - b.id);
  return selectors.at(-1)?.value ?? "";
}

function groupModeForNode(node, modes) {
  const nodeRect = nodeBounds(node);
  const matchedModes = [];

  for (const group of allGroups()) {
    const title = groupTitle(group);
    if (!Object.hasOwn(modes, title)) continue;

    if (intersects(nodeRect, groupBounds(group))) {
      matchedModes.push(modes[title]);
    }
  }

  return matchedModes;
}

function priorityForSetNode(node, modes) {
  const matchedModes = groupModeForNode(node, modes);
  if (!matchedModes.length) return 0;
  if (matchedModes.includes("Active")) return 1;
  return null;
}

function valueForSetNode(node) {
  const valueWidget = findWidget(node, "value");
  if (valueWidget) return valueWidget.value;

  const values = node.widgets_values;
  return Array.isArray(values) ? values[1] : undefined;
}

function keyForSetNode(node) {
  return String(getWidgetValue(node, "key", "") || "").trim();
}

function resolveGetNodeValue(getNode) {
  const getType = nodeType(getNode);
  const setType = SET_TYPES_BY_GET_TYPE[getType];
  const key = String(getWidgetValue(getNode, "key", "") || "").trim();
  if (!setType || !key) return null;

  const selectedConfig = selectedConfigFromSelectors();
  const config = selectedConfig ? configsByName().get(selectedConfig) : null;
  const modes = config?.modes ?? null;

  const candidates = [];
  for (const node of allNodes()) {
    if (nodeType(node) !== setType) continue;
    if (keyForSetNode(node) !== key) continue;

    let priority = 0;
    if (modes) {
      priority = priorityForSetNode(node, modes);
      if (priority === null) continue;
    } else if (node.mode === MODES.Mute || node.mode === MODES.Bypass) {
      continue;
    }

    candidates.push({
      id: Number(node.id ?? 0),
      priority,
      value: valueForSetNode(node),
    });
  }

  if (!candidates.length) return null;

  const bestPriority = Math.min(...candidates.map((candidate) => candidate.priority));
  const bestCandidates = candidates
    .filter((candidate) => candidate.priority === bestPriority)
    .sort((a, b) => a.id - b.id);

  if (bestCandidates.length > 1) {
    console.warn(
      `[WorkflowX_Configurator] Multiple active ${setType} nodes found for key "${key}"; using node id ${bestCandidates.at(-1).id}.`,
    );
  }

  return {
    configName: selectedConfig,
    typeName: GET_TYPES[getType],
    key,
    value: bestCandidates.at(-1).value,
  };
}

function materializeGetValuesBeforeQueue() {
  for (const getNode of allNodes().filter(isGetNode)) {
    const resolved = resolveGetNodeValue(getNode);
    if (!resolved) {
      setWidgetValueSilently(getNode, "resolved_value", "");
      setWidgetValueSilently(getNode, "resolved_config", "");
      setWidgetValueSilently(getNode, "resolved_digest", "");
      continue;
    }

    const value = String(resolved.value);
    const digest = digestResolvedValue(
      resolved.typeName,
      resolved.key,
      resolved.configName,
      value,
    );
    setWidgetValueSilently(getNode, "resolved_value", value);
    setWidgetValueSilently(getNode, "resolved_config", resolved.configName);
    setWidgetValueSilently(getNode, "resolved_digest", digest);
  }
}

function updateComboValues(widget, values) {
  if (!widget) return;

  widget.options ??= {};
  widget.options.values = values;

  if (!values.includes(widget.value)) {
    widget.value = values[0] ?? "";
  }
}

function refreshSelectorNode(node) {
  hideSelectorBackingWidgets(node);
  ensureRefreshButton(node, "refresh_configs");
  syncSelectorToggles(node);
}

function hideGetBackingWidgets(node) {
  for (const name of ["resolved_value", "resolved_config", "resolved_digest"]) {
    const widget = findWidget(node, name);
    if (!widget || widget.__workflowXHidden) continue;

    widget.__workflowXHidden = true;
    widget.type = "hidden";
    widget.options ??= {};
    widget.options.serialize = true;
    widget.computeSize = () => [0, 0];
    widget.draw = () => {};
  }
}

function refreshSelectorNodes() {
  for (const node of allNodes().filter(isSelector)) {
    refreshSelectorNode(node);
  }
}

function selectedConfigName(node) {
  return String(getWidgetValue(node, "selected_config", "") || "").trim();
}

function configNames() {
  return [...configsByName().keys()].sort((a, b) => a.localeCompare(b));
}

function selectConfig(node, configName, apply = true) {
  const names = configNames();
  if (!names.includes(configName)) return false;

  setWidgetValueSilently(node, "selected_config", configName);

  for (const widget of node.widgets ?? []) {
    if (widget.__workflowXConfigToggle) {
      widget.value = widget.__workflowXConfigName === configName;
    }
  }

  node.setDirtyCanvas?.(true, true);
  markCanvasDirty();

  if (apply) {
    applyConfig(configName);
  }

  return true;
}

function syncSelectorToggles(node) {
  const names = configNames();
  let selected = selectedConfigName(node);

  if (!names.includes(selected)) {
    selected = names[0] ?? "";
    if (selected) {
      setWidgetValueSilently(node, "selected_config", selected);
    }
  }

  const beforeCount = node.widgets?.length ?? 0;
  node.widgets = (node.widgets ?? []).filter((widget) => {
    if (widget.name === "enabled") return false;
    return !widget.__workflowXConfigToggle || names.includes(widget.__workflowXConfigName);
  });

  const existingWidgets = new Map(
    (node.widgets ?? [])
      .filter((widget) => widget.__workflowXConfigToggle)
      .map((widget) => [widget.__workflowXConfigName, widget]),
  );

  for (const name of names) {
    let widget = existingWidgets.get(name);

    if (!widget) {
      widget = node.addWidget(
        "toggle",
        name,
        name === selected,
        (value) => {
          if (value) {
            selectConfig(node, name, true);
            return;
          }

          if (selectedConfigName(node) === name) {
            widget.value = true;
            markCanvasDirty();
          }
        },
      );
      widget.serialize = false;
      widget.__workflowXConfigToggle = true;
      widget.__workflowXConfigName = name;
      continue;
    }

    widget.value = name === selected;
  }

  if ((node.widgets?.length ?? 0) !== beforeCount) {
    node.setSize?.(node.computeSize?.() ?? node.size);
    markCanvasDirty();
  }
}

function syncConfiguratorRows(node) {
  hideBackingConfigWidget(node);
  ensureRefreshButton(node, "refresh_groups");

  const groups = uniqueGroupTitles();
  const modes = readConfigModes(node);
  let changed = false;

  for (const groupName of groups) {
    if (!MODE_NAMES.includes(modes[groupName])) {
      modes[groupName] = "Active";
      changed = true;
    }
  }

  for (const existingName of Object.keys(modes)) {
    if (!groups.includes(existingName)) {
      delete modes[existingName];
      changed = true;
    }
  }

  if (changed) {
    writeConfigModes(node, modes);
  }

  const beforeCount = node.widgets?.length ?? 0;
  node.widgets = (node.widgets ?? []).filter(
    (widget) => !widget.name?.startsWith("group:") || groups.includes(widget.name.slice(6)),
  );

  const existingWidgets = new Map((node.widgets ?? []).map((widget) => [widget.name, widget]));
  for (const groupName of groups) {
    const widgetName = `group:${groupName}`;
    let widget = existingWidgets.get(widgetName);

    if (!widget) {
      widget = node.addWidget(
        "combo",
        widgetName,
        modes[groupName] ?? "Active",
        (value) => {
          const updated = readConfigModes(node);
          updated[groupName] = value;
          writeConfigModes(node, updated);
          refreshSelectorNodes();
        },
        { values: MODE_NAMES },
      );
      widget.label = groupName;
      widget.serialize = false;
      continue;
    }

    widget.label = groupName;
    updateComboValues(widget, MODE_NAMES);
    widget.value = modes[groupName] ?? "Active";
  }

  if ((node.widgets?.length ?? 0) !== beforeCount) {
    node.setSize?.(node.computeSize?.() ?? node.size);
    markCanvasDirty();
  }
}

function hideBackingConfigWidget(node) {
  const configJson = findWidget(node, "config_json");
  if (!configJson || configJson.__workflowXHidden) return;

  configJson.__workflowXHidden = true;
  configJson.type = "hidden";
  configJson.name = "config_json";
  configJson.options ??= {};
  configJson.options.serialize = true;
  configJson.computeSize = () => [0, 0];
  configJson.draw = () => {};
}

function hideSelectorBackingWidgets(node) {
  const selected = findWidget(node, "selected_config");
  if (selected && !selected.__workflowXHidden) {
    selected.__workflowXHidden = true;
    selected.type = "hidden";
    selected.options ??= {};
    selected.options.serialize = true;
    selected.computeSize = () => [0, 0];
    selected.draw = () => {};
  }

  const enabled = findWidget(node, "enabled");
  if (enabled) {
    node.widgets = (node.widgets ?? []).filter((widget) => widget !== enabled);
  }
}

function ensureRefreshButton(node, name) {
  if (findWidget(node, name)) return;

  const label = name === "refresh_groups" ? "Refresh groups" : "Refresh configs";
  const widget = node.addWidget("button", name, label, () => {
    refreshAll();
  });
  widget.serialize = false;
}

function refreshConfiguratorNodes() {
  for (const node of allNodes().filter(isConfigurator)) {
    syncConfiguratorRows(node);
  }
}

function refreshAll() {
  refreshConfiguratorNodes();
  refreshSelectorNodes();
  for (const node of allNodes().filter(isGetNode)) {
    hideGetBackingWidgets(node);
  }
}

app.registerExtension({
  name: EXTENSION_NAME,

  async beforeRegisterNodeDef(nodeTypeDef, nodeData) {
    if (nodeData.name === SELECTOR_TYPE) {
      const originalOnNodeCreated = nodeTypeDef.prototype.onNodeCreated;
      nodeTypeDef.prototype.onNodeCreated = function () {
        originalOnNodeCreated?.apply(this, arguments);

        hideSelectorBackingWidgets(this);
        refreshSelectorNode(this);
      };
    }

    if (Object.hasOwn(GET_TYPES, nodeData.name)) {
      const originalOnNodeCreated = nodeTypeDef.prototype.onNodeCreated;
      nodeTypeDef.prototype.onNodeCreated = function () {
        originalOnNodeCreated?.apply(this, arguments);
        hideGetBackingWidgets(this);

        const key = findWidget(this, "key");
        if (key && !key.__workflowXBeforeQueued) {
          key.__workflowXBeforeQueued = true;
          key.beforeQueued = () => {
            materializeGetValuesBeforeQueue();
          };
        }
      };
    }

    if (nodeData.name === CONFIGURATOR_TYPE) {
      const originalOnNodeCreated = nodeTypeDef.prototype.onNodeCreated;
      nodeTypeDef.prototype.onNodeCreated = function () {
        originalOnNodeCreated?.apply(this, arguments);

        const configName = findWidget(this, "config_name");
        if (configName) {
          const originalCallback = configName.callback;
          configName.callback = () => {
            originalCallback?.apply(configName, arguments);
            refreshSelectorNodes();
          };
        }

        const configJson = findWidget(this, "config_json");
        if (configJson) {
          hideBackingConfigWidget(this);
        }

        syncConfiguratorRows(this);
      };
    }
  },

  async nodeCreated() {
    refreshAll();
  },

  async loadedGraphNode() {
    refreshAll();
  },

  async afterConfigureGraph() {
    refreshAll();
  },
});
