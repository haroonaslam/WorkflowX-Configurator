import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { $el } from "../../scripts/ui.js";

const ROUTE = "/xflows";
const STORE_PREFIX = "xflows";
const WORKFLOWX_SETTING_PREFIX = "workflowx.setting";
const WORKFLOWX_SETTING_CATEGORY = ["WorkflowX", "Features"];
const XFLOW_SETTING = {
  id: "WorkflowX.XFlows.Enabled",
  name: "Enable XFlows",
  defaultValue: true,
  tooltip: "Show the WorkflowX workflow manager side panel.",
};

const XFM = {
  workflows: [],
  folders: [],
  root: null,
  data: null,
  query: "",
  view: localStorage.getItem(`${STORE_PREFIX}.view`) || "hierarchy",
  sort: localStorage.getItem(`${STORE_PREFIX}.sort`) || "name",
  favoritesOnly: localStorage.getItem(`${STORE_PREFIX}.favoritesOnly`) === "true",
  expandedFolders: new Set(),
  collapsedFolders: new Set(),
  expandedTags: new Set(),
  expandedActions: new Set(),
  activeWorkflow: null,
  loadedSnapshot: null,
  loadingFromManager: false,
  duplicateResult: null,
  dialog: null,
  refreshTimers: new Map(),
  recentlyUpdated: new Map(),
  fallbackPanel: null,
  fallbackButton: null,
};

