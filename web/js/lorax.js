import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { compactArray, creatorName, itemMatchesQuery, normalizePath, trainedWords } from "./lorax_search.js";

const NODE_TYPE = "KVGC_LoraX";
const EXTENSION_NAME = "workflowx.lorax";
const LORAX_ROUTE = "/workflowx_configurator/lorax/loras";
const LORA_MANAGER_LIST_ROUTE = "/api/lm/loras/list";
const LORA_MANAGER_TREE_ROUTE = "/api/lm/loras/unified-folder-tree";
const LORA_MANAGER_METADATA_ROUTE = "/api/lm/loras/metadata";
const LORA_MANAGER_DESCRIPTION_ROUTE = "/api/lm/loras/model-description";
const STYLE_ID = "workflowx-lorax-styles";
const ROW_H = 24;
const HEADER_H = 22;
const MIN_W = 560;
const STRENGTH_W = 130;
const REMOVE_W = 28;
const CONTROL_GAP = 8;
const MAX_MANAGER_PAGES = 200;
const LORA_EXT_RE = /\.(safetensors|ckpt|pt|bin)$/i;
const VIDEO_EXT_RE = /\.(mp4|webm|mov)(?:[?#].*)?$/i;

let catalogPromise = null;
let activePicker = null;

function markDirty(node) {
  node?.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

async function fetchJson(path) {
  const response = api?.fetchApi ? await api.fetchApi(path, { cache: "no-store" }) : await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
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

async function loadCatalog() {
  if (!catalogPromise) {
    catalogPromise = (async () => {
      const canonical = await fetchJson(LORAX_ROUTE).catch(() => ({ items: [] }));
      const [managerItems, managerTree] = await Promise.all([
        loadLoraManagerItems().catch(() => []),
        loadLoraManagerTree().catch(() => null),
      ]);
      const items = mergeCatalog(Array.isArray(canonical.items) ? canonical.items : [], managerItems);
      const tree = managerTree ? buildTreeFromManagerData(managerTree, items) : buildTreeFromItems(items);
      return { items, tree };
    })();
  }
  return catalogPromise;
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
    .workflowx-lorax-top{display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid #30343b;background:#202328}
    .workflowx-lorax-search{height:32px;border-radius:6px;border:1px solid #4e5560;background:#111316;color:#f3f5f7;padding:0 10px;font-size:14px;outline:none}
    .workflowx-lorax-strict{height:32px;border:1px solid #4e5560;border-radius:6px;background:#1a1f26;color:#d5dce6;display:flex;align-items:center;gap:7px;padding:0 10px;white-space:nowrap;cursor:pointer;user-select:none}
    .workflowx-lorax-strict input{accent-color:#6f8fd4}
    .workflowx-lorax-close{height:32px;width:32px;border:1px solid #4e5560;border-radius:6px;background:#242830;color:#d5d9df;cursor:pointer}
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
    .workflowx-lorax-card{position:relative;min-height:122px;border:1px solid #303640;background:#1c2026;border-radius:7px;display:grid;grid-template-columns:92px 1fr;gap:10px;padding:8px;cursor:pointer;overflow:hidden;color:inherit;text-align:left}
    .workflowx-lorax-card:hover{border-color:#6f8fd4;background:#232a34}
    .workflowx-lorax-thumb,.workflowx-lorax-video{width:92px;height:106px;border-radius:5px;background:#0d0f12;object-fit:cover;border:1px solid #30343b}
    .workflowx-lorax-no-thumb{width:92px;height:106px;border-radius:5px;background:#222831;border:1px solid #30343b;display:flex;align-items:center;justify-content:center;color:#8f98a5}
    .workflowx-lorax-card-body{min-width:0;padding-right:48px}
    .workflowx-lorax-card-actions{position:absolute;right:8px;top:8px;display:flex;gap:5px}
    .workflowx-lorax-view{height:25px;border:1px solid #4b5563;border-radius:5px;background:#252d37;color:#d9e4f2;cursor:pointer;font-size:11px;padding:0 7px}
    .workflowx-lorax-view:hover{background:#31415a;border-color:#6f8fd4;color:#fff}
    .workflowx-lorax-name{font-weight:700;color:#f4f6f9;line-height:1.2;max-height:34px;overflow:hidden}
    .workflowx-lorax-path{color:#9fa8b4;margin-top:4px;line-height:1.25;max-height:34px;overflow:hidden}
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
    .workflowx-lorax-detail-actions{display:flex;gap:8px;justify-content:flex-end;padding:12px 16px;border-top:1px solid #30343b;background:#202328}
    .workflowx-lorax-detail-actions button,.workflowx-lorax-detail-actions a{height:32px;border-radius:6px;border:1px solid #4e5560;background:#252d37;color:#e8eef7;padding:0 12px;text-decoration:none;display:inline-flex;align-items:center;cursor:pointer}
    .workflowx-lorax-detail-actions .primary{background:#315a94;border-color:#5783c4;color:#fff}
    @media (max-width:760px){
      .workflowx-lorax-body{grid-template-columns:1fr}
      .workflowx-lorax-top{grid-template-columns:1fr auto}
      .workflowx-lorax-strict{grid-column:1/-1;justify-content:flex-start}
      .workflowx-lorax-tree{max-height:190px;border-right:0;border-bottom:1px solid #30343b}
      .workflowx-lorax-detail-body{grid-template-columns:1fr}
    }
  `;
  document.head.appendChild(style);
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
  const chips = [item.base_model, item.sub_type, item.favorite ? "Favorite" : "", item.update_available ? "Update" : "", ...item.tags].filter(Boolean).slice(0, 5);
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

function addTextSection(grid, title, value) {
  const text = String(value || "").trim();
  if (!text) return;
  const section = document.createElement("div");
  section.className = "workflowx-lorax-detail-section";
  const h = document.createElement("h3");
  h.textContent = title;
  const content = document.createElement("div");
  content.className = "workflowx-lorax-detail-text";
  content.textContent = text;
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
  const select = document.createElement("button");
  select.className = "primary";
  select.type = "button";
  select.textContent = "Select";
  select.addEventListener("click", () => {
    onSelect(item);
    closeDetails();
  });
  actions.appendChild(select);
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
  const close = document.createElement("button");
  close.className = "workflowx-lorax-close";
  close.type = "button";
  close.textContent = "x";
  top.append(search, strictLabel, close);

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
  const expandedFolders = new Set([""]);

  function closePicker() {
    backdrop.remove();
    if (activePicker === backdrop) activePicker = null;
  }

  function selectAndClose(item) {
    onSelect(item);
    closePicker();
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

  close.addEventListener("click", closePicker);
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
  const strength = Number(value.strength ?? value.modelStrength ?? value.model_strength ?? value.strength_model ?? 1);
  row.strength = Number.isFinite(strength) ? strength : 1;
  row.metadata = value.metadata && typeof value.metadata === "object" ? value.metadata : {};
  row.trigger_words = Array.isArray(value.trigger_words) ? value.trigger_words : trainedWords(value);
  return row;
}

function isRowValue(value) {
  return value && typeof value === "object" && ("load_name" in value || "lora" in value || "name" in value);
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
      ctx.textAlign = "center";
      ctx.fillText("Strength", width - 124, y + HEADER_H / 2);
      ctx.fillText("Remove", width - 28, y + HEADER_H / 2);
      ctx.restore();
    },
    mouse(event, pos, node) {
      if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
      if (pos[0] < 140) {
        toggleAllRows(node);
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
      openPicker((item) => setRowFromItem(node, this, item));
      return true;
    },
  };
}

function rowWidgets(node) {
  return (node.widgets || []).filter((widget) => widget.__loraxRow);
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
  if (typeof node.addCustomWidget === "function") {
    return node.addCustomWidget(widget);
  }
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

function addRow(node, value = defaultRowValue()) {
  const widget = addCustomWidget(node, createRowWidget(nextRowName(node), value));
  moveWidgetBeforeButton(node, widget);
  resizeNode(node);
  return widget;
}

function removeLoraXWidgets(node) {
  node.widgets = (node.widgets || []).filter((widget) => !widget.__lorax);
}

function resizeNode(node) {
  node.size = node.size || [MIN_W, 120];
  node.size[0] = Math.max(node.size[0], MIN_W);
  const computed = node.computeSize?.() || [node.size[0], node.size[1]];
  node.size[1] = Math.max(120, computed[1]);
  markDirty(node);
}

function setupNode(node, rowValues = null) {
  removeLoraXWidgets(node);
  node.serialize_widgets = true;
  node.__loraxCounter = 0;

  addCustomWidget(node, createHeaderWidget());
  for (const value of rowValues || []) addRow(node, value);

  const addButton = node.addWidget("button", "+ Add Lora", "", () => {
    openPicker((item) => addRow(node, defaultRowValue(item)));
  });
  addButton.__lorax = true;
  addButton.__loraxAddButton = true;
  resizeNode(node);
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
  node.widgets = (node.widgets || []).filter((widget) => widget !== row);
  resizeNode(node);
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

function handleRowClick(node, event, pos) {
  let localX = Number(pos?.[0] || 0);
  let localY = Number(pos?.[1] || 0);
  const width = node.size?.[0] || MIN_W;
  const height = node.size?.[1] || 0;
  if (node.pos && (localX > width || localY > height)) {
    localX -= node.pos[0];
    localY -= node.pos[1];
  }

  for (const widget of node.widgets || []) {
    if (!widget.__lorax || widget.last_y == null) continue;
    const y = widget.last_y;
    const h = widget.__loraxRow ? ROW_H : HEADER_H;
    if (localY < y || localY > y + h) continue;

    if (widget.name === "lorax_header") {
      if (localX < 140) {
        toggleAllRows(node);
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

    openPicker((item) => setRowFromItem(node, widget, item));
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
      const values = Array.isArray(info?.widgets_values) ? info.widgets_values.filter(isRowValue) : [];
      const result = originalConfigure?.apply(this, arguments);
      setupNode(this, values);
      return result;
    };

    const originalMouseDown = nodeType.prototype.onMouseDown;
    nodeType.prototype.onMouseDown = function workflowXLoraXMouseDown(event, pos) {
      if (handleRowClick(this, event, pos || app.canvas?.graph_mouse || [0, 0])) return true;
      return originalMouseDown?.apply(this, arguments);
    };
  },
});
