import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const EXTENSION_NAME = "key_config_tools.group_configurator";
const DEBUG_LOG_ROUTE = "/workflowx_configurator/debug_log";

const CONFIGURATOR_TYPE = "KVGC_GroupConfigurator";
const SELECTOR_TYPE = "KVGC_ConfigSelector";
const ADVANCED_SELECTOR_TYPE = "KVGC_ConfigSelectorAdvanced";
const GROUP_SCOPES_TYPE = "KVGC_GroupScopes";
const SET_RELAY_TYPE = "KVGC_SetRelay";
const GET_RELAY_TYPE = "KVGC_GetRelay";
const GET_TYPES = Object.freeze({
  KVGC_GetInt: "Int",
  KVGC_GetFloat: "Float",
  KVGC_GetString: "String",
  KVGC_GetText: "Text",
  KVGC_GetBoolean: "Boolean",
  KVGC_GetSampler: "Sampler",
  KVGC_GetScheduler: "Scheduler",
});
const SET_TYPES_BY_GET_TYPE = Object.freeze({
  KVGC_GetInt: "KVGC_SetInt",
  KVGC_GetFloat: "KVGC_SetFloat",
  KVGC_GetString: "KVGC_SetString",
  KVGC_GetText: "KVGC_SetText",
  KVGC_GetBoolean: "KVGC_SetBoolean",
  KVGC_GetSampler: "KVGC_SetSampler",
  KVGC_GetScheduler: "KVGC_SetScheduler",
});

const MODES = Object.freeze({
  Active: 0,
  Mute: 2,
  Bypass: 4,
});

const MODE_NAMES = Object.freeze(["Active", "Bypass", "Mute", "Ignore"]);
const SCOPE_NAMES = Object.freeze(["Group Configurator", "Selector Mute", "Selector Bypass", "Ignore"]);
const CONFIGURATOR_SCOPE = "Group Configurator";
const SELECTOR_MUTE_SCOPE = "Selector Mute";
const SELECTOR_BYPASS_SCOPE = "Selector Bypass";

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
  return nodeType(node) === SELECTOR_TYPE || nodeType(node) === ADVANCED_SELECTOR_TYPE;
}

function isAdvancedSelector(node) {
  return nodeType(node) === ADVANCED_SELECTOR_TYPE;
}

function isGroupScopes(node) {
  return nodeType(node) === GROUP_SCOPES_TYPE;
}

function isSetRelay(node) {
  return nodeType(node) === SET_RELAY_TYPE;
}

function isGetRelay(node) {
  return nodeType(node) === GET_RELAY_TYPE;
}

function isGetNode(node) {
  return Object.hasOwn(GET_TYPES, nodeType(node));
}

function groupScopesNodes() {
  return allNodes().filter(isGroupScopes);
}

function hasDuplicateGroupScopes() {
  return groupScopesNodes().length > 1;
}

function workflowScopes() {
  const nodes = groupScopesNodes();
  if (nodes.length !== 1) {
    if (nodes.length > 1 && !app.__workflowXDuplicateScopesWarningShown) {
      console.warn(
        "[WorkflowX_Configurator] Multiple Group Scopes nodes found; scope filtering is disabled until only one remains.",
      );
      app.__workflowXDuplicateScopesWarningShown = true;
    }
    return null;
  }

  app.__workflowXDuplicateScopesWarningShown = false;
  const rawScopes = readScopeChoices(nodes[0]);
  return Object.fromEntries(
    Object.entries(rawScopes).filter(([, scope]) => SCOPE_NAMES.includes(scope)),
  );
}

function groupsForScope(scopeName) {
  const groups = uniqueGroupTitles();
  const scopes = workflowScopes();
  if (!scopes) {
    return scopeName === CONFIGURATOR_SCOPE ? groups : [];
  }
  return groups.filter((groupName) => scopes[groupName] === scopeName);
}

