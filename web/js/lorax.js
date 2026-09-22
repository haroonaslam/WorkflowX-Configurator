import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyIdentity, itemFileSize, itemSha256, normalizeSha256, sortedHashMatches } from "./lorax_identity.js";
import { compactArray, creatorName, itemMatchesQuery, normalizePath, trainedWords } from "./lorax_search.js";

const NODE_TYPE = "KVGC_LoraX";
const EXTENSION_NAME = "workflowx.lorax";
const LORAX_ROUTE = "/workflowx_configurator/lorax/loras";
const LORAX_HASH_ROUTE = "/workflowx_configurator/lorax/hash";
const LORAX_REMAP_ROUTE = "/workflowx_configurator/lorax/remap";
const LORA_MANAGER_LIST_ROUTE = "/api/lm/loras/list";
const LORA_MANAGER_TREE_ROUTE = "/api/lm/loras/unified-folder-tree";
const LORA_MANAGER_SCAN_ROUTE = "/api/lm/loras/scan";
const LORA_MANAGER_METADATA_ROUTE = "/api/lm/loras/metadata";
const LORA_MANAGER_DESCRIPTION_ROUTE = "/api/lm/loras/model-description";
const STYLE_ID = "workflowx-lorax-styles";
const ROW_H = 24;
const HEADER_H = 22;
const MIN_W = 560;
const STRENGTH_W = 130;
const REMOVE_W = 28;
const CONTROL_GAP = 8;
const REMAP_X = 122;
const REMAP_W = 26;
const MAX_MANAGER_PAGES = 200;
const LORA_EXT_RE = /\.(safetensors|ckpt|pt|bin)$/i;
const VIDEO_EXT_RE = /\.(mp4|webm|mov)(?:[?#].*)?$/i;

let catalogPromise = null;
let canonicalItemsPromise = null;
let activePicker = null;

function markDirty(node) {
  node?.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

async function fetchJson(path, options = {}) {
  const requestOptions = { cache: "no-store", ...options };
  const response = api?.fetchApi ? await api.fetchApi(path, requestOptions) : await fetch(path, requestOptions);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.error || `${response.status} ${response.statusText}`);
  return data;
}

function postJson(path, payload) {
  return fetchJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function stripExt(value) {
  return normalizePath(value).replace(LORA_EXT_RE, "");
}

function lower(value) {
  return normalizePath(value).toLowerCase();
}

function uniqueStrings(values) {
  const seen = new Set();
  const out = [];
  for (const value of values) {
    const text = String(value || "").trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key)) continue;
    seen.add(key);
    out.push(text);
  }
  return out;
}

function asBool(value, fallback = true) {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") return !["", "0", "false", "no", "off"].includes(value.trim().toLowerCase());
  return Boolean(value);
}

function managerKeys(item) {
  const keys = new Set();
  const folder = normalizePath(item.folder);
  const fileName = stripExt(item.file_name);
  const filePath = lower(item.file_path);
  if (filePath) keys.add(filePath);
  if (folder && fileName) keys.add(`${lower(folder)}/${lower(fileName)}`);
  if (fileName) keys.add(lower(fileName));
  return keys;
}

function canonicalKey(item) {
  return lower(stripExt(item.load_name));
}

function normalizeCanonical(item) {
  const loadName = normalizePath(item.load_name);
  const fileStem = stripExt(item.file_stem || item.filename || loadName).split("/").pop() || stripExt(loadName).split("/").pop() || loadName;
  return {
    load_name: loadName,
    folder: normalizePath(item.folder),
    filename: normalizePath(item.filename || loadName.split("/").pop()),
    file_stem: fileStem,
    full_path: normalizePath(item.full_path),
    file_size: itemFileSize(item),
    sha256: itemSha256(item),
    canonical_display_name: fileStem,
    display_name: fileStem,
  };
}

function mergeCatalog(canonicalItems, managerItems) {
  const byFullPath = new Map();
  const byRelative = new Map();
  const byName = new Map();

  for (const item of managerItems) {
    for (const key of managerKeys(item)) {
      if (!key) continue;
      if (key.includes(":/") || key.startsWith("//")) byFullPath.set(key, item);
      else if (key.includes("/")) byRelative.set(key, item);
      else if (!byName.has(key)) byName.set(key, item);
    }
  }

  return canonicalItems.map((raw) => {
    const item = normalizeCanonical(raw);
    const fullPathKey = lower(item.full_path);
    const relativeKey = canonicalKey(item);
    const nameKey = lower(item.file_stem);
    const manager = byFullPath.get(fullPathKey) || byRelative.get(relativeKey) || byName.get(nameKey) || null;
    const words = trainedWords(manager);
    const tags = compactArray(manager?.tags);
    const autoTags = compactArray(manager?.auto_tags);
    const displayName = normalizePath(manager?.model_name || item.display_name || item.file_stem || item.load_name);

    return {
      ...item,
      display_name: displayName,
      model_name: normalizePath(manager?.model_name),
      base_model: normalizePath(manager?.base_model),
      tags,
      auto_tags: autoTags,
      trained_words: words,
      preview_url: normalizePath(manager?.preview_url),
      favorite: Boolean(manager?.favorite),
      update_available: Boolean(manager?.update_available),
      sub_type: normalizePath(manager?.sub_type),
      creator: creatorName(manager),
      sha256: itemSha256(manager) || item.sha256,
      file_size: itemFileSize(manager) || item.file_size,
      metadata: manager || null,
    };
  });
}

async function loadLoraManagerItems() {
  const items = [];
  let totalPages = 1;
  for (let page = 1; page <= totalPages && page <= MAX_MANAGER_PAGES; page++) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: "100",
      sort_by: "name",
      search_filename: "true",
      search_modelname: "true",
      search_tags: "true",
      search_creator: "true",
      recursive: "true",
    });
    const data = await fetchJson(`${LORA_MANAGER_LIST_ROUTE}?${params}`);
    items.push(...(Array.isArray(data.items) ? data.items : []));
    totalPages = Number(data.total_pages || 1);
  }
  return items;
}

function createTreeRoot() {
  return { name: "Root", path: "", children: new Map() };
}

function insertTreePath(root, folderPath) {
  const parts = normalizePath(folderPath).split("/").filter(Boolean);
  let node = root;
  let currentPath = "";
  for (const part of parts) {
    currentPath = currentPath ? `${currentPath}/${part}` : part;
    if (!node.children.has(part)) {
      node.children.set(part, { name: part, path: currentPath, children: new Map() });
    }
    node = node.children.get(part);
  }
}

function mergeTreeObject(root, treeData, basePath = "") {
  if (!treeData || typeof treeData !== "object" || Array.isArray(treeData)) return;
  for (const [folderName, children] of Object.entries(treeData)) {
    if (!folderName) continue;
    const path = basePath ? `${basePath}/${folderName}` : folderName;
    insertTreePath(root, path);
    mergeTreeObject(root, children, path);
  }
}

function buildTreeFromItems(items) {
  const root = createTreeRoot();
  for (const item of items) insertTreePath(root, item.folder);
  return root;
}

function buildTreeFromManagerData(data, items) {
  const root = createTreeRoot();
  const source = data?.tree || data;
  mergeTreeObject(root, source);
  for (const item of items) insertTreePath(root, item.folder);
  return root;
}

function sortedChildren(node) {
  return [...node.children.values()].sort((a, b) => a.name.localeCompare(b.name));
}

async function loadLoraManagerTree() {
  const data = await fetchJson(LORA_MANAGER_TREE_ROUTE);
  if (data?.success === false) return null;
  return data;
}

async function loadCanonicalItems() {
  if (!canonicalItemsPromise) {
    canonicalItemsPromise = fetchJson(LORAX_ROUTE)
      .then((data) => (Array.isArray(data.items) ? data.items : []))
      .catch((error) => {
        canonicalItemsPromise = null;
        throw error;
      });
  }
  return canonicalItemsPromise;
}

async function loadCatalog() {
  if (!catalogPromise) {
    catalogPromise = (async () => {
      const canonicalItems = await loadCanonicalItems().catch(() => []);
      const [managerItems, managerTree] = await Promise.all([
        loadLoraManagerItems().catch(() => []),
        loadLoraManagerTree().catch(() => null),
      ]);
      const items = mergeCatalog(canonicalItems, managerItems);
      const tree = managerTree ? buildTreeFromManagerData(managerTree, items) : buildTreeFromItems(items);
      return { items, tree };
    })();
  }
  return catalogPromise;
}

