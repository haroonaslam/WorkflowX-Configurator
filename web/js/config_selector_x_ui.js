import {
  BYPASS_SCOPE,
  CONFIG_SCOPE,
  IGNORE_SCOPE,
  MODE_NAMES,
  MUTE_SCOPE,
  SCOPE_NAMES,
  cloneSelectorXState,
  createBlankSelectorXState,
  nextConfigName,
  parseSelectorXState,
  reconcileSelectorXState,
} from "./config_selector_x_state.mjs";

const UI_MARKER = "__workflowXSelectorXWidget";

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function button(label, onClick, className = "") {
  const node = el("button", `workflowx-csx-btn ${className}`.trim(), label);
  node.type = "button";
  node.addEventListener("click", onClick);
  return node;
}

function roundedRect(ctx, x, y, width, height, radius) {
  if (typeof ctx.roundRect === "function") {
    ctx.roundRect(x, y, width, height, radius);
    return;
  }
  ctx.rect(x, y, width, height);
}

function installStyles() {
  if (document.getElementById("workflowx-csx-style")) return;
  const style = document.createElement("style");
  style.id = "workflowx-csx-style";
  style.textContent = `
    .workflowx-csx-overlay{position:fixed;inset:0;z-index:10040;display:none;place-items:center;padding:18px;box-sizing:border-box;background:rgba(5,8,12,.78);color:var(--fg-color,#e7edf5);font-family:Inter,"Segoe UI",sans-serif}
    .workflowx-csx-modal{width:min(1120px,96vw);height:min(780px,92vh);display:grid;grid-template-rows:auto minmax(0,1fr) auto;overflow:hidden;border:1px solid var(--border-color,#3d4b59);border-radius:8px;background:var(--comfy-menu-bg,#151a20);box-shadow:0 22px 70px rgba(0,0,0,.5)}
    .workflowx-csx-head,.workflowx-csx-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border-bottom:1px solid var(--border-color,#35414c)}
    .workflowx-csx-foot{border-top:1px solid var(--border-color,#35414c);border-bottom:0}.workflowx-csx-title{font-size:16px;font-weight:700}.workflowx-csx-sub{margin-top:2px;color:var(--descrip-text,#9aa8b6);font-size:12px}
    .workflowx-csx-actions{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.workflowx-csx-btn{min-height:32px;border:1px solid var(--border-color,#465665);border-radius:6px;padding:6px 10px;background:var(--comfy-input-bg,#222a32);color:var(--fg-color,#eef3f8);cursor:pointer}.workflowx-csx-btn:hover{border-color:#62a8d7;background:#273746}.workflowx-csx-btn.primary{border-color:#2380b9;background:#176a9d;color:#fff}.workflowx-csx-btn.danger{border-color:#a85252;color:#ffc5c5}.workflowx-csx-btn:disabled{opacity:.4;cursor:default}
    .workflowx-csx-body{min-height:0;overflow:auto;padding:12px 14px}.workflowx-csx-scope-grid{display:grid;gap:1px;min-width:720px;border:1px solid var(--border-color,#35414c);background:var(--border-color,#35414c)}.workflowx-csx-scope-row{display:grid;grid-template-columns:minmax(180px,1fr) minmax(440px,2fr);gap:12px;align-items:center;min-height:45px;padding:6px 9px;background:var(--comfy-menu-bg,#151a20)}
    .workflowx-csx-group-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}.workflowx-csx-segments{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:4px}.workflowx-csx-segment{min-height:30px;border:1px solid var(--border-color,#465665);border-radius:5px;padding:4px 7px;background:var(--comfy-input-bg,#222a32);color:var(--descrip-text,#aeb9c4);cursor:pointer;white-space:nowrap}.workflowx-csx-segment.active{border-color:#39a5d8;background:#164f6d;color:#fff}
    .workflowx-csx-config-layout{height:100%;min-height:470px;display:grid;grid-template-columns:260px minmax(0,1fr);gap:12px}.workflowx-csx-config-sidebar{min-height:0;display:grid;grid-template-rows:auto minmax(0,1fr) auto;border-right:1px solid var(--border-color,#35414c);padding-right:12px}.workflowx-csx-config-list{min-height:0;overflow:auto;display:grid;align-content:start;gap:5px;padding:8px 0}.workflowx-csx-config-item{width:100%;min-height:34px;overflow:hidden;text-align:left;text-overflow:ellipsis;white-space:nowrap;border:1px solid transparent;border-radius:5px;padding:6px 9px;background:transparent;color:var(--fg-color,#e7edf5);cursor:pointer}.workflowx-csx-config-item.active{border-color:#39a5d8;background:#173f55}
    .workflowx-csx-editor{min-width:0;min-height:0;display:grid;grid-template-rows:auto minmax(0,1fr)}.workflowx-csx-field{display:grid;grid-template-columns:80px minmax(0,1fr);gap:9px;align-items:center;padding-bottom:10px}.workflowx-csx-input{width:100%;min-height:34px;box-sizing:border-box;border:1px solid var(--border-color,#465665);border-radius:6px;padding:6px 9px;background:var(--comfy-input-bg,#222a32);color:var(--fg-color,#eef3f8)}.workflowx-csx-mode-list{min-height:0;overflow:auto;display:grid;align-content:start;border:1px solid var(--border-color,#35414c);background:var(--comfy-menu-bg,#151a20)}.workflowx-csx-mode-row{display:grid;grid-template-columns:minmax(160px,1fr) minmax(340px,1.7fr);gap:10px;align-items:center;min-height:44px;padding:6px 9px;border-bottom:1px solid var(--border-color,#35414c);background:var(--comfy-menu-bg,#151a20)}.workflowx-csx-empty{padding:24px;color:var(--descrip-text,#9aa8b6);text-align:center}
    @media(max-width:800px){.workflowx-csx-overlay{padding:8px}.workflowx-csx-modal{width:100%;height:96vh}.workflowx-csx-config-layout{grid-template-columns:190px minmax(0,1fr);gap:8px}.workflowx-csx-scope-row,.workflowx-csx-mode-row{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);
}

export function createSelectorXController(adapter) {
  let overlay = null;
  let modal = null;
  let editorNode = null;
  let draft = null;
  let draftSelected = "";
  let configIndex = 0;
  let configListScrollTop = 0;

  function readState(node) {
    return parseSelectorXState(String(adapter.getWidgetValue(node, "selectorx_state", "{}") || "{}"));
  }

  function writeState(node, state) {
    adapter.writeJsonWidget(node, "selectorx_state", state);
  }

  function ensureInitialized(node) {
    const existing = readState(node);
    if (existing) {
      const names = existing.configs.map((config) => config.name);
      if (!names.includes(adapter.selectedConfigName(node))) {
        adapter.setWidgetValueSilently(node, "selected_config", names[0] ?? "");
      }
      return existing;
    }
    const raw = String(adapter.getWidgetValue(node, "selectorx_state", "{}") || "{}").trim();
    if (raw && raw !== "{}") return null;

    const imported = adapter.collectLegacyImport();
    const state = imported.summary.hasLegacyConfigs
      ? imported.state
      : createBlankSelectorXState(adapter.groupNames());
    const selected = imported.summary.hasLegacyConfigs
      ? imported.selectedConfig
      : state.configs[0].name;
    writeState(node, state);
    adapter.setWidgetValueSilently(node, "selected_config", selected);
    if (imported.summary.hasLegacyConfigs) {
      adapter.setWidgetValueSilently(node, "console_output", imported.consoleOutput);
      console.info(`[WorkflowX_Configurator] Config SelectorX imported ${state.configs.length} legacy config(s).`);
    }
    return state;
  }

  function ensureModal() {
    if (overlay) return;
    installStyles();
    overlay = el("div", "workflowx-csx-overlay");
    modal = el("div", "workflowx-csx-modal");
    overlay.append(modal);
    document.body.append(overlay);
    overlay.addEventListener("pointerdown", (event) => {
      if (event.target === overlay) closeModal();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && overlay?.style.display === "grid") closeModal();
    });
  }

  function closeModal() {
    if (overlay) overlay.style.display = "none";
    editorNode = null;
    draft = null;
  }

  function shell(title, subtitle) {
    ensureModal();
    modal.replaceChildren();
    const head = el("div", "workflowx-csx-head");
    const titleWrap = el("div");
    titleWrap.append(el("div", "workflowx-csx-title", title), el("div", "workflowx-csx-sub", subtitle));
    head.append(titleWrap);
    modal.append(head);
    return { head, body: el("div", "workflowx-csx-body") };
  }

  function saveDraft() {
    if (!editorNode || !draft) return;
    const names = draft.configs.map((config) => config.name.trim());
    if (names.some((name) => !name) || new Set(names).size !== names.length) {
      window.alert("Config names must be non-empty and unique.");
      return;
    }
    draft.configs.forEach((config, index) => {
      config.name = names[index];
    });
    draft = reconcileSelectorXState(draft, adapter.groupNames());
    if (!names.includes(draftSelected)) draftSelected = names[0];
    writeState(editorNode, draft);
    adapter.setWidgetValueSilently(editorNode, "selected_config", draftSelected);
    const node = editorNode;
    closeModal();
    refresh(node);
  }

  function footer() {
    const foot = el("div", "workflowx-csx-foot");
    foot.append(el("div", "workflowx-csx-sub", "Changes are stored with the workflow."));
    const actions = el("div", "workflowx-csx-actions");
    actions.append(button("Cancel", closeModal), button("Save", saveDraft, "primary"));
    foot.append(actions);
    modal.append(foot);
  }

  function scopeSegment(segments, groupName, scope, label) {
    const control = el("button", "workflowx-csx-segment", label);
    control.type = "button";
    if (draft.scopes[groupName] === scope) control.classList.add("active");
    control.addEventListener("click", () => {
      draft.scopes[groupName] = scope;
      for (const peer of segments.children) peer.classList.remove("active");
      control.classList.add("active");
    });
    return control;
  }

  function openScopes(node) {
    const state = readState(node);
    if (!state) return;
    editorNode = node;
    draft = reconcileSelectorXState(cloneSelectorXState(state), adapter.groupNames());
    draftSelected = adapter.selectedConfigName(node);
    const { body } = shell("Scopes", "Choose which SelectorX control owns each canvas group.");
    const grid = el("div", "workflowx-csx-scope-grid");
    const labels = new Map([
      [IGNORE_SCOPE, "Ignore"], [CONFIG_SCOPE, "Config"],
      [MUTE_SCOPE, "Selector Mute"], [BYPASS_SCOPE, "Selector Bypass"],
    ]);
    for (const groupName of adapter.groupNames()) {
      const row = el("div", "workflowx-csx-scope-row");
      row.append(el("div", "workflowx-csx-group-name", groupName));
      const segments = el("div", "workflowx-csx-segments");
      for (const scope of SCOPE_NAMES) segments.append(scopeSegment(segments, groupName, scope, labels.get(scope)));
      row.append(segments);
      grid.append(row);
    }
    if (!grid.children.length) grid.append(el("div", "workflowx-csx-empty", "No canvas groups found."));
    body.append(grid);
    modal.append(body);
    footer();
    overlay.style.display = "grid";
  }

  function copiedName(baseName) {
    const names = new Set(draft.configs.map((config) => config.name));
    let candidate = `${baseName} Copy`;
    let index = 1;
    while (names.has(candidate)) {
      index += 1;
      candidate = `${baseName} Copy ${index}`;
    }
    return candidate;
  }

  function importLegacy() {
    const imported = adapter.collectLegacyImport();
    if (!imported.summary.hasLegacyConfigs) {
      window.alert("No legacy Group Configurator nodes were found.");
      return;
    }
    const details = [
      `${imported.summary.configs} config(s)`,
      `${imported.summary.groups} canvas group(s)`,
    ];
    if (imported.summary.duplicateConfigs) {
      details.push(`${imported.summary.duplicateConfigs} duplicate config name(s); highest node id wins`);
    }
    if (imported.summary.scopeNodes !== 1) {
      details.push("legacy scope fallback will assign groups to Config control");
    }
    if (!window.confirm(`Replace this draft with legacy canvas data?\n\n${details.join("\n")}`)) return;
    draft = imported.state;
    draftSelected = imported.selectedConfig;
    configIndex = Math.max(0, draft.configs.findIndex((config) => config.name === draftSelected));
    renderConfigs();
  }

  function renderConfigs(preserveScroll = true) {
    const currentList = preserveScroll ? modal?.querySelector(".workflowx-csx-config-list") : null;
    if (currentList) configListScrollTop = currentList.scrollTop;
    const { head, body } = shell("Configs", "Edit stored profiles. Apply a profile from its toggle on the node.");
    const headActions = el("div", "workflowx-csx-actions");
    headActions.append(button("Re-import from canvas", importLegacy));
    head.append(headActions);

    const layout = el("div", "workflowx-csx-config-layout");
    const sidebar = el("div", "workflowx-csx-config-sidebar");
    const topActions = el("div", "workflowx-csx-actions");
    const list = el("div", "workflowx-csx-config-list");
    list.addEventListener("scroll", () => {
      configListScrollTop = list.scrollTop;
    }, { passive: true });
    const bottomActions = el("div", "workflowx-csx-actions");
    const editor = el("div", "workflowx-csx-editor");
    const rerender = () => renderConfigs();

    topActions.append(
      button("Add", () => {
        const name = nextConfigName(draft.configs);
        const modes = Object.fromEntries(
          Object.entries(draft.scopes)
            .filter(([, scope]) => scope === CONFIG_SCOPE)
            .map(([groupName]) => [groupName, "Active"]),
        );
        draft.configs.push({ name, modes });
        configIndex = draft.configs.length - 1;
        rerender();
      }),
      button("Duplicate", () => {
        const source = draft.configs[configIndex];
        draft.configs.splice(configIndex + 1, 0, {
          name: copiedName(source.name),
          modes: { ...source.modes },
        });
        configIndex += 1;
        rerender();
      }),
    );

    draft.configs.forEach((config, index) => {
      const item = el("button", "workflowx-csx-config-item", config.name);
      item.type = "button";
      if (index === configIndex) item.classList.add("active");
      item.addEventListener("click", () => {
        configIndex = index;
        rerender();
      });
      list.append(item);
    });

    const move = (direction) => {
      const nextIndex = configIndex + direction;
      if (nextIndex < 0 || nextIndex >= draft.configs.length) return;
      const [config] = draft.configs.splice(configIndex, 1);
      draft.configs.splice(nextIndex, 0, config);
      configIndex = nextIndex;
      rerender();
    };
    const up = button("Up", () => move(-1));
    const down = button("Down", () => move(1));
    const remove = button("Delete", () => {
      if (draft.configs.length <= 1) return;
      const current = draft.configs[configIndex];
      if (!window.confirm(`Delete config '${current.name}'?`)) return;
      draft.configs.splice(configIndex, 1);
      if (draftSelected === current.name) {
        draftSelected = draft.configs[Math.min(configIndex, draft.configs.length - 1)].name;
      }
      configIndex = Math.min(configIndex, draft.configs.length - 1);
      rerender();
    }, "danger");
    up.disabled = configIndex === 0;
    down.disabled = configIndex === draft.configs.length - 1;
    remove.disabled = draft.configs.length <= 1;
    bottomActions.append(up, down, remove);
    sidebar.append(topActions, list, bottomActions);

    const config = draft.configs[configIndex];
    const field = el("label", "workflowx-csx-field");
    field.append(el("span", "", "Name"));
    const nameInput = el("input", "workflowx-csx-input");
    nameInput.value = config.name;
    nameInput.addEventListener("input", () => {
      const previous = config.name;
      config.name = nameInput.value;
      if (draftSelected === previous) draftSelected = nameInput.value;
      list.children[configIndex].textContent = nameInput.value || "Untitled";
    });
    field.append(nameInput);

    const modeList = el("div", "workflowx-csx-mode-list");
    const configGroups = Object.entries(draft.scopes)
      .filter(([, scope]) => scope === CONFIG_SCOPE)
      .map(([groupName]) => groupName);
    for (const groupName of configGroups) {
      if (!MODE_NAMES.includes(config.modes[groupName])) config.modes[groupName] = "Active";
      const row = el("div", "workflowx-csx-mode-row");
      row.append(el("div", "workflowx-csx-group-name", groupName));
      const segments = el("div", "workflowx-csx-segments");
      for (const mode of MODE_NAMES) {
        const control = el("button", "workflowx-csx-segment", mode);
        control.type = "button";
        if (config.modes[groupName] === mode) control.classList.add("active");
        control.addEventListener("click", () => {
          config.modes[groupName] = mode;
          for (const peer of segments.children) peer.classList.remove("active");
          control.classList.add("active");
        });
        segments.append(control);
      }
      row.append(segments);
      modeList.append(row);
    }
    if (!configGroups.length) modeList.append(el("div", "workflowx-csx-empty", "No groups are assigned to Config scope."));
    editor.append(field, modeList);
    layout.append(sidebar, editor);
    body.append(layout);
    modal.append(body);
    footer();
    overlay.style.display = "grid";
    const requestedScrollTop = configListScrollTop;
    requestAnimationFrame(() => {
      if (list !== modal?.querySelector(".workflowx-csx-config-list")) return;
      list.scrollTop = requestedScrollTop;
      const selectedItem = list.children[configIndex];
      if (!selectedItem) return;
      const viewportRect = list.getBoundingClientRect();
      const selectedRect = selectedItem.getBoundingClientRect();
      if (selectedRect.top < viewportRect.top) {
        list.scrollTop -= viewportRect.top - selectedRect.top;
      } else if (selectedRect.bottom > viewportRect.bottom) {
        list.scrollTop += selectedRect.bottom - viewportRect.bottom;
      }
      configListScrollTop = list.scrollTop;
    });
  }

  function openConfigs(node) {
    const state = readState(node);
    if (!state) return;
    editorNode = node;
    draft = reconcileSelectorXState(cloneSelectorXState(state), adapter.groupNames());
    draftSelected = adapter.selectedConfigName(node);
    configIndex = Math.max(0, draft.configs.findIndex((config) => config.name === draftSelected));
    configListScrollTop = 0;
    renderConfigs(false);
  }

  function addChoice(node, configName) {
    let widget = null;
    widget = node.addWidget(
      "toggle",
      configName,
      adapter.selectedConfigName(node) === configName,
      (value) => {
        const wasSelected = adapter.selectedConfigName(node) === configName;
        if (!value && wasSelected) {
          widget.value = true;
          if (adapter.isAuthoritative(node)) adapter.applySelectedConfig();
          adapter.markCanvasDirty();
          return;
        }
        if (!value) return;

        adapter.setWidgetValueSilently(node, "selected_config", configName);
        for (const candidate of node.widgets ?? []) {
          if (candidate.__workflowXSelectorXConfig) {
            candidate.value = candidate === widget;
          }
        }
        adapter.markCanvasDirty();
        if (adapter.isAuthoritative(node)) adapter.applySelectedConfig();
      },
    );
    widget.value = adapter.selectedConfigName(node) === configName;
    widget.serialize = false;
    widget[UI_MARKER] = true;
    widget.__workflowXSelectorXConfig = true;
  }

  function addScopeToggle(node, sectionName, groupName, targetMode, enabled) {
    const widget = node.addWidget(
      "toggle",
      groupName,
      enabled,
      (value) => {
        const state = readState(node);
        if (!state) return;
        state.advanced[sectionName][groupName] = Boolean(value);
        writeState(node, state);
        if (adapter.isAuthoritative(node)) {
          adapter.applyModeToGroup(groupName, value ? "Active" : targetMode);
        }
        adapter.markCanvasDirty();
      },
    );
    widget.value = Boolean(enabled);
    widget.serialize = false;
    widget[UI_MARKER] = true;
    widget.__workflowXSelectorXScopeToggle = sectionName;
  }

  function addActionBar(node) {
    const labels = ["Console", "Scopes", "Configs"];
    const gap = 6;
    const left = 8;
    const rects = (width, y, height) => {
      const buttonWidth = (width - left * 2 - gap * 2) / 3;
      return labels.map((_, index) => ({
        x: left + index * (buttonWidth + gap),
        y: y + 1,
        w: buttonWidth,
        h: Math.max(24, height - 2),
      }));
    };
    const widget = {
      name: "selectorx:actions",
      type: "workflowx_selectorx_actions",
      serialize: false,
      [UI_MARKER]: true,
      computeSize: () => [node.size?.[0] ?? 300, 42],
      mouse(event, pos) {
        if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
        const width = node.size?.[0] ?? 300;
        const x = Number(pos?.[0] ?? 0);
        const buttonWidth = (width - left * 2 - gap * 2) / 3;
        const index = labels.findIndex((_, candidate) => {
          const start = left + candidate * (buttonWidth + gap);
          return x >= start && x <= start + buttonWidth;
        });
        if (index === 0) {
          const enabled = String(adapter.getWidgetValue(node, "console_output", "no")) === "yes";
          adapter.setWidgetValueSilently(node, "console_output", enabled ? "no" : "yes");
          refresh(node);
        } else if (index === 1) openScopes(node);
        else if (index === 2) openConfigs(node);
        return index >= 0;
      },
      draw(ctx, _node, width, y, height) {
        const consoleEnabled = String(adapter.getWidgetValue(node, "console_output", "no")) === "yes";
        const mouse = adapter.nodeMousePosition?.(node);
        ctx.save();
        rects(width, y, height).forEach((rect, index) => {
          const active = index === 0 && consoleEnabled;
          const hovered = Boolean(
            mouse &&
              mouse[0] >= rect.x &&
              mouse[0] <= rect.x + rect.w &&
              mouse[1] >= rect.y &&
              mouse[1] <= rect.y + rect.h,
          );
          ctx.beginPath();
          roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 4);
          ctx.fillStyle = active ? "#367fa3" : "#2a2c2e";
          ctx.fill();
          ctx.strokeStyle = active || hovered ? "#58a9cf" : "#4a4d50";
          ctx.lineWidth = 1;
          ctx.stroke();
          ctx.fillStyle = active ? "#ffffff" : hovered ? "#dddddd" : "#aaaaaa";
          ctx.font = "11px 'Segoe UI', sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(labels[index], rect.x + rect.w * 0.5, rect.y + rect.h * 0.5);
        });
        ctx.restore();
      },
    };
    node.widgets ??= [];
    node.widgets.push(widget);
  }

  function refresh(node) {
    adapter.hideBackingWidgets(node);
    const state = ensureInitialized(node);
    node.widgets = (node.widgets ?? []).filter((widget) => !widget[UI_MARKER]);
    if (!state) {
      adapter.addTextRow(node, "selectorx:invalid", "Invalid SelectorX state", UI_MARKER);
      addActionBar(node);
      adapter.recomputeNodeHeight(node);
      return;
    }
    for (const config of state.configs) addChoice(node, config.name);
    const muteGroups = Object.entries(state.scopes).filter(([, scope]) => scope === MUTE_SCOPE).map(([name]) => name);
    const bypassGroups = Object.entries(state.scopes).filter(([, scope]) => scope === BYPASS_SCOPE).map(([name]) => name);
    if (muteGroups.length) {
      adapter.addTextRow(node, "selectorx:mute", "Mute", UI_MARKER);
      for (const groupName of muteGroups) addScopeToggle(node, "mute", groupName, "Mute", state.advanced.mute[groupName] === true);
    }
    if (bypassGroups.length) {
      adapter.addTextRow(node, "selectorx:bypass", "Bypass", UI_MARKER);
      for (const groupName of bypassGroups) addScopeToggle(node, "bypass", groupName, "Bypass", state.advanced.bypass[groupName] === true);
    }
    addActionBar(node);
    node.size ??= [300, 100];
    node.size[0] = Math.max(node.size[0], 300);
    adapter.recomputeNodeHeight(node);
    const hiddenSpacing = (node.widgets ?? [])
      .filter((widget) => !widget[UI_MARKER])
      .reduce((total, widget) => total + Math.max(0, Number(widget.computeSize?.()[1] ?? 0) + 4), 0);
    const visibleHeight = (node.widgets ?? [])
      .filter((widget) => widget[UI_MARKER])
      .reduce((total, widget) => total + Number(widget.computeSize?.()[1] ?? 24) + 4, 0);
    const compactHeight = Math.max(64, hiddenSpacing + visibleHeight - 20);
    node.setSize?.([node.size[0], compactHeight]);
    node.size[1] = compactHeight;
    adapter.markCanvasDirty();
  }

  return { refresh, readState, ensureInitialized, openScopes, openConfigs };
}