const style = `
.xfm-shell {
  --xfm-bg: color-mix(in srgb, var(--comfy-menu-bg, #181a20) 94%, #0f766e 6%);
  --xfm-panel: color-mix(in srgb, var(--comfy-menu-bg, #181a20) 84%, #ffffff 7%);
  --xfm-panel-2: color-mix(in srgb, var(--comfy-input-bg, #101217) 88%, #14b8a6 6%);
  --xfm-border: color-mix(in srgb, var(--border-color, #3c3f45) 78%, #14b8a6 22%);
  --xfm-accent: #14b8a6;
  --xfm-warn: #f59e0b;
  --xfm-danger: #ef4444;
  --xfm-muted: color-mix(in srgb, var(--fg-color, #e7e9ee) 64%, transparent);
  background: var(--xfm-bg);
  color: var(--fg-color);
  display: flex;
  flex-direction: column;
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  position: relative;
}
.xfm-shell * { box-sizing: border-box; letter-spacing: 0; }
.xfm-header {
  border-bottom: 1px solid var(--xfm-border);
  display: grid;
  gap: 9px;
  padding: 12px;
}
.xfm-title-row, .xfm-toolbar, .xfm-filter-row, .xfm-card-main, .xfm-card-actions, .xfm-modal-title {
  align-items: center;
  display: flex;
  gap: 8px;
  min-width: 0;
}
.xfm-title {
  flex: 1;
  font-size: 15px;
  font-weight: 760;
  min-width: 0;
}
.xfm-count, .xfm-subtle {
  color: var(--xfm-muted);
  font-size: 11px;
}
.xfm-search-wrap { position: relative; }
.xfm-search-wrap .pi {
  color: var(--xfm-muted);
  left: 10px;
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
}
.xfm-input, .xfm-select {
  background: var(--comfy-input-bg, #111318);
  border: 1px solid var(--xfm-border);
  border-radius: 7px;
  color: var(--fg-color);
  font: inherit;
  min-height: 34px;
  outline: none;
  padding: 7px 9px;
  width: 100%;
}
.xfm-search-wrap .xfm-input { padding-left: 32px; }
.xfm-input:focus, .xfm-select:focus {
  border-color: var(--xfm-accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--xfm-accent) 24%, transparent);
}
.xfm-field {
  align-items: center;
  display: flex;
  flex: 1;
  gap: 6px;
  min-width: 132px;
}
.xfm-label {
  color: var(--xfm-muted);
  font-size: 11px;
  font-weight: 720;
  white-space: nowrap;
}
.xfm-btn {
  align-items: center;
  background: var(--xfm-panel-2);
  border: 1px solid var(--xfm-border);
  border-radius: 7px;
  color: var(--fg-color);
  cursor: pointer;
  display: inline-flex;
  font: inherit;
  font-size: 12px;
  font-weight: 650;
  gap: 6px;
  justify-content: center;
  min-height: 32px;
  padding: 6px 9px;
  text-decoration: none;
  white-space: nowrap;
}
.xfm-btn:hover { border-color: var(--xfm-accent); filter: brightness(1.08); }
.xfm-btn.active, .xfm-btn[aria-pressed="true"] {
  background: color-mix(in srgb, var(--xfm-accent) 28%, var(--xfm-panel-2));
  border-color: var(--xfm-accent);
}
.xfm-icon-btn {
  aspect-ratio: 1 / 1;
  min-width: 34px;
  padding: 0;
}
.xfm-segment {
  background: color-mix(in srgb, var(--xfm-panel-2) 70%, transparent);
  border: 1px solid var(--xfm-border);
  border-radius: 8px;
  display: inline-flex;
  padding: 2px;
}
.xfm-segment .xfm-btn {
  background: transparent;
  border-color: transparent;
  min-height: 28px;
}
.xfm-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 10px;
}
.xfm-empty {
  border: 1px dashed var(--xfm-border);
  border-radius: 8px;
  color: var(--xfm-muted);
  font-size: 12px;
  padding: 18px;
  text-align: center;
}
.xfm-folder {
  border-left: 1px solid color-mix(in srgb, var(--xfm-border) 55%, transparent);
  margin-left: 6px;
  padding-left: 8px;
}
.xfm-folder > summary {
  align-items: center;
  color: var(--xfm-muted);
  cursor: pointer;
  display: flex;
  font-size: 12px;
  font-weight: 720;
  gap: 6px;
  list-style: none;
  min-height: 28px;
}
.xfm-folder > summary::-webkit-details-marker { display: none; }
.xfm-folder > summary::before {
  color: var(--xfm-accent);
  content: ">";
  display: inline-block;
  font-size: 13px;
  transition: transform 120ms ease;
}
.xfm-folder[open] > summary::before { transform: rotate(90deg); }
.xfm-card-list {
  display: grid;
  gap: 8px;
}
.xfm-card {
  background: linear-gradient(180deg, var(--xfm-panel), color-mix(in srgb, var(--xfm-panel) 86%, #000 14%));
  border: 1px solid var(--xfm-border);
  border-radius: 8px;
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 10px;
}
.xfm-card.updated {
  animation: xfm-updated-pulse 1400ms ease-out 1;
  border-color: color-mix(in srgb, var(--xfm-accent) 75%, #fff 25%);
}
@keyframes xfm-updated-pulse {
  0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--xfm-accent) 36%, transparent); }
  100% { box-shadow: 0 0 0 8px transparent; }
}
.xfm-card-main {
  align-items: start;
  justify-content: space-between;
}
.xfm-name {
  font-size: 13px;
  font-weight: 740;
  line-height: 1.25;
  overflow-wrap: anywhere;
}
.xfm-path {
  color: var(--xfm-muted);
  font-size: 11px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}
.xfm-meta, .xfm-tags {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  min-width: 0;
}
.xfm-meta {
  color: var(--xfm-muted);
  font-size: 11px;
  gap: 7px;
}
.xfm-pill {
  background: color-mix(in srgb, var(--xfm-accent) 18%, transparent);
  border: 1px solid color-mix(in srgb, var(--xfm-accent) 45%, transparent);
  border-radius: 999px;
  color: var(--fg-color);
  display: inline-flex;
  font-size: 10.5px;
  line-height: 1.15;
  max-width: 100%;
  overflow-wrap: anywhere;
  padding: 3px 7px;
}
.xfm-pill.manual {
  background: color-mix(in srgb, var(--xfm-warn) 18%, transparent);
  border-color: color-mix(in srgb, var(--xfm-warn) 48%, transparent);
}
.xfm-tag-manager {
  border: 1px solid var(--xfm-border);
  border-radius: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 250px;
  overflow: auto;
  padding: 8px;
}
.xfm-tag-chip {
  align-items: center;
  background: color-mix(in srgb, var(--xfm-panel-2) 82%, transparent);
  border: 1px solid var(--xfm-border);
  border-radius: 999px;
  display: inline-flex;
  gap: 5px;
  max-width: 100%;
  padding: 4px 5px 4px 8px;
}
.xfm-tag-chip.manual {
  border-color: color-mix(in srgb, var(--xfm-warn) 52%, transparent);
}
.xfm-tag-chip.auto {
  border-color: color-mix(in srgb, var(--xfm-accent) 52%, transparent);
}
.xfm-tag-text {
  font-size: 11px;
  overflow-wrap: anywhere;
}
.xfm-tag-source {
  color: var(--xfm-muted);
  font-size: 9px;
  text-transform: uppercase;
}
.xfm-tag-remove {
  min-height: 22px;
  min-width: 22px;
}
.xfm-star {
  background: transparent;
  border-color: transparent;
  color: var(--xfm-muted);
}
.xfm-star.active { color: var(--xfm-warn); }
.xfm-danger:hover { border-color: var(--xfm-danger); color: #fecaca; }
.xfm-panel {
  background: var(--xfm-panel);
  border-top: 1px solid var(--xfm-border);
  display: grid;
  gap: 8px;
  max-height: 42%;
  overflow: auto;
  padding: 10px;
}
.xfm-duplicate-group {
  border: 1px solid var(--xfm-border);
  border-radius: 8px;
  padding: 8px;
}
.xfm-duplicate-title {
  font-size: 12px;
  font-weight: 740;
  margin-bottom: 5px;
}
.xfm-small-list {
  color: var(--xfm-muted);
  display: grid;
  font-size: 11px;
  gap: 4px;
}
.xfm-floating-panel {
  bottom: 18px;
  box-shadow: 0 24px 70px rgba(0,0,0,.42);
  max-width: min(520px, calc(100vw - 28px));
  position: fixed;
  right: 14px;
  top: 18px;
  width: 420px;
  z-index: 9999;
}
.xfm-modal-backdrop {
  align-items: center;
  background: rgba(0, 0, 0, .48);
  display: flex;
  inset: 0;
  justify-content: center;
  padding: 14px;
  position: absolute;
  z-index: 20;
}
.xfm-modal {
  background: color-mix(in srgb, var(--comfy-menu-bg, #181a20) 94%, #111 6%);
  border: 1px solid var(--xfm-border);
  border-radius: 10px;
  box-shadow: 0 18px 60px rgba(0,0,0,.48);
  display: grid;
  gap: 10px;
  max-height: min(620px, 92%);
  min-width: min(440px, 100%);
  overflow: hidden;
  padding: 12px;
  width: min(520px, 100%);
}
.xfm-modal-title .xfm-title { font-size: 14px; }
.xfm-folder-picker {
  border: 1px solid var(--xfm-border);
  border-radius: 8px;
  display: grid;
  gap: 3px;
  max-height: 310px;
  overflow: auto;
  padding: 8px;
}
.xfm-folder-row {
  align-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--fg-color);
  cursor: pointer;
  display: flex;
  font: inherit;
  font-size: 12px;
  gap: 6px;
  min-height: 28px;
  padding: 4px 8px;
  text-align: left;
  width: 100%;
}
.xfm-folder-row:hover, .xfm-folder-row.active {
  background: color-mix(in srgb, var(--xfm-accent) 18%, transparent);
  border-color: color-mix(in srgb, var(--xfm-accent) 42%, transparent);
}
.xfm-dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
`;

