import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { $el } from "../../scripts/ui.js";

const ROUTE = "/xflows";
const STORE_PREFIX = "xflows";
const WORKFLOWX_SETTING_PREFIX = "workflowx.setting";
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
  duplicateUi: null,
  showDuplicateDialog: false,
  dialog: null,
  manager: {
    open: false,
    tab: "workflows",
    query: "",
    folder: "",
    sort: localStorage.getItem(`${STORE_PREFIX}.managerSort`) || "name",
    selected: new Set(),
    expandedFolders: new Set([""]),
    move: null,
    tag: null,
    detail: null,
    message: "",
    newFolder: "",
    drag: null,
    scrollTop: 0,
    treeScrollTop: 0,
  },
  refreshTimers: new Map(),
  recentlyUpdated: new Map(),
  fallbackPanel: null,
  fallbackButton: null,
};

const DUPLICATE_TABS = [
  {
    key: "same_name_nodes",
    label: "Same name + nodes",
    title: "Same name + same nodes",
    reason: "Workflow names match and the node structure is the same.",
  },
  {
    key: "same_nodes_values",
    label: "Same nodes + values",
    title: "Same nodes + same values",
    reason: "Node structure and editable node values match, even if workflow names differ.",
  },
  {
    key: "same_nodes_changed_values",
    label: "Same nodes, changed values",
    title: "Same nodes + different values",
    reason: "Node structure matches, but editable node values differ. Review before cleanup.",
  },
];

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
.xfm-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
.xfm-btn:disabled:hover {
  border-color: var(--xfm-border);
  filter: none;
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
.xfm-duplicate-modal {
  align-content: start;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  max-height: min(760px, 94%);
  width: min(900px, 96%);
}
.xfm-duplicate-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.xfm-duplicate-body {
  border: 1px solid var(--xfm-border);
  border-radius: 9px;
  display: grid;
  gap: 8px;
  min-height: 0;
  overflow: auto;
  padding: 8px;
}
.xfm-duplicate-section {
  border: 1px solid color-mix(in srgb, var(--xfm-border) 78%, transparent);
  border-radius: 8px;
  display: grid;
  gap: 8px;
  padding: 8px;
}
.xfm-duplicate-section-title {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.xfm-duplicate-group {
  background: color-mix(in srgb, var(--xfm-panel-2) 70%, transparent);
  border: 1px solid var(--xfm-border);
  border-radius: 8px;
  display: grid;
  gap: 8px;
  padding: 8px;
}
.xfm-duplicate-group summary {
  align-items: center;
  cursor: pointer;
  display: flex;
  gap: 8px;
  list-style: none;
}
.xfm-duplicate-group summary::-webkit-details-marker { display: none; }
.xfm-duplicate-title {
  flex: 1;
  font-size: 12px;
  font-weight: 740;
  min-width: 0;
}
.xfm-signature {
  color: var(--xfm-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10px;
}
.xfm-duplicate-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.xfm-duplicate-workflow {
  background: color-mix(in srgb, var(--xfm-panel) 78%, transparent);
  border: 1px solid color-mix(in srgb, var(--xfm-border) 70%, transparent);
  border-radius: 8px;
  display: grid;
  gap: 6px;
  padding: 8px;
}
.xfm-duplicate-workflow.keep {
  border-color: color-mix(in srgb, var(--xfm-accent) 75%, #fff 10%);
  box-shadow: inset 3px 0 0 var(--xfm-accent);
}
.xfm-duplicate-row {
  align-items: start;
  display: grid;
  gap: 8px;
  grid-template-columns: auto minmax(0, 1fr) auto;
}
.xfm-duplicate-check {
  margin-top: 3px;
}
.xfm-preview-box {
  background: color-mix(in srgb, var(--xfm-panel-2) 80%, transparent);
  border: 1px solid var(--xfm-border);
  border-radius: 8px;
  display: grid;
  gap: 8px;
  max-height: 260px;
  overflow: auto;
  padding: 8px;
}
.xfm-preview-grid {
  display: grid;
  gap: 4px 10px;
  grid-template-columns: max-content minmax(0, 1fr);
}
.xfm-preview-grid dt {
  color: var(--xfm-muted);
  font-size: 10px;
  font-weight: 720;
}
.xfm-preview-grid dd {
  font-size: 11px;
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}
.xfm-confirm-box {
  background: color-mix(in srgb, var(--xfm-danger) 12%, var(--xfm-panel-2));
  border: 1px solid color-mix(in srgb, var(--xfm-danger) 50%, var(--xfm-border));
  border-radius: 8px;
  display: grid;
  gap: 7px;
  padding: 8px;
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
.xfm-duplicate-overlay {
  z-index: 60;
}
.xfm-duplicate-floating {
  width: min(720px, 96%);
}
.xfm-duplicate-floating .xfm-preview-box {
  max-height: min(520px, 70vh);
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
.xfm-folder-row.drop-target {
  background: color-mix(in srgb, var(--xfm-accent) 22%, transparent);
  border-color: var(--xfm-accent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--xfm-accent) 55%, transparent);
}
.xfm-dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.xfm-folder-toggle {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 5px;
  color: var(--xfm-muted);
  cursor: pointer;
  display: inline-flex;
  height: 24px;
  justify-content: center;
  padding: 0;
  width: 24px;
}
.xfm-folder-toggle:hover { background: color-mix(in srgb, var(--xfm-accent) 16%, transparent); color: var(--fg-color); }
.xfm-folder-label {
  align-items: center;
  background: transparent;
  border: 0;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  flex: 1;
  font: inherit;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
  padding: 0;
  text-align: left;
}
.xfm-folder-label span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.xfm-manager-backdrop {
  align-items: center;
  background: rgba(8, 10, 12, .62);
  display: flex;
  inset: 0;
  justify-content: center;
  padding: 24px;
  position: fixed;
  z-index: 10000;
}
.xfm-manager {
  --xfm-bg: color-mix(in srgb, var(--comfy-menu-bg, #181a20) 94%, #0f766e 6%);
  --xfm-panel: color-mix(in srgb, var(--comfy-menu-bg, #181a20) 84%, #ffffff 7%);
  --xfm-panel-2: color-mix(in srgb, var(--comfy-input-bg, #101217) 88%, #14b8a6 6%);
  --xfm-border: color-mix(in srgb, var(--border-color, #3c3f45) 78%, #14b8a6 22%);
  --xfm-accent: #14b8a6;
  --xfm-warn: #f59e0b;
  --xfm-danger: #ef4444;
  --xfm-muted: color-mix(in srgb, var(--fg-color, #e7e9ee) 64%, transparent);
  background: var(--xfm-bg);
  border: 1px solid var(--xfm-border);
  border-radius: 8px;
  box-shadow: 0 24px 80px rgba(0,0,0,.58);
  color: var(--fg-color);
  display: grid;
  font: 13px Inter, ui-sans-serif, system-ui, sans-serif;
  grid-template-rows: auto auto 1fr;
  height: min(820px, calc(100vh - 48px));
  overflow: hidden;
  width: min(1220px, calc(100vw - 48px));
}
.xfm-manager-top {
  align-items: center;
  background: color-mix(in srgb, var(--xfm-panel) 88%, #000 12%);
  border-bottom: 1px solid var(--xfm-border);
  display: grid;
  gap: 10px;
  grid-template-columns: minmax(0, 1fr) auto;
  padding: 10px 12px;
}
.xfm-manager-title {
  font-size: 16px;
  font-weight: 760;
  min-width: 0;
}
.xfm-manager-subtitle {
  color: var(--xfm-muted);
  font-size: 11px;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.xfm-manager-tabs, .xfm-manager-tools, .xfm-manager-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.xfm-toolbar-spacer {
  flex: 1 1 auto;
  min-width: 12px;
}
.xfm-manager-tools {
  background: color-mix(in srgb, var(--xfm-bg) 88%, #000 12%);
  border-bottom: 1px solid var(--xfm-border);
  padding: 9px 12px;
}
.xfm-manager-search {
  background: var(--xfm-panel-2);
  border: 1px solid var(--xfm-border);
  border-radius: 6px;
  color: var(--fg-color);
  flex: 1;
  font-size: 14px;
  height: 32px;
  min-width: 220px;
  outline: none;
  padding: 0 10px;
}
.xfm-manager-select {
  background: var(--xfm-panel-2);
  border: 1px solid var(--xfm-border);
  border-radius: 6px;
  color: var(--fg-color);
  height: 32px;
  padding: 0 8px;
}
.xfm-manager-body {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: 0;
}
.xfm-manager-tree {
  background: color-mix(in srgb, var(--xfm-bg) 92%, #000 8%);
  border-right: 1px solid var(--xfm-border);
  min-height: 0;
  overflow: auto;
  padding: 8px;
}
.xfm-manager-tree-create {
  border-bottom: 1px solid var(--xfm-border);
  display: grid;
  gap: 6px;
  margin: -2px -2px 8px;
  padding: 2px 2px 9px;
}
.xfm-manager-tree-create-row {
  align-items: center;
  display: grid;
  gap: 6px;
  grid-template-columns: minmax(0, 1fr) auto;
}
.xfm-manager-tree-create .xfm-input {
  min-height: 30px;
  padding: 5px 8px;
}
.xfm-manager-tree-create .xfm-btn {
  min-height: 30px;
}
.xfm-manager-main {
  background: color-mix(in srgb, var(--xfm-bg) 84%, #000 16%);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 0;
}
.xfm-manager-list {
  align-content: start;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  min-height: 0;
  overflow: auto;
  padding: 10px;
}
.xfm-manager-card {
  color: inherit;
  overflow: visible;
}
.xfm-manager-card[draggable="true"] {
  cursor: grab;
}
.xfm-manager-card[draggable="true"]:active {
  cursor: grabbing;
}
.xfm-manager-card.dragging {
  opacity: 0.62;
  outline: 1px dashed color-mix(in srgb, var(--xfm-accent) 65%, transparent);
}
.xfm-manager-card.selected {
  border-color: #6f8fd4;
  box-shadow: inset 3px 0 0 #6f8fd4;
}
.xfm-manager-card .xfm-card-main {
  justify-content: flex-start;
}
.xfm-manager-card .xfm-card-main > div {
  flex: 1 1 auto;
  min-width: 0;
}
.xfm-manager-check { margin-top: 3px; }
.xfm-manager-batch {
  align-items: center;
  background: color-mix(in srgb, var(--xfm-panel) 88%, #000 12%);
  border-bottom: 1px solid var(--xfm-border);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 38px;
  padding: 7px 10px;
}
.xfm-manager-detail {
  border-top: 1px solid var(--xfm-border);
  display: grid;
  gap: 8px;
  padding: 10px;
}
.xfm-manager-popover {
  background: var(--xfm-panel);
  border-top: 1px solid var(--xfm-border);
  box-shadow: 0 -14px 34px rgba(0,0,0,.28);
  display: grid;
  gap: 8px;
  padding: 10px 12px;
}
.xfm-manager-duplicates {
  display: grid;
  gap: 8px;
  min-height: 0;
  overflow: auto;
  padding: 10px;
}
@media (max-width: 760px) {
  .xfm-manager-backdrop { padding: 10px; }
  .xfm-manager { height: calc(100vh - 20px); width: calc(100vw - 20px); }
  .xfm-manager-body { grid-template-columns: 1fr; }
  .xfm-manager-tree { border-bottom: 1px solid var(--xfm-border); border-right: 0; max-height: 190px; }
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

function renderSurfaces(options = {}) {
  if (XFM.root) renderShell(XFM.root, options);
  if (XFM.manager.open) renderManagerModal();
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

function formatDateTime(ms) {
  if (!ms) return "never";
  try {
    return new Date(ms).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return "unknown";
  }
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let current = value;
  let index = 0;
  while (current >= 1024 && index < units.length - 1) {
    current /= 1024;
    index += 1;
  }
  return `${current >= 10 || index === 0 ? current.toFixed(0) : current.toFixed(1)} ${units[index]}`;
}

function shortHash(value) {
  const text = String(value || "");
  return text ? text.slice(0, 12) : "none";
}

function icon(name) {
  return $el("i", { className: `pi ${name}` });
}

function makeButton({ label, iconName, className = "", onClick, title, pressed = false, disabled = false }) {
  const element = $el("button.xfm-btn", {
    type: "button",
    onclick: disabled ? undefined : onClick,
    title: title || label || "",
    "aria-label": title || label || "",
    "aria-pressed": pressed ? "true" : "false",
    disabled,
  });
  for (const name of className.split(/\s+/).filter(Boolean)) element.classList.add(name);
  if (iconName) element.append(icon(iconName));
  if (label) element.append($el("span", { textContent: label }));
  return element;
}

function iconButton(iconName, title, onClick, className = "") {
  return makeButton({ iconName, title, onClick, className: `xfm-icon-btn ${className}` });
}

function containComfyKeys(event) {
  event.stopPropagation();
}

function protectField(element) {
  if (!element) return element;
  for (const eventName of ["keydown", "keypress", "keyup", "beforeinput", "input", "compositionstart", "compositionupdate", "compositionend", "paste", "cut"]) {
    element.addEventListener(eventName, containComfyKeys);
  }
  return element;
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
  renderSurfaces();
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
  if (XFM.manager.detail?.path === workflow.path) {
    XFM.manager.detail = workflow;
  }
}

function searchTerms(query) {
  return String(query || "")
    .toLowerCase()
    .split(/\s+/)
    .map((term) => term.trim())
    .filter(Boolean);
}

function workflowSearchText(workflow) {
  return [
    workflow.name,
    workflow.file_name,
    workflow.path,
    workflow.folder,
    ...(workflow.all_tags || []),
    ...(workflow.manual_tags || []),
    ...(workflow.auto_tags || []),
    ...(workflow.node_types || []),
    ...(workflow.detected_models || []).flatMap((model) => [
      model.folder,
      model.name,
      model.filename,
      model.relative,
      `${model.folder} ${model.name}`,
      `${model.folder}/${model.name}`,
    ]),
  ].filter(Boolean).join("\n").toLowerCase();
}

function workflowMatchesQuery(workflow, query) {
  const terms = searchTerms(query);
  if (!terms.length) return true;
  const haystack = workflowSearchText(workflow);
  return terms.every((term) => haystack.includes(term));
}

function filteredWorkflows() {
  let items = XFM.workflows.filter((workflow) => {
    if (XFM.favoritesOnly && !workflow.favorite) return false;
    return workflowMatchesQuery(workflow, XFM.query);
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
    makeButton({ label: "Manager", iconName: "pi-window-maximize", className: "active", onClick: openManager }),
    iconButton("pi-sync", "Sync workflows", () => loadData(true)),
    iconButton("pi-clone", "Find duplicates", () => findDuplicates({ openDialog: true }))
  );

  const searchWrap = $el("div.xfm-search-wrap", { parent: header });
  searchWrap.append(icon("pi-search"));
  const search = protectField($el("input.xfm-input", {
    type: "search",
    placeholder: "Search XFlows...",
    value: XFM.query,
    oninput: (event) => {
      const preserveSearchFocus = {
        start: event.target.selectionStart,
        end: event.target.selectionEnd,
      };
      XFM.query = event.target.value;
      renderSurfaces({ preserveSearchFocus });
    },
    parent: searchWrap,
  }));

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
  const sort = protectField($el("select.xfm-select", {
    value: XFM.sort,
    onchange: (event) => {
      XFM.sort = event.target.value;
      localStorage.setItem(`${STORE_PREFIX}.sort`, XFM.sort);
      renderSurfaces();
    },
    parent: sortField,
  }, [
    $el("option", { value: "name", textContent: "Name" }),
    $el("option", { value: "newest", textContent: "Newest" }),
    $el("option", { value: "most_used", textContent: "Most used" }),
    $el("option", { value: "last_used", textContent: "Last used" }),
  ]));
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
      renderSurfaces();
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

  if (XFM.duplicateResult && XFM.showDuplicateDialog) renderDuplicates(target);
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
  renderSurfaces();
}

function setFavoritesOnly(value) {
  XFM.favoritesOnly = value;
  localStorage.setItem(`${STORE_PREFIX}.favoritesOnly`, value ? "true" : "false");
  renderSurfaces();
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
  renderSurfaces({ preserveScroll: true });
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

function workflowMatchesFolder(workflow, folder) {
  if (!folder) return true;
  return workflow.folder === folder || workflow.folder?.startsWith(`${folder}/`);
}

function sortWorkflows(items, sortMode) {
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (sortMode === "newest") return (b.mtime || 0) - (a.mtime || 0) || a.path.localeCompare(b.path);
    if (sortMode === "most_used") return (b.run_count || 0) - (a.run_count || 0) || a.path.localeCompare(b.path);
    if (sortMode === "last_used") return (b.last_run_at || 0) - (a.last_run_at || 0) || a.path.localeCompare(b.path);
    return a.name.localeCompare(b.name) || a.path.localeCompare(b.path);
  });
  return sorted;
}

function managerWorkflows() {
  return sortWorkflows(
    XFM.workflows
      .filter((workflow) => workflowMatchesFolder(workflow, XFM.manager.folder))
      .filter((workflow) => workflowMatchesQuery(workflow, XFM.manager.query)),
    XFM.manager.sort
  );
}

function managerSelectedPaths() {
  const available = new Set(XFM.workflows.map((workflow) => workflow.path));
  return [...XFM.manager.selected].filter((path) => available.has(path));
}

function managerDragPathsForWorkflow(workflow) {
  const selected = managerSelectedPaths();
  if (XFM.manager.selected.has(workflow.path) && selected.length) return selected;
  return workflow?.path ? [workflow.path] : [];
}

function managerDragPathsFromEvent(event) {
  const raw = event?.dataTransfer?.getData?.("application/x-xflows-workflows");
  if (raw) {
    try {
      const payload = JSON.parse(raw);
      if (Array.isArray(payload?.paths)) return payload.paths.filter(Boolean);
    } catch (_error) {
      // Fall back to in-memory drag state below.
    }
  }
  return Array.isArray(XFM.manager.drag?.paths) ? XFM.manager.drag.paths : [];
}

function startManagerCardDrag(workflow, event) {
  if (event?.target?.closest?.("button,input,select,textarea,a")) {
    event.preventDefault();
    return;
  }
  const paths = managerDragPathsForWorkflow(workflow);
  if (!paths.length) {
    event.preventDefault();
    return;
  }
  XFM.manager.drag = { paths, sourcePath: workflow.path };
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("application/x-xflows-workflows", JSON.stringify({ paths }));
  event.dataTransfer.setData("text/plain", paths.join("\n"));
  event.currentTarget?.classList?.add("dragging");
}

function endManagerCardDrag(event) {
  event?.currentTarget?.classList?.remove("dragging");
  XFM.manager.drag = null;
}

async function moveManagerDraggedPaths(paths, folder) {
  const uniquePaths = [...new Set(paths)].filter(Boolean);
  const targetFolder = folder || "";
  const movablePaths = uniquePaths.filter((path) => {
    const workflow = XFM.workflows.find((item) => item.path === path);
    return workflow && (workflow.folder || "") !== targetFolder;
  });
  if (!movablePaths.length) {
    XFM.manager.drag = null;
    XFM.manager.message = "Already in that folder.";
    renderManagerModal();
    return;
  }
  XFM.manager.drag = null;
  XFM.manager.message = `Moving ${movablePaths.length} workflow(s)...`;
  renderManagerModal();
  try {
    const data = movablePaths.length === 1
      ? await postJson(`${ROUTE}/move`, { path: movablePaths[0], folder: targetFolder })
      : await postJson(`${ROUTE}/move-batch`, { paths: movablePaths, folder: targetFolder });
    const results = data.results || [data];
    for (const result of results) {
      if (result.ok) XFM.manager.selected.delete(result.old_path);
    }
    XFM.manager.message = data.failed_count
      ? `Moved ${data.moved_count || results.filter((result) => result.ok).length} workflow(s). ${data.failed_count} failed.`
      : `Moved ${data.moved_count || results.filter((result) => result.ok).length} workflow(s).`;
    await refreshAfterMove(data);
  } catch (error) {
    XFM.manager.message = `Drop move failed: ${error.message}`;
    renderManagerModal();
  }
}

function openManager() {
  XFM.manager.open = true;
  XFM.manager.tab = XFM.manager.tab || "workflows";
  if (!XFM.manager.expandedFolders.size) XFM.manager.expandedFolders.add("");
  renderManagerModal();
}

function closeManager() {
  XFM.manager.open = false;
  XFM.manager.move = null;
  XFM.manager.tag = null;
  XFM.manager.detail = null;
  document.getElementById("xflows-manager-modal")?.remove();
}

function setManagerTab(tab) {
  XFM.manager.tab = tab;
  XFM.manager.detail = null;
  XFM.manager.message = "";
  renderManagerModal();
}

function setManagerSelected(path, checked) {
  if (checked) XFM.manager.selected.add(path);
  else XFM.manager.selected.delete(path);
  renderManagerModal();
}

function selectManagerVisible(checked) {
  for (const workflow of managerWorkflows()) {
    if (checked) XFM.manager.selected.add(workflow.path);
    else XFM.manager.selected.delete(workflow.path);
  }
  renderManagerModal();
}

function openManagerMove(paths, title = "Move workflow") {
  const first = paths.length === 1 ? XFM.workflows.find((workflow) => workflow.path === paths[0]) : null;
  const selectedFolder = first?.folder || XFM.manager.folder || "";
  XFM.manager.move = {
    title,
    paths: [...new Set(paths)].filter(Boolean),
    selectedFolder,
    newFolder: "",
    expandedFolders: folderAncestors(selectedFolder),
    pickerScroll: 0,
  };
  renderManagerModal();
}

function openManagerTag(workflow) {
  XFM.manager.tag = { path: workflow.path, tag: "" };
  XFM.manager.move = null;
  renderManagerModal();
}

function managerTagWorkflow() {
  return XFM.workflows.find((workflow) => workflow.path === XFM.manager.tag?.path) || null;
}

async function addManagerTag() {
  const workflow = managerTagWorkflow();
  const tag = XFM.manager.tag?.tag?.trim();
  if (!workflow || !tag) return;
  try {
    const data = await postJson(`${ROUTE}/tags`, { path: workflow.path, add: [tag] });
    applyTagResponse(data);
    XFM.manager.tag.tag = "";
    XFM.manager.message = "";
    renderManagerModal({ preserveTagFocus: true });
  } catch (error) {
    XFM.manager.message = `Add tag failed: ${error.message}`;
    renderManagerModal();
  }
}

async function removeManagerTag(tag) {
  const workflow = managerTagWorkflow();
  if (!workflow || !tag) return;
  try {
    const data = await postJson(`${ROUTE}/tags`, { path: workflow.path, remove: [tag] });
    applyTagResponse(data);
    XFM.manager.message = "";
    renderManagerModal();
  } catch (error) {
    XFM.manager.message = `Remove tag failed: ${error.message}`;
    renderManagerModal();
  }
}

async function refreshAfterMove(data) {
  const results = data?.results || [data];
  const activePath = XFM.activeWorkflow?.path;
  const activeMove = results.find((result) => result?.ok && result.old_path === activePath);
  await loadData(true);
  if (activeMove?.path) {
    const workflow = XFM.workflows.find((item) => item.path === activeMove.path) || activeMove.workflow;
    if (workflow) await useWorkflow(workflow);
  }
}

async function confirmManagerMove() {
  const move = XFM.manager.move;
  if (!move?.paths?.length) return;
  try {
    const folder = move.selectedFolder || "";
    const data = move.paths.length === 1
      ? await postJson(`${ROUTE}/move`, { path: move.paths[0], folder })
      : await postJson(`${ROUTE}/move-batch`, { paths: move.paths, folder });
    const results = data.results || [data];
    for (const result of results) {
      if (result.ok) XFM.manager.selected.delete(result.old_path);
    }
    XFM.manager.move = null;
    XFM.manager.message = data.failed_count
      ? `Moved ${data.moved_count || results.filter((result) => result.ok).length} workflow(s). ${data.failed_count} failed.`
      : `Moved ${data.moved_count || results.filter((result) => result.ok).length} workflow(s).`;
    await refreshAfterMove(data);
  } catch (error) {
    XFM.manager.message = `Move failed: ${error.message}`;
    renderManagerModal();
  }
}

async function deleteManagerPaths(paths) {
  const filtered = [...new Set(paths)].filter(Boolean);
  if (!filtered.length) return;
  if (!confirm(`Move ${filtered.length} workflow(s) to XFlows trash?`)) return;
  try {
    const result = await postJson(`${ROUTE}/delete-batch`, { paths: filtered });
    for (const path of filtered) XFM.manager.selected.delete(path);
    XFM.manager.detail = null;
    XFM.manager.message = result.failed_count
      ? `Moved ${result.deleted_count} workflow(s) to trash. ${result.failed_count} failed.`
      : `Moved ${result.deleted_count} workflow(s) to XFlows trash.`;
    await loadData(true);
    if (XFM.duplicateResult) XFM.duplicateResult = await postJson(`${ROUTE}/duplicates`);
    renderManagerModal();
  } catch (error) {
    XFM.manager.message = `Delete failed: ${error.message}`;
    renderManagerModal();
  }
}

function renderManagerModal(options = {}) {
  document.getElementById("xflows-manager-modal")?.remove();
  if (!XFM.manager.open) return;

  const backdrop = $el("div.xfm-manager-backdrop", { id: "xflows-manager-modal", parent: document.body });
  const modal = $el("div.xfm-manager", { parent: backdrop });
  backdrop.addEventListener("mousedown", (event) => {
    if (event.target === backdrop) closeManager();
  });

  const top = $el("div.xfm-manager-top", { parent: modal });
  const titleWrap = $el("div", { parent: top });
  $el("div.xfm-manager-title", { textContent: "XFlows Manager", parent: titleWrap });
  $el("div.xfm-manager-subtitle", { textContent: XFM.data?.workflow_root || "Workflow root", parent: titleWrap });
  const topActions = $el("div.xfm-manager-actions", { parent: top });
  topActions.append(
    makeButton({ label: "Sync", iconName: "pi-sync", onClick: () => loadData(true) }),
    iconButton("pi-times", "Close manager", closeManager)
  );

  const tools = $el("div.xfm-manager-tools", { parent: modal });
  const tabs = $el("div.xfm-manager-tabs", { parent: tools });
  tabs.append(
    makeButton({ label: "Workflows", iconName: "pi-folder-open", className: XFM.manager.tab === "workflows" ? "active" : "", pressed: XFM.manager.tab === "workflows", onClick: () => setManagerTab("workflows") }),
    makeButton({ label: "Duplicates", iconName: "pi-clone", className: XFM.manager.tab === "duplicates" ? "active" : "", pressed: XFM.manager.tab === "duplicates", onClick: () => setManagerTab("duplicates") })
  );
  const search = protectField($el("input.xfm-manager-search", {
    type: "search",
    placeholder: "Search name, path, tag, node, model",
    value: XFM.manager.query,
    oninput: (event) => {
      const preserveSearchFocus = {
        start: event.target.selectionStart,
        end: event.target.selectionEnd,
      };
      XFM.manager.query = event.target.value;
      renderManagerModal({ preserveSearchFocus });
    },
    parent: tools,
  }));
  const sort = protectField($el("select.xfm-manager-select", {
    value: XFM.manager.sort,
    onchange: (event) => {
      XFM.manager.sort = event.target.value;
      localStorage.setItem(`${STORE_PREFIX}.managerSort`, XFM.manager.sort);
      renderManagerModal();
    },
    parent: tools,
  }, [
    $el("option", { value: "name", textContent: "Name" }),
    $el("option", { value: "newest", textContent: "Newest" }),
    $el("option", { value: "most_used", textContent: "Most used" }),
    $el("option", { value: "last_used", textContent: "Last used" }),
  ]));
  sort.value = XFM.manager.sort;

  const body = $el("div.xfm-manager-body", { parent: modal });
  if (XFM.manager.tab === "duplicates") renderManagerDuplicateTab(body);
  else renderManagerWorkflowTab(body);
  if (XFM.manager.move) renderManagerMoveDialog(modal);
  if (XFM.manager.tag) renderManagerTagDialog(modal);
  if (XFM.manager.tab === "duplicates") renderDuplicateOverlays(backdrop);

  requestAnimationFrame(() => {
    if (XFM.manager.tab === "workflows") {
      const tree = modal.querySelector(".xfm-manager-tree");
      const list = modal.querySelector(".xfm-manager-list");
      if (tree) tree.scrollTop = XFM.manager.treeScrollTop || 0;
      if (list) list.scrollTop = XFM.manager.scrollTop || 0;
    }
    if (options.preserveSearchFocus) {
      search.focus({ preventScroll: true });
      const { start, end } = options.preserveSearchFocus;
      if (Number.isInteger(start) && Number.isInteger(end)) {
        try {
          search.setSelectionRange(start, end);
        } catch {
        }
      }
      return;
    }
  });
}

function renderManagerWorkflowTab(body) {
  const tree = $el("div.xfm-manager-tree", {
    parent: body,
    onscroll: (event) => {
      XFM.manager.treeScrollTop = event.currentTarget.scrollTop;
    },
  });
  renderManagerTreeCreate(tree);
  renderManagerFolderTree(tree, buildFolderTree(XFM.folders));

  const main = $el("div.xfm-manager-main", { parent: body });
  const visible = managerWorkflows();
  const selected = managerSelectedPaths();
  const batch = $el("div.xfm-manager-batch", { parent: main });
  const visibleSelected = visible.length > 0 && visible.every((workflow) => XFM.manager.selected.has(workflow.path));
  const selectAll = protectField($el("input.xfm-manager-check", {
    type: "checkbox",
    title: "Select visible workflows",
    onchange: (event) => selectManagerVisible(event.target.checked),
    parent: batch,
  }));
  selectAll.checked = visibleSelected;
  batch.append(
    $el("div.xfm-subtle", { textContent: `${selected.length} selected | ${visible.length}/${XFM.workflows.length} shown` }),
    makeButton({ label: "Move selected", iconName: "pi-folder", onClick: () => openManagerMove(selected, "Move selected workflows") }),
    makeButton({ label: "Delete selected", iconName: "pi-trash", className: "xfm-danger", onClick: () => deleteManagerPaths(selected) }),
    makeButton({ label: "Clear", onClick: () => { XFM.manager.selected.clear(); renderManagerModal(); } })
  );
  if (XFM.manager.message) $el("div.xfm-subtle", { textContent: XFM.manager.message, parent: batch });

  const list = $el("div.xfm-manager-list", {
    parent: main,
    onscroll: (event) => {
      XFM.manager.scrollTop = event.currentTarget.scrollTop;
    },
  });
  if (!visible.length) {
    $el("div.xfm-empty", { textContent: "No workflows match the current filters.", parent: list });
  } else {
    for (const workflow of visible) list.append(renderManagerWorkflowCard(workflow));
  }
  if (XFM.manager.detail) renderManagerDetail(main, XFM.manager.detail);
}

function renderManagerWorkflowCard(workflow) {
  const selected = XFM.manager.selected.has(workflow.path);
  return renderCard(workflow, {
    context: "manager",
    selected,
    onSelect: (checked) => setManagerSelected(workflow.path, checked),
    onManageTags: openManagerTag,
    onDetails: () => {
      XFM.manager.detail = workflow;
      renderManagerModal();
    },
    onMove: () => openManagerMove([workflow.path]),
    onDelete: () => deleteManagerPaths([workflow.path]),
    draggable: true,
    onDragStart: (event) => startManagerCardDrag(workflow, event),
    onDragEnd: endManagerCardDrag,
  });
}

function renderManagerDetail(parent, workflow) {
  const box = $el("div.xfm-manager-detail", { parent });
  const title = $el("div.xfm-title-row", { parent: box });
  $el("div.xfm-title", { textContent: "Workflow details", parent: title });
  title.append(iconButton("pi-times", "Close details", () => { XFM.manager.detail = null; renderManagerModal(); }));
  const grid = $el("dl.xfm-preview-grid", { parent: box });
  const addRow = (label, value) => {
    grid.append($el("dt", { textContent: label }), $el("dd", { textContent: value || "none" }));
  };
  addRow("Path", workflow.path);
  addRow("Folder", workflow.folder || "(root)");
  addRow("Runs", `${workflow.run_count || 0}`);
  addRow("Last run", formatDateTime(workflow.last_run_at));
  addRow("Modified", formatDateTime(workflow.mtime));
  addRow("Size", formatBytes(workflow.size));
  addRow("Content hash", shortHash(workflow.content_hash));
  addRow("Graph hash", shortHash(workflow.canonical_hash));
  addRow("Models", (workflow.detected_models || []).map((model) => `${model.folder}/${model.name}`).slice(0, 10).join(", "));
  addRow("Tags", (workflow.all_tags || workflow.auto_tags || []).join(", "));
}

function renderManagerDuplicateTab(body) {
  const main = $el("div.xfm-manager-main", { parent: body });
  main.style.gridColumn = "1 / -1";
  const batch = $el("div.xfm-manager-batch", { parent: main });
  const selected = XFM.duplicateResult ? duplicateSelectedPaths() : [];
  batch.append(
    makeButton({ label: XFM.duplicateResult ? "Rescan duplicates" : "Scan duplicates", iconName: "pi-sync", onClick: () => findDuplicates({ openDialog: false }) }),
    $el("div.xfm-subtle", { textContent: "Duplicate finder compares workflow names, node structure, and node values." }),
    $el("div.xfm-toolbar-spacer"),
    $el("div.xfm-subtle", { textContent: `${selected.length} selected for soft delete` }),
    makeButton({
      label: "Delete selected",
      iconName: "pi-trash",
      className: "xfm-danger",
      disabled: !selected.length,
      onClick: () => openDuplicateDeleteConfirm(selected),
    })
  );
  const wrap = $el("div.xfm-manager-duplicates", { parent: main });
  if (!XFM.duplicateResult) {
    $el("div.xfm-empty", { textContent: "Scan duplicates to review and clean repeated workflows.", parent: wrap });
    return;
  }
  renderManagerDuplicateGroups(wrap);
}

function renderManagerDuplicateGroups(parent) {
  const ui = duplicateUi();
  if (ui.message) $el("div.xfm-subtle", { textContent: ui.message, parent });
  for (const section of DUPLICATE_TABS) {
    const box = $el("section.xfm-duplicate-section", { parent });
    const heading = $el("div.xfm-duplicate-section-title", { parent: box });
    $el("div.xfm-duplicate-title", { textContent: `${section.title} (${duplicateGroups(section.key).length})`, parent: heading });
    $el("div.xfm-subtle", { textContent: section.reason, parent: box });
    const groups = duplicateGroups(section.key);
    if (!groups.length) {
      $el("div.xfm-empty", { textContent: `No ${section.title.toLowerCase()} found.`, parent: box });
      continue;
    }
    groups.forEach((group, index) => renderManagerDuplicateGroup(box, section, group, index));
  }
}

function renderManagerDuplicateGroup(parent, activeTab, group, index) {
  const ui = duplicateUi();
  const groupKey = duplicateGroupKey(activeTab.key, group, index);
  const keeper = ui.keepers[groupKey] || chooseWorkflowToKeep(group, "most_used")?.path || group.workflows?.[0]?.path;
  const details = $el("details.xfm-duplicate-group", {
    ontoggle: (event) => toggleDuplicateGroup(activeTab.key, group, index, event.currentTarget.open),
    parent,
  });
  details.open = !ui.collapsed.has(groupKey);
  const summaryRow = $el("summary", { parent: details });
  summaryRow.append(icon(details.open ? "pi-angle-down" : "pi-angle-right"));
  summaryRow.append($el("div.xfm-duplicate-title", { textContent: `${activeTab.title}: ${group.count} workflows` }));
  summaryRow.append($el("span.xfm-signature", { textContent: shortHash(group.signature) }));
  const metaText = duplicateGroupMeta(group);
  if (metaText) $el("div.xfm-subtle", { textContent: metaText, title: metaText, parent: details });
  const actions = $el("div.xfm-duplicate-actions", { parent: details });
  actions.append(
    makeButton({ label: "Keep newest", iconName: "pi-calendar", onClick: () => {
      const pick = chooseWorkflowToKeep(group, "newest");
      if (pick) markDuplicateKeeper(activeTab.key, group, index, pick.path);
    } }),
    makeButton({ label: "Keep most used", iconName: "pi-chart-bar", onClick: () => {
      const pick = chooseWorkflowToKeep(group, "most_used");
      if (pick) markDuplicateKeeper(activeTab.key, group, index, pick.path);
    } }),
    makeButton({ label: "Delete selected", iconName: "pi-trash", className: "xfm-danger", onClick: () => openDuplicateDeleteConfirm((group.workflows || []).map((item) => item.path).filter((path) => ui.selected.has(path))) })
  );
  for (const workflow of group.workflows || []) renderManagerDuplicateWorkflow(details, activeTab, group, index, workflow, keeper);
}

function renderManagerDuplicateWorkflow(parent, activeTab, group, index, workflow, keeper) {
  const ui = duplicateUi();
  const isKeeper = keeper === workflow.path;
  const card = $el("div.xfm-duplicate-workflow" + (isKeeper ? ".keep" : ""), { parent });
  const line = $el("div.xfm-duplicate-row", { parent: card });
  const checkbox = protectField($el("input.xfm-duplicate-check", {
    type: "checkbox",
    title: "Select for soft delete",
    onchange: (event) => setDuplicateChecked(workflow.path, event.target.checked),
    parent: line,
  }));
  checkbox.checked = ui.selected.has(workflow.path);
  const itemMain = $el("div", { parent: line });
  $el("div.xfm-name", { textContent: workflow.name || workflow.path, parent: itemMain });
  $el("div.xfm-path", { textContent: workflow.path, title: workflow.path, parent: itemMain });
  const meta = $el("div.xfm-meta", { parent: itemMain });
  meta.append($el("span", { textContent: `${workflow.run_count || 0} runs` }), $el("span", { textContent: formatBytes(workflow.size) }));
  const itemActions = $el("div.xfm-duplicate-actions", { parent: line });
  itemActions.append(
    makeButton({ label: "Preview", iconName: "pi-eye", onClick: () => previewDuplicateWorkflow(workflow) }),
    makeButton({ label: "Use", iconName: "pi-play", onClick: () => useWorkflow(workflow) }),
    makeButton({ label: isKeeper ? "Keeper" : "Keep this", iconName: "pi-check", className: isKeeper ? "active" : "", onClick: () => markDuplicateKeeper(activeTab.key, group, index, workflow.path) })
  );
}

function renderCard(workflow, options = {}) {
  const context = options.context || "panel";
  const isManager = context === "manager";
  const updatedAt = XFM.recentlyUpdated.get(workflow.path) || 0;
  const recentlyUpdated = Date.now() - updatedAt < 6000;
  const card = $el(
    "div.xfm-card" +
    (isManager ? ".xfm-manager-card" : "") +
    (recentlyUpdated ? ".updated" : "") +
    (options.selected ? ".selected" : "")
  );
  if (isManager && options.draggable) {
    card.draggable = true;
    card.addEventListener("dragstart", options.onDragStart);
    card.addEventListener("dragend", options.onDragEnd);
  }
  const main = $el("div.xfm-card-main", { parent: card });
  if (isManager) {
    const checkbox = protectField($el("input.xfm-manager-check", {
      type: "checkbox",
      title: "Select workflow",
      onchange: (event) => options.onSelect?.(event.target.checked),
      parent: main,
    }));
    checkbox.checked = !!options.selected;
  }
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
        renderSurfaces({ preserveScroll: true });
      },
    }));
  }
  tagRow.append(makeButton({
    label: "Manage tags",
    iconName: "pi-tags",
    title: "Manage tags",
    onClick: () => (options.onManageTags || openTagDialog)(workflow),
  }));

  const actionKey = isManager ? `${context}:${workflow.path}` : workflow.path;
  const actions = $el("div.xfm-card-actions", { parent: card });
  actions.append(
    makeButton({ label: "Use", iconName: "pi-play", className: "active", onClick: () => useWorkflow(workflow) }),
    iconButton("pi-ellipsis-v", "More actions", () => {
      if (XFM.expandedActions.has(actionKey)) XFM.expandedActions.delete(actionKey);
      else XFM.expandedActions.add(actionKey);
      renderSurfaces({ preserveScroll: true });
    })
  );

  if (XFM.expandedActions.has(actionKey)) {
    const more = $el("div.xfm-card-actions", { parent: card });
    if (isManager) {
      more.append(
        makeButton({ label: "Details", iconName: "pi-eye", onClick: options.onDetails }),
        makeButton({ label: "Move", iconName: "pi-folder", onClick: options.onMove }),
        makeButton({ label: "Delete", iconName: "pi-trash", className: "xfm-danger", onClick: options.onDelete })
      );
    } else {
      more.append(
        makeButton({ label: "Move", iconName: "pi-folder", onClick: () => openMoveDialog(workflow) }),
        makeButton({ label: "Delete", iconName: "pi-trash", className: "xfm-danger", onClick: () => deleteWorkflow(workflow) })
      );
    }
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
    XFM.showDuplicateDialog = false;
    renderSurfaces();
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

function setActiveWorkflow(workflow, path = workflow?.path) {
  if (!path) return;
  XFM.activeWorkflow = {
    path,
    contentHash: workflow?.content_hash || null,
    loadedAt: Date.now(),
  };
  try {
    XFM.loadedSnapshot = stableStringify(app.graph.serialize());
  } catch {
    XFM.loadedSnapshot = null;
  }
}

async function refreshWorkflow(path, options = {}) {
  try {
    const data = await postJson(`${ROUTE}/refresh`, { path });
    if (data.workflow) {
      upsertWorkflow(data.workflow);
      XFM.folders = data.folders || XFM.folders;
      XFM.recentlyUpdated.set(path, Date.now());
      if (options.activate) {
        setActiveWorkflow(data.workflow, path);
      } else if (XFM.activeWorkflow?.path === path) {
        XFM.activeWorkflow.contentHash = data.workflow.content_hash;
        XFM.loadedSnapshot = stableStringify(app.graph.serialize());
      }
      renderSurfaces();
      setTimeout(() => {
        XFM.recentlyUpdated.delete(path);
        renderSurfaces();
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
    await refreshWorkflow(path, { activate: true });
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

function workflowPathFromLoadValue(value, depth = 0) {
  if (depth > 3 || value == null) return null;
  if (typeof value === "string") {
    const normalized = value.replace(/\\/g, "/");
    const userdata = workflowPathFromUserdataRoute(normalized);
    if (userdata) return userdata;
    const workflowsIndex = normalized.lastIndexOf("workflows/");
    const candidate = workflowsIndex >= 0 ? normalized.slice(workflowsIndex + "workflows/".length) : normalized;
    if (candidate && candidate.toLowerCase().endsWith(".json") && !candidate.includes("://")) {
      return candidate.replace(/^\/+/, "");
    }
    return null;
  }
  if (typeof value !== "object") return null;
  for (const key of ["path", "workflowPath", "filename", "file", "name", "url"]) {
    const result = workflowPathFromLoadValue(value[key], depth + 1);
    if (result) return result;
  }
  return null;
}

function workflowPathFromLoadArguments(args) {
  for (const value of args) {
    const path = workflowPathFromLoadValue(value);
    if (path) return path;
  }
  return null;
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
    setActiveWorkflow(workflow);
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
  renderSurfaces({ preserveScroll: true });
}

async function addTagFromDialog() {
  const tag = XFM.dialog?.tag?.trim();
  const workflow = XFM.dialog?.workflow;
  if (!tag || !workflow) return;
  const data = await postJson(`${ROUTE}/tags`, { path: workflow.path, add: [tag] });
  applyTagResponse(data);
  XFM.dialog.tag = "";
  XFM.expandedTags.add(workflow.path);
  renderSurfaces({ preserveScroll: true });
}

async function removeTagFromDialog(tag) {
  const workflow = XFM.dialog?.workflow;
  if (!tag || !workflow) return;
  const data = await postJson(`${ROUTE}/tags`, { path: workflow.path, remove: [tag] });
  applyTagResponse(data);
  renderSurfaces({ preserveScroll: true });
}

function openMoveDialog(workflow) {
  XFM.dialog = {
    type: "move",
    workflow,
    selectedFolder: workflow.folder || "",
    newFolder: "",
    expandedFolders: folderAncestors(workflow.folder || ""),
    pickerScroll: 0,
  };
  renderSurfaces({ preserveScroll: true });
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
    dialog.expandedFolders = folderAncestors(data.folder);
    dialog.newFolder = "";
    renderSurfaces({ preserveScroll: true });
  } catch (error) {
    alert(`Create folder failed: ${error.message}`);
  }
}

async function confirmMoveDialog() {
  const dialog = XFM.dialog;
  if (!dialog || dialog.type !== "move") return;
  try {
    const data = await postJson(`${ROUTE}/move`, { path: dialog.workflow.path, folder: dialog.selectedFolder || "" });
    XFM.dialog = null;
    await refreshAfterMove(data);
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

async function findDuplicates({ openDialog = true } = {}) {
  try {
    XFM.duplicateResult = await postJson(`${ROUTE}/duplicates`);
    XFM.showDuplicateDialog = openDialog;
    XFM.duplicateUi = {
      tab: XFM.duplicateUi?.tab || DUPLICATE_TABS[0].key,
      collapsed: XFM.duplicateUi?.collapsed || new Set(),
      selected: XFM.duplicateUi?.selected || new Set(),
      keepers: XFM.duplicateUi?.keepers || {},
      preview: null,
      confirmDelete: null,
      message: "",
    };
    renderSurfaces();
  } catch (error) {
    alert(`Duplicate scan failed: ${error.message}`);
  }
}

function duplicateUi() {
  if (!XFM.duplicateUi) {
    XFM.duplicateUi = {
      tab: DUPLICATE_TABS[0].key,
      collapsed: new Set(),
      selected: new Set(),
      keepers: {},
      preview: null,
      confirmDelete: null,
      message: "",
    };
  }
  return XFM.duplicateUi;
}

function duplicateTabInfo(key = duplicateUi().tab) {
  return DUPLICATE_TABS.find((item) => item.key === key) || DUPLICATE_TABS[0];
}

function duplicateGroups(key = duplicateUi().tab) {
  return XFM.duplicateResult?.[key] || [];
}

function duplicateGroupKey(tab, group, index) {
  return `${tab}:${shortHash(group.signature)}:${index}`;
}

function duplicateSectionSummary() {
  return DUPLICATE_TABS
    .map((section) => `${section.label}: ${duplicateGroups(section.key).length}`)
    .join(" | ");
}

function duplicateGroupMeta(group) {
  const parts = [];
  if (group.name_key) parts.push(`name ${group.name_key}`);
  if (Number.isFinite(group.node_count)) parts.push(`${group.node_count} nodes`);
  if (Number.isFinite(group.value_variant_count)) parts.push(`${group.value_variant_count} value variant(s)`);
  if (group.node_signature) parts.push(`nodes ${shortHash(group.node_signature)}`);
  if (group.value_signature) parts.push(`values ${shortHash(group.value_signature)}`);
  return parts.join(" | ");
}

function duplicateSelectedPaths() {
  const available = new Set();
  for (const tab of DUPLICATE_TABS) {
    for (const group of duplicateGroups(tab.key)) {
      for (const workflow of group.workflows || []) available.add(workflow.path);
    }
  }
  return [...duplicateUi().selected].filter((path) => available.has(path));
}

function chooseWorkflowToKeep(group, mode) {
  const workflows = [...(group.workflows || [])];
  if (!workflows.length) return null;
  if (mode === "favorite") {
    const favorites = workflows.filter((workflow) => workflow.favorite);
    if (favorites.length) workflows.splice(0, workflows.length, ...favorites);
  }
  workflows.sort((a, b) => {
    if (mode === "newest") return (b.mtime || 0) - (a.mtime || 0) || (b.run_count || 0) - (a.run_count || 0);
    if (mode === "most_used" || mode === "favorite") return (b.run_count || 0) - (a.run_count || 0) || (b.mtime || 0) - (a.mtime || 0);
    return a.path.localeCompare(b.path);
  });
  return workflows[0] || null;
}

function markDuplicateKeeper(tab, group, index, keeperPath, selectRest = true) {
  const ui = duplicateUi();
  const key = duplicateGroupKey(tab, group, index);
  ui.keepers[key] = keeperPath;
  ui.selected.delete(keeperPath);
  if (selectRest) {
    for (const workflow of group.workflows || []) {
      if (workflow.path !== keeperPath) ui.selected.add(workflow.path);
    }
  }
  ui.message = "Keeper selected. Review the checked workflows, then delete selected when ready.";
  renderSurfaces();
}

function setDuplicateTab(tab) {
  const ui = duplicateUi();
  ui.tab = tab;
  ui.preview = null;
  ui.confirmDelete = null;
  renderSurfaces();
}

function toggleDuplicateGroup(tab, group, index, open) {
  const ui = duplicateUi();
  const key = duplicateGroupKey(tab, group, index);
  if (open) ui.collapsed.delete(key);
  else ui.collapsed.add(key);
}

function setDuplicateChecked(path, checked) {
  const ui = duplicateUi();
  if (checked) ui.selected.add(path);
  else ui.selected.delete(path);
  renderSurfaces();
}

function renderDuplicatePills(parent, tags = []) {
  for (const tag of (tags || []).slice(0, 6)) {
    parent.append($el("span.xfm-pill", { textContent: tag }));
  }
  if ((tags || []).length > 6) parent.append($el("span.xfm-pill", { textContent: `+${tags.length - 6}` }));
}

function workflowNodeSummary(workflowJson) {
  const nodes = Array.isArray(workflowJson?.nodes) ? workflowJson.nodes : [];
  const links = Array.isArray(workflowJson?.links) ? workflowJson.links : [];
  const typeCounts = new Map();
  for (const node of nodes) {
    const type = String(node.type || node.class_type || node.title || "Unknown");
    typeCounts.set(type, (typeCounts.get(type) || 0) + 1);
  }
  const topTypes = [...typeCounts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 12)
    .map(([type, count]) => `${type} (${count})`);
  const titles = nodes
    .map((node) => String(node.title || node.type || node.class_type || "").trim())
    .filter(Boolean)
    .slice(0, 16);
  return { nodeCount: nodes.length, linkCount: links.length, topTypes, titles };
}

async function previewDuplicateWorkflow(workflow) {
  try {
    const data = await apiJson(`${ROUTE}/workflow?path=${encodeURIComponent(workflow.path)}`, { cache: "no-store" });
    duplicateUi().preview = {
      workflow,
      summary: workflowNodeSummary(data.workflow),
    };
    duplicateUi().confirmDelete = null;
    renderSurfaces();
  } catch (error) {
    duplicateUi().message = `Preview failed: ${error.message}`;
    renderSurfaces();
  }
}

function openDuplicateDeleteConfirm(paths = duplicateSelectedPaths()) {
  const filtered = [...new Set(paths)].filter(Boolean);
  if (!filtered.length) {
    duplicateUi().message = "Select at least one workflow to delete.";
    renderSurfaces();
    return;
  }
  duplicateUi().preview = null;
  duplicateUi().confirmDelete = filtered;
  renderSurfaces();
}

async function confirmDuplicateDelete() {
  const ui = duplicateUi();
  const paths = [...new Set(ui.confirmDelete || [])];
  if (!paths.length) return;
  try {
    const result = await postJson(`${ROUTE}/delete-batch`, { paths });
    const data = await apiJson(`${ROUTE}/workflows`, { cache: "no-store" });
    XFM.data = data;
    XFM.workflows = data.workflows || [];
    XFM.folders = data.folders || [];
    XFM.duplicateResult = await postJson(`${ROUTE}/duplicates`);
    for (const path of paths) ui.selected.delete(path);
    ui.confirmDelete = null;
    ui.preview = null;
    ui.message = result.failed_count
      ? `Moved ${result.deleted_count} workflow(s) to trash. ${result.failed_count} item(s) could not be deleted.`
      : `Moved ${result.deleted_count} workflow(s) to XFlows trash.`;
    renderSurfaces();
  } catch (error) {
    ui.message = `Delete failed: ${error.message}`;
    renderSurfaces();
  }
}

async function rescanDuplicates() {
  try {
    XFM.duplicateResult = await postJson(`${ROUTE}/duplicates`);
    const ui = duplicateUi();
    ui.confirmDelete = null;
    ui.preview = null;
    ui.message = "Duplicate scan refreshed.";
    renderSurfaces();
  } catch (error) {
    duplicateUi().message = `Rescan failed: ${error.message}`;
    renderSurfaces();
  }
}

function renderDuplicatePreview(parent) {
  const preview = duplicateUi().preview;
  if (!preview) return;
  const { workflow, summary } = preview;
  const box = $el("div.xfm-preview-box", { parent });
  const title = $el("div.xfm-title-row", { parent: box });
  $el("div.xfm-title", { textContent: "Preview", parent: title });
  title.append(iconButton("pi-times", "Close preview", () => {
    duplicateUi().preview = null;
    renderSurfaces();
  }));
  const grid = $el("dl.xfm-preview-grid", { parent: box });
  const addRow = (label, value) => {
    grid.append($el("dt", { textContent: label }), $el("dd", { textContent: value || "none" }));
  };
  addRow("Path", workflow.path);
  addRow("Nodes", `${summary.nodeCount} nodes, ${summary.linkCount} links`);
  addRow("Runs", `${workflow.run_count || 0}`);
  addRow("Modified", formatDateTime(workflow.mtime));
  addRow("Size", formatBytes(workflow.size));
  addRow("Content hash", shortHash(workflow.content_hash));
  addRow("Graph hash", shortHash(workflow.canonical_hash));
  addRow("Near signature", shortHash(workflow.near_signature));
  addRow("Name signature", workflow.name_signature);
  addRow("Node signature", shortHash(workflow.node_signature));
  addRow("Value signature", shortHash(workflow.value_signature));
  addRow("Models", (workflow.detected_models || []).map((model) => `${model.folder}/${model.name}`).slice(0, 8).join(", "));
  addRow("Top node types", summary.topTypes.join(", "));
  addRow("Node titles", summary.titles.join(", "));
  addRow("Tags", (workflow.all_tags || workflow.auto_tags || []).join(", "));
}

function renderDuplicateDeleteConfirm(parent) {
  const paths = duplicateUi().confirmDelete || [];
  if (!paths.length) return;
  const box = $el("div.xfm-confirm-box", { parent });
  $el("div.xfm-duplicate-title", { textContent: `Move ${paths.length} workflow(s) to XFlows trash?`, parent: box });
  const list = $el("div.xfm-small-list", { parent: box });
  for (const path of paths.slice(0, 8)) $el("div", { textContent: path, title: path, parent: list });
  if (paths.length > 8) $el("div", { textContent: `${paths.length - 8} more selected workflow(s)`, parent: list });
  const actions = $el("div.xfm-dialog-actions", { parent: box });
  actions.append(
    makeButton({ label: "Cancel", onClick: () => {
      duplicateUi().confirmDelete = null;
      renderSurfaces();
    } }),
    makeButton({ label: "Move to trash", iconName: "pi-trash", className: "xfm-danger", onClick: confirmDuplicateDelete })
  );
}

function renderDuplicateOverlays(parent) {
  const ui = duplicateUi();
  const hasConfirm = !!ui.confirmDelete?.length;
  const hasPreview = !!ui.preview;
  if (!hasConfirm && !hasPreview) return;
  const backdrop = $el("div.xfm-modal-backdrop.xfm-duplicate-overlay", { parent });
  backdrop.addEventListener("mousedown", (event) => {
    if (event.target !== backdrop) return;
    ui.preview = null;
    ui.confirmDelete = null;
    renderSurfaces();
  });
  const modal = $el("div.xfm-modal.xfm-duplicate-floating", { parent: backdrop });
  if (hasConfirm) renderDuplicateDeleteConfirm(modal);
  else renderDuplicatePreview(modal);
}

function renderDuplicateGroup(parent, section, group, index) {
  const ui = duplicateUi();
  const groupKey = duplicateGroupKey(section.key, group, index);
  const keeper = ui.keepers[groupKey] || chooseWorkflowToKeep(group, "most_used")?.path || group.workflows?.[0]?.path;
  const details = $el("details.xfm-duplicate-group", {
    ontoggle: (event) => toggleDuplicateGroup(section.key, group, index, event.currentTarget.open),
    parent,
  });
  details.open = !ui.collapsed.has(groupKey);
  const summaryRow = $el("summary", { parent: details });
  summaryRow.append(icon(details.open ? "pi-angle-down" : "pi-angle-right"));
  const title = $el("div.xfm-duplicate-title", {
    textContent: `${section.title}: ${group.count} workflows`,
    parent: summaryRow,
  });
  title.title = group.signature || "";
  summaryRow.append($el("span.xfm-signature", { textContent: shortHash(group.signature) }));
  const metaText = duplicateGroupMeta(group);
  if (metaText) $el("div.xfm-subtle", { textContent: metaText, title: metaText, parent: details });

  const actions = $el("div.xfm-duplicate-actions", { parent: details });
  actions.append(
    makeButton({ label: "Keep newest", iconName: "pi-calendar", onClick: () => {
      const pick = chooseWorkflowToKeep(group, "newest");
      if (pick) markDuplicateKeeper(section.key, group, index, pick.path);
    } }),
    makeButton({ label: "Keep most used", iconName: "pi-chart-bar", onClick: () => {
      const pick = chooseWorkflowToKeep(group, "most_used");
      if (pick) markDuplicateKeeper(section.key, group, index, pick.path);
    } }),
    makeButton({ label: "Keep favorite", iconName: "pi-star", onClick: () => {
      const pick = chooseWorkflowToKeep(group, "favorite");
      if (pick) markDuplicateKeeper(section.key, group, index, pick.path);
    } }),
    makeButton({
      label: "Delete selected",
      iconName: "pi-trash",
      className: "xfm-danger",
      onClick: () => openDuplicateDeleteConfirm((group.workflows || []).map((workflow) => workflow.path).filter((path) => ui.selected.has(path))),
    })
  );

  for (const workflow of group.workflows || []) {
    const isKeeper = keeper === workflow.path;
    const card = $el("div.xfm-duplicate-workflow" + (isKeeper ? ".keep" : ""), { parent: details });
    const line = $el("div.xfm-duplicate-row", { parent: card });
    const checkbox = $el("input.xfm-duplicate-check", {
      type: "checkbox",
      title: "Select for soft delete",
      onchange: (event) => setDuplicateChecked(workflow.path, event.target.checked),
      parent: line,
    });
    checkbox.checked = ui.selected.has(workflow.path);
    protectField(checkbox);
    const main = $el("div", { parent: line });
    $el("div.xfm-name", { textContent: workflow.name || workflow.path, parent: main });
    $el("div.xfm-path", { textContent: workflow.path, title: workflow.path, parent: main });
    const meta = $el("div.xfm-meta", { parent: main });
    meta.append(
      $el("span", { textContent: `${workflow.run_count || 0} runs` }),
      $el("span", { textContent: `${workflow.node_count || 0} nodes` }),
      $el("span", { textContent: formatBytes(workflow.size) }),
      $el("span", { textContent: `modified ${shortDate(workflow.mtime)}` })
    );
    if (workflow.favorite) meta.append($el("span", { textContent: "favorite" }));
    const tags = $el("div.xfm-tags", { parent: main });
    renderDuplicatePills(tags, workflow.all_tags || workflow.auto_tags || []);
    const itemActions = $el("div.xfm-duplicate-actions", { parent: line });
    itemActions.append(
      makeButton({ label: "Preview", iconName: "pi-eye", onClick: () => previewDuplicateWorkflow(workflow) }),
      makeButton({ label: "Use", iconName: "pi-play", onClick: () => {
        XFM.duplicateResult = null;
        XFM.duplicateUi = null;
        XFM.showDuplicateDialog = false;
        renderSurfaces();
        useWorkflow(workflow);
      } }),
      makeButton({ label: isKeeper ? "Keeper" : "Keep this", iconName: "pi-check", className: isKeeper ? "active" : "", onClick: () => markDuplicateKeeper(section.key, group, index, workflow.path) })
    );
  }
}

function renderDuplicates(parent) {
  const ui = duplicateUi();
  const backdrop = $el("div.xfm-modal-backdrop", { parent });
  const panel = $el("div.xfm-modal.xfm-duplicate-modal", { parent: backdrop });
  const row = $el("div.xfm-title-row", { parent: panel });
  $el("div.xfm-title", { textContent: `Duplicate Finder | ${duplicateSectionSummary()}`, parent: row });
  row.append(
    makeButton({ label: "Rescan", iconName: "pi-sync", onClick: rescanDuplicates }),
    iconButton("pi-times", "Close duplicate finder", () => {
      XFM.showDuplicateDialog = false;
      renderSurfaces();
    })
  );

  const body = $el("div.xfm-duplicate-body", { parent: panel });
  if (ui.message) $el("div.xfm-subtle", { textContent: ui.message, parent: body });
  for (const section of DUPLICATE_TABS) {
    const sectionBox = $el("section.xfm-duplicate-section", { parent: body });
    const heading = $el("div.xfm-duplicate-section-title", { parent: sectionBox });
    $el("div.xfm-duplicate-title", { textContent: `${section.title} (${duplicateGroups(section.key).length})`, parent: heading });
    $el("div.xfm-subtle", { textContent: section.reason, parent: sectionBox });
    const groups = duplicateGroups(section.key);
    if (!groups.length) {
      $el("div.xfm-empty", { textContent: `No ${section.title.toLowerCase()} found.`, parent: sectionBox });
      continue;
    }
    groups.forEach((group, index) => renderDuplicateGroup(sectionBox, section, group, index));
  }

  const selected = duplicateSelectedPaths();
  const footer = $el("div.xfm-dialog-actions", { parent: panel });
  footer.append(
    $el("div.xfm-subtle", { textContent: `${selected.length} selected for soft delete` }),
    makeButton({
      label: "Delete selected",
      iconName: "pi-trash",
      className: "xfm-danger",
      disabled: !selected.length,
      onClick: () => openDuplicateDeleteConfirm(selected),
    })
  );
  renderDuplicateOverlays(backdrop);
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

function folderAncestors(path) {
  const expanded = new Set([""]);
  const parts = String(path || "").split("/").filter(Boolean);
  let current = "";
  for (const part of parts) {
    current = current ? `${current}/${part}` : part;
    expanded.add(current);
  }
  return expanded;
}

function attachManagerFolderDrop(row, node) {
  const markDropTarget = (event) => {
    const paths = managerDragPathsFromEvent(event);
    if (!paths.length) return false;
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
    row.classList.add("drop-target");
    return true;
  };
  row.addEventListener("dragenter", markDropTarget);
  row.addEventListener("dragover", markDropTarget);
  row.addEventListener("dragleave", (event) => {
    if (!row.contains(event.relatedTarget)) row.classList.remove("drop-target");
  });
  row.addEventListener("drop", (event) => {
    if (!markDropTarget(event)) return;
    row.classList.remove("drop-target");
    moveManagerDraggedPaths(managerDragPathsFromEvent(event), node.path);
  });
}

function renderFolderRows(parent, node, depth, selected, state, onSelect, rerender, options = {}) {
  if (!state.expandedFolders) state.expandedFolders = folderAncestors(selected);
  const children = [...node.children.values()].sort((a, b) => a.name.localeCompare(b.name));
  const hasChildren = children.length > 0;
  const open = !node.path || state.expandedFolders.has(node.path);
  const row = $el("div.xfm-folder-row" + (node.path === selected ? ".active" : ""), {
    title: node.path || "Workflow root",
    parent,
  });
  row.style.paddingLeft = `${8 + depth * 14}px`;
  if (options.enableDrop) attachManagerFolderDrop(row, node);
  row.append($el("button.xfm-folder-toggle", {
    type: "button",
    title: hasChildren ? (open ? "Collapse folder" : "Expand folder") : "",
    onclick: (event) => {
      event.stopPropagation();
      if (!hasChildren) return;
      if (open) state.expandedFolders.delete(node.path);
      else state.expandedFolders.add(node.path);
      rerender();
    },
  }, [hasChildren ? icon(open ? "pi-angle-down" : "pi-angle-right") : $el("span")]));
  row.append($el("button.xfm-folder-label", {
    type: "button",
    onclick: () => {
      onSelect(node.path);
      if (hasChildren) state.expandedFolders.add(node.path);
      rerender();
    },
  }, [
    icon(node.path ? "pi-folder" : "pi-home"),
    $el("span", { textContent: node.name }),
  ]));
  if (open) {
    for (const child of children) renderFolderRows(parent, child, depth + 1, selected, state, onSelect, rerender, options);
  }
}

function renderManagerFolderTree(parent, tree) {
  renderFolderRows(
    parent,
    tree,
    0,
    XFM.manager.folder || "",
    XFM.manager,
    (path) => {
      XFM.manager.folder = path;
      XFM.manager.scrollTop = 0;
    },
    renderManagerModal,
    { enableDrop: true }
  );
}

function renderManagerTreeCreate(parent) {
  const box = $el("div.xfm-manager-tree-create", { parent });
  const selected = XFM.manager.folder || "(root)";
  $el("div.xfm-subtle", { textContent: `Create in: ${selected}`, title: XFM.manager.folder || "Workflow root", parent: box });
  const row = $el("div.xfm-manager-tree-create-row", { parent: box });
  const input = protectField($el("input.xfm-input", {
    value: XFM.manager.newFolder,
    placeholder: "New folder",
    oninput: (event) => { XFM.manager.newFolder = event.target.value; },
    onkeydown: (event) => {
      if (event.key === "Enter") createManagerTreeFolder();
      if (event.key === "Escape") {
        XFM.manager.newFolder = "";
        renderManagerModal();
      }
    },
    parent: row,
  }));
  row.append(makeButton({
    iconName: "pi-plus",
    className: "xfm-icon-btn",
    title: "Create folder",
    onClick: createManagerTreeFolder,
  }));
}

async function createManagerTreeFolder() {
  const name = (XFM.manager.newFolder || "").trim();
  if (!name) {
    XFM.manager.message = "Enter a folder name first.";
    renderManagerModal();
    return;
  }
  try {
    const data = await postJson(`${ROUTE}/folder`, { parent: XFM.manager.folder || "", name });
    XFM.folders = data.folders || XFM.folders;
    XFM.manager.folder = data.folder || "";
    XFM.manager.expandedFolders = folderAncestors(data.folder || "");
    XFM.manager.newFolder = "";
    XFM.manager.scrollTop = 0;
    XFM.manager.message = `Created folder: ${data.folder || name}`;
    renderManagerModal();
  } catch (error) {
    XFM.manager.message = `Create folder failed: ${error.message}`;
    renderManagerModal();
  }
}

function renderManagerMoveDialog(parent) {
  const move = XFM.manager.move;
  if (!move) return;
  const box = $el("div.xfm-manager-popover", { parent });
  const title = $el("div.xfm-title-row", { parent: box });
  $el("div.xfm-title", { textContent: move.title || "Move workflows", parent: title });
  title.append(iconButton("pi-times", "Cancel move", () => { XFM.manager.move = null; renderManagerModal(); }));
  $el("div.xfm-subtle", { textContent: `${move.paths.length} workflow(s) selected`, parent: box });
  const picker = $el("div.xfm-folder-picker", {
    parent: box,
    onscroll: (event) => { move.pickerScroll = event.currentTarget.scrollTop; },
  });
  renderFolderRows(
    picker,
    buildFolderTree(XFM.folders),
    0,
    move.selectedFolder || "",
    move,
    (path) => { move.selectedFolder = path; },
    renderManagerModal
  );
  requestAnimationFrame(() => { picker.scrollTop = move.pickerScroll || 0; });
  const selected = move.selectedFolder || "(root)";
  $el("div.xfm-subtle", { textContent: `Destination: ${selected}`, parent: box });
  const createRow = $el("div.xfm-toolbar", { parent: box });
  const input = protectField($el("input.xfm-input", {
    value: move.newFolder,
    placeholder: "New folder under selected destination",
    oninput: (event) => { move.newFolder = event.target.value; },
    onkeydown: (event) => {
      if (event.key === "Enter") createManagerFolder();
      if (event.key === "Escape") {
        XFM.manager.move = null;
        renderManagerModal();
      }
    },
    parent: createRow,
  }));
  createRow.append(makeButton({ label: "Create", iconName: "pi-plus", onClick: createManagerFolder }));
  const actions = $el("div.xfm-dialog-actions", { parent: box });
  actions.append(
    makeButton({ label: "Cancel", onClick: () => { XFM.manager.move = null; renderManagerModal(); } }),
    makeButton({ label: "Move here", iconName: "pi-folder", className: "active", onClick: confirmManagerMove })
  );
  requestAnimationFrame(() => input.focus({ preventScroll: true }));
}

function renderManagerTagDialog(parent) {
  const workflow = managerTagWorkflow();
  if (!workflow) {
    XFM.manager.tag = null;
    return;
  }
  const box = $el("div.xfm-manager-popover", { parent });
  const title = $el("div.xfm-title-row", { parent: box });
  $el("div.xfm-title", { textContent: "Manage tags", parent: title });
  title.append(iconButton("pi-times", "Close tags", () => { XFM.manager.tag = null; renderManagerModal(); }));
  $el("div.xfm-subtle", { textContent: workflow.path, title: workflow.path, parent: box });
  const tagList = $el("div.xfm-tag-manager", { parent: box });
  const tags = workflow.all_tags || [];
  if (!tags.length) $el("div.xfm-subtle", { textContent: "No tags yet.", parent: tagList });
  for (const tag of tags) {
    const source = tagSource(workflow, tag);
    const chip = $el("div.xfm-tag-chip" + (source.includes("custom") ? ".manual" : ".auto"), {
      title: source,
      parent: tagList,
    });
    chip.append($el("span.xfm-tag-text", { textContent: tag }));
    chip.append($el("span.xfm-tag-source", { textContent: source }));
    chip.append(iconButton("pi-times", `Remove ${tag}`, () => removeManagerTag(tag), "xfm-tag-remove"));
  }
  const row = $el("div.xfm-toolbar", { parent: box });
  const input = protectField($el("input.xfm-input", {
    value: XFM.manager.tag.tag,
    placeholder: "Add custom tag",
    oninput: (event) => { XFM.manager.tag.tag = event.target.value; },
    onkeydown: (event) => {
      if (event.key === "Enter") addManagerTag();
      if (event.key === "Escape") {
        XFM.manager.tag = null;
        renderManagerModal();
      }
    },
    parent: row,
  }));
  row.append(makeButton({ label: "Add custom tag", iconName: "pi-plus", className: "active", onClick: addManagerTag }));
  requestAnimationFrame(() => {
    if (XFM.manager.tag && document.activeElement !== input) input.focus({ preventScroll: true });
  });
}

async function createManagerFolder() {
  const move = XFM.manager.move;
  if (!move) return;
  const name = (move.newFolder || "").trim();
  if (!name) return;
  try {
    const data = await postJson(`${ROUTE}/folder`, { parent: move.selectedFolder || "", name });
    XFM.folders = data.folders || XFM.folders;
    move.selectedFolder = data.folder;
    move.expandedFolders = folderAncestors(data.folder);
    move.newFolder = "";
    renderManagerModal();
  } catch (error) {
    XFM.manager.message = `Create folder failed: ${error.message}`;
    renderManagerModal();
  }
}

function renderDialog(parent) {
  const backdrop = $el("div.xfm-modal-backdrop", { parent });
  const modal = $el("div.xfm-modal", { parent: backdrop });
  const title = $el("div.xfm-modal-title", { parent: modal });
  const close = () => {
    XFM.dialog = null;
    renderSurfaces({ preserveScroll: true });
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
    const input = protectField($el("input.xfm-input", {
      value: XFM.dialog.tag,
      placeholder: "Add custom tag",
      oninput: (event) => { XFM.dialog.tag = event.target.value; },
      onkeydown: (event) => {
        if (event.key === "Enter") addTagFromDialog();
        if (event.key === "Escape") close();
      },
      parent: modal,
    }));
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
    const picker = $el("div.xfm-folder-picker", {
      parent: modal,
      onscroll: (event) => { XFM.dialog.pickerScroll = event.currentTarget.scrollTop; },
    });
    renderFolderRows(
      picker,
      buildFolderTree(XFM.folders),
      0,
      XFM.dialog.selectedFolder || "",
      XFM.dialog,
      (path) => { XFM.dialog.selectedFolder = path; },
      () => renderSurfaces({ preserveScroll: true })
    );
    requestAnimationFrame(() => { picker.scrollTop = XFM.dialog.pickerScroll || 0; });
    const selected = XFM.dialog.selectedFolder || "(root)";
    $el("div.xfm-subtle", { textContent: `Destination: ${selected}`, parent: modal });
    const createRow = $el("div.xfm-toolbar", { parent: modal });
    const input = protectField($el("input.xfm-input", {
      value: XFM.dialog.newFolder,
      placeholder: "New folder under selected destination",
      oninput: (event) => { XFM.dialog.newFolder = event.target.value; },
      onkeydown: (event) => {
        if (event.key === "Enter") createFolderFromDialog();
        if (event.key === "Escape") close();
      },
      parent: createRow,
    }));
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
    requestAnimationFrame(() => input.focus({ preventScroll: true }));
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
    const args = [...arguments];
    const path = XFM.loadingFromManager ? null : workflowPathFromLoadArguments(args);
    if (!XFM.loadingFromManager) {
      if (!path) {
        XFM.activeWorkflow = null;
        XFM.loadedSnapshot = null;
      }
    }
    const result = originalLoadGraphData(...args);
    if (!XFM.loadingFromManager && path) {
      Promise.resolve(result).then(() => {
        const workflow = XFM.workflows.find((item) => item.path === path);
        setActiveWorkflow(workflow, path);
        scheduleWorkflowRefresh(path);
      });
    }
    return result;
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
    wrapGraphLoading();
    wrapPromptTracking();
    window.addEventListener("workflowx:imported", () => loadData(true));
    window.addEventListener("workflowx:feature-settings-changed", applyXFlowsVisibility);
    if (isXFlowsEnabled()) {
      const registered = registerSidebar();
      if (!registered) await registerFallbackButton();
      await loadData(false);
    }
    applyXFlowsVisibility();
  },
});