function readJsonWidget(node, name) {
  const raw = String(getWidgetValue(node, name, "{}") || "{}");
  try {
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

function writeJsonWidget(node, name, value) {
  const widget = findWidget(node, name);
  if (widget) {
    widget.__workflowXInternalWrite = true;
  }
  setWidgetValue(node, name, JSON.stringify(value));
  if (widget) {
    widget.__workflowXInternalWrite = false;
  }
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
  return readJsonWidget(node, "config_json");
}

function writeConfigModes(node, modes) {
  writeJsonWidget(node, "config_json", modes);
}

function readAdvancedState(node) {
  const parsed = readJsonWidget(node, "advanced_state");
  return {
    mute:
      typeof parsed.mute === "object" && parsed.mute !== null && !Array.isArray(parsed.mute)
        ? parsed.mute
        : {},
    bypass:
      typeof parsed.bypass === "object" && parsed.bypass !== null && !Array.isArray(parsed.bypass)
        ? parsed.bypass
        : {},
  };
}

function writeAdvancedState(node, state) {
  writeJsonWidget(node, "advanced_state", state);
}

function readScopeChoices(node) {
  return readJsonWidget(node, "scopes_json");
}

function writeScopeChoices(node, scopes) {
  writeJsonWidget(node, "scopes_json", scopes);
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
  if (isConfigurator(node) || isSelector(node) || isGroupScopes(node)) return false;
  return intersects(nodeBounds(node), groupBounds(group));
}

function applyModeToGroup(groupName, modeName) {
  if (!Object.hasOwn(MODES, modeName)) return 0;

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

function applySelectedConfigAndAdvancedOverrides() {
  const selector = selectedSelectorNode();
  const selectedConfig = selectedConfigName(selector);
  if (!selectedConfig) return false;

  const applied = applyConfig(selectedConfig);
  if (isAdvancedSelector(selector)) {
    applyAdvancedSelectorState(selector);
  }
  return applied;
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

function selectedSelectorNode() {
  const selectors = allNodes()
    .filter(isSelector)
    .map((node) => ({ id: Number(node.id ?? 0), node, value: selectedConfigName(node) }))
    .filter((entry) => entry.value);
  selectors.sort((a, b) => a.id - b.id);
  return selectors.at(-1)?.node ?? null;
}

function selectedConfigFromSelectors() {
  return selectedConfigName(selectedSelectorNode());
}

function consoleOutputEnabled() {
  return String(getWidgetValue(selectedSelectorNode(), "console_output", "no") || "no") === "yes";
}

function groupNamesForNode(node, modes = null) {
  const names = [];
  const nodeRect = nodeBounds(node);

  for (const group of allGroups()) {
    const title = groupTitle(group);
    if (modes && (!Object.hasOwn(modes, title) || modes[title] === "Ignore")) continue;
    if (intersects(nodeRect, groupBounds(group))) {
      names.push(title);
    }
  }

  return names;
}

function formatDebugGroups(groupNames) {
  return groupNames.length ? ` group="${groupNames.join(", ")}"` : ' group="global"';
}

function logResolution(message) {
  if (consoleOutputEnabled()) {
    console.info(`[WorkflowX_Configurator] ${message}`);
    api
      .fetchApi(DEBUG_LOG_ROUTE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      })
      .catch(() => {});
  }
}

function groupModeForNode(node, modes) {
  const nodeRect = nodeBounds(node);
  const matchedModes = [];

  for (const group of allGroups()) {
    const title = groupTitle(group);
    if (!Object.hasOwn(modes, title)) continue;

    if (intersects(nodeRect, groupBounds(group))) {
      const mode = modes[title];
      if (mode !== "Ignore") {
        matchedModes.push(mode);
      }
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
      groupNames: groupNamesForNode(node, modes),
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
    setType,
    ...bestCandidates.at(-1),
  };
}

function materializeGetValuesBeforeQueue() {
  applySelectedConfigAndAdvancedOverrides();

  for (const getNode of allNodes().filter(isGetNode)) {
    const resolved = resolveGetNodeValue(getNode);
    if (!resolved) {
      logResolution(
        `Get ${GET_TYPES[nodeType(getNode)]} key="${String(getWidgetValue(getNode, "key", "") || "").trim()}" unresolved`,
      );
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

    logResolution(
      `Get ${resolved.typeName} key="${resolved.key}" resolved from ${resolved.setType} node ${resolved.id}${formatDebugGroups(resolved.groupNames)} value=${JSON.stringify(value)} config="${resolved.configName || "none"}"`,
    );
  }
}

function relayKey(node) {
  return String(getWidgetValue(node, "key", "") || "").trim();
}

function resolveRelaySource(getNode, promptOutput) {
  const key = relayKey(getNode);
  if (!key || !promptOutput) return null;

  const selectedConfig = selectedConfigFromSelectors();
  const config = selectedConfig ? configsByName().get(selectedConfig) : null;
  const modes = config?.modes ?? null;

  const candidates = [];
  for (const node of allNodes()) {
    if (!isSetRelay(node)) continue;
    if (relayKey(node) !== key) continue;
    if (!promptOutput[String(node.id)]) continue;

    let priority = 0;
    if (modes) {
      priority = priorityForSetNode(node, modes);
      if (priority === null) continue;
    }

    candidates.push({
      id: Number(node.id ?? 0),
      priority,
      node,
      groupNames: groupNamesForNode(node, modes),
    });
  }

  if (!candidates.length) return null;

  const bestPriority = Math.min(...candidates.map((candidate) => candidate.priority));
  const bestCandidates = candidates
    .filter((candidate) => candidate.priority === bestPriority)
    .sort((a, b) => a.id - b.id);

  if (bestCandidates.length > 1) {
    console.warn(
      `[WorkflowX_Configurator] Multiple active Set Relay nodes found for key "${key}"; using node id ${bestCandidates.at(-1).id}.`,
    );
  }

  return bestCandidates.at(-1);
}

function materializeRelayLinksInPrompt(promptResult) {
  const output = promptResult?.output;
  if (!output) return promptResult;

  for (const getNode of allNodes().filter(isGetRelay)) {
    const getOutput = output[String(getNode.id)];
    if (!getOutput) continue;

    const source = resolveRelaySource(getNode, output);
    if (!source) {
      console.warn(
        `[WorkflowX_Configurator] No active Set Relay found for key "${relayKey(getNode)}"; keeping any existing Get Relay input.`,
      );
      continue;
    }

    getOutput.inputs ??= {};
    getOutput.inputs.value = [String(source.node.id), 0];

    logResolution(
      `Get Relay key="${relayKey(getNode)}" resolved from Set Relay node ${source.id}${formatDebugGroups(source.groupNames)} output_slot=0`,
    );
  }

  return promptResult;
}

function installGraphToPromptPatch() {
  if (app.__workflowXRelayGraphToPromptPatched || typeof app.graphToPrompt !== "function") {
    return;
  }

  const originalGraphToPrompt = app.graphToPrompt.bind(app);
  app.graphToPrompt = async function (...args) {
    const shouldMaterializeRelays = app.__workflowXRelayQueueing === true;
    if (shouldMaterializeRelays) {
      applySelectedConfigAndAdvancedOverrides();
    }

    try {
      const promptResult = await originalGraphToPrompt(...args);
      return shouldMaterializeRelays
        ? materializeRelayLinksInPrompt(promptResult)
        : promptResult;
    } finally {
      app.__workflowXRelayQueueing = false;
    }
  };

  app.__workflowXRelayGraphToPromptPatched = true;
}

function updateComboValues(widget, values) {
  if (!widget) return;

  widget.options ??= {};
  widget.options.values = values;

  if (!values.includes(widget.value)) {
    widget.value = values[0] ?? "";
  }
}

function recomputeNodeHeightPreservingWidth(node) {
  const computed = node.computeSize?.() ?? node.size;
  if (!computed) return;

  const current = node.size ?? computed;
  node.setSize?.([Math.max(current[0], computed[0]), computed[1]]);
}

function addTextRow(node, name, label, markerName) {
  node.widgets ??= [];
  const widget = {
    name,
    type: "text",
    value: label,
    serialize: false,
    computeSize: () => [node.size?.[0] ?? 220, 24],
    draw(ctx, _node, _width, y, height) {
      ctx.save();
      ctx.fillStyle = name.includes("warning") ? "#f2a93b" : "#9ca3af";
      ctx.font = "bold 12px sans-serif";
      ctx.textBaseline = "middle";
      ctx.fillText(label, 15, y + height * 0.5);
      ctx.restore();
    },
  };
  widget[markerName] = true;
  node.widgets.push(widget);
  return widget;
}

function roundedRectPath(ctx, x, y, width, height, radius) {
  if (typeof ctx.roundRect === "function") {
    ctx.roundRect(x, y, width, height, radius);
    return;
  }

  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
}

function refreshSelectorNode(node) {
  hideSelectorBackingWidgets(node);
  ensureRefreshButton(node, "refresh_configs");
  syncSelectorToggles(node);
  if (isAdvancedSelector(node)) {
    syncAdvancedSelectorRows(node);
  }
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
    applySelectedConfigAndAdvancedOverrides();
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
    recomputeNodeHeightPreservingWidth(node);
    markCanvasDirty();
  }
}

function normalizeAdvancedSection(section, visibleGroups, canvasGroups) {
  let changed = false;

  for (const groupName of visibleGroups) {
    if (typeof section[groupName] !== "boolean") {
      section[groupName] = false;
      changed = true;
    }
  }

  for (const groupName of Object.keys(section)) {
    if (!canvasGroups.includes(groupName)) {
      delete section[groupName];
      changed = true;
    }
  }

  return changed;
}

function applyAdvancedSelectorState(node) {
  const state = readAdvancedState(node);
  let changed = 0;

  for (const groupName of groupsForScope(SELECTOR_MUTE_SCOPE)) {
    changed += applyModeToGroup(groupName, state.mute[groupName] === true ? "Active" : "Mute");
  }

  for (const groupName of groupsForScope(SELECTOR_BYPASS_SCOPE)) {
    changed += applyModeToGroup(groupName, state.bypass[groupName] === true ? "Active" : "Bypass");
  }

  if (changed) {
    markCanvasDirty();
  }
}

function writeAdvancedToggleState(node, sectionName, groupName, value, targetMode) {
  const state = readAdvancedState(node);
  state[sectionName] ??= {};
  state[sectionName][groupName] = value === true;
  writeAdvancedState(node, state);
  applyModeToGroup(groupName, value === true ? "Active" : targetMode);
  markCanvasDirty();
}

function addAdvancedToggle(node, sectionName, groupName, targetMode, value) {
  const widgetName = `advanced:${sectionName}:${groupName}`;
  const widget = {
    name: widgetName,
    type: "workflowx_switch",
    label: groupName,
    value,
    serialize: false,
    computeSize: () => [node.size?.[0] ?? 240, 30],
    callback(nextValue) {
      this.value = nextValue === true;
      writeAdvancedToggleState(node, sectionName, groupName, this.value, targetMode);
    },
    mouse(event, _pos, _node) {
      if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
      this.callback?.(!this.value);
      return true;
    },
    draw(ctx, _node, width, y, height) {
      const enabled = this.value === true;
      const switchWidth = 54;
      const switchHeight = 22;
      const switchX = Math.max(width - switchWidth - 12, 120);
      const switchY = y + (height - switchHeight) * 0.5;
      const radius = switchHeight * 0.5;
      const knobRadius = 8;
      const knobX = enabled
        ? switchX + switchWidth - radius
        : switchX + radius;

      ctx.save();
      ctx.font = "12px sans-serif";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#d1d5db";
      ctx.fillText(this.label, 15, y + height * 0.5);

      ctx.beginPath();
      roundedRectPath(ctx, switchX, switchY, switchWidth, switchHeight, radius);
      ctx.fillStyle = enabled ? "#22c55e" : "#6b7280";
      ctx.fill();

      ctx.beginPath();
      ctx.arc(knobX, switchY + radius, knobRadius, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.fill();

      ctx.font = "bold 9px sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.fillText(enabled ? "ON" : "OFF", switchX + switchWidth * 0.5, switchY + radius);
      ctx.restore();
    },
  };
  widget.serialize = false;
  widget.__workflowXAdvancedWidget = true;
  node.widgets ??= [];
  node.widgets.push(widget);
}

function syncAdvancedSelectorRows(node) {
  const canvasGroups = uniqueGroupTitles();
  const muteGroups = groupsForScope(SELECTOR_MUTE_SCOPE);
  const bypassGroups = groupsForScope(SELECTOR_BYPASS_SCOPE);
  const state = readAdvancedState(node);
  let changed = false;

  state.mute ??= {};
  state.bypass ??= {};
  changed = normalizeAdvancedSection(state.mute, muteGroups, canvasGroups) || changed;
  changed = normalizeAdvancedSection(state.bypass, bypassGroups, canvasGroups) || changed;

  if (changed) {
    writeAdvancedState(node, state);
  }

  const beforeCount = node.widgets?.length ?? 0;
  node.widgets = (node.widgets ?? []).filter((widget) => !widget.__workflowXAdvancedWidget);

  if (muteGroups.length) {
    addTextRow(node, "section:advanced_mute", "Group Mute", "__workflowXAdvancedWidget");
    for (const groupName of muteGroups) {
      addAdvancedToggle(node, "mute", groupName, "Mute", state.mute[groupName] === true);
    }
  }

  if (bypassGroups.length) {
    addTextRow(node, "section:advanced_bypass", "Group Bypass", "__workflowXAdvancedWidget");
    for (const groupName of bypassGroups) {
      addAdvancedToggle(node, "bypass", groupName, "Bypass", state.bypass[groupName] === true);
    }
  }

  if ((node.widgets?.length ?? 0) !== beforeCount) {
    recomputeNodeHeightPreservingWidth(node);
    markCanvasDirty();
  }

  applyAdvancedSelectorState(node);
}

function syncConfiguratorRows(node) {
  hideBackingConfigWidget(node);
  ensureRefreshButton(node, "refresh_groups");

  const canvasGroups = uniqueGroupTitles();
  const groups = groupsForScope(CONFIGURATOR_SCOPE);
  const modes = readConfigModes(node);
  let changed = false;

  for (const groupName of groups) {
    if (!MODE_NAMES.includes(modes[groupName])) {
      modes[groupName] = "Active";
      changed = true;
    }
  }

  for (const existingName of Object.keys(modes)) {
    if (!canvasGroups.includes(existingName)) {
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
    recomputeNodeHeightPreservingWidth(node);
    markCanvasDirty();
  }
}

function syncGroupScopesRows(node) {
  hideGroupScopesBackingWidget(node);
  ensureRefreshButton(node, "refresh_scopes");

  const groups = uniqueGroupTitles();
  const scopes = readScopeChoices(node);
  let changed = false;

  for (const groupName of groups) {
    if (!SCOPE_NAMES.includes(scopes[groupName])) {
      scopes[groupName] = CONFIGURATOR_SCOPE;
      changed = true;
    }
  }

  for (const existingName of Object.keys(scopes)) {
    if (!groups.includes(existingName)) {
      delete scopes[existingName];
      changed = true;
    }
  }

  if (changed) {
    writeScopeChoices(node, scopes);
  }

  const beforeCount = node.widgets?.length ?? 0;
  node.widgets = (node.widgets ?? []).filter(
    (widget) => !widget.__workflowXScopeWidget && !widget.__workflowXScopeWarning,
  );

  if (hasDuplicateGroupScopes()) {
    addTextRow(
      node,
      "warning:duplicate_group_scopes",
      "Duplicate Group Scopes nodes; scopes ignored",
      "__workflowXScopeWarning",
    );
  }

  for (const groupName of groups) {
    const widgetName = `scope:${groupName}`;
    const widget = node.addWidget(
      "combo",
      widgetName,
      scopes[groupName] ?? CONFIGURATOR_SCOPE,
      (value) => {
        const updated = readScopeChoices(node);
        updated[groupName] = value;
        writeScopeChoices(node, updated);
        refreshConfiguratorNodes();
        refreshSelectorNodes();
      },
      { values: SCOPE_NAMES },
    );
    widget.label = groupName;
    widget.serialize = false;
    widget.__workflowXScopeWidget = true;
  }

  if ((node.widgets?.length ?? 0) !== beforeCount) {
    recomputeNodeHeightPreservingWidth(node);
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

  const advancedState = findWidget(node, "advanced_state");
  if (advancedState && !advancedState.__workflowXHidden) {
    advancedState.__workflowXHidden = true;
    advancedState.type = "hidden";
    advancedState.options ??= {};
    advancedState.options.serialize = true;
    advancedState.computeSize = () => [0, 0];
    advancedState.draw = () => {};
  }

  const enabled = findWidget(node, "enabled");
  if (enabled) {
    node.widgets = (node.widgets ?? []).filter((widget) => widget !== enabled);
  }
}

function hideGroupScopesBackingWidget(node) {
  const scopesJson = findWidget(node, "scopes_json");
  if (!scopesJson || scopesJson.__workflowXHidden) return;

  scopesJson.__workflowXHidden = true;
  scopesJson.type = "hidden";
  scopesJson.name = "scopes_json";
  scopesJson.options ??= {};
  scopesJson.options.serialize = true;
  scopesJson.computeSize = () => [0, 0];
  scopesJson.draw = () => {};
}

function ensureRefreshButton(node, name) {
  if (findWidget(node, name)) return;

  let label = "Refresh configs";
  if (name === "refresh_groups") {
    label = "Refresh groups";
  } else if (name === "refresh_scopes") {
    label = "Refresh scopes";
  }
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

function refreshGroupScopesNodes() {
  for (const node of groupScopesNodes()) {
    syncGroupScopesRows(node);
  }
}

function refreshAll() {
  refreshGroupScopesNodes();
  refreshConfiguratorNodes();
  refreshSelectorNodes();
  for (const node of allNodes().filter(isGetNode)) {
    hideGetBackingWidgets(node);
  }
}

app.registerExtension({
  name: EXTENSION_NAME,

  async setup() {
    installGraphToPromptPatch();
  },

  async beforeRegisterNodeDef(nodeTypeDef, nodeData) {
    installGraphToPromptPatch();

    if (nodeData.name === SELECTOR_TYPE || nodeData.name === ADVANCED_SELECTOR_TYPE) {
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

    if (nodeData.name === GET_RELAY_TYPE) {
      const originalOnNodeCreated = nodeTypeDef.prototype.onNodeCreated;
      nodeTypeDef.prototype.onNodeCreated = function () {
        originalOnNodeCreated?.apply(this, arguments);

        const key = findWidget(this, "key");
        if (key && !key.__workflowXRelayBeforeQueued) {
          key.__workflowXRelayBeforeQueued = true;
          key.beforeQueued = () => {
            app.__workflowXRelayQueueing = true;
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

    if (nodeData.name === GROUP_SCOPES_TYPE) {
      const originalOnNodeCreated = nodeTypeDef.prototype.onNodeCreated;
      nodeTypeDef.prototype.onNodeCreated = function () {
        originalOnNodeCreated?.apply(this, arguments);

        hideGroupScopesBackingWidget(this);
        syncGroupScopesRows(this);
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