function stableStringify(value) {
  const seen = new WeakSet();
  const normalize = (item) => {
    if (!item || typeof item !== "object") return item;
    if (seen.has(item)) return null;
    seen.add(item);
    if (Array.isArray(item)) return item.map(normalize);
    return Object.keys(item).sort().reduce((acc, key) => {
      acc[key] = normalize(item[key]);
      return acc;
    }, {});
  };
  return JSON.stringify(normalize(value));
}

async function apiJson(path, options = {}) {
  const response = await api.fetchApi(path, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.error || response.statusText || `Request failed: ${response.status}`);
  }
  return data;
}

async function postJson(path, body = {}) {
  return apiJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function clear(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function shortDate(ms) {
  if (!ms) return "never";
  try {
    return new Date(ms).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "unknown";
  }
}

function icon(name) {
  return $el("i", { className: `pi ${name}` });
}

function makeButton({ label, iconName, className = "", onClick, title, pressed = false }) {
  const element = $el("button.xfm-btn", {
    type: "button",
    onclick: onClick,
    title: title || label || "",
    "aria-label": title || label || "",
    "aria-pressed": pressed ? "true" : "false",
  });
  for (const name of className.split(/\s+/).filter(Boolean)) element.classList.add(name);
  if (iconName) element.append(icon(iconName));
  if (label) element.append($el("span", { textContent: label }));
  return element;
}

function iconButton(iconName, title, onClick, className = "") {
  return makeButton({ iconName, title, onClick, className: `xfm-icon-btn ${className}` });
}

function settingStorageKey(id) {
  return `${WORKFLOWX_SETTING_PREFIX}.${id}`;
}

function isXFlowsEnabled() {
  try {
    const value = app.ui?.settings?.getSettingValue?.(XFLOW_SETTING.id);
    if (value !== undefined && value !== null) return value !== false && value !== "false";
  } catch {}
  const stored = localStorage.getItem(settingStorageKey(XFLOW_SETTING.id));
  return stored == null ? XFLOW_SETTING.defaultValue : stored !== "false";
}

function setButtonVisible(buttonRef, visible) {
  const target = buttonRef?.element || buttonRef?.button || buttonRef?.root || buttonRef;
  if (target?.style) target.style.display = visible ? "" : "none";
}

function applyXFlowsVisibility() {
  const enabled = isXFlowsEnabled();
  setButtonVisible(XFM.fallbackButton, enabled);
  if (!enabled && XFM.fallbackPanel) XFM.fallbackPanel.style.display = "none";
  if (XFM.root) renderShell(XFM.root);
}

function registerXFlowsSetting() {
  const apply = (value) => {
    const enabled = value !== false && value !== "false";
    localStorage.setItem(settingStorageKey(XFLOW_SETTING.id), String(enabled));
    applyXFlowsVisibility();
  };
  try {
    app.ui?.settings?.addSetting?.({
      id: XFLOW_SETTING.id,
      category: WORKFLOWX_SETTING_CATEGORY,
      name: XFLOW_SETTING.name,
      type: "boolean",
      defaultValue: XFLOW_SETTING.defaultValue,
      tooltip: XFLOW_SETTING.tooltip,
      onChange: apply,
      callback: apply,
    });
  } catch {
    if (localStorage.getItem(settingStorageKey(XFLOW_SETTING.id)) == null) {
      localStorage.setItem(settingStorageKey(XFLOW_SETTING.id), String(XFLOW_SETTING.defaultValue));
    }
  }
}

function lowerSet(values = []) {
  return new Set((values || []).map((value) => String(value).toLowerCase()));
}

function tagSource(workflow, tag) {
  const key = String(tag).toLowerCase();
  const auto = lowerSet(workflow.auto_tags).has(key);
  const manual = lowerSet(workflow.manual_tags).has(key);
  if (auto && manual) return "auto + custom";
  if (manual) return "custom";
  return "auto";
}

function applyTagResponse(data) {
  const workflow = XFM.workflows.find((item) => item.path === data.path);
  if (!workflow) return;
  workflow.manual_tags = data.manual_tags || [];
  workflow.hidden_auto_tags = data.hidden_auto_tags || [];
  workflow.all_tags = data.all_tags || [];
  if (XFM.dialog?.workflow?.path === workflow.path) {
    XFM.dialog.workflow = workflow;
  }
}

function filteredWorkflows() {
  const query = XFM.query.trim().toLowerCase();
  let items = XFM.workflows.filter((workflow) => {
    if (XFM.favoritesOnly && !workflow.favorite) return false;
    if (!query) return true;
    const haystack = [
      workflow.name,
      workflow.file_name,
      workflow.path,
      workflow.folder,
      ...(workflow.all_tags || []),
      ...(workflow.node_types || []),
      ...(workflow.detected_models || []).map((model) => `${model.folder} ${model.name}`),
    ].join("\n").toLowerCase();
    return haystack.includes(query);
  });

  items.sort((a, b) => {
    if (XFM.sort === "newest") return (b.mtime || 0) - (a.mtime || 0) || a.path.localeCompare(b.path);
    if (XFM.sort === "most_used") return (b.run_count || 0) - (a.run_count || 0) || a.path.localeCompare(b.path);
    if (XFM.sort === "last_used") return (b.last_run_at || 0) - (a.last_run_at || 0) || a.path.localeCompare(b.path);
    return a.name.localeCompare(b.name) || a.path.localeCompare(b.path);
  });
  return items;
}

function renderShell(target, options = {}) {
  const previousScrollTop = options.preserveScroll
    ? target.querySelector(".xfm-content")?.scrollTop || 0
    : 0;
  clear(target);
  target.classList.add("xfm-shell");
  XFM.root = target;

  const header = $el("div.xfm-header", { parent: target });
  const titleRow = $el("div.xfm-title-row", { parent: header });
  $el("div.xfm-title", { textContent: "XFlows", parent: titleRow });
  if (!isXFlowsEnabled()) {
    $el("div.xfm-content", { parent: target }, [
      $el("div.xfm-empty", { textContent: "XFlows is disabled in WorkflowX settings." }),
    ]);
    return;
  }
  $el("div.xfm-count", {
    textContent: `${filteredWorkflows().length}/${XFM.workflows.length}`,
    parent: titleRow,
  });
  titleRow.append(
    iconButton("pi-sync", "Sync workflows", () => loadData(true)),
    iconButton("pi-clone", "Find duplicates", () => findDuplicates())
  );

  const searchWrap = $el("div.xfm-search-wrap", { parent: header });
  searchWrap.append(icon("pi-search"));
  const search = $el("input.xfm-input", {
    type: "search",
    placeholder: "Search XFlows...",
    value: XFM.query,
    oninput: (event) => {
      const preserveSearchFocus = {
        start: event.target.selectionStart,
        end: event.target.selectionEnd,
      };
      XFM.query = event.target.value;
      renderShell(XFM.root, { preserveSearchFocus });
    },
    parent: searchWrap,
  });

  const toolbar = $el("div.xfm-toolbar", { parent: header });
  const segment = $el("div.xfm-segment", { parent: toolbar });
  segment.append(
    makeButton({
      iconName: "pi-sitemap",
      title: "Hierarchy view",
      pressed: XFM.view === "hierarchy",
      className: XFM.view === "hierarchy" ? "active" : "",
      onClick: () => setView("hierarchy"),
    }),
    makeButton({
      iconName: "pi-list",
      title: "List view",
      pressed: XFM.view === "list",
      className: XFM.view === "list" ? "active" : "",
      onClick: () => setView("list"),
    })
  );
  toolbar.append(
    iconButton("pi-angle-double-down", "Expand all folders", () => setAllFoldersOpen(true)),
    iconButton("pi-angle-double-up", "Collapse all folders", () => setAllFoldersOpen(false))
  );

  const sortField = $el("label.xfm-field", { parent: toolbar });
  sortField.append($el("span.xfm-label", { textContent: "Sort" }));
  const sort = $el("select.xfm-select", {
    value: XFM.sort,
    onchange: (event) => {
      XFM.sort = event.target.value;
      localStorage.setItem(`${STORE_PREFIX}.sort`, XFM.sort);
      renderShell(XFM.root);
    },
    parent: sortField,
  }, [
    $el("option", { value: "name", textContent: "Name" }),
    $el("option", { value: "newest", textContent: "Newest" }),
    $el("option", { value: "most_used", textContent: "Most used" }),
    $el("option", { value: "last_used", textContent: "Last used" }),
  ]);
  sort.value = XFM.sort;

  const filterRow = $el("div.xfm-filter-row", { parent: header });
  filterRow.append(
    makeButton({
      label: "All items",
      iconName: "pi-folder-open",
      className: XFM.favoritesOnly ? "" : "active",
      pressed: !XFM.favoritesOnly,
      onClick: () => setFavoritesOnly(false),
    }),
    makeButton({
      label: "Favorites",
      iconName: "pi-star",
      className: XFM.favoritesOnly ? "active" : "",
      pressed: XFM.favoritesOnly,
      onClick: () => setFavoritesOnly(true),
    }),
    iconButton("pi-info-circle", XFM.data?.workflow_root || "Workflow root", () => {
      XFM.dialog = { type: "info" };
      renderShell(XFM.root);
    })
  );

  const content = $el("div.xfm-content", { parent: target });
  const items = filteredWorkflows();
  if (!items.length) {
    $el("div.xfm-empty", { textContent: "No workflows match the current filters.", parent: content });
  } else if (XFM.view === "list") {
    renderList(content, items);
  } else {
    renderHierarchy(content, items);
  }

  if (XFM.duplicateResult) renderDuplicates(target);
  if (XFM.dialog) renderDialog(target);

  if (options.preserveScroll) {
    requestAnimationFrame(() => {
      content.scrollTop = previousScrollTop;
    });
  }

  if (options.preserveSearchFocus) {
    requestAnimationFrame(() => {
      search.focus({ preventScroll: true });
      const { start, end } = options.preserveSearchFocus;
      if (Number.isInteger(start) && Number.isInteger(end)) {
        try {
          search.setSelectionRange(start, end);
        } catch {
        }
      }
    });
  }
}

function setView(view) {
  XFM.view = view;
  localStorage.setItem(`${STORE_PREFIX}.view`, XFM.view);
  renderShell(XFM.root);
}

function setFavoritesOnly(value) {
  XFM.favoritesOnly = value;
  localStorage.setItem(`${STORE_PREFIX}.favoritesOnly`, value ? "true" : "false");
  renderShell(XFM.root);
}

function folderPathsForItems(items = filteredWorkflows()) {
  const folders = new Set();
  for (const workflow of items) {
    if (!workflow.folder) continue;
    const parts = workflow.folder.split("/").filter(Boolean);
    let current = "";
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      folders.add(current);
    }
  }
  return folders;
}

function setAllFoldersOpen(open) {
  const folders = folderPathsForItems();
  if (open) {
    XFM.expandedFolders = new Set(folders);
    XFM.collapsedFolders.clear();
  } else {
    XFM.collapsedFolders = new Set(folders);
    XFM.expandedFolders.clear();
  }
  renderShell(XFM.root, { preserveScroll: true });
}

function renderList(parent, items) {
  const list = $el("div.xfm-card-list", { parent });
  for (const workflow of items) list.append(renderCard(workflow));
}

function renderHierarchy(parent, items) {
  const root = { name: "", path: "", children: new Map(), workflows: [] };
  for (const workflow of items) {
    const parts = workflow.folder ? workflow.folder.split("/") : [];
    let node = root;
    let current = "";
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      if (!node.children.has(part)) {
        node.children.set(part, { name: part, path: current, children: new Map(), workflows: [] });
      }
      node = node.children.get(part);
    }
    node.workflows.push(workflow);
  }
  const container = $el("div.xfm-card-list", { parent });
  renderTreeNode(container, root, 0);
}