async function refreshCatalog() {
  await fetchJson(`${LORA_MANAGER_SCAN_ROUTE}?full_rebuild=false`).catch(() => null);
  catalogPromise = null;
  canonicalItemsPromise = null;
  return loadCatalog();
}

async function ensureItemIdentity(item) {
  const sha256 = itemSha256(item);
  const fileSize = itemFileSize(item);
  if (sha256) return { ...item, sha256, file_size: fileSize };
  const identity = await postJson(LORAX_HASH_ROUTE, { load_name: item?.load_name });
  const calculatedHash = itemSha256(identity);
  if (!calculatedHash) throw new Error("The backend did not return a valid SHA-256 identity.");
  return {
    ...item,
    ...identity,
    display_name: item?.display_name || identity?.file_stem || identity?.load_name,
    metadata: item?.metadata || null,
    sha256: calculatedHash,
    file_size: itemFileSize(identity),
  };
}

function itemMatchesFolder(item, folder) {
  if (!folder) return true;
  return item.folder === folder || item.folder.startsWith(`${folder}/`);
}

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .workflowx-lorax-backdrop{position:fixed;inset:0;z-index:10000;background:rgba(8,10,12,.58);display:flex;align-items:center;justify-content:center}
    .workflowx-lorax-picker{width:min(1180px,calc(100vw - 48px));height:min(800px,calc(100vh - 48px));background:#17191d;color:#e8ebef;border:1px solid #41464f;border-radius:8px;box-shadow:0 24px 80px rgba(0,0,0,.58);display:grid;grid-template-rows:auto 1fr;overflow:hidden;font:13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .workflowx-lorax-top{display:grid;grid-template-columns:1fr auto auto auto;gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid #30343b;background:#202328}
    .workflowx-lorax-search{height:32px;border-radius:6px;border:1px solid #4e5560;background:#111316;color:#f3f5f7;padding:0 10px;font-size:14px;outline:none}
    .workflowx-lorax-strict{height:32px;border:1px solid #4e5560;border-radius:6px;background:#1a1f26;color:#d5dce6;display:flex;align-items:center;gap:7px;padding:0 10px;white-space:nowrap;cursor:pointer;user-select:none}
    .workflowx-lorax-strict input{accent-color:#6f8fd4}
    .workflowx-lorax-refresh,.workflowx-lorax-close{height:32px;width:32px;border:1px solid #4e5560;border-radius:6px;background:#242830;color:#d5d9df;cursor:pointer;font-size:17px;line-height:1}
    .workflowx-lorax-refresh:hover,.workflowx-lorax-close:hover{background:#303743;border-color:#6f8fd4;color:#fff}
    .workflowx-lorax-refresh:disabled{cursor:wait;opacity:.7}
    .workflowx-lorax-refresh span{display:block}
    .workflowx-lorax-refresh.loading span{animation:workflowx-lorax-spin .8s linear infinite}
    @keyframes workflowx-lorax-spin{to{transform:rotate(360deg)}}
    .workflowx-lorax-body{display:grid;grid-template-columns:280px 1fr;min-height:0}
    .workflowx-lorax-tree{border-right:1px solid #30343b;overflow:auto;padding:8px;background:#14161a}
    .workflowx-lorax-tree-row{display:flex;align-items:center;gap:4px;height:28px;color:#bfc5ce}
    .workflowx-lorax-expand{width:22px;height:22px;border:0;border-radius:4px;background:transparent;color:#9fa8b4;cursor:pointer}
    .workflowx-lorax-expand:hover{background:#242a32;color:#fff}
    .workflowx-lorax-folder{flex:1;min-width:0;height:24px;border:0;background:transparent;color:inherit;text-align:left;border-radius:5px;padding:0 7px;cursor:pointer;display:flex;align-items:center;gap:6px}
    .workflowx-lorax-folder:hover,.workflowx-lorax-folder.active{background:#28303a;color:#fff}
    .workflowx-lorax-folder-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .workflowx-lorax-folder-count{margin-left:auto;color:#88919d;font-size:11px}
    .workflowx-lorax-results{overflow:auto;padding:10px;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px;align-content:start;background:#101215}
    .workflowx-lorax-results[aria-busy="true"]{opacity:.55;pointer-events:none;cursor:progress}
    .workflowx-lorax-card{position:relative;min-height:156px;border:1px solid #303640;background:#1c2026;border-radius:7px;display:grid;grid-template-columns:100px 1fr;gap:10px;padding:8px;cursor:pointer;overflow:hidden;color:inherit;text-align:left}
    .workflowx-lorax-card:hover{border-color:#6f8fd4;background:#232a34}
    .workflowx-lorax-thumb,.workflowx-lorax-video{width:100px;height:140px;border-radius:5px;background:#0d0f12;object-fit:cover;border:1px solid #30343b}
    .workflowx-lorax-no-thumb{width:100px;height:140px;border-radius:5px;background:#222831;border:1px solid #30343b;display:flex;align-items:center;justify-content:center;color:#8f98a5}
    .workflowx-lorax-card-body{min-width:0;padding-bottom:31px}
    .workflowx-lorax-card-actions{position:absolute;right:8px;bottom:8px;display:flex;gap:5px}
    .workflowx-lorax-view{height:25px;border:1px solid #4b5563;border-radius:5px;background:#252d37;color:#d9e4f2;cursor:pointer;font-size:11px;padding:0 7px}
    .workflowx-lorax-view:hover{background:#31415a;border-color:#6f8fd4;color:#fff}
    .workflowx-lorax-filename{font-weight:700;color:#f4f6f9;line-height:1.25;overflow-wrap:anywhere;word-break:break-word}
    .workflowx-lorax-name{color:#cbd4df;line-height:1.2;margin-top:5px;max-height:32px;overflow:hidden}
    .workflowx-lorax-path{color:#9fa8b4;margin-top:5px;font-size:11px;line-height:1.25;max-height:30px;overflow:hidden;overflow-wrap:anywhere}
    .workflowx-lorax-meta{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}
    .workflowx-lorax-chip{font-size:11px;line-height:18px;padding:0 6px;border-radius:4px;background:#2a3440;color:#cdd5df;max-width:128px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .workflowx-lorax-empty{grid-column:1/-1;color:#a7afba;padding:32px;text-align:center}
    .workflowx-lorax-detail-backdrop{position:fixed;inset:0;z-index:10001;background:rgba(6,8,10,.66);display:flex;align-items:center;justify-content:center}
    .workflowx-lorax-detail{width:min(900px,calc(100vw - 64px));max-height:min(780px,calc(100vh - 64px));background:#17191d;color:#e8ebef;border:1px solid #4b5563;border-radius:8px;box-shadow:0 24px 90px rgba(0,0,0,.62);display:grid;grid-template-rows:auto 1fr auto;overflow:hidden;font:13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .workflowx-lorax-detail-head{display:flex;align-items:flex-start;gap:12px;padding:14px 16px;border-bottom:1px solid #30343b;background:#202328}
    .workflowx-lorax-detail-title{font-size:18px;font-weight:750;line-height:1.2;min-width:0;overflow:hidden;text-overflow:ellipsis}
    .workflowx-lorax-detail-sub{margin-top:4px;color:#a7afba;word-break:break-word}
    .workflowx-lorax-detail-close{margin-left:auto;width:32px;height:32px;border:1px solid #4e5560;border-radius:6px;background:#242830;color:#d5d9df;cursor:pointer}
    .workflowx-lorax-detail-body{overflow:auto;padding:14px 16px;display:grid;grid-template-columns:minmax(220px,300px) 1fr;gap:16px}
    .workflowx-lorax-detail-preview{width:100%;aspect-ratio:1/1.2;border-radius:7px;background:#0d0f12;border:1px solid #30343b;object-fit:cover}
    .workflowx-lorax-detail-grid{display:grid;grid-template-columns:130px 1fr;gap:8px 12px;align-content:start}
    .workflowx-lorax-detail-label{color:#98a3b1}
    .workflowx-lorax-detail-value{color:#eef2f6;word-break:break-word}
    .workflowx-lorax-detail-section{grid-column:1/-1;border-top:1px solid #30343b;margin-top:8px;padding-top:10px}
    .workflowx-lorax-detail-section h3{font-size:13px;margin:0 0 8px;color:#cbd4df}
    .workflowx-lorax-detail-tags{display:flex;flex-wrap:wrap;gap:6px}
    .workflowx-lorax-detail-text{white-space:pre-wrap;color:#d7dde5;line-height:1.42}
    .workflowx-lorax-detail-text.rich{white-space:normal}
    .workflowx-lorax-detail-text.rich p{margin:0 0 10px}
    .workflowx-lorax-detail-text.rich p:last-child{margin-bottom:0}
    .workflowx-lorax-detail-text.rich ul,.workflowx-lorax-detail-text.rich ol{margin:6px 0 10px 20px;padding:0}
    .workflowx-lorax-detail-text.rich li{margin:4px 0}
    .workflowx-lorax-detail-text.rich pre{white-space:pre-wrap;background:#11151b;border:1px solid #30343b;border-radius:6px;padding:9px;overflow:auto}
    .workflowx-lorax-detail-text.rich code{background:#202630;border:1px solid #30343b;border-radius:4px;padding:1px 4px}
    .workflowx-lorax-detail-text.rich pre code{background:transparent;border:0;padding:0}
    .workflowx-lorax-detail-text.rich blockquote{margin:8px 0;padding:6px 10px;border-left:3px solid #4f6fa4;color:#cbd4df;background:#151a21}
    .workflowx-lorax-detail-text.rich a{color:#8eb5ff;text-decoration:none}
    .workflowx-lorax-detail-text.rich a:hover{text-decoration:underline}
    .workflowx-lorax-detail-actions{display:flex;gap:8px;justify-content:flex-end;padding:12px 16px;border-top:1px solid #30343b;background:#202328}
    .workflowx-lorax-detail-actions button,.workflowx-lorax-detail-actions a{height:32px;border-radius:6px;border:1px solid #4e5560;background:#252d37;color:#e8eef7;padding:0 12px;text-decoration:none;display:inline-flex;align-items:center;cursor:pointer}
    .workflowx-lorax-detail-actions .primary{background:#315a94;border-color:#5783c4;color:#fff}
    .workflowx-lorax-toast{position:fixed;z-index:10003;left:50%;bottom:32px;transform:translateX(-50%);max-width:min(560px,calc(100vw - 32px));padding:9px 14px;border:1px solid #536174;border-radius:6px;background:#20262f;color:#edf2f8;box-shadow:0 8px 28px rgba(0,0,0,.45);font:13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .workflowx-lorax-toast.error{border-color:#9b5050;background:#3a2224;color:#ffe4e4}
    @media (max-width:760px){
      .workflowx-lorax-body{grid-template-columns:1fr}
      .workflowx-lorax-top{grid-template-columns:1fr auto auto}
      .workflowx-lorax-strict{grid-column:1/-1;grid-row:2;justify-content:flex-start}
      .workflowx-lorax-tree{max-height:190px;border-right:0;border-bottom:1px solid #30343b}
      .workflowx-lorax-detail-body{grid-template-columns:1fr}
    }
  `;
  document.head.appendChild(style);
}

function showLoraXToast(message, isError = false) {
  ensureStyles();
  document.querySelector(".workflowx-lorax-toast")?.remove();
  const toast = document.createElement("div");
  toast.className = `workflowx-lorax-toast${isError ? " error" : ""}`;
  toast.textContent = String(message || "");
  document.body.appendChild(toast);
  window.setTimeout(() => toast.remove(), isError ? 6000 : 3600);
}

function countFolderItems(items, folder) {
  return items.filter((item) => itemMatchesFolder(item, folder)).length;
}

function renderTreeNode(container, node, items, selectedFolder, expandedFolders, onSelect, depth = 0) {
  const children = sortedChildren(node);
  for (const child of children) {
    const hasChildren = child.children.size > 0;
    const expanded = expandedFolders.has(child.path);
    const row = document.createElement("div");
    row.className = "workflowx-lorax-tree-row";
    row.style.paddingLeft = `${depth * 12}px`;

    const expand = document.createElement("button");
    expand.className = "workflowx-lorax-expand";
    expand.type = "button";
    expand.textContent = hasChildren ? (expanded ? "v" : ">") : "";
    expand.title = hasChildren ? (expanded ? "Collapse" : "Expand") : "";
    expand.disabled = !hasChildren;
    expand.addEventListener("click", (event) => {
      event.stopPropagation();
      if (expandedFolders.has(child.path)) expandedFolders.delete(child.path);
      else expandedFolders.add(child.path);
      onSelect(selectedFolder);
    });
    row.appendChild(expand);

    const button = document.createElement("button");
    button.className = `workflowx-lorax-folder${child.path === selectedFolder ? " active" : ""}`;
    button.type = "button";
    button.title = child.path;
    const name = document.createElement("span");
    name.className = "workflowx-lorax-folder-name";
    name.textContent = child.name;
    const count = document.createElement("span");
    count.className = "workflowx-lorax-folder-count";
    count.textContent = String(countFolderItems(items, child.path));
    button.append(name, count);
    button.addEventListener("click", () => onSelect(child.path));
    row.appendChild(button);
    container.appendChild(row);

    if (hasChildren && expanded) renderTreeNode(container, child, items, selectedFolder, expandedFolders, onSelect, depth + 1);
  }
}

function renderFolderTree(tree, container, items, selectedFolder, expandedFolders, onSelect) {
  container.textContent = "";
  const rootRow = document.createElement("div");
  rootRow.className = "workflowx-lorax-tree-row";
  const spacer = document.createElement("span");
  spacer.className = "workflowx-lorax-expand";
  rootRow.appendChild(spacer);
  const rootButton = document.createElement("button");
  rootButton.className = `workflowx-lorax-folder${selectedFolder === "" ? " active" : ""}`;
  rootButton.type = "button";
  rootButton.title = "Root";
  const rootName = document.createElement("span");
  rootName.className = "workflowx-lorax-folder-name";
  rootName.textContent = "Root";
  const rootCount = document.createElement("span");
  rootCount.className = "workflowx-lorax-folder-count";
  rootCount.textContent = String(items.length);
  rootButton.append(rootName, rootCount);
  rootButton.addEventListener("click", () => onSelect(""));
  rootRow.appendChild(rootButton);
  container.appendChild(rootRow);
  renderTreeNode(container, tree, items, selectedFolder, expandedFolders, onSelect);
}

function createPreviewElement(item, className = "") {
  const url = item.preview_url || item.metadata?.preview_url || "";
  if (!url) {
    const ph = document.createElement("div");
    ph.className = className || "workflowx-lorax-no-thumb";
    ph.textContent = "LoRA";
    return ph;
  }
  if (VIDEO_EXT_RE.test(url)) {
    const video = document.createElement("video");
    video.className = className || "workflowx-lorax-video";
    video.src = url;
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    video.addEventListener("mouseenter", () => video.play().catch(() => {}));
    video.addEventListener("mouseleave", () => video.pause());
    return video;
  }
  const img = document.createElement("img");
  img.className = className || "workflowx-lorax-thumb";
  img.loading = "lazy";
  img.src = url;
  img.alt = "";
  return img;
}

function createCard(item, onSelect, onView) {
  const card = document.createElement("div");
  card.className = "workflowx-lorax-card";
  card.tabIndex = 0;
  card.role = "button";
  card.title = item.load_name;

  card.appendChild(createPreviewElement(item));

  const body = document.createElement("div");
  body.className = "workflowx-lorax-card-body";
  const filename = document.createElement("div");
  filename.className = "workflowx-lorax-filename";
  filename.textContent = item.filename || normalizePath(item.load_name).split("/").pop() || item.load_name;
  body.appendChild(filename);
  const name = document.createElement("div");
  name.className = "workflowx-lorax-name";
  name.textContent = item.display_name || item.file_stem || item.load_name;
  body.appendChild(name);

  const path = document.createElement("div");
  path.className = "workflowx-lorax-path";
  path.textContent = item.load_name;
  body.appendChild(path);

  const meta = document.createElement("div");
  meta.className = "workflowx-lorax-meta";
  const chips = [item.base_model, item.favorite ? "Favorite" : "", item.update_available ? "Update" : "", ...item.tags]
    .filter((value) => value && lower(value).replace(/[^a-z0-9]+/g, "") !== "lora")
    .slice(0, 5);
  for (const value of chips) {
    const chip = document.createElement("span");
    chip.className = "workflowx-lorax-chip";
    chip.textContent = value;
    meta.appendChild(chip);
  }
  body.appendChild(meta);
  card.appendChild(body);

  const actions = document.createElement("div");
  actions.className = "workflowx-lorax-card-actions";
  const view = document.createElement("button");
  view.className = "workflowx-lorax-view";
  view.type = "button";
  view.textContent = "View";
  view.title = "View LoRA details";
  view.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onView(item);
  });
  actions.appendChild(view);
  card.appendChild(actions);

  card.addEventListener("click", () => onSelect(item));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(item);
    }
  });
  return card;
}

function managerFilePath(item) {
  return normalizePath(item.metadata?.file_path || item.full_path);
}

async function fetchManagerDetails(item) {
  const filePath = managerFilePath(item);
  if (!filePath) return { metadata: null, description: "" };
  const params = new URLSearchParams({ file_path: filePath });
  const [metadataData, descriptionData] = await Promise.all([
    fetchJson(`${LORA_MANAGER_METADATA_ROUTE}?${params}`).catch(() => null),
    fetchJson(`${LORA_MANAGER_DESCRIPTION_ROUTE}?${params}`).catch(() => null),
  ]);
  return {
    metadata: metadataData?.success ? metadataData.metadata : null,
    description: descriptionData?.success ? String(descriptionData.description || "") : "",
  };
}

function detailsMetadata(item, fetchedMetadata) {
  const base = item.metadata || {};
  const civitai = fetchedMetadata?.civitai || base.civitai || fetchedMetadata || {};
  return {
    ...base,
    ...(fetchedMetadata && typeof fetchedMetadata === "object" ? fetchedMetadata : {}),
    civitai,
  };
}

function civitaiUrl(metadata) {
  const modelId = metadata?.civitai?.modelId || metadata?.modelId;
  const versionId = metadata?.civitai?.id || metadata?.id;
  if (!modelId) return "";
  const suffix = versionId ? `?modelVersionId=${encodeURIComponent(versionId)}` : "";
  return `https://civitai.com/models/${encodeURIComponent(modelId)}${suffix}`;
}

function formatFileSize(size) {
  const value = Number(size);
  if (!Number.isFinite(value) || value <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function addDetailRow(grid, label, value) {
  if (value === undefined || value === null || value === "") return;
  const labelEl = document.createElement("div");
  labelEl.className = "workflowx-lorax-detail-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("div");
  valueEl.className = "workflowx-lorax-detail-value";
  valueEl.textContent = String(value);
  grid.append(labelEl, valueEl);
}

function addChipSection(grid, title, values) {
  const unique = uniqueStrings(values);
  if (!unique.length) return;
  const section = document.createElement("div");
  section.className = "workflowx-lorax-detail-section";
  const h = document.createElement("h3");
  h.textContent = title;
  const wrap = document.createElement("div");
  wrap.className = "workflowx-lorax-detail-tags";
  for (const value of unique) {
    const chip = document.createElement("span");
    chip.className = "workflowx-lorax-chip";
    chip.textContent = value;
    wrap.appendChild(chip);
  }
  section.append(h, wrap);
  grid.appendChild(section);
}

const RICH_TEXT_TAGS = new Set(["a", "b", "blockquote", "br", "code", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "li", "ol", "p", "pre", "s", "span", "strong", "u", "ul"]);

function textSectionValue(value) {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) return uniqueStrings(value).join("\n");
  if (typeof value === "object") {
    const keys = Object.keys(value);
    if (!keys.length) return "";
    for (const key of ["html", "description", "content", "text", "markdown", "usage_tips", "notes"]) {
      if (typeof value[key] === "string" && value[key].trim()) return value[key].trim();
    }
    return JSON.stringify(value, null, 2);
  }
  return String(value).trim();
}

function hasHtmlMarkup(text) {
  return /<\/?(?:a|b|blockquote|br|code|div|em|h[1-6]|hr|i|li|ol|p|pre|s|span|strong|u|ul)(?:\s|>|\/)/i.test(text);
}

function safeHref(value) {
  try {
    const url = new URL(value, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function sanitizeRichTextNode(sourceNode) {
  if (sourceNode.nodeType === Node.TEXT_NODE) return document.createTextNode(sourceNode.textContent || "");
  if (sourceNode.nodeType !== Node.ELEMENT_NODE) return document.createDocumentFragment();

  const tag = sourceNode.nodeName.toLowerCase();
  if (["script", "style", "template", "iframe", "object", "embed"].includes(tag)) return document.createDocumentFragment();

  const children = document.createDocumentFragment();
  for (const child of sourceNode.childNodes) children.appendChild(sanitizeRichTextNode(child));

  if (!RICH_TEXT_TAGS.has(tag)) return children;

  const el = document.createElement(tag);
  if (tag === "a") {
    const href = safeHref(sourceNode.getAttribute("href") || "");
    if (!href) return children;
    el.href = href;
    el.target = "_blank";
    el.rel = "noreferrer";
  }
  el.appendChild(children);
  return el;
}

function renderTextSectionContent(container, text) {
  if (!hasHtmlMarkup(text)) {
    container.textContent = text;
    return;
  }

  container.classList.add("rich");
  const parsed = new DOMParser().parseFromString(text, "text/html");
  const fragment = document.createDocumentFragment();
  for (const child of parsed.body.childNodes) fragment.appendChild(sanitizeRichTextNode(child));
  container.appendChild(fragment);
}

function addTextSection(grid, title, value) {
  const text = textSectionValue(value);
  if (!text) return;
  const section = document.createElement("div");
  section.className = "workflowx-lorax-detail-section";
  const h = document.createElement("h3");
  h.textContent = title;
  const content = document.createElement("div");
  content.className = "workflowx-lorax-detail-text";
  renderTextSectionContent(content, text);
  section.append(h, content);
  grid.appendChild(section);
}

async function openDetailsModal(item, onSelect) {
  ensureStyles();
  const backdrop = document.createElement("div");
  backdrop.className = "workflowx-lorax-detail-backdrop";
  const modal = document.createElement("div");
  modal.className = "workflowx-lorax-detail";
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);

  const closeDetails = () => backdrop.remove();
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) closeDetails();
  });

  const head = document.createElement("div");
  head.className = "workflowx-lorax-detail-head";
  const titleWrap = document.createElement("div");
  titleWrap.style.minWidth = "0";
  const title = document.createElement("div");
  title.className = "workflowx-lorax-detail-title";
  title.textContent = item.display_name || item.file_stem || item.load_name;
  const sub = document.createElement("div");
  sub.className = "workflowx-lorax-detail-sub";
  sub.textContent = item.load_name;
  titleWrap.append(title, sub);
  const close = document.createElement("button");
  close.className = "workflowx-lorax-detail-close";
  close.type = "button";
  close.textContent = "x";
  close.title = "Close";
  close.addEventListener("click", closeDetails);
  head.append(titleWrap, close);

  const body = document.createElement("div");
  body.className = "workflowx-lorax-detail-body";
  const loading = document.createElement("div");
  loading.className = "workflowx-lorax-empty";
  loading.textContent = "Loading details...";
  body.appendChild(loading);

  const actions = document.createElement("div");
  actions.className = "workflowx-lorax-detail-actions";
  let select = null;
  if (typeof onSelect === "function") {
    select = document.createElement("button");
    select.className = "primary";
    select.type = "button";
    select.textContent = "Select";
    select.addEventListener("click", async () => {
      select.disabled = true;
      const selected = await onSelect(item);
      if (selected !== false) closeDetails();
      else select.disabled = false;
    });
    actions.appendChild(select);
  }
  modal.append(head, body, actions);

  const fetched = await fetchManagerDetails(item);
  const metadata = detailsMetadata(item, fetched.metadata);
  const tags = uniqueStrings([...(item.tags || []), ...(metadata.tags || []), ...(item.auto_tags || []), ...(metadata.auto_tags || [])]);
  const words = uniqueStrings([...trainedWords(item), ...trainedWords(metadata)]);
  const link = civitaiUrl(metadata);

  body.textContent = "";
  const previewWrap = document.createElement("div");
  previewWrap.appendChild(createPreviewElement(item, "workflowx-lorax-detail-preview"));
  body.appendChild(previewWrap);

  const grid = document.createElement("div");
  grid.className = "workflowx-lorax-detail-grid";
  addDetailRow(grid, "Model name", metadata.model_name || item.model_name || item.display_name);
  addDetailRow(grid, "File name", metadata.file_name || item.filename);
  addDetailRow(grid, "Load name", item.load_name);
  addDetailRow(grid, "Folder", metadata.folder || item.folder || "Root");
  addDetailRow(grid, "Path", metadata.file_path || item.full_path);
  addDetailRow(grid, "Base model", metadata.base_model || item.base_model);
  addDetailRow(grid, "Type", metadata.sub_type || item.sub_type || "LoRA");
  addDetailRow(grid, "Creator", creatorName(metadata) || item.creator);
  addDetailRow(grid, "Favorite", metadata.favorite || item.favorite ? "Yes" : "No");
  addDetailRow(grid, "Update", metadata.update_available || item.update_available ? "Available" : "No");
  addDetailRow(grid, "Size", formatFileSize(metadata.file_size));
  addChipSection(grid, "Tags", tags);
  addChipSection(grid, "Trained words", words);
  addTextSection(grid, "Usage tips", metadata.usage_tips || metadata.notes);
  addTextSection(grid, "Description", fetched.description || metadata.description);
  body.appendChild(grid);

  if (link) {
    const open = document.createElement("a");
    open.href = link;
    open.target = "_blank";
    open.rel = "noreferrer";
    open.textContent = "Open Civitai";
    actions.insertBefore(open, select);
  }
}

async function openPicker(onSelect) {
  ensureStyles();
  activePicker?.remove?.();

  const backdrop = document.createElement("div");
  backdrop.className = "workflowx-lorax-backdrop";
  const picker = document.createElement("div");
  picker.className = "workflowx-lorax-picker";

  const top = document.createElement("div");
  top.className = "workflowx-lorax-top";
  const search = document.createElement("input");
  search.className = "workflowx-lorax-search";
  search.placeholder = "Search name, tag, path";
  const strictLabel = document.createElement("label");
  strictLabel.className = "workflowx-lorax-strict";
  strictLabel.title = "Search only LoRA name, path, and actual base model";
  const strictSearch = document.createElement("input");
  strictSearch.type = "checkbox";
  strictSearch.checked = false;
  const strictText = document.createElement("span");
  strictText.textContent = "Strict search";
  strictLabel.append(strictSearch, strictText);
  const refresh = document.createElement("button");
  refresh.className = "workflowx-lorax-refresh";
  refresh.type = "button";
  refresh.title = "Refresh LoRAs";
  refresh.setAttribute("aria-label", "Refresh LoRAs");
  const refreshIcon = document.createElement("span");
  refreshIcon.textContent = "\u21bb";
  refresh.appendChild(refreshIcon);
  const close = document.createElement("button");
  close.className = "workflowx-lorax-close";
  close.type = "button";
  close.textContent = "x";
  top.append(search, strictLabel, refresh, close);

  const body = document.createElement("div");
  body.className = "workflowx-lorax-body";
  const tree = document.createElement("div");
  tree.className = "workflowx-lorax-tree";
  const results = document.createElement("div");
  results.className = "workflowx-lorax-results";
  body.append(tree, results);
  picker.append(top, body);
  backdrop.appendChild(picker);
  document.body.appendChild(backdrop);
  activePicker = backdrop;

  let allItems = [];
  let treeRoot = createTreeRoot();
  let selectedFolder = "";
  let selectionBusy = false;
  const expandedFolders = new Set([""]);

  function closePicker() {
    backdrop.remove();
    if (activePicker === backdrop) activePicker = null;
  }

  async function selectAndClose(item) {
    if (selectionBusy) return false;
    selectionBusy = true;
    search.disabled = true;
    strictSearch.disabled = true;
    refresh.disabled = true;
    close.disabled = true;
    results.setAttribute("aria-busy", "true");
    try {
      const identified = await ensureItemIdentity(item);
      await onSelect(identified);
      closePicker();
      return true;
    } catch (error) {
      console.warn("[WorkflowX LoraX] Failed to identify selected LoRA", error);
      showLoraXToast(`Could not hash LoRA: ${error.message || error}`, true);
      return false;
    } finally {
      selectionBusy = false;
      search.disabled = false;
      strictSearch.disabled = false;
      refresh.disabled = false;
      close.disabled = false;
      results.removeAttribute("aria-busy");
    }
  }

  function render() {
    const query = search.value || "";
    const strict = strictSearch.checked;
    const filtered = allItems
      .filter((item) => itemMatchesFolder(item, selectedFolder))
      .filter((item) => itemMatchesQuery(item, query, strict));
    const items = filtered.slice(0, 500);

    renderFolderTree(treeRoot, tree, allItems, selectedFolder, expandedFolders, (folder) => {
      selectedFolder = folder;
      render();
    });

    results.textContent = "";
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "workflowx-lorax-empty";
      empty.textContent = "No LoRAs found";
      results.appendChild(empty);
      return;
    }
    for (const item of items) {
      results.appendChild(createCard(item, selectAndClose, (selected) => openDetailsModal(selected, selectAndClose)));
    }
    if (filtered.length > items.length) {
      const more = document.createElement("div");
      more.className = "workflowx-lorax-empty";
      more.textContent = `Showing first ${items.length} of ${filtered.length} matches`;
      results.appendChild(more);
    }
  }

  async function reloadCatalog() {
    if (refresh.disabled) return;
    refresh.disabled = true;
    refresh.classList.add("loading");
    tree.innerHTML = '<div class="workflowx-lorax-empty">Refreshing LoRAs...</div>';
    results.innerHTML = '<div class="workflowx-lorax-empty">Refreshing LoRAs...</div>';
    try {
      const catalog = await refreshCatalog();
      if (!backdrop.isConnected) return;
      allItems = catalog.items || [];
      treeRoot = catalog.tree || buildTreeFromItems(allItems);
      if (selectedFolder && !allItems.some((item) => itemMatchesFolder(item, selectedFolder))) selectedFolder = "";
      render();
    } catch (error) {
      console.warn("[WorkflowX LoraX] Failed to refresh LoRA catalog", error);
      if (backdrop.isConnected) {
        results.innerHTML = '<div class="workflowx-lorax-empty">Could not refresh LoRAs</div>';
      }
    } finally {
      refresh.disabled = false;
      refresh.classList.remove("loading");
    }
  }

  close.addEventListener("click", closePicker);
  refresh.addEventListener("click", reloadCatalog);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) closePicker();
  });
  search.addEventListener("input", render);
  strictSearch.addEventListener("change", render);
  search.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePicker();
  });

  results.innerHTML = '<div class="workflowx-lorax-empty">Loading LoRAs...</div>';
  try {
    const catalog = await loadCatalog();
    allItems = catalog.items || [];
    treeRoot = catalog.tree || buildTreeFromItems(allItems);
  } catch (error) {
    console.warn("[WorkflowX LoraX] Failed to load LoRA catalog", error);
    allItems = [];
    treeRoot = createTreeRoot();
  }
  render();
  search.focus();
}

function defaultRowValue(item = null) {
  return {
    on: true,
    load_name: item?.load_name || null,
    lora: item?.load_name || null,
    display_name: item?.display_name || item?.file_stem || item?.load_name || null,
    path: item?.folder || null,
    sha256: itemSha256(item),
    file_size: itemFileSize(item),
    strength: 1,
    metadata: item
      ? {
          preview_url: item.preview_url || "",
          tags: item.tags || [],
          auto_tags: item.auto_tags || [],
          base_model: item.base_model || "",
          model_name: item.model_name || "",
          civitai: item.metadata?.civitai || {},
          trigger_words: item.trained_words || [],
        }
      : {},
    trigger_words: item?.trained_words || [],
  };
}

function sanitizeRowValue(value) {
  const row = defaultRowValue();
  if (!value || typeof value !== "object") return row;
  const loadName = value.load_name || value.loadName || value.lora || value.name || null;
  row.on = asBool(value.on ?? value.enabled ?? value.active, true);
  row.load_name = loadName;
  row.lora = loadName;
  row.display_name = value.display_name || value.displayName || value.model_name || value.name || loadName;
  row.path = value.path || value.folder || null;
  row.sha256 = normalizeSha256(value.sha256 || value.hash || value.metadata?.sha256);
  row.file_size = itemFileSize(value);
  const strength = Number(value.strength ?? value.modelStrength ?? value.model_strength ?? value.strength_model ?? 1);
  row.strength = Number.isFinite(strength) ? strength : 1;
  row.metadata = value.metadata && typeof value.metadata === "object" ? value.metadata : {};
  row.trigger_words = Array.isArray(value.trigger_words) ? value.trigger_words : trainedWords(value);
  return row;
}

function rowDetailsFallback(value) {
  const row = sanitizeRowValue(value);
  const loadName = normalizePath(row.load_name);
  const filename = loadName.split("/").pop() || loadName;
  const fileStem = stripExt(filename);
  const metadata = row.metadata || {};
  return {
    load_name: loadName,
    folder: normalizePath(row.path || loadName.slice(0, Math.max(0, loadName.lastIndexOf("/")))),
    filename,
    file_stem: fileStem,
    full_path: normalizePath(metadata.file_path),
    sha256: row.sha256,
    file_size: row.file_size,
    canonical_display_name: fileStem,
    display_name: row.display_name || metadata.model_name || fileStem,
    model_name: normalizePath(metadata.model_name),
    base_model: normalizePath(metadata.base_model),
    tags: compactArray(metadata.tags),
    auto_tags: compactArray(metadata.auto_tags),
    trained_words: uniqueStrings([...row.trigger_words, ...trainedWords(metadata)]),
    preview_url: normalizePath(metadata.preview_url),
    favorite: Boolean(metadata.favorite),
    update_available: Boolean(metadata.update_available),
    sub_type: normalizePath(metadata.sub_type),
    creator: creatorName(metadata),
    metadata,
  };
}

async function resolveRowDetailsItem(value) {
  const fallback = rowDetailsFallback(value);
  if (!fallback.load_name) return fallback;
  try {
    const key = canonicalKey(fallback);
    const canonicalItems = await loadCanonicalItems();
    const match = canonicalItems.map(normalizeCanonical).find((item) => canonicalKey(item) === key);
    if (!match) return fallback;
    return {
      ...fallback,
      ...match,
      display_name: fallback.display_name || match.display_name,
      model_name: fallback.model_name,
      base_model: fallback.base_model,
      tags: fallback.tags,
      auto_tags: fallback.auto_tags,
      trained_words: fallback.trained_words,
      preview_url: fallback.preview_url,
      favorite: fallback.favorite,
      update_available: fallback.update_available,
      sub_type: fallback.sub_type,
      creator: fallback.creator,
      metadata: fallback.metadata,
    };
  } catch {
    return fallback;
  }
}

async function openRowDetails(row) {
  if (!row?.value || row.__loraxDetailsOpening) return;
  row.__loraxDetailsOpening = true;
  try {
    const item = await resolveRowDetailsItem(row.value);
    if (item.load_name) await openDetailsModal(item);
  } finally {
    row.__loraxDetailsOpening = false;
  }
}

function rowLoadName(value) {
  if (!value || typeof value !== "object") return "";
  const loadName = value.load_name ?? value.loadName ?? value.lora;
  if (loadName !== undefined && loadName !== null && loadName !== "") return normalizePath(loadName);
  const legacyNameLooksLikeRow =
    "strength" in value || "modelStrength" in value || "model_strength" in value || "strength_model" in value;
  if (!legacyNameLooksLikeRow) return "";
  const legacyName = value.name ?? "";
  return normalizePath(legacyName);
}

function isRowValue(value) {
  const loadName = rowLoadName(value);
  return Boolean(loadName && loadName.toLowerCase() !== "none");
}

function rowRestoreKey(value) {
  const row = sanitizeRowValue(value);
  return JSON.stringify({
    on: row.on !== false,
    load_name: row.load_name || "",
    strength: Number(row.strength ?? 1),
  });
}

function restoredRowValues(widgetValues) {
  if (!Array.isArray(widgetValues)) return [];
  const rows = widgetValues.filter(isRowValue).map((value) => sanitizeRowValue(value));
  while (rows.length > 1 && rowRestoreKey(rows.at(-1)) === rowRestoreKey(rows[0])) rows.pop();
  return rows;
}

function drawToggle(ctx, x, y, value) {
  ctx.beginPath();
  ctx.arc(x + 9, y + 12, 8, 0, Math.PI * 2);
  ctx.fillStyle = value ? "#8fa8e8" : "#555b64";
  ctx.fill();
}

function drawTextBox(ctx, x, y, w, text, align = "center") {
  ctx.strokeStyle = "#707782";
  ctx.fillStyle = "#2a2e35";
  ctx.beginPath();
  ctx.roundRect?.(x, y + 2, w, ROW_H - 4, 8);
  if (!ctx.roundRect) ctx.rect(x, y + 2, w, ROW_H - 4);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#e7eaee";
  ctx.textAlign = align;
  ctx.textBaseline = "middle";
  ctx.fillText(text, align === "left" ? x + 8 : x + w / 2, y + ROW_H / 2);
}

function drawStrengthControl(ctx, x, y, value) {
  drawTextBox(ctx, x, y, 28, "<");
  drawTextBox(ctx, x + 30, y, 70, Number(value ?? 1).toFixed(2));
  drawTextBox(ctx, x + 102, y, 28, ">");
}

function drawRemoveControl(ctx, x, y) {
  drawTextBox(ctx, x, y, REMOVE_W, "x");
}

function fitText(ctx, text, width) {
  const raw = String(text || "None");
  if (ctx.measureText(raw).width <= width) return raw;
  let out = raw;
  while (out.length > 4 && ctx.measureText(`${out.slice(0, -1)}...`).width > width) out = out.slice(0, -1);
  return `${out.slice(0, -1)}...`;
}

function createHeaderWidget() {
  return {
    name: "lorax_header",
    type: "custom",
    __lorax: true,
    value: { type: "header" },
    computeSize: () => [MIN_W, HEADER_H],
    serializeValue: () => ({ type: "header" }),
    draw(ctx, node, width, y) {
      this.last_y = y;
      ctx.save();
      ctx.globalAlpha = app.canvas?.editor_alpha ?? 1;
      drawToggle(ctx, 10, y - 1, allRowsOn(node));
      ctx.fillStyle = "#aeb6c1";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText("Toggle All", 38, y + HEADER_H / 2);
      drawTextBox(ctx, REMAP_X, y - 1, REMAP_W, node.__loraxRemapping ? "..." : "\u21bb");
      ctx.textAlign = "center";
      ctx.fillText("Strength", width - 124, y + HEADER_H / 2);
      ctx.fillText("Remove", width - 28, y + HEADER_H / 2);
      if (node.__loraxRemapHover) {
        const tooltip = "Remap moved LoRAs";
        ctx.font = "12px sans-serif";
        const tooltipWidth = ctx.measureText(tooltip).width + 16;
        ctx.fillStyle = "#11151a";
        ctx.strokeStyle = "#596270";
        ctx.beginPath();
        ctx.roundRect?.(REMAP_X, y + HEADER_H + 2, tooltipWidth, 24, 5);
        if (!ctx.roundRect) ctx.rect(REMAP_X, y + HEADER_H + 2, tooltipWidth, 24);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = "#eef2f6";
        ctx.textAlign = "left";
        ctx.fillText(tooltip, REMAP_X + 8, y + HEADER_H + 14);
      }
      ctx.restore();
    },
    mouse(event, pos, node) {
      if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
      if (pos[0] < 112) {
        toggleAllRows(node);
        return true;
      }
      if (pos[0] >= REMAP_X && pos[0] <= REMAP_X + REMAP_W) {
        remapRows(node);
        return true;
      }
      return false;
    },
  };
}

function createRowWidget(name, value) {
  return {
    name,
    type: "custom",
    __lorax: true,
    __loraxRow: true,
    value: sanitizeRowValue(value),
    computeSize: () => [MIN_W, ROW_H],
    serializeValue() {
      return sanitizeRowValue(this.value);
    },
    draw(ctx, node, width, y) {
      this.last_y = y;
      ctx.save();
      ctx.globalAlpha = app.canvas?.editor_alpha ?? 1;
      ctx.fillStyle = "#252930";
      ctx.strokeStyle = "#707782";
      ctx.beginPath();
      ctx.roundRect?.(10, y + 2, width - 20, ROW_H - 4, 10);
      if (!ctx.roundRect) ctx.rect(10, y + 2, width - 20, ROW_H - 4);
      ctx.fill();
      ctx.stroke();
      drawToggle(ctx, 18, y, this.value.on);

      ctx.fillStyle = this.value.on ? "#f1f4f7" : "#8a919b";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      const removeX = width - 10 - REMOVE_W;
      const strengthX = removeX - CONTROL_GAP - STRENGTH_W;
      const labelWidth = Math.max(100, strengthX - 56);
      const label = this.value.display_name || this.value.lora || this.value.load_name || "None";
      ctx.fillText(fitText(ctx, label, labelWidth), 48, y + ROW_H / 2);
      drawStrengthControl(ctx, strengthX, y, this.value.strength);
      drawRemoveControl(ctx, removeX, y);
      ctx.restore();
    },
    mouse(event, pos, node) {
      if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
      const width = node.size?.[0] || MIN_W;
      const x = Number(pos?.[0] || 0);
      const removeX = width - 10 - REMOVE_W;
      const strengthX = removeX - CONTROL_GAP - STRENGTH_W;

      if (event.button === 2) {
        rowMenu(node, this, event);
        return true;
      }
      if (x < 44) {
        this.value.on = !this.value.on;
        markDirty(node);
        return true;
      }
      if (x >= strengthX && x <= strengthX + 28) {
        stepStrength(node, this, -1);
        return true;
      }
      if (x >= strengthX + 30 && x <= strengthX + 100) {
        promptStrength(node, this, event);
        return true;
      }
      if (x >= strengthX + 102 && x <= strengthX + STRENGTH_W) {
        stepStrength(node, this, 1);
        return true;
      }
      if (x >= removeX && x <= removeX + REMOVE_W) {
        removeRow(node, this);
        return true;
      }
      openRowDetails(this);
      return true;
    },
  };
}

function rowWidgets(node) {
  return (node.widgets || []).filter((widget) => widget.__loraxRow);
}

function catalogItemByLoadName(items, loadName) {
  const key = lower(loadName);
  return (items || []).find((item) => lower(item?.load_name) === key) || null;
}

function updateRowIdentity(row, entry, catalogItems) {
  if (!row?.value || !entry) return;
  const old = sanitizeRowValue(row.value);
  const catalogItem = catalogItemByLoadName(catalogItems, entry.load_name);
  let next = applyIdentity(old, catalogItem || entry);
  if (catalogItem) {
    const fresh = defaultRowValue(catalogItem);
    next = {
      ...next,
      display_name: fresh.display_name,
      path: fresh.path,
      metadata: fresh.metadata,
      sha256: fresh.sha256 || next.sha256,
      file_size: fresh.file_size || next.file_size,
    };
  }
  next.on = old.on;
  next.strength = old.strength;
  next.trigger_words = old.trigger_words?.length ? old.trigger_words : catalogItem?.trained_words || [];
  row.value = Object.assign(row.value, next);
}

async function remapRows(node) {
  if (node.__loraxRemapping) return;
  const rows = rowWidgets(node);
  if (!rows.length) {
    showLoraXToast("No LoRAs to remap");
    return;
  }

  const originalSize = node.size ? [Number(node.size[0]), Number(node.size[1])] : null;
  node.__loraxRemapping = true;
  node.__loraxRemapHover = false;
  markDirty(node);
  try {
    const catalog = await refreshCatalog();
    const items = catalog.items || [];
    const pending = [];
    const counts = { remapped: 0, unchanged: 0, unresolved: 0, duplicates: 0 };

    for (const row of rows) {
      const value = sanitizeRowValue(row.value);
      const current = catalogItemByLoadName(items, value.load_name);
      const storedHash = normalizeSha256(value.sha256);
      if (storedHash) {
        const matches = sortedHashMatches(items, storedHash);
        const currentHash = itemSha256(current);
        const currentMatches = Boolean(currentHash && currentHash === storedHash);
        const chosen = currentMatches ? current : !current ? matches[0] : null;
        if (chosen) {
          updateRowIdentity(row, chosen, items);
          counts[currentMatches ? "unchanged" : "remapped"] += 1;
          counts.duplicates += Math.max(0, matches.length - 1);
          continue;
        }
      } else if (current && itemSha256(current)) {
        updateRowIdentity(row, current, items);
        counts.unchanged += 1;
        continue;
      }
      pending.push({
        row,
        request: {
          row_id: row.name,
          load_name: value.load_name,
          sha256: storedHash,
          file_size: value.file_size,
        },
      });
    }

    if (pending.length) {
      const response = await postJson(LORAX_REMAP_ROUTE, { items: pending.map((item) => item.request) });
      const byRowId = new Map(pending.map((item) => [item.request.row_id, item.row]));
      for (const result of response.items || []) {
        const status = ["remapped", "unchanged", "unresolved"].includes(result.status) ? result.status : "unresolved";
        counts[status] += 1;
        counts.duplicates += Math.max(0, Number(result.duplicate_count || 0) - 1);
        if (result.entry && status !== "unresolved") updateRowIdentity(byRowId.get(result.row_id), result.entry, items);
      }
    }

    const duplicateText = counts.duplicates ? `, ${counts.duplicates} duplicate match${counts.duplicates === 1 ? "" : "es"}` : "";
    showLoraXToast(`${counts.remapped} remapped, ${counts.unchanged} unchanged, ${counts.unresolved} unresolved${duplicateText}`);
  } catch (error) {
    console.warn("[WorkflowX LoraX] Remapping failed", error);
    showLoraXToast(`LoRA remapping failed: ${error.message || error}`, true);
  } finally {
    node.__loraxRemapping = false;
    if (originalSize && node.size) {
      node.size[0] = originalSize[0];
      node.size[1] = originalSize[1];
    }
    markDirty(node);
  }
}

function nodeWidth(node) {
  const width = Number(node?.size?.[0]);
  return Number.isFinite(width) && width > 0 ? width : MIN_W;
}

function restoreNodeWidth(node, width) {
  const targetWidth = Number(width);
  if (!node?.size || !Number.isFinite(targetWidth) || targetWidth <= 0) return;
  if (node.size[0] === targetWidth) return;
  node.size[0] = targetWidth;
  markDirty(node);
}

function restoreNodeWidthSoon(node, width) {
  restoreNodeWidth(node, width);
  if (typeof queueMicrotask === "function") queueMicrotask(() => restoreNodeWidth(node, width));
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => restoreNodeWidth(node, width));
  window.setTimeout(() => restoreNodeWidth(node, width), 0);
}

function allRowsOn(node) {
  const rows = rowWidgets(node);
  if (!rows.length) return false;
  return rows.every((row) => row.value?.on);
}

function toggleAllRows(node) {
  const rows = rowWidgets(node);
  const next = !allRowsOn(node);
  for (const row of rows) row.value.on = next;
  markDirty(node);
}

function addCustomWidget(node, widget) {
  node.widgets = node.widgets || [];
  node.widgets.push(widget);
  return widget;
}

function moveWidgetBeforeButton(node, widget) {
  const widgets = node.widgets || [];
  const buttonIndex = widgets.findIndex((item) => item.__loraxAddButton);
  const currentIndex = widgets.indexOf(widget);
  if (buttonIndex === -1 || currentIndex === -1 || currentIndex < buttonIndex) return;
  widgets.splice(currentIndex, 1);
  widgets.splice(buttonIndex, 0, widget);
}

function nextRowName(node) {
  node.__loraxCounter = Number(node.__loraxCounter || 0) + 1;
  return `lora_${node.__loraxCounter}`;
}

function addRow(node, value = defaultRowValue(), preservedWidth = nodeWidth(node)) {
  const widget = addCustomWidget(node, createRowWidget(nextRowName(node), value));
  moveWidgetBeforeButton(node, widget);
  resizeNode(node, preservedWidth);
  return widget;
}

function removeLoraXWidgets(node) {
  node.widgets = (node.widgets || []).filter((widget) => !widget.__lorax);
}

function resizeNode(node, preservedWidth = null) {
  const currentWidth = nodeWidth(node);
  const requestedWidth = Number(preservedWidth);
  const hasPreservedWidth = Number.isFinite(requestedWidth) && requestedWidth > 0;
  const targetWidth = hasPreservedWidth ? requestedWidth : Math.max(MIN_W, currentWidth);
  node.size = node.size || [targetWidth, 120];
  node.size[0] = targetWidth;
  const computed = node.computeSize?.() || [targetWidth, node.size[1]];
  const computedWidth = Number(computed?.[0]);
  node.size[0] = hasPreservedWidth ? targetWidth : Math.max(targetWidth, Number.isFinite(computedWidth) ? computedWidth : 0, MIN_W);
  node.size[1] = Math.max(120, Number(computed?.[1]) || node.size[1] || 120);
  if (hasPreservedWidth) restoreNodeWidthSoon(node, targetWidth);
  markDirty(node);
}

function setupNode(node, rowValues = null) {
  const preservedWidth = nodeWidth(node);
  removeLoraXWidgets(node);
  node.serialize_widgets = true;
  node.__loraxCounter = 0;

  addCustomWidget(node, createHeaderWidget());
  resizeNode(node, preservedWidth);
  for (const value of rowValues || []) addRow(node, value, preservedWidth);

  const addButton = node.addWidget("button", "+ Add Lora", "", () => {
    openPicker((item) => addRow(node, defaultRowValue(item)));
  });
  addButton.__lorax = true;
  addButton.__loraxAddButton = true;
  resizeNode(node, preservedWidth);
}

function setRowFromItem(node, row, item) {
  const old = sanitizeRowValue(row.value || defaultRowValue());
  row.value = {
    ...defaultRowValue(item),
    strength: Number(old.strength ?? 1),
    on: old.on !== false,
  };
  markDirty(node);
}

function promptStrength(node, row, event) {
  const current = Number(row.value.strength ?? 1);
  const canvas = app.canvas;
  const finish = (value) => {
    const next = Number(value);
    if (!Number.isFinite(next)) return;
    row.value.strength = next;
    markDirty(node);
  };
  if (canvas?.prompt) canvas.prompt("Strength", current, finish, event);
  else {
    const value = window.prompt("Strength", String(current));
    if (value != null) finish(value);
  }
}

function stepStrength(node, row, direction) {
  const current = Number(row.value.strength ?? 1);
  row.value.strength = Math.round((current + direction * 0.05) * 100) / 100;
  markDirty(node);
}

function moveRow(node, row, direction) {
  const widgets = node.widgets || [];
  const rows = rowWidgets(node);
  const rowIndex = rows.indexOf(row);
  const targetRow = rows[rowIndex + direction];
  if (!targetRow) return;
  const a = widgets.indexOf(row);
  const b = widgets.indexOf(targetRow);
  widgets[a] = targetRow;
  widgets[b] = row;
  markDirty(node);
}

function removeRow(node, row) {
  const preservedWidth = nodeWidth(node);
  node.widgets = (node.widgets || []).filter((widget) => widget !== row);
  resizeNode(node, preservedWidth);
}

function rowMenu(node, row, event) {
  if (!window.LiteGraph?.ContextMenu) return;
  new LiteGraph.ContextMenu(
    [
      {
        content: row.value.on ? "Toggle Off" : "Toggle On",
        callback: () => {
          row.value.on = !row.value.on;
          markDirty(node);
        },
      },
      {
        content: "Replace",
        callback: () => openPicker((item) => setRowFromItem(node, row, item)),
      },
      null,
      { content: "Move Up", callback: () => moveRow(node, row, -1) },
      { content: "Move Down", callback: () => moveRow(node, row, 1) },
      { content: "Remove", callback: () => removeRow(node, row) },
    ],
    { event, title: "LoraX" },
  );
}

function nodeLocalPosition(node, pos) {
  let x = Number(pos?.[0] || 0);
  let y = Number(pos?.[1] || 0);
  const width = node.size?.[0] || MIN_W;
  const height = node.size?.[1] || 0;
  if (node.pos && (x > width || y > height)) {
    x -= node.pos[0];
    y -= node.pos[1];
  }
  return [x, y];
}

function updateRemapHover(node, pos) {
  const header = (node.widgets || []).find((widget) => widget.name === "lorax_header");
  if (!header || header.last_y == null) return;
  const [x, y] = nodeLocalPosition(node, pos);
  const hover = x >= REMAP_X && x <= REMAP_X + REMAP_W && y >= header.last_y && y <= header.last_y + HEADER_H;
  if (hover === Boolean(node.__loraxRemapHover)) return;
  node.__loraxRemapHover = hover;
  markDirty(node);
}

function handleRowClick(node, event, pos) {
  let [localX, localY] = nodeLocalPosition(node, pos);
  const width = node.size?.[0] || MIN_W;

  for (const widget of node.widgets || []) {
    if (!widget.__lorax || widget.last_y == null) continue;
    const y = widget.last_y;
    const h = widget.__loraxRow ? ROW_H : HEADER_H;
    if (localY < y || localY > y + h) continue;

    if (widget.name === "lorax_header") {
      if (localX < 112) {
        toggleAllRows(node);
        return true;
      }
      if (localX >= REMAP_X && localX <= REMAP_X + REMAP_W) {
        remapRows(node);
        return true;
      }
      return false;
    }

    if (!widget.__loraxRow) return false;
    if (event.button === 2) {
      rowMenu(node, widget, event);
      return true;
    }
    if (localX < 44) {
      widget.value.on = !widget.value.on;
      markDirty(node);
      return true;
    }

    const removeX = width - 10 - REMOVE_W;
    const strengthX = removeX - CONTROL_GAP - STRENGTH_W;
    if (localX >= strengthX && localX <= strengthX + 28) {
      stepStrength(node, widget, -1);
      return true;
    }
    if (localX >= strengthX + 30 && localX <= strengthX + 100) {
      promptStrength(node, widget, event);
      return true;
    }
    if (localX >= strengthX + 102 && localX <= strengthX + STRENGTH_W) {
      stepStrength(node, widget, 1);
      return true;
    }
    if (localX >= removeX && localX <= removeX + REMOVE_W) {
      removeRow(node, widget);
      return true;
    }

    openRowDetails(widget);
    return true;
  }
  return false;
}

app.registerExtension({
  name: EXTENSION_NAME,
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_TYPE) return;

    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function workflowXLoraXCreated() {
      originalCreated?.apply(this, arguments);
      setupNode(this);
    };

    const originalConfigure = nodeType.prototype.configure;
    nodeType.prototype.configure = function workflowXLoraXConfigure(info) {
      const values = restoredRowValues(info?.widgets_values);
      const configureInfo = info && Array.isArray(info.widgets_values) ? { ...info, widgets_values: [] } : info;
      const args = [...arguments];
      args[0] = configureInfo;
      const result = originalConfigure?.apply(this, args);
      setupNode(this, values);
      return result;
    };

    const originalMouseDown = nodeType.prototype.onMouseDown;
    nodeType.prototype.onMouseDown = function workflowXLoraXMouseDown(event, pos) {
      if (handleRowClick(this, event, pos || app.canvas?.graph_mouse || [0, 0])) return true;
      return originalMouseDown?.apply(this, arguments);
    };

    const originalMouseMove = nodeType.prototype.onMouseMove;
    nodeType.prototype.onMouseMove = function workflowXLoraXMouseMove(event, pos) {
      updateRemapHover(this, pos || app.canvas?.graph_mouse || [0, 0]);
      return originalMouseMove?.apply(this, arguments);
    };

    const originalMouseLeave = nodeType.prototype.onMouseLeave;
    nodeType.prototype.onMouseLeave = function workflowXLoraXMouseLeave() {
      if (this.__loraxRemapHover) {
        this.__loraxRemapHover = false;
        markDirty(this);
      }
      return originalMouseLeave?.apply(this, arguments);
    };
  },
});
