export const SELECTOR_X_VERSION = 1;
export const MODE_NAMES = Object.freeze(["Active", "Bypass", "Mute", "Ignore"]);
export const SCOPE_NAMES = Object.freeze([
  "Group Configurator",
  "Selector Mute",
  "Selector Bypass",
  "Ignore",
]);
export const CONFIG_SCOPE = "Group Configurator";
export const MUTE_SCOPE = "Selector Mute";
export const BYPASS_SCOPE = "Selector Bypass";
export const IGNORE_SCOPE = "Ignore";

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function cloneSelectorXState(state) {
  return JSON.parse(JSON.stringify(state));
}

export function nextConfigName(configs, prefix = "Config") {
  const names = new Set((configs ?? []).map((config) => String(config?.name ?? "").trim()));
  let index = 1;
  while (names.has(`${prefix} ${index}`)) index += 1;
  return `${prefix} ${index}`;
}

export function createBlankSelectorXState(groupNames = []) {
  const scopes = Object.fromEntries(groupNames.map((name) => [name, IGNORE_SCOPE]));
  return {
    version: SELECTOR_X_VERSION,
    initialized: true,
    configs: [{ name: "Config 1", modes: {} }],
    scopes,
    advanced: { mute: {}, bypass: {} },
  };
}

export function parseSelectorXState(raw) {
  let value = raw;
  if (typeof raw === "string") {
    try {
      value = JSON.parse(raw || "{}");
    } catch {
      return null;
    }
  }
  if (!isRecord(value) || value.version !== SELECTOR_X_VERSION || value.initialized !== true) {
    return null;
  }
  if (!Array.isArray(value.configs) || value.configs.length === 0) return null;
  if (!isRecord(value.scopes) || !isRecord(value.advanced)) return null;
  if (!isRecord(value.advanced.mute) || !isRecord(value.advanced.bypass)) return null;

  const names = new Set();
  const configs = [];
  for (const rawConfig of value.configs) {
    if (!isRecord(rawConfig) || !isRecord(rawConfig.modes)) return null;
    if (typeof rawConfig.name !== "string") return null;
    const name = rawConfig.name.trim();
    if (!name || names.has(name)) return null;
    names.add(name);
    const modes = {};
    for (const [groupName, mode] of Object.entries(rawConfig.modes)) {
      if (!MODE_NAMES.includes(mode)) return null;
      modes[String(groupName)] = mode;
    }
    configs.push({ name, modes });
  }

  const scopes = {};
  for (const [groupName, scope] of Object.entries(value.scopes)) {
    if (!SCOPE_NAMES.includes(scope)) return null;
    scopes[String(groupName)] = scope;
  }

  const advanced = { mute: {}, bypass: {} };
  for (const sectionName of ["mute", "bypass"]) {
    for (const [groupName, enabled] of Object.entries(value.advanced[sectionName])) {
      if (typeof enabled !== "boolean") return null;
      advanced[sectionName][String(groupName)] = enabled;
    }
  }

  return {
    version: SELECTOR_X_VERSION,
    initialized: true,
    configs,
    scopes,
    advanced,
  };
}

export function reconcileSelectorXState(state, groupNames) {
  const currentGroups = [...new Set(groupNames.map((name) => String(name).trim()).filter(Boolean))];
  const currentSet = new Set(currentGroups);
  const next = cloneSelectorXState(state);

  next.scopes = Object.fromEntries(
    currentGroups.map((groupName) => [groupName, next.scopes[groupName] ?? IGNORE_SCOPE]),
  );

  for (const config of next.configs) {
    config.modes = Object.fromEntries(
      Object.entries(config.modes).filter(([groupName]) => currentSet.has(groupName)),
    );
    for (const groupName of currentGroups) {
      if (next.scopes[groupName] === CONFIG_SCOPE && !MODE_NAMES.includes(config.modes[groupName])) {
        config.modes[groupName] = "Active";
      }
    }
  }

  for (const sectionName of ["mute", "bypass"]) {
    next.advanced[sectionName] = Object.fromEntries(
      Object.entries(next.advanced[sectionName]).filter(
        ([groupName, enabled]) => currentSet.has(groupName) && typeof enabled === "boolean",
      ),
    );
  }
  for (const groupName of currentGroups) {
    if (next.scopes[groupName] === MUTE_SCOPE && typeof next.advanced.mute[groupName] !== "boolean") {
      next.advanced.mute[groupName] = false;
    }
    if (
      next.scopes[groupName] === BYPASS_SCOPE &&
      typeof next.advanced.bypass[groupName] !== "boolean"
    ) {
      next.advanced.bypass[groupName] = false;
    }
  }
  return next;
}

export function buildImportedSelectorXState({ groupNames, configs, scopes, advanced }) {
  const orderedConfigs = [...configs]
    .sort((a, b) => Number(a.id ?? 0) - Number(b.id ?? 0))
    .reduce((map, config) => {
      const name = String(config.name ?? "").trim();
      if (!name) return map;
      map.set(name, {
        name,
        modes: Object.fromEntries(
          Object.entries(config.modes ?? {}).filter(([, mode]) => MODE_NAMES.includes(mode)),
        ),
      });
      return map;
    }, new Map());

  const imported = {
    version: SELECTOR_X_VERSION,
    initialized: true,
    configs: [...orderedConfigs.values()],
    scopes: Object.fromEntries(
      groupNames.map((groupName) => [
        groupName,
        SCOPE_NAMES.includes(scopes?.[groupName]) ? scopes[groupName] : CONFIG_SCOPE,
      ]),
    ),
    advanced: {
      mute: isRecord(advanced?.mute)
        ? Object.fromEntries(Object.entries(advanced.mute).filter(([, value]) => typeof value === "boolean"))
        : {},
      bypass: isRecord(advanced?.bypass)
        ? Object.fromEntries(Object.entries(advanced.bypass).filter(([, value]) => typeof value === "boolean"))
        : {},
    },
  };

  if (imported.configs.length === 0) return createBlankSelectorXState(groupNames);
  return reconcileSelectorXState(imported, groupNames);
}

export function effectiveSelectorXModes(state, selectedConfig) {
  const config = state.configs.find((item) => item.name === selectedConfig) ?? state.configs[0];
  const modes = {};
  for (const [groupName, scope] of Object.entries(state.scopes)) {
    if (scope === CONFIG_SCOPE) {
      modes[groupName] = config?.modes[groupName] ?? "Active";
    } else if (scope === MUTE_SCOPE) {
      modes[groupName] = state.advanced.mute[groupName] === true ? "Active" : "Mute";
    } else if (scope === BYPASS_SCOPE) {
      modes[groupName] = state.advanced.bypass[groupName] === true ? "Active" : "Bypass";
    } else {
      modes[groupName] = "Ignore";
    }
  }
  return modes;
}