function renderTreeNode(parent, node, depth) {
  if (node.path) {
    const open = XFM.expandedFolders.has(node.path) || (!XFM.collapsedFolders.has(node.path) && depth < 3);
    const details = $el("details.xfm-folder", {
      open,
      ontoggle: (event) => {
        if (event.target !== details) return;
        if (details.open) {
          XFM.expandedFolders.add(node.path);
          XFM.collapsedFolders.delete(node.path);
        } else {
          XFM.collapsedFolders.add(node.path);
          XFM.expandedFolders.delete(node.path);
        }
      },
      parent,
    });
    $el("summary", { textContent: `${node.name} (${countTree(node)})`, parent: details });
    parent = details;
  }
  if (node.workflows.length) {
    const list = $el("div.xfm-card-list", { parent });
    for (const workflow of node.workflows) list.append(renderCard(workflow));
  }
  [...node.children.values()]
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((child) => renderTreeNode(parent, child, depth + 1));
}

function countTree(node) {
  let count = node.workflows.length;
  for (const child of node.children.values()) count += countTree(child);
  return count;
}

function renderCard(workflow) {
  const updatedAt = XFM.recentlyUpdated.get(workflow.path) || 0;
  const recentlyUpdated = Date.now() - updatedAt < 6000;
  const card = $el("div.xfm-card" + (recentlyUpdated ? ".updated" : ""));
  const main = $el("div.xfm-card-main", { parent: card });
  const title = $el("div", { parent: main });
  $el("div.xfm-name", { textContent: workflow.name, title: workflow.file_name, parent: title });
  $el("div.xfm-path", { textContent: workflow.folder || "(root)", title: workflow.path, parent: title });

  main.append(makeButton({
    iconName: workflow.favorite ? "pi-star-fill" : "pi-star",
    className: workflow.favorite ? "xfm-icon-btn xfm-star active" : "xfm-icon-btn xfm-star",
    title: workflow.favorite ? "Remove favorite" : "Add favorite",
    onClick: () => toggleFavorite(workflow),
  }));

  $el("div.xfm-meta", { parent: card }, [
    $el("span", { textContent: `${workflow.run_count || 0} runs` }),
    $el("span", { textContent: `${workflow.node_count || 0} nodes` }),
    $el("span", { textContent: `new ${shortDate(workflow.mtime)}` }),
    recentlyUpdated ? $el("span", { textContent: "Updated just now" }) : null,
    workflow.parse_error ? $el("span", { textContent: "parse error" }) : null,
  ].filter(Boolean));

  const tagRow = $el("div.xfm-tags", { parent: card });
  const expanded = XFM.expandedTags.has(workflow.path);
  const tags = expanded ? workflow.all_tags || [] : (workflow.all_tags || []).slice(0, 5);
  for (const tag of tags) {
    const manual = (workflow.manual_tags || []).some((manualTag) => manualTag.toLowerCase() === tag.toLowerCase());
    tagRow.append($el("span.xfm-pill" + (manual ? ".manual" : ""), { textContent: tag }));
  }
  if ((workflow.all_tags || []).length > 5) {
    tagRow.append(makeButton({
      label: expanded ? "Less" : `+${workflow.all_tags.length - 5}`,
      title: expanded ? "Collapse tags" : "Show all tags",
      onClick: () => {
        if (expanded) XFM.expandedTags.delete(workflow.path);
        else XFM.expandedTags.add(workflow.path);
        renderShell(XFM.root, { preserveScroll: true });
      },
    }));
  }
  tagRow.append(makeButton({
    label: "Manage tags",
    iconName: "pi-tags",
    title: "Manage tags",
    onClick: () => openTagDialog(workflow),
  }));

  const actions = $el("div.xfm-card-actions", { parent: card });
  actions.append(
    makeButton({ label: "Use", iconName: "pi-play", className: "active", onClick: () => useWorkflow(workflow) }),
    iconButton("pi-ellipsis-v", "More actions", () => {
      if (XFM.expandedActions.has(workflow.path)) XFM.expandedActions.delete(workflow.path);
      else XFM.expandedActions.add(workflow.path);
      renderShell(XFM.root, { preserveScroll: true });
    })
  );

  if (XFM.expandedActions.has(workflow.path)) {
    const more = $el("div.xfm-card-actions", { parent: card });
    more.append(
      makeButton({ label: "Move", iconName: "pi-folder", onClick: () => openMoveDialog(workflow) }),
      makeButton({ label: "Delete", iconName: "pi-trash", className: "xfm-danger", onClick: () => deleteWorkflow(workflow) })
    );
  }

  return card;
}

