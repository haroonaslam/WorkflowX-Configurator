import test from "node:test";
import assert from "node:assert/strict";

import {
  buildImportedSelectorXState,
  cloneSelectorXState,
  createBlankSelectorXState,
  effectiveSelectorXModes,
  nextConfigName,
  parseSelectorXState,
  reconcileSelectorXState,
} from "../web/js/config_selector_x_state.mjs";

test("blank state creates Config 1 and ignores new canvas groups", () => {
  const state = createBlankSelectorXState(["Draft", "Utility"]);
  assert.equal(state.configs[0].name, "Config 1");
  assert.deepEqual(state.configs[0].modes, {});
  assert.deepEqual(state.scopes, { Draft: "Ignore", Utility: "Ignore" });
  assert.deepEqual(parseSelectorXState(JSON.stringify(state)), state);
});

test("legacy import preserves order and highest node id wins duplicate names", () => {
  const state = buildImportedSelectorXState({
    groupNames: ["Draft", "Utility"],
    configs: [
      { id: 10, name: "Speed", modes: { Draft: "Mute" } },
      { id: 20, name: "Quality", modes: { Draft: "Active" } },
      { id: 30, name: "Speed", modes: { Draft: "Active" } },
    ],
    scopes: null,
    advanced: {},
  });
  assert.deepEqual(state.configs.map((config) => config.name), ["Speed", "Quality"]);
  assert.equal(state.configs[0].modes.Draft, "Active");
  assert.deepEqual(state.scopes, {
    Draft: "Group Configurator",
    Utility: "Group Configurator",
  });
});

test("reconcile defaults new groups to Ignore and prunes removed groups on save", () => {
  const state = buildImportedSelectorXState({
    groupNames: ["Draft", "Removed"],
    configs: [{ id: 1, name: "Speed", modes: { Draft: "Mute", Removed: "Bypass" } }],
    scopes: { Draft: "Group Configurator", Removed: "Selector Mute" },
    advanced: { mute: { Removed: true }, bypass: {} },
  });
  const reconciled = reconcileSelectorXState(state, ["Draft", "New Group"]);
  assert.deepEqual(reconciled.scopes, { Draft: "Group Configurator", "New Group": "Ignore" });
  assert.deepEqual(reconciled.configs[0].modes, { Draft: "Mute" });
  assert.deepEqual(reconciled.advanced, { mute: {}, bypass: {} });
});

test("effective modes combine config, mute, bypass, and ignored scopes", () => {
  const state = {
    version: 1,
    initialized: true,
    configs: [{ name: "Profile", modes: { Draft: "Bypass" } }],
    scopes: {
      Draft: "Group Configurator",
      Optional: "Selector Mute",
      Preview: "Selector Bypass",
      Notes: "Ignore",
    },
    advanced: { mute: { Optional: true }, bypass: { Preview: false } },
  };
  assert.deepEqual(effectiveSelectorXModes(state, "Profile"), {
    Draft: "Bypass",
    Optional: "Active",
    Preview: "Bypass",
    Notes: "Ignore",
  });
});

test("draft cloning, ordering, and generated config names do not mutate saved state", () => {
  const saved = createBlankSelectorXState([]);
  const draft = cloneSelectorXState(saved);
  draft.configs.push({ name: nextConfigName(draft.configs), modes: {} });
  draft.configs.reverse();
  assert.deepEqual(saved.configs.map((config) => config.name), ["Config 1"]);
  assert.deepEqual(draft.configs.map((config) => config.name), ["Config 2", "Config 1"]);
});

test("invalid versions, duplicate names, and invalid modes do not parse", () => {
  const state = createBlankSelectorXState([]);
  assert.equal(parseSelectorXState({ ...state, version: 2 }), null);
  assert.equal(parseSelectorXState({ ...state, configs: [{ name: 1, modes: {} }] }), null);
  assert.equal(parseSelectorXState({ ...state, configs: [state.configs[0], state.configs[0]] }), null);
  assert.equal(
    parseSelectorXState({
      ...state,
      configs: [{ name: "Config 1", modes: { Draft: "Disable" } }],
    }),
    null,
  );
});
