import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  buildImportedSelectorXState,
  cloneSelectorXState,
  createBlankSelectorXState,
  effectiveSelectorXModes,
  nextConfigName,
  parseSelectorXState,
  reconcileSelectorXState,
} from "../web/js/config_selector_x_state.mjs";
import { createSelectorXController } from "../web/js/config_selector_x_ui.js";

const uiSource = readFileSync(new URL("../web/js/config_selector_x_ui.js", import.meta.url), "utf8");

test("blank state creates Config 1 and ignores new canvas groups", () => {
  const state = createBlankSelectorXState(["Draft", "Utility"]);
  assert.equal(state.configs[0].name, "Config 1");
  assert.equal(state.configs[0].enabled, true);
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
  assert.deepEqual(state.configs.map((config) => config.enabled), [true, true]);
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
  assert.equal(reconciled.configs[0].enabled, true);
  assert.deepEqual(reconciled.configs[0].modes, { Draft: "Mute" });
  assert.deepEqual(reconciled.advanced, { mute: {}, bypass: {} });
});

test("reconcile preserves an explicit disabled flag without applying a default override", () => {
  const state = createBlankSelectorXState([]);
  state.configs[0].enabled = false;
  assert.equal(reconcileSelectorXState(state, []).configs[0].enabled, false);
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
  assert.equal(parseSelectorXState({ ...state, configs: [{ name: "Config 1", enabled: "yes", modes: {} }] }), null);
  assert.equal(parseSelectorXState({ ...state, configs: [state.configs[0], state.configs[0]] }), null);
  assert.equal(
    parseSelectorXState({
      ...state,
      configs: [{ name: "Config 1", modes: { Draft: "Disable" } }],
    }),
    null,
  );
});

test("legacy configs default to enabled and disabled configs remain persisted", () => {
  const state = createBlankSelectorXState([]);
  const legacy = parseSelectorXState({
    ...state,
    configs: [{ name: "Legacy", modes: {} }],
  });
  assert.equal(legacy.configs[0].enabled, true);

  const disabled = parseSelectorXState({
    ...state,
    configs: [{ name: "Hidden", enabled: false, modes: {} }],
  });
  assert.deepEqual(disabled.configs[0], { name: "Hidden", enabled: false, modes: {} });
});