async function loadData(sync = false) {
  try {
    const data = sync ? await postJson(`${ROUTE}/sync`) : await apiJson(`${ROUTE}/workflows`, { cache: "no-store" });
    XFM.data = data;
    XFM.workflows = data.workflows || [];
    XFM.folders = data.folders || [];
    XFM.duplicateResult = null;
    if (XFM.root) renderShell(XFM.root);
  } catch (error) {
    console.error("[XFlows] Failed to load workflows", error);
    alert(`XFlows failed to load: ${error.message}`);
  }
}

function upsertWorkflow(workflow) {
  const index = XFM.workflows.findIndex((item) => item.path === workflow.path);
  if (index === -1) XFM.workflows.push(workflow);
  else XFM.workflows[index] = workflow;
  XFM.workflows.sort((a, b) => a.path.localeCompare(b.path));
}

async function refreshWorkflow(path) {
  try {
    const data = await postJson(`${ROUTE}/refresh`, { path });
    if (data.workflow) {
      upsertWorkflow(data.workflow);
      XFM.folders = data.folders || XFM.folders;
      XFM.recentlyUpdated.set(path, Date.now());
      if (XFM.activeWorkflow?.path === path) {
        XFM.activeWorkflow.contentHash = data.workflow.content_hash;
        XFM.loadedSnapshot = stableStringify(app.graph.serialize());
      }
      if (XFM.root) renderShell(XFM.root);
      setTimeout(() => {
        XFM.recentlyUpdated.delete(path);
        if (XFM.root) renderShell(XFM.root);
      }, 6500);
    }
  } catch (error) {
    if (error.message?.includes("workflow not found")) {
      await loadData(true);
      return;
    }
    console.warn("[XFlows] Failed to refresh saved workflow", error);
  }
}

