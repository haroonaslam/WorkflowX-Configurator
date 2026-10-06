import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import {
  buildImportedSelectorXState,
  effectiveSelectorXModes,
  parseSelectorXState,
} from "./config_selector_x_state.mjs?workflowx=2";
import { createSelectorXController } from "./config_selector_x_ui.js?workflowx=2";
import {
  applyModeToNamedGroup,
  buildGraphInventory,
  candidateTier,
  describeDuplicateGroups,
  effectiveRecordState,
  graphNodes,
  resolveCandidates,
} from "./key_config_graph.mjs?workflowx=2";

const EXTENSION_NAME = "key_config_tools.group_configurator";
const DEBUG_LOG_ROUTE = "/workflowx_configurator/debug_log";

const CONFIGURATOR_TYPE = "KVGC_GroupConfigurator";
const SELECTOR_TYPE = "KVGC_ConfigSelector";
const ADVANCED_SELECTOR_TYPE = "KVGC_ConfigSelectorAdvanced";
const SELECTOR_X_TYPE = "KVGC_ConfigSelectorX";
const GROUP_SCOPES_TYPE = "KVGC_GroupScopes";
const GET_RELAY_TYPE = "KVGC_GetRelay";
const GET_DIMENSIONS_TYPE = "KVGC_GetDimensions";
const SET_REFERENCE_TYPE = "KVGC_SetReference";
const GET_REFERENCE_TYPE = "KVGC_GetReference";
const GET_TYPES = Object.freeze({
  KVGC_GetInt: "Int",
  KVGC_GetFloat: "Float",
  KVGC_GetString: "String",
  KVGC_GetText: "Text",
  KVGC_GetBoolean: "Boolean",
  KVGC_GetSampler: "Sampler",
  KVGC_GetScheduler: "Scheduler",
});
const FAMILY_BY_SET_TYPE = Object.freeze({
  KVGC_SetInt: "Int",
  KVGC_SetFloat: "Float",
  KVGC_SetString: "String",
  KVGC_SetText: "Text",
  KVGC_SetBoolean: "Boolean",
  KVGC_SetSampler: "Sampler",
  KVGC_SetScheduler: "Scheduler",
  KVGC_SetRelay: "Relay",
  KVGC_SetDimensions: "Dimensions",
  KVGC_SetReference: "Reference",
});
const FAMILY_BY_GET_TYPE = Object.freeze({
  ...GET_TYPES,
  KVGC_GetRelay: "Relay",
  KVGC_GetDimensions: "Dimensions",
  KVGC_GetReference: "Reference",
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
  return buildGraphInventory(getGraph()).graphs.flatMap(({ graph }) => graphNodes(graph));
}

function rootNodes() {
  return graphNodes(getGraph());
}

function uniqueGroupTitles() {
  return [...new Set(buildGraphInventory(getGraph()).groups.map(({ name }) => name))].sort((a, b) =>
    a.localeCompare(b),
  );
}

function rootGroupTitles() {
  return [
    ...new Set(
      buildGraphInventory(getGraph()).groups
        .filter(({ isRoot }) => isRoot)
        .map(({ name }) => name),
    ),
  ].sort((a, b) => a.localeCompare(b));
}

function groupDisplayLabel(groupName) {
  return buildGraphInventory(getGraph()).groups.find(({ name }) => name === groupName)?.location ?? groupName;
}

function nodeType(node) {
  return node?.comfyClass ?? node?.type;
}

function isConfigurator(node) {
  return nodeType(node) === CONFIGURATOR_TYPE;
}

function isSelector(node) {
  return (
    nodeType(node) === SELECTOR_TYPE ||
    nodeType(node) === ADVANCED_SELECTOR_TYPE ||
    nodeType(node) === SELECTOR_X_TYPE
  );
}

function isAdvancedSelector(node) {
  return nodeType(node) === ADVANCED_SELECTOR_TYPE;
}

function isSelectorX(node) {
  return nodeType(node) === SELECTOR_X_TYPE;
}

function isGroupScopes(node) {
  return nodeType(node) === GROUP_SCOPES_TYPE;
}

function isGetReference(node) {
  return nodeType(node) === GET_REFERENCE_TYPE;
}

function isGetNode(node) {
  return Object.hasOwn(GET_TYPES, nodeType(node));
}

function groupScopesNodes() {
  return rootNodes().filter(isGroupScopes);
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
  const groups = rootGroupTitles();
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

function readSelectorXState(node) {
  return parseSelectorXState(String(getWidgetValue(node, "selectorx_state", "{}") || "{}"));
}

function legacySelectorNodes() {
  return rootNodes().filter((node) =>
    [SELECTOR_TYPE, ADVANCED_SELECTOR_TYPE].includes(nodeType(node)),
  );
}

function highestIdNode(nodes) {
  return [...nodes].sort((a, b) => Number(a.id ?? 0) - Number(b.id ?? 0)).at(-1) ?? null;
}

function collectLegacyImport() {
  const configNodes = rootNodes().filter(isConfigurator);
  const configNames = configNodes
    .map((node) => String(getWidgetValue(node, "config_name", "")).trim())
    .filter(Boolean);
  const duplicateConfigCount = configNames.length - new Set(configNames).size;
  const scopeNodes = groupScopesNodes();
  const selector = highestIdNode(
    legacySelectorNodes().filter((node) => selectedConfigName(node)),
  );
  const advancedSelector = highestIdNode(legacySelectorNodes().filter(isAdvancedSelector));

  const configs = configNodes.map((node) => ({
    id: Number(node.id ?? 0),
    name: String(getWidgetValue(node, "config_name", "")).trim(),
    modes: readConfigModes(node),
  }));
  const scopes = scopeNodes.length === 1 ? readScopeChoices(scopeNodes[0]) : null;
  const advanced = advancedSelector
    ? readAdvancedState(advancedSelector)
    : { mute: {}, bypass: {} };
  const state = buildImportedSelectorXState({
    groupNames: uniqueGroupTitles(),
    configs,
    scopes,
    advanced,
  });
  const names = state.configs.map((config) => config.name);
  const requestedSelection = selectedConfigName(selector);

  return {
    state,
    selectedConfig: names.includes(requestedSelection) ? requestedSelection : names[0] ?? "",
    consoleOutput: String(getWidgetValue(selector, "console_output", "no")) === "yes" ? "yes" : "no",
    summary: {
      configs: state.configs.length,
      groups: uniqueGroupTitles().length,
      duplicateConfigs: duplicateConfigCount,
      scopeNodes: scopeNodes.length,
      hasLegacyConfigs: configs.some((config) => config.name),
    },
  };
}

const selectorXController = createSelectorXController({
  groupNames: uniqueGroupTitles,
  groupLabel: groupDisplayLabel,
  getWidgetValue,
  setWidgetValueSilently,
  writeJsonWidget,
  selectedConfigName,
  collectLegacyImport,
  applySelectedConfig: applySelectedConfigAndAdvancedOverrides,
  applyModeToGroup,
  isAuthoritative: (node) => selectedSelectorNode() === node,
  nodeMousePosition: (node) => {
    const mouse = app.canvas?.graph_mouse;
    if (!mouse) return null;
    return [mouse[0] - Number(node.pos?.[0] ?? 0), mouse[1] - Number(node.pos?.[1] ?? 0)];
  },
  markCanvasDirty,
  addTextRow,
  recomputeNodeHeight: recomputeNodeHeightPreservingWidth,
  hideBackingWidgets: hideSelectorBackingWidgets,
});

function configsByName() {
  const configs = new Map();
  for (const node of rootNodes().filter(isConfigurator)) {
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

function applyModeToGroup(groupName, modeName, recursive = true) {
  if (!Object.hasOwn(MODES, modeName)) return 0;
  const inventory = buildGraphInventory(getGraph());
  if (!recursive) inventory.groups = inventory.groups.filter(({ isRoot }) => isRoot);
  return applyModeToNamedGroup(
    inventory,
    groupName,
    MODES[modeName],
    (node) => isConfigurator(node) || isSelector(node) || isGroupScopes(node),
  );
}

function applyConfig(configName, selector = selectedSelectorNode()) {
  if (isSelectorX(selector)) {
    const state = readSelectorXState(selector);
    if (!state || !state.configs.some((config) => config.name === configName)) return false;
    for (const [groupName, modeName] of Object.entries(
      effectiveSelectorXModes(state, configName),
    )) {
      applyModeToGroup(groupName, modeName);
    }
    markCanvasDirty();
    return true;
  }

  const config = configsByName().get(String(configName || "").trim());
  if (!config) return false;

  for (const [groupName, modeName] of Object.entries(config.modes)) {
    applyModeToGroup(groupName, modeName, false);
  }

  markCanvasDirty();
  return true;
}

function applySelectedConfigAndAdvancedOverrides() {
  const selector = selectedSelectorNode();
  const selectedConfig = selectedConfigName(selector);
  if (!selectedConfig) return false;

  const applied = applyConfig(selectedConfig, selector);
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

function digestResolvedValue(typeName, key, configName, modes, source, value) {
  const payload = {
    config: String(configName || ""),
    key: String(key || "").trim(),
    modes: modes ?? {},
    source: String(source || ""),
    type: typeName,
    value,
  };
  return `workflowx:v2:${stableStringify(payload)}`;
}

function selectedSelectorNode() {
  const selectorXNodes = rootNodes()
    .filter(isSelectorX)
    .map((node) => ({ id: Number(node.id ?? 0), node, value: selectedConfigName(node) }))
    .filter((entry) => {
      const state = readSelectorXState(entry.node);
      return state?.configs.some((config) => config.name === entry.value);
    });
  selectorXNodes.sort((a, b) => a.id - b.id);
  if (selectorXNodes.length) return selectorXNodes.at(-1).node;

  const selectors = legacySelectorNodes()
    .map((node) => ({ id: Number(node.id ?? 0), node, value: selectedConfigName(node) }))
    .filter((entry) => entry.value);
  selectors.sort((a, b) => a.id - b.id);
  return selectors.at(-1)?.node ?? null;
}

function graphValidation() {
  const inventory = buildGraphInventory(getGraph());
  const { modes, recursive } = selectedConfigContext();
  const effectiveModes = modes ?? {};
  const rootSelectors = rootNodes().filter((node) => isSelectorX(node) && readSelectorXState(node));
  const nestedSelectors = inventory.instances.filter((record) => !record.isRoot && isSelectorX(record.node));
  const errors = [];
  const warnings = [];
  if (inventory.duplicateGroups.length) {
    errors.push(`Duplicate group names: ${describeDuplicateGroups(inventory.duplicateGroups).join("; ")}`);
  }
  if (inventory.cycles.length) errors.push(`Circular subgraph reference: ${inventory.cycles.join(", ")}`);
  if (rootSelectors.length > 1) errors.push("Multiple initialized Config SelectorX nodes exist on the root canvas.");
  for (const record of inventory.instances) {
    const family = FAMILY_BY_SET_TYPE[nodeType(record.node)];
    if (!family) continue;
    const controlledGroups = recursive || record.isRoot
      ? record.containingGroups.filter(
          ({ name }) => Object.hasOwn(effectiveModes, name) && effectiveModes[name] !== "Ignore",
        )
      : [];
    if (controlledGroups.length > 1) {
      errors.push(
        `${family} Set ${record.executionId} intersects multiple controlled groups: ${controlledGroups.map(({ name }) => name).join(", ")}.`,
      );
    }
  }
  if (nestedSelectors.length) warnings.push(`${nestedSelectors.length} nested Config SelectorX node(s) are ignored.`);
  return { inventory, errors, warnings };
}

function assertQueueGraphValid() {
  const validation = graphValidation();
  for (const warning of validation.warnings) console.warn(`[WorkflowX_Configurator] ${warning}`);
  if (validation.errors.length) throw new Error(`[WorkflowX_Configurator] ${validation.errors.join(" ")}`);
  return validation.inventory;
}

function selectedConfigContext() {
  const selector = selectedSelectorNode();
  const selectedConfig = selectedConfigName(selector);
  if (!selectedConfig) return { selectedConfig: "", modes: null, recursive: false };

  if (isSelectorX(selector)) {
    const state = readSelectorXState(selector);
    return {
      selectedConfig,
      modes: state ? effectiveSelectorXModes(state, selectedConfig) : null,
      recursive: true,
    };
  }

  return {
    selectedConfig,
    modes: configsByName().get(selectedConfig)?.modes ?? null,
    recursive: false,
  };
}

function consoleOutputEnabled() {
  return String(getWidgetValue(selectedSelectorNode(), "console_output", "no") || "no") === "yes";
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

function keyForSetNode(node) {
  return String(getWidgetValue(node, "key", "") || "").trim();
}

function promptScalar(value, fallback = "") {
  return Array.isArray(value) ? fallback : value ?? fallback;
}

function promptBoolean(value) {
  return value === true || String(value).toLowerCase() === "true";
}

function showResolutionWarnings(warnings) {
  for (const node of rootNodes().filter(isSelectorX)) {
    node.widgets = (node.widgets ?? []).filter((widget) => !widget.__workflowXResolutionWarning);
    if (warnings.length) {
      const suffix = warnings.length > 1 ? ` (+${warnings.length - 1} more)` : "";
      addTextRow(
        node,
        "warning:set_resolution",
        `${warnings[0]}${suffix}`,
        "__workflowXResolutionWarning",
      );
    }
    recomputeNodeHeightPreservingWidth(node);
  }
}

function materializeRecursiveSetGets(promptResult, inventory) {
  const output = promptResult?.output;
  if (!output) return promptResult;
  const { selectedConfig, modes, recursive } = selectedConfigContext();
  const effectiveModes = modes ?? {};
  const candidatesByLookup = new Map();

  for (const record of inventory.instances) {
    const promptNode = output[record.executionId];
    const family = FAMILY_BY_SET_TYPE[nodeType(record.node)];
    if (!promptNode || !family) continue;
    const key = String(promptScalar(promptNode.inputs?.key, keyForSetNode(record.node)) || "").trim();
    if (!key) continue;
    const state = effectiveRecordState(record, effectiveModes, recursive);
    if (state.overlap) {
      throw new Error(
        `[WorkflowX_Configurator] ${family} Set ${record.executionId} intersects multiple controlled groups: ${state.controlledGroups.map(({ name }) => name).join(", ")}.`,
      );
    }
    const tier = candidateTier(record, effectiveModes, recursive);
    if (tier === null) continue;
    const lookup = `${family}\u0000${key}`;
    const candidates = candidatesByLookup.get(lookup) ?? [];
    candidates.push({
      executionId: record.executionId,
      family,
      key,
      node: record.node,
      promptNode,
      tier,
      groupNames: record.containingGroups.map(({ name }) => name),
    });
    candidatesByLookup.set(lookup, candidates);
  }

  const resolved = new Map();
  const resolutionWarnings = [];
  for (const [lookup, candidates] of candidatesByLookup) {
    const [family, key] = lookup.split("\u0000");
    const result = resolveCandidates(candidates, family, key);
    for (const warning of result.warnings) {
      resolutionWarnings.push(warning);
      console.warn(`[WorkflowX_Configurator] ${warning}`);
    }
    if (result.candidate) resolved.set(lookup, result.candidate);
  }
  showResolutionWarnings(resolutionWarnings);

  const removedReferences = new Set();
  for (const [executionId, getPrompt] of Object.entries(output)) {
    const family = FAMILY_BY_GET_TYPE[getPrompt.class_type];
    if (!family) continue;
    const key = String(promptScalar(getPrompt.inputs?.key, "") || "").trim();
    const source = resolved.get(`${family}\u0000${key}`);
    if (!source) {
      if (Object.hasOwn(GET_TYPES, getPrompt.class_type)) {
        getPrompt.inputs.resolved_value = "";
        getPrompt.inputs.resolved_config = "";
        getPrompt.inputs.resolved_digest = "";
      }
      continue;
    }

    getPrompt.inputs ??= {};
    if (Object.hasOwn(GET_TYPES, getPrompt.class_type)) {
      const value = String(promptScalar(source.promptNode.inputs?.value, ""));
      getPrompt.inputs.resolved_value = value;
      getPrompt.inputs.resolved_config = selectedConfig;
      getPrompt.inputs.resolved_digest = digestResolvedValue(
        family,
        key,
        selectedConfig,
        effectiveModes,
        source.executionId,
        value,
      );
    } else if (family === "Dimensions") {
      getPrompt.inputs.width = [source.executionId, 0];
      getPrompt.inputs.height = [source.executionId, 1];
    } else {
      getPrompt.inputs.value = [source.executionId, 0];
      if (
        family === "Reference" &&
        (promptBoolean(getPrompt.inputs.mute) || promptBoolean(source.promptNode.inputs?.mute))
      ) {
        removedReferences.add(executionId);
      }
    }
    logResolution(
      `Get ${family} key="${key}" resolved from Set ${family} ${source.executionId}${formatDebugGroups(source.groupNames)} config="${selectedConfig || "none"}"`,
    );
  }

  for (const executionId of removedReferences) delete output[executionId];
  if (removedReferences.size) {
    for (const promptNode of Object.values(output)) {
      for (const [name, input] of Object.entries(promptNode.inputs ?? {})) {
        if (Array.isArray(input) && removedReferences.has(String(input[0]))) delete promptNode.inputs[name];
      }
    }
  }
  return promptResult;
}

function installGraphToPromptPatch() {
  if (app.__workflowXRelayGraphToPromptPatched || typeof app.graphToPrompt !== "function") {
    return;
  }

  const originalGraphToPrompt = app.graphToPrompt.bind(app);
  app.graphToPrompt = async function (...args) {
    const inventory = assertQueueGraphValid();
    applySelectedConfigAndAdvancedOverrides();
    const promptResult = await originalGraphToPrompt(...args);
    return materializeRecursiveSetGets(promptResult, inventory);
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
  if (isSelectorX(node)) {
    selectorXController.refresh(node);
    node.widgets = (node.widgets ?? []).filter((widget) => !widget.__workflowXGraphValidation);
    if (rootNodes().includes(node)) {
      const validation = graphValidation();
      const message = validation.errors[0] ?? validation.warnings[0];
      if (message) addTextRow(node, "warning:graph_validation", message, "__workflowXGraphValidation");
      recomputeNodeHeightPreservingWidth(node);
    }
    return;
  }
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
  for (const node of rootNodes().filter(isSelector)) {
    refreshSelectorNode(node);
  }
}

function selectedConfigName(node) {
  return String(getWidgetValue(node, "selected_config", "") || "").trim();
}

function configNames(node = null) {
  if (isSelectorX(node)) {
    return readSelectorXState(node)?.configs.map((config) => config.name) ?? [];
  }
  return [...configsByName().keys()].sort((a, b) => a.localeCompare(b));
}

function selectConfig(node, configName, apply = true) {
  const names = configNames(node);
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
  const names = configNames(node);
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
    changed += applyModeToGroup(groupName, state.mute[groupName] === true ? "Active" : "Mute", false);
  }

  for (const groupName of groupsForScope(SELECTOR_BYPASS_SCOPE)) {
    changed += applyModeToGroup(groupName, state.bypass[groupName] === true ? "Active" : "Bypass", false);
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
  applyModeToGroup(groupName, value === true ? "Active" : targetMode, false);
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

  if (isSelectorX(node)) {
    for (const name of ["selected_config", "console_output", "selectorx_state"]) {
      const widget = findWidget(node, name);
      if (!widget) continue;
      widget.__workflowXHidden = true;
      widget.type = "hidden";
      widget.options ??= {};
      widget.options.serialize = true;
      widget.computeSize = () => [0, -4];
      widget.draw = () => {};
    }
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

function hideReferenceBackingWidgets(node) {
  const setMute = findWidget(node, "set_mute");
  if (!setMute || setMute.__workflowXHidden) return;

  setMute.__workflowXHidden = true;
  setMute.type = "hidden";
  setMute.options ??= {};
  setMute.options.serialize = true;
  setMute.computeSize = () => [0, 0];
  setMute.draw = () => {};
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
  for (const node of rootNodes().filter(isConfigurator)) {
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
  for (const node of allNodes().filter(isGetReference)) {
    hideReferenceBackingWidgets(node);
  }
}

app.registerExtension({
  name: EXTENSION_NAME,

  async setup() {
    installGraphToPromptPatch();
  },

  async beforeRegisterNodeDef(nodeTypeDef, nodeData) {
    installGraphToPromptPatch();

    if (
      nodeData.name === SELECTOR_TYPE ||
      nodeData.name === ADVANCED_SELECTOR_TYPE ||
      nodeData.name === SELECTOR_X_TYPE
    ) {
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
            assertQueueGraphValid();
            applySelectedConfigAndAdvancedOverrides();
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
            assertQueueGraphValid();
            applySelectedConfigAndAdvancedOverrides();
          };
        }
      };
    }

    if (nodeData.name === GET_DIMENSIONS_TYPE) {
      const originalOnNodeCreated = nodeTypeDef.prototype.onNodeCreated;
      nodeTypeDef.prototype.onNodeCreated = function () {
        originalOnNodeCreated?.apply(this, arguments);

        const key = findWidget(this, "key");
        if (key && !key.__workflowXDimensionsBeforeQueued) {
          key.__workflowXDimensionsBeforeQueued = true;
          key.beforeQueued = () => {
            assertQueueGraphValid();
            applySelectedConfigAndAdvancedOverrides();
          };
        }
      };
    }

    if (nodeData.name === GET_REFERENCE_TYPE) {
      const originalOnNodeCreated = nodeTypeDef.prototype.onNodeCreated;
      nodeTypeDef.prototype.onNodeCreated = function () {
        originalOnNodeCreated?.apply(this, arguments);
        hideReferenceBackingWidgets(this);

        const key = findWidget(this, "key");
        if (key && !key.__workflowXReferenceBeforeQueued) {
          key.__workflowXReferenceBeforeQueued = true;
          key.beforeQueued = () => {
            assertQueueGraphValid();
            applySelectedConfigAndAdvancedOverrides();
          };
        }

        const mute = findWidget(this, "mute");
        if (mute && !mute.__workflowXReferenceBeforeQueued) {
          mute.__workflowXReferenceBeforeQueued = true;
          mute.beforeQueued = () => {
            assertQueueGraphValid();
            applySelectedConfigAndAdvancedOverrides();
          };
        }
      };
    }

    if (nodeData.name === SET_REFERENCE_TYPE) {
      const originalOnNodeCreated = nodeTypeDef.prototype.onNodeCreated;
      nodeTypeDef.prototype.onNodeCreated = function () {
        originalOnNodeCreated?.apply(this, arguments);

        const mute = findWidget(this, "mute");
        if (mute && !mute.__workflowXReferenceBeforeQueued) {
          mute.__workflowXReferenceBeforeQueued = true;
          mute.beforeQueued = () => {
            assertQueueGraphValid();
            applySelectedConfigAndAdvancedOverrides();
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