test("configs UI uses one clickable switch and defaults missing enabled flags to visible", () => {
  assert.match(uiSource, /function configIsEnabled\(config\) \{[\s\S]*config\?\.enabled !== false/);
  assert.match(uiSource, /const visibility = el\("button", "workflowx-csx-switch"\)/);
  assert.match(uiSource, /visibility\.setAttribute\("role", "switch"\)/);
  assert.match(uiSource, /visibility\.addEventListener\("click", \(\) => \{[\s\S]*config\.enabled = !configIsEnabled\(config\)/);
  assert.match(uiSource, /visibility\.setAttribute\("aria-checked", String\(config\.enabled\)\)/);
  assert.doesNotMatch(uiSource, /workflowx-csx-switch-input/);
  assert.doesNotMatch(uiSource, /\[\["Enable", true\], \["Disable", false\]\]/);
  assert.doesNotMatch(uiSource, /"Main node"/);
  assert.match(uiSource, /workflowx-csx-editor-fields\{[^}]*grid-template-columns:minmax\(300px,600px\) auto/);
  assert.match(uiSource, /fields\.append\(field, visibility\)/);
  assert.match(uiSource, /if \(configIsEnabled\(config\)\) addChoice\(node, config\.name\);/);
  assert.match(uiSource, /enabledNames\[0\] \?\? names\[0\]/);
  assert.match(uiSource, /config_selector_x_state\.mjs\?workflowx=2/);
});

test("clicking the Configs switch persists visibility and refreshes main-node choices", () => {
  class FakeClassList {
    constructor(element) {
      this.element = element;
    }
    values() {
      return new Set(this.element.className.split(/\s+/).filter(Boolean));
    }
    add(name) {
      const values = this.values();
      values.add(name);
      this.element.className = [...values].join(" ");
    }
    remove(name) {
      const values = this.values();
      values.delete(name);
      this.element.className = [...values].join(" ");
    }
    toggle(name, force) {
      const enabled = force ?? !this.values().has(name);
      if (enabled) this.add(name);
      else this.remove(name);
      return enabled;
    }
  }

  class FakeElement {
    constructor(tagName) {
      this.tagName = tagName;
      this.className = "";
      this.classList = new FakeClassList(this);
      this.children = [];
      this.listeners = new Map();
      this.attributes = new Map();
      this.style = {};
      this.textContent = "";
      this.scrollTop = 0;
    }
    append(...children) {
      for (const child of children) {
        child.parentNode = this;
        this.children.push(child);
      }
    }
    appendChild(child) {
      this.append(child);
      return child;
    }
    replaceChildren(...children) {
      this.children = [];
      this.append(...children);
    }
    addEventListener(type, callback) {
      const callbacks = this.listeners.get(type) ?? [];
      callbacks.push(callback);
      this.listeners.set(type, callbacks);
    }
    dispatch(type) {
      for (const callback of this.listeners.get(type) ?? []) callback({ type, target: this });
    }
    setAttribute(name, value) {
      this.attributes.set(name, String(value));
    }
    getAttribute(name) {
      return this.attributes.get(name) ?? null;
    }
    querySelector(selector) {
      const className = selector.startsWith(".") ? selector.slice(1) : null;
      for (const child of this.children) {
        if (className && child.className.split(/\s+/).includes(className)) return child;
        const nested = child.querySelector?.(selector);
        if (nested) return nested;
      }
      return null;
    }
    getBoundingClientRect() {
      return { top: 0, bottom: 100 };
    }
  }

  const oldDocument = globalThis.document;
  const oldWindow = globalThis.window;
  const oldAnimationFrame = globalThis.requestAnimationFrame;
  const head = new FakeElement("head");
  const body = new FakeElement("body");
  globalThis.document = {
    head,
    body,
    createElement: (tagName) => new FakeElement(tagName),
    addEventListener() {},
    getElementById(id) {
      const find = (element) => {
        if (element.id === id) return element;
        for (const child of element.children) {
          const match = find(child);
          if (match) return match;
        }
        return null;
      };
      return find(head) ?? find(body);
    },
  };
  globalThis.window = { alert() {}, confirm: () => true };
  globalThis.requestAnimationFrame = (callback) => callback();

  try {
    const state = {
      version: 1,
      initialized: true,
      configs: [
        { name: "Visible", enabled: true, modes: {} },
        { name: "Also visible", enabled: true, modes: {} },
      ],
      scopes: {},
      advanced: { mute: {}, bypass: {} },
    };
    const node = {
      widgets: [
        { name: "selected_config", value: "Visible" },
        { name: "console_output", value: "no" },
        { name: "selectorx_state", value: JSON.stringify(state) },
      ],
      size: [300, 100],
      addWidget(type, name, value, callback) {
        const widget = { type, name, value, callback, computeSize: () => [300, 24] };
        this.widgets.push(widget);
        return widget;
      },
      setSize(size) {
        this.size = size;
      },
      setDirtyCanvas() {},
    };
    const widget = (name) => node.widgets.find((item) => item.name === name);
    const adapter = {
      groupNames: () => [],
      getWidgetValue: (_node, name, fallback) => widget(name)?.value ?? fallback,
      setWidgetValueSilently: (_node, name, value) => {
        widget(name).value = value;
      },
      writeJsonWidget: (_node, name, value) => {
        widget(name).value = JSON.stringify(value);
      },
      selectedConfigName: () => String(widget("selected_config").value),
      collectLegacyImport: () => ({ summary: { hasLegacyConfigs: false } }),
      applySelectedConfig() {},
      applyModeToGroup() {},
      isAuthoritative: () => true,
      markCanvasDirty() {},
      addTextRow() {},
      recomputeNodeHeight() {},
      hideBackingWidgets() {},
    };

    const controller = createSelectorXController(adapter);
    controller.openConfigs(node);
    const switchControl = body.querySelector(".workflowx-csx-switch");
    assert.equal(switchControl.getAttribute("aria-checked"), "true");
    switchControl.dispatch("click");
    assert.equal(switchControl.getAttribute("aria-checked"), "false");

    const findByText = (element, text) => {
      if (element.textContent === text) return element;
      for (const child of element.children) {
        const match = findByText(child, text);
        if (match) return match;
      }
      return null;
    };
    findByText(body, "Save").dispatch("click");

    const saved = JSON.parse(widget("selectorx_state").value);
    assert.equal(saved.configs[0].enabled, false);
    assert.equal(widget("selected_config").value, "Also visible");
    assert.deepEqual(
      node.widgets.filter((item) => item.__workflowXSelectorXConfig).map((item) => item.name),
      ["Also visible"],
    );
  } finally {
    globalThis.document = oldDocument;
    globalThis.window = oldWindow;
    globalThis.requestAnimationFrame = oldAnimationFrame;
  }
});