function scheduleWorkflowRefresh(path) {
  if (!path) return;
  const existing = XFM.refreshTimers.get(path);
  if (existing) clearTimeout(existing);
  XFM.refreshTimers.set(path, setTimeout(async () => {
    XFM.refreshTimers.delete(path);
    await refreshWorkflow(path);
  }, 450));
}

function workflowPathFromUserdataRoute(routeText) {
  let pathname;
  try {
    pathname = new URL(routeText, window.location.origin).pathname;
  } catch {
    pathname = String(routeText).split("?")[0];
  }
  const prefixes = ["/userdata/", "/api/userdata/"];
  const prefix = prefixes.find((value) => pathname.startsWith(value));
  if (!prefix) return null;
  const decoded = decodeURIComponent(pathname.slice(prefix.length));
  const normalized = decoded.replace(/\\/g, "/");
  if (!normalized.startsWith("workflows/") || !normalized.toLowerCase().endsWith(".json")) return null;
  if (normalized === "workflows/.index.json") return null;
  return normalized.slice("workflows/".length);
}

function layoutSnapshot(graphData) {
  const result = new Map();
  for (const node of graphData?.nodes || []) {
    const id = String(node.id);
    result.set(id, {
      pos: Array.isArray(node.pos) ? node.pos.map(Number) : null,
      size: Array.isArray(node.size) ? node.size.map(Number) : null,
    });
  }
  return result;
}

function sameNumberArray(a, b) {
  if (!a && !b) return true;
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
  return a.every((value, index) => Math.abs(Number(value) - Number(b[index])) < 0.001);
}

function immediateLayoutDiff(sourceWorkflow, loadedGraph) {
  const source = layoutSnapshot(sourceWorkflow);
  const loaded = layoutSnapshot(loadedGraph);
  const diffs = [];
  for (const [id, before] of source.entries()) {
    const after = loaded.get(id);
    if (!after) {
      diffs.push({ id, field: "missing-after-load" });
      continue;
    }
    if (!sameNumberArray(before.pos, after.pos)) diffs.push({ id, field: "pos", source: before.pos, loaded: after.pos });
    if (!sameNumberArray(before.size, after.size)) diffs.push({ id, field: "size", source: before.size, loaded: after.size });
    if (diffs.length >= 12) break;
  }
  return diffs;
}

function warnIfLayoutChangedOnLoad(sourceWorkflow) {
  if (localStorage.getItem("xflows.debugLayout") !== "true") return;
  try {
    const diffs = immediateLayoutDiff(sourceWorkflow, app.graph.serialize());
    if (diffs.length) {
      console.warn("[XFlows] Graph layout differs immediately after app.loadGraphData. XFlows did not normalize layout; this points to ComfyUI load/migration behavior.", diffs);
    }
  } catch (error) {
    console.debug("[XFlows] Layout diagnostic skipped", error);
  }
}

async function useWorkflow(workflow) {
  try {
    const data = await apiJson(`${ROUTE}/workflow?path=${encodeURIComponent(workflow.path)}`, { cache: "no-store" });
    const sourceWorkflow = JSON.parse(JSON.stringify(data.workflow));
    XFM.loadingFromManager = true;
    try {
      await app.loadGraphData(
        data.workflow,
        true,
        true,
        workflow.path,
        { checkForRerouteMigration: false, openSource: "xflows" }
      );
    } finally {
      XFM.loadingFromManager = false;
    }
    warnIfLayoutChangedOnLoad(sourceWorkflow);
    XFM.activeWorkflow = {
      path: workflow.path,
      contentHash: workflow.content_hash,
      loadedAt: Date.now(),
    };
    XFM.loadedSnapshot = stableStringify(app.graph.serialize());
  } catch (error) {
    console.error("[XFlows] Failed to load workflow", error);
    alert(`Could not load workflow: ${error.message}`);
  }
}

async function toggleFavorite(workflow) {
  await postJson(`${ROUTE}/favorite`, { path: workflow.path, favorite: !workflow.favorite });
  await loadData(false);
}

function openTagDialog(workflow) {
  XFM.dialog = { type: "tags", workflow, tag: "" };
  renderShell(XFM.root, { preserveScroll: true });
}

async function addTagFromDialog() {
  const tag = XFM.dialog?.tag?.trim();
  const workflow = XFM.dialog?.workflow;
  if (!tag || !workflow) return;
  const data = await postJson(`${ROUTE}/tags`, { path: workflow.path, add: [tag] });
  applyTagResponse(data);
  XFM.dialog.tag = "";
  XFM.expandedTags.add(workflow.path);
  renderShell(XFM.root, { preserveScroll: true });
}

async function removeTagFromDialog(tag) {
  const workflow = XFM.dialog?.workflow;
  if (!tag || !workflow) return;
  const data = await postJson(`${ROUTE}/tags`, { path: workflow.path, remove: [tag] });
  applyTagResponse(data);
  renderShell(XFM.root, { preserveScroll: true });
}

function openMoveDialog(workflow) {
  XFM.dialog = {
    type: "move",
    workflow,
    selectedFolder: workflow.folder || "",
    newFolder: "",
  };
  renderShell(XFM.root);
}

async function createFolderFromDialog() {
  const dialog = XFM.dialog;
  if (!dialog || dialog.type !== "move") return;
  const name = (dialog.newFolder || "").trim();
  if (!name) return;
  try {
    const data = await postJson(`${ROUTE}/folder`, { parent: dialog.selectedFolder || "", name });
    XFM.folders = data.folders || XFM.folders;
    dialog.selectedFolder = data.folder;
    dialog.newFolder = "";
    renderShell(XFM.root);
  } catch (error) {
    alert(`Create folder failed: ${error.message}`);
  }
}

async function confirmMoveDialog() {
  const dialog = XFM.dialog;
  if (!dialog || dialog.type !== "move") return;
  try {
    await postJson(`${ROUTE}/move`, { path: dialog.workflow.path, folder: dialog.selectedFolder || "" });
    XFM.dialog = null;
    await loadData(true);
  } catch (error) {
    alert(`Move failed: ${error.message}`);
  }
}

async function deleteWorkflow(workflow) {
  if (!confirm(`Move "${workflow.name}" to XFlows trash?`)) return;
  try {
    await postJson(`${ROUTE}/delete`, { path: workflow.path });
    await loadData(true);
  } catch (error) {
    alert(`Delete failed: ${error.message}`);
  }
}

async function findDuplicates() {
  try {
    XFM.duplicateResult = await postJson(`${ROUTE}/duplicates`);
    renderShell(XFM.root);
  } catch (error) {
    alert(`Duplicate scan failed: ${error.message}`);
  }
}

function renderDuplicates(parent) {
  const panel = $el("div.xfm-panel", { parent });
  const summary = [
    `Exact: ${XFM.duplicateResult.exact?.length || 0}`,
    `Graph: ${XFM.duplicateResult.canonical?.length || 0}`,
    `Near: ${XFM.duplicateResult.near?.length || 0}`,
  ].join(" | ");
  const row = $el("div.xfm-title-row", { parent: panel });
  $el("div.xfm-title", { textContent: `Duplicate Finder | ${summary}`, parent: row });
  row.append(iconButton("pi-times", "Close duplicate finder", () => {
    XFM.duplicateResult = null;
    renderShell(XFM.root);
  }));

  const sections = [
    ["Exact duplicates", XFM.duplicateResult.exact || []],
    ["Same graph structure", XFM.duplicateResult.canonical || []],
    ["Near duplicates", XFM.duplicateResult.near || []],
  ];
  for (const [title, groups] of sections) {
    const group = groups[0];
    if (!group) continue;
    const box = $el("div.xfm-duplicate-group", { parent: panel });
    $el("div.xfm-duplicate-title", { textContent: `${title}: ${group.count} workflows`, parent: box });
    const list = $el("div.xfm-small-list", { parent: box });
    group.workflows.slice(0, 8).forEach((workflow) => {
      $el("div", { textContent: workflow.path, title: workflow.path, parent: list });
    });
    if (groups.length > 1) {
      $el("div", { textContent: `${groups.length - 1} more duplicate groups`, parent: list });
    }
  }
}

function buildFolderTree(folders) {
  const root = { name: "Workflow root", path: "", children: new Map() };
  for (const folder of folders || []) {
    if (!folder) continue;
    const parts = folder.split("/").filter(Boolean);
    let node = root;
    let current = "";
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      if (!node.children.has(part)) {
        node.children.set(part, { name: part, path: current, children: new Map() });
      }
      node = node.children.get(part);
    }
  }
  return root;
}

function renderFolderRows(parent, node, depth, selected) {
  const row = $el("button.xfm-folder-row" + (node.path === selected ? ".active" : ""), {
    type: "button",
    title: node.path || "Workflow root",
    onclick: () => {
      XFM.dialog.selectedFolder = node.path;
      renderShell(XFM.root);
    },
    parent,
  });
  row.style.paddingLeft = `${8 + depth * 14}px`;
  row.append(icon(node.path ? "pi-folder" : "pi-home"));
  row.append($el("span", { textContent: node.name }));
  [...node.children.values()]
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((child) => renderFolderRows(parent, child, depth + 1, selected));
}

function renderDialog(parent) {
  const backdrop = $el("div.xfm-modal-backdrop", { parent });
  const modal = $el("div.xfm-modal", { parent: backdrop });
  const title = $el("div.xfm-modal-title", { parent: modal });
  const close = () => {
    XFM.dialog = null;
    renderShell(XFM.root);
  };

  if (XFM.dialog.type === "info") {
    $el("div.xfm-title", { textContent: "XFlows paths", parent: title });
    title.append(iconButton("pi-times", "Close", close));
    $el("div.xfm-small-list", { parent: modal }, [
      $el("div", { textContent: `Workflow root: ${XFM.data?.workflow_root || ""}` }),
      $el("div", { textContent: `Metadata: ${XFM.data?.metadata_path || ""}` }),
    ]);
    return;
  }

  if (XFM.dialog.type === "tags") {
    const workflow = XFM.dialog.workflow;
    $el("div.xfm-title", { textContent: "Manage tags", parent: title });
    title.append(iconButton("pi-times", "Close", close));
    $el("div.xfm-subtle", { textContent: workflow.path, title: workflow.path, parent: modal });
    const tags = workflow.all_tags || [];
    const tagList = $el("div.xfm-tag-manager", { parent: modal });
    if (!tags.length) {
      $el("div.xfm-subtle", { textContent: "No tags yet.", parent: tagList });
    }
    for (const tag of tags) {
      const source = tagSource(workflow, tag);
      const chip = $el("div.xfm-tag-chip" + (source.includes("custom") ? ".manual" : ".auto"), {
        title: source,
        parent: tagList,
      });
      chip.append($el("span.xfm-tag-text", { textContent: tag }));
      chip.append($el("span.xfm-tag-source", { textContent: source }));
      chip.append(iconButton("pi-times", `Remove ${tag}`, () => removeTagFromDialog(tag), "xfm-tag-remove"));
    }
    const input = $el("input.xfm-input", {
      value: XFM.dialog.tag,
      placeholder: "Add custom tag",
      oninput: (event) => { XFM.dialog.tag = event.target.value; },
      onkeydown: (event) => {
        if (event.key === "Enter") addTagFromDialog();
        if (event.key === "Escape") close();
      },
      parent: modal,
    });
    const actions = $el("div.xfm-dialog-actions", { parent: modal });
    actions.append(
      makeButton({ label: "Done", onClick: close }),
      makeButton({ label: "Add custom tag", iconName: "pi-plus", className: "active", onClick: addTagFromDialog })
    );
    requestAnimationFrame(() => input.focus());
    return;
  }

  if (XFM.dialog.type === "move") {
    const workflow = XFM.dialog.workflow;
    $el("div.xfm-title", { textContent: "Move workflow", parent: title });
    title.append(iconButton("pi-times", "Close", close));
    $el("div.xfm-subtle", { textContent: workflow.path, title: workflow.path, parent: modal });
    const picker = $el("div.xfm-folder-picker", { parent: modal });
    renderFolderRows(picker, buildFolderTree(XFM.folders), 0, XFM.dialog.selectedFolder || "");
    const selected = XFM.dialog.selectedFolder || "(root)";
    $el("div.xfm-subtle", { textContent: `Destination: ${selected}`, parent: modal });
    const createRow = $el("div.xfm-toolbar", { parent: modal });
    const input = $el("input.xfm-input", {
      value: XFM.dialog.newFolder,
      placeholder: "New folder under selected destination",
      oninput: (event) => { XFM.dialog.newFolder = event.target.value; },
      onkeydown: (event) => {
        if (event.key === "Enter") createFolderFromDialog();
        if (event.key === "Escape") close();
      },
      parent: createRow,
    });
    createRow.append(makeButton({ label: "Create", iconName: "pi-plus", onClick: createFolderFromDialog }));
    const actions = $el("div.xfm-dialog-actions", { parent: modal });
    actions.append(
      makeButton({ label: "Cancel", onClick: close }),
      makeButton({
        label: "Move here",
        iconName: "pi-folder",
        className: "active",
        onClick: confirmMoveDialog,
      })
    );
    requestAnimationFrame(() => input.focus());
  }
}

function wrapPromptTracking() {
  if (api.__xflowsWrappedFetchApi) return;
  const originalFetchApi = api.fetchApi.bind(api);
  api.fetchApi = async function xflowsFetchApi(route, options = {}) {
    const response = await originalFetchApi(route, options);
    const routeText = String(route);
    const method = String(options?.method || "GET").toUpperCase();
    if (routeText === "/prompt" && method === "POST" && response.ok && XFM.activeWorkflow?.path) {
      queueMicrotask(async () => {
        try {
          const currentSnapshot = stableStringify(app.graph.serialize());
          await postJson(`${ROUTE}/run`, {
            path: XFM.activeWorkflow.path,
            content_hash: XFM.activeWorkflow.contentHash,
            modified: currentSnapshot !== XFM.loadedSnapshot,
          });
          await loadData(false);
        } catch (error) {
          console.warn("[XFlows] Failed to record workflow run", error);
        }
      });
    }
    if (method === "POST" && response.ok) {
      const savedWorkflowPath = workflowPathFromUserdataRoute(routeText);
      if (savedWorkflowPath) scheduleWorkflowRefresh(savedWorkflowPath);
    }
    return response;
  };
  api.__xflowsWrappedFetchApi = true;
}

function wrapGraphLoading() {
  if (app.__xflowsWrappedLoadGraphData) return;
  const originalLoadGraphData = app.loadGraphData.bind(app);
  app.loadGraphData = function xflowsLoadGraphData() {
    if (!XFM.loadingFromManager) {
      XFM.activeWorkflow = null;
      XFM.loadedSnapshot = null;
    }
    return originalLoadGraphData(...arguments);
  };
  app.__xflowsWrappedLoadGraphData = true;
}

function registerSidebar() {
  if (app.extensionManager?.registerSidebarTab) {
    app.extensionManager.registerSidebarTab({
      id: "xflowsManager",
      icon: "pi pi-folder-open",
      title: "XFlows",
      tooltip: "XFlows Manager",
      type: "custom",
      render: (element) => {
        renderShell(element);
        loadData(false);
      },
    });
    return true;
  }
  return false;
}

async function registerFallbackButton() {
  const panel = $el("div.xfm-shell.xfm-floating-panel", { style: { display: "none" }, parent: document.body });
  XFM.fallbackPanel = panel;
  renderShell(panel);
  const toggle = () => {
    if (!isXFlowsEnabled()) return;
    panel.style.display = panel.style.display === "none" ? "flex" : "none";
    if (panel.style.display !== "none") loadData(false);
  };
  try {
    const { ComfyButton } = await import("../../scripts/ui/components/button.js");
    const workflowButton = new ComfyButton({
      icon: "folder",
      action: toggle,
      tooltip: "XFlows Manager",
      content: "XFlows",
    });
    XFM.fallbackButton = workflowButton;
    app.menu?.settingsGroup?.append(workflowButton);
  } catch {
    const menu = document.querySelector(".comfy-menu") || document.body;
    XFM.fallbackButton = makeButton({ label: "XFlows", iconName: "pi-folder-open", onClick: toggle });
    menu.append(XFM.fallbackButton);
  }
  applyXFlowsVisibility();
}

app.registerExtension({
  name: "Comfy.XFlowsManager",
  init() {
    if (!document.getElementById("xflows-style")) {
      $el("style", { id: "xflows-style", textContent: style, parent: document.head });
    }
  },
  async setup() {
    registerXFlowsSetting();
    wrapGraphLoading();
    wrapPromptTracking();
    window.addEventListener("workflowx:imported", () => loadData(true));
    if (isXFlowsEnabled()) {
      const registered = registerSidebar();
      if (!registered) await registerFallbackButton();
      await loadData(false);
    }
    applyXFlowsVisibility();
  },
});
