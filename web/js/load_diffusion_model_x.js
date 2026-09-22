import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { itemMatchesQuery, normalizePath } from "./load_diffusion_model_x_search.js";
import {
  activateModelRow,
  applyModelIdentity,
  defaultModelRow,
  modelItemFileSize,
  modelItemSha256,
  normalizeModelRow,
  normalizeSha256,
  removeModelRow,
  restoreModelRows,
  sortedModelHashMatches,
} from "./load_diffusion_model_x_state.mjs";

const NODE_TYPE = "KVGC_LoadDiffusionModelX";
const EXTENSION_NAME = "workflowx.load_diffusion_model_x";
const CATALOG_ROUTE = "/workflowx_configurator/load_diffusion_model_x/models";
const HASH_ROUTE = "/workflowx_configurator/load_diffusion_model_x/hash";
const REMAP_ROUTE = "/workflowx_configurator/load_diffusion_model_x/remap";
const MANAGER_LIST_ROUTE = "/api/lm/checkpoints/list";
const MANAGER_SCAN_ROUTE = "/api/lm/checkpoints/scan";
const MANAGER_METADATA_ROUTE = "/api/lm/checkpoints/metadata";
const MANAGER_DESCRIPTION_ROUTE = "/api/lm/checkpoints/model-description";
const STYLE_ID = "workflowx-load-diffusion-model-x-styles";
const ROW_H = 28;
const HEADER_H = 24;
const MIN_W = 560;
const REMOVE_W = 30;
const REMAP_X = 104;
const REMAP_W = 28;
const MAX_MANAGER_PAGES = 200;
const VIDEO_EXT_RE = /\.(mp4|webm|mov)(?:[?#].*)?$/i;

let catalogPromise = null;
let activePicker = null;

function markDirty(node) {
  node?.setDirtyCanvas?.(true, true);
  app.canvas?.setDirty?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

async function fetchJson(path, options = {}) {
  const requestOptions = { cache: "no-store", ...options };
  const response = api?.fetchApi
    ? await api.fetchApi(path, requestOptions)
    : await fetch(path, requestOptions);
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

function lower(value) {
  return normalizePath(value).toLowerCase();
}

function stripExtension(value) {
  return normalizePath(value).replace(/\.[^.\/]+$/i, "");
}

function rowFilenameStem(value) {
  const candidate = typeof value === "object" && value !== null
    ? value.filename || value.file_name || value.load_name || value.loadName || value.unet_name || value.unetName
    : value;
  const normalized = normalizePath(candidate);
  return stripExtension(normalized.split("/").pop() || normalized);
}

function normalizeCanonical(item) {
  const loadName = normalizePath(item?.load_name);
  const filename = normalizePath(item?.filename || loadName.split("/").pop());
  const fileStem = item?.file_stem || stripExtension(filename);
  return {
    ...item,
    load_name: loadName,
    folder: normalizePath(item?.folder),
    filename,
    file_stem: fileStem,
    display_name: item?.display_name || fileStem || loadName,
    full_path: normalizePath(item?.full_path),
    file_size: modelItemFileSize(item),
    sha256: modelItemSha256(item),
    sub_type: item?.sub_type || "diffusion_model",
    tags: Array.isArray(item?.tags) ? item.tags : [],
  };
}

function managerKeys(item) {
  const keys = new Set();
  const filePath = lower(item?.file_path);
  const folder = lower(item?.folder);
  const fileName = lower(item?.file_name || item?.filename);
  if (filePath) keys.add(filePath);
  if (folder && fileName) keys.add(`${folder}/${fileName}`);
  if (fileName) keys.add(fileName);
  return keys;
}

function mergeCatalog(canonicalItems, managerItems) {
  const byPath = new Map();
  const byRelative = new Map();
  const byName = new Map();
  for (const item of managerItems) {
    for (const key of managerKeys(item)) {
      if (key.includes(":/") || key.startsWith("//")) byPath.set(key, item);
      else if (key.includes("/")) byRelative.set(key, item);
      else if (!byName.has(key)) byName.set(key, item);
    }
  }

  return canonicalItems.map((raw) => {
    const item = normalizeCanonical(raw);
    const fullPathKey = lower(item.full_path);
    const relativeKey = lower(item.load_name);
    const nameKey = lower(item.filename);
    const manager = byPath.get(fullPathKey) || byRelative.get(relativeKey) || byName.get(nameKey) || null;
    if (!manager) return item;
    return {
      ...item,
      display_name: manager.model_name || item.display_name,
      model_name: manager.model_name || "",
      base_model: manager.base_model || "",
      tags: Array.isArray(manager.tags) ? manager.tags : [],
      preview_url: normalizePath(manager.preview_url),
      favorite: Boolean(manager.favorite),
      update_available: Boolean(manager.update_available),
      sub_type: manager.sub_type || item.sub_type,
      file_size: modelItemFileSize(manager) || item.file_size,
      sha256: modelItemSha256(manager) || item.sha256,
      metadata: manager,
    };
  });
}

async function loadManagerItems() {
  const items = [];
  let totalPages = 1;
  for (let page = 1; page <= totalPages && page <= MAX_MANAGER_PAGES; page += 1) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: "100",
      sort_by: "name",
      recursive: "true",
      search_filename: "true",
      search_modelname: "true",
      search_tags: "true",
      model_type: "diffusion_model",
    });
    const data = await fetchJson(`${MANAGER_LIST_ROUTE}?${params}`);
    const pageItems = Array.isArray(data?.items) ? data.items : [];
    items.push(...pageItems.filter((item) => !item?.sub_type || item.sub_type === "diffusion_model"));
    totalPages = Math.max(1, Number(data?.total_pages || 1));
  }
  return items;
}

async function loadCatalog(force = false) {
  if (force) catalogPromise = null;
  if (!catalogPromise) {
    catalogPromise = (async () => {
      const canonicalData = await fetchJson(CATALOG_ROUTE);
      const canonical = Array.isArray(canonicalData?.items) ? canonicalData.items : [];
      const managerItems = await loadManagerItems().catch(() => []);
      return mergeCatalog(canonical, managerItems);
    })().catch((error) => {
      catalogPromise = null;
      throw error;
    });
  }
  return catalogPromise;
}

async function refreshCatalog() {
  await fetchJson(`${MANAGER_SCAN_ROUTE}?full_rebuild=false`).catch(() => null);
  return loadCatalog(true);
}

async function ensureModelIdentity(item) {
  const sha256 = modelItemSha256(item);
  const fileSize = modelItemFileSize(item);
  if (sha256) return { ...item, sha256, file_size: fileSize };
  const identity = await postJson(HASH_ROUTE, { load_name: item?.load_name });
  const calculatedHash = modelItemSha256(identity);
  if (!calculatedHash) throw new Error("The backend did not return a valid SHA-256 identity.");
  return {
    ...item,
    ...identity,
    display_name: item?.display_name || identity?.file_stem || identity?.load_name,
    metadata: item?.metadata || null,
    sha256: calculatedHash,
    file_size: modelItemFileSize(identity),
  };
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
    if (!node.children.has(part)) node.children.set(part, { name: part, path: currentPath, children: new Map() });
    node = node.children.get(part);
  }
}

function buildTree(items) {
  const root = createTreeRoot();
  for (const item of items) insertTreePath(root, item.folder);
  return root;
}

function itemMatchesFolder(item, folder) {
  if (!folder) return true;
  return item.folder === folder || item.folder.startsWith(`${folder}/`);
}

function folderCount(items, path) {
  if (!path) return items.length;
  return items.filter((item) => itemMatchesFolder(item, path)).length;
}

function renderTreeNode(treeNode, container, items, selectedFolder, expanded, onSelect, depth = 0) {
  const children = [...treeNode.children.values()].sort((a, b) => a.name.localeCompare(b.name));
  for (const child of children) {
    const row = document.createElement("div");
    row.className = "workflowx-dmx-tree-row";
    row.style.paddingLeft = `${depth * 12}px`;
    const expander = document.createElement("button");
    expander.className = "workflowx-dmx-expand";
    const hasChildren = child.children.size > 0;
    expander.textContent = hasChildren ? (expanded.has(child.path) ? "−" : "+") : "";
    expander.disabled = !hasChildren;
    expander.addEventListener("click", () => {
      if (expanded.has(child.path)) expanded.delete(child.path);
      else expanded.add(child.path);
      onSelect(selectedFolder);
    });
    const button = document.createElement("button");
    button.className = `workflowx-dmx-folder${selectedFolder === child.path ? " active" : ""}`;
    button.innerHTML = `<span class="workflowx-dmx-folder-name"></span><span class="workflowx-dmx-folder-count"></span>`;
    button.querySelector(".workflowx-dmx-folder-name").textContent = child.name;
    button.querySelector(".workflowx-dmx-folder-count").textContent = String(folderCount(items, child.path));
    button.addEventListener("click", () => onSelect(child.path));
    row.append(expander, button);
    container.appendChild(row);
    if (hasChildren && expanded.has(child.path)) renderTreeNode(child, container, items, selectedFolder, expanded, onSelect, depth + 1);
  }
}

function renderFolderTree(root, container, items, selectedFolder, expanded, onSelect) {
  container.textContent = "";
  const row = document.createElement("div");
  row.className = "workflowx-dmx-tree-row";
  const spacer = document.createElement("span");
  spacer.className = "workflowx-dmx-expand";
  const button = document.createElement("button");
  button.className = `workflowx-dmx-folder${selectedFolder === "" ? " active" : ""}`;
  button.innerHTML = `<span class="workflowx-dmx-folder-name">All models</span><span class="workflowx-dmx-folder-count">${items.length}</span>`;
  button.addEventListener("click", () => onSelect(""));
  row.append(spacer, button);
  container.appendChild(row);
  renderTreeNode(root, container, items, selectedFolder, expanded, onSelect);
}

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .workflowx-dmx-backdrop{position:fixed;inset:0;z-index:10000;background:rgba(8,10,12,.62);display:flex;align-items:center;justify-content:center}
    .workflowx-dmx-picker{width:min(1180px,calc(100vw - 48px));height:min(800px,calc(100vh - 48px));background:#17191d;color:#e8ebef;border:1px solid #41464f;border-radius:8px;box-shadow:0 24px 80px rgba(0,0,0,.58);display:grid;grid-template-rows:auto 1fr;overflow:hidden;font:13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .workflowx-dmx-top{display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid #30343b;background:#202328}
    .workflowx-dmx-search{height:32px;border-radius:6px;border:1px solid #4e5560;background:#111316;color:#f3f5f7;padding:0 10px;font-size:14px;outline:none}
    .workflowx-dmx-refresh,.workflowx-dmx-close,.workflowx-dmx-view{height:32px;border:1px solid #4e5560;border-radius:6px;background:#252d37;color:#dce4ef;cursor:pointer;padding:0 10px}
    .workflowx-dmx-close{width:32px;padding:0}
    .workflowx-dmx-body{display:grid;grid-template-columns:280px 1fr;min-height:0}
    .workflowx-dmx-tree{border-right:1px solid #30343b;overflow:auto;padding:8px;background:#14161a}
    .workflowx-dmx-tree-row{display:flex;align-items:center;gap:4px;min-height:28px;color:#bfc5ce}
    .workflowx-dmx-expand{width:22px;height:22px;border:0;border-radius:4px;background:transparent;color:#9fa8b4;cursor:pointer}
    .workflowx-dmx-folder{flex:1;min-width:0;height:24px;border:0;background:transparent;color:inherit;text-align:left;border-radius:5px;padding:0 7px;cursor:pointer;display:flex;align-items:center;gap:6px}
    .workflowx-dmx-folder:hover,.workflowx-dmx-folder.active{background:#28303a;color:#fff}
    .workflowx-dmx-folder-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.workflowx-dmx-folder-count{margin-left:auto;color:#88919d;font-size:11px}
    .workflowx-dmx-results{overflow:auto;padding:10px;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;align-content:start;background:#101215}
    .workflowx-dmx-results[aria-busy="true"]{opacity:.55;pointer-events:none;cursor:progress}
    .workflowx-dmx-card{position:relative;min-height:156px;border:1px solid #303640;background:#1c2026;border-radius:7px;display:grid;grid-template-columns:100px 1fr;gap:10px;padding:8px;cursor:pointer;overflow:hidden;color:inherit;text-align:left}
    .workflowx-dmx-card:hover{border-color:#6f8fd4;background:#232a34}.workflowx-dmx-thumb,.workflowx-dmx-video{width:100px;height:140px;border-radius:5px;background:#0d0f12;object-fit:cover;border:1px solid #30343b}
    .workflowx-dmx-no-thumb{width:100px;height:140px;border-radius:5px;background:#222831;border:1px solid #30343b;display:flex;align-items:center;justify-content:center;color:#8f98a5;text-align:center;padding:4px;box-sizing:border-box}
    .workflowx-dmx-card-body{min-width:0;padding-bottom:31px}.workflowx-dmx-filename{font-weight:700;color:#f4f6f9;line-height:1.25;overflow-wrap:anywhere;word-break:break-word}.workflowx-dmx-name{color:#cbd4df;line-height:1.2;margin-top:5px;max-height:32px;overflow:hidden}.workflowx-dmx-path{color:#9fa8b4;margin-top:5px;font-size:11px;line-height:1.25;max-height:30px;overflow:hidden;overflow-wrap:anywhere}
    .workflowx-dmx-meta{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}.workflowx-dmx-chip{font-size:11px;line-height:18px;padding:0 6px;border-radius:4px;background:#2a3440;color:#cdd5df;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .workflowx-dmx-view{position:absolute;right:8px;bottom:8px;height:25px;font-size:11px;padding:0 7px}.workflowx-dmx-empty{grid-column:1/-1;color:#a7afba;padding:32px;text-align:center}
    .workflowx-dmx-detail{width:min(900px,calc(100vw - 64px));max-height:min(780px,calc(100vh - 64px));background:#17191d;color:#e8ebef;border:1px solid #4b5563;border-radius:8px;box-shadow:0 24px 90px rgba(0,0,0,.62);display:grid;grid-template-rows:auto 1fr auto;overflow:hidden;font:13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .workflowx-dmx-detail-head{display:flex;gap:12px;align-items:flex-start;padding:14px 16px;border-bottom:1px solid #30343b;background:#202328}.workflowx-dmx-detail-title{font-size:18px;font-weight:750}.workflowx-dmx-detail-sub{margin-top:4px;color:#a7afba;word-break:break-word}
    .workflowx-dmx-detail-body{overflow:auto;padding:14px 16px;display:grid;grid-template-columns:minmax(220px,300px) 1fr;gap:16px}.workflowx-dmx-detail-preview{width:100%;max-height:360px;border-radius:7px;background:#0d0f12;border:1px solid #30343b;object-fit:cover}.workflowx-dmx-detail-grid{display:grid;grid-template-columns:120px 1fr;gap:8px 12px;align-content:start}.workflowx-dmx-detail-label{color:#98a3b1}.workflowx-dmx-detail-value{color:#eef2f6;word-break:break-word}.workflowx-dmx-description{grid-column:1/-1;white-space:pre-wrap;border-top:1px solid #30343b;padding-top:10px;line-height:1.42}.workflowx-dmx-description.rich{white-space:normal}.workflowx-dmx-description.rich :is(h1,h2,h3,h4,h5,h6,p,pre,blockquote,ul,ol){margin:0 0 9px}.workflowx-dmx-description.rich :is(ul,ol){padding-left:22px}.workflowx-dmx-description.rich a{color:#8db8ff}.workflowx-dmx-description.rich pre,.workflowx-dmx-description.rich code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.workflowx-dmx-description.rich pre{overflow:auto;background:#101318;border:1px solid #30343b;border-radius:5px;padding:8px}
    .workflowx-dmx-detail-actions{display:flex;gap:8px;justify-content:flex-end;padding:12px 16px;border-top:1px solid #30343b;background:#202328}.workflowx-dmx-detail-actions button{height:32px;border-radius:6px;border:1px solid #4e5560;background:#252d37;color:#e8eef7;padding:0 12px;cursor:pointer}.workflowx-dmx-detail-actions .primary{background:#315a94;border-color:#5783c4;color:#fff}
    .workflowx-dmx-toast{position:fixed;z-index:10003;left:50%;bottom:32px;transform:translateX(-50%);max-width:min(560px,calc(100vw - 32px));padding:9px 14px;border:1px solid #536174;border-radius:6px;background:#20262f;color:#edf2f8;box-shadow:0 8px 28px rgba(0,0,0,.45);font:13px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.workflowx-dmx-toast.error{border-color:#9b5050;background:#3a2224;color:#ffe4e4}
    @media(max-width:760px){.workflowx-dmx-body{grid-template-columns:1fr}.workflowx-dmx-tree{max-height:190px;border-right:0;border-bottom:1px solid #30343b}.workflowx-dmx-detail-body{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);
}

function showDmxToast(message, isError = false) {
  ensureStyles();
  document.querySelector(".workflowx-dmx-toast")?.remove();
  const toast = document.createElement("div");
  toast.className = `workflowx-dmx-toast${isError ? " error" : ""}`;
  toast.textContent = String(message || "");
  document.body.appendChild(toast);
  window.setTimeout(() => toast.remove(), isError ? 6000 : 3600);
}

function formatFileSize(size) {
  let value = Number(size);
  if (!Number.isFinite(value) || value <= 0) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function previewElement(item, className = "") {
  const url = item.preview_url || item.metadata?.preview_url || "";
  if (!url) {
    const empty = document.createElement("div");
    empty.className = className || "workflowx-dmx-no-thumb";
    empty.textContent = "Diffusion model";
    return empty;
  }
  if (VIDEO_EXT_RE.test(url)) {
    const video = document.createElement("video");
    video.className = className || "workflowx-dmx-video";
    video.src = url; video.muted = true; video.loop = true; video.playsInline = true;
    video.addEventListener("mouseenter", () => video.play().catch(() => {}));
    video.addEventListener("mouseleave", () => video.pause());
    return video;
  }
  const image = document.createElement("img");
  image.className = className || "workflowx-dmx-thumb";
  image.loading = "lazy"; image.src = url; image.alt = "";
  return image;
}

function addDetailRow(grid, label, value) {
  if (value === undefined || value === null || value === "") return;
  const labelElement = document.createElement("div");
  labelElement.className = "workflowx-dmx-detail-label";
  labelElement.textContent = label;
  const valueElement = document.createElement("div");
  valueElement.className = "workflowx-dmx-detail-value";
  valueElement.textContent = String(value);
  grid.append(labelElement, valueElement);
}

const RICH_TEXT_TAGS = new Set(["a", "b", "blockquote", "br", "code", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "li", "ol", "p", "pre", "s", "span", "strong", "u", "ul"]);

function textSectionValue(value) {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean).join("\n");
  if (typeof value === "object") {
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

function decodeEscapedMarkup(text) {
  if (hasHtmlMarkup(text) || !/&(?:lt|gt|amp|quot|#\d+|#x[\da-f]+);/i.test(text)) return text;
  const parsed = new DOMParser().parseFromString(text, "text/html");
  const decoded = parsed.body.textContent || "";
  return hasHtmlMarkup(decoded) ? decoded : text;
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
  const element = document.createElement(tag);
  if (tag === "a") {
    const href = safeHref(sourceNode.getAttribute("href") || "");
    if (!href) return children;
    element.href = href;
    element.target = "_blank";
    element.rel = "noreferrer";
  }
  element.appendChild(children);
  return element;
}

function renderRichTextContent(container, value) {
  const text = decodeEscapedMarkup(textSectionValue(value));
  if (!text) return;
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

async function fetchManagerDetails(item) {
  const filePath = normalizePath(item.metadata?.file_path || item.full_path);
  if (!filePath) return { metadata: null, description: "" };
  const params = new URLSearchParams({ file_path: filePath });
  const [metadataData, descriptionData] = await Promise.all([
    fetchJson(`${MANAGER_METADATA_ROUTE}?${params}`).catch(() => null),
    fetchJson(`${MANAGER_DESCRIPTION_ROUTE}?${params}`).catch(() => null),
  ]);
  return {
    metadata: metadataData?.success ? metadataData.metadata : null,
    description: descriptionData?.success ? (descriptionData.description ?? "") : "",
  };
}

async function openDetails(item, onSelect) {
  ensureStyles();
  const backdrop = document.createElement("div");
  backdrop.className = "workflowx-dmx-backdrop";
  const modal = document.createElement("div");
  modal.className = "workflowx-dmx-detail";
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);
  const close = () => backdrop.remove();
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });

  const head = document.createElement("div");
  head.className = "workflowx-dmx-detail-head";
  const titleWrap = document.createElement("div");
  const title = document.createElement("div");
  title.className = "workflowx-dmx-detail-title";
  title.textContent = item.display_name || item.file_stem || item.load_name;
  const sub = document.createElement("div");
  sub.className = "workflowx-dmx-detail-sub";
  sub.textContent = item.load_name;
  titleWrap.append(title, sub);
  const closeButton = document.createElement("button");
  closeButton.className = "workflowx-dmx-close";
  closeButton.textContent = "x";
  closeButton.addEventListener("click", close);
  head.append(titleWrap, closeButton);

  const body = document.createElement("div");
  body.className = "workflowx-dmx-detail-body";
  body.innerHTML = '<div class="workflowx-dmx-empty">Loading details...</div>';
  const actions = document.createElement("div");
  actions.className = "workflowx-dmx-detail-actions";
  const select = document.createElement("button");
  select.className = "primary"; select.textContent = "Select";
  select.addEventListener("click", async () => {
    select.disabled = true;
    const selected = await onSelect(item);
    if (selected !== false) close();
    else select.disabled = false;
  });
  actions.appendChild(select);
  modal.append(head, body, actions);

  const fetched = await fetchManagerDetails(item);
  const metadata = { ...(item.metadata || {}), ...(fetched.metadata || {}) };
  body.textContent = "";
  body.appendChild(previewElement(item, "workflowx-dmx-detail-preview"));
  const grid = document.createElement("div");
  grid.className = "workflowx-dmx-detail-grid";
  addDetailRow(grid, "Model name", metadata.model_name || item.display_name);
  addDetailRow(grid, "File name", metadata.file_name || item.filename);
  addDetailRow(grid, "Load name", item.load_name);
  addDetailRow(grid, "Folder", metadata.folder || item.folder || "Root");
  addDetailRow(grid, "Path", metadata.file_path || item.full_path);
  addDetailRow(grid, "Base model", metadata.base_model || item.base_model);
  addDetailRow(grid, "Type", metadata.sub_type || item.sub_type || "diffusion_model");
  addDetailRow(grid, "Size", formatFileSize(metadata.file_size || item.file_size));
  const description = fetched.description || metadata.description || metadata.notes;
  if (description) {
    const text = document.createElement("div");
    text.className = "workflowx-dmx-description";
    renderRichTextContent(text, description);
    grid.appendChild(text);
  }
  body.appendChild(grid);
}

function createCard(item, onSelect, onView) {
  const card = document.createElement("div");
  card.className = "workflowx-dmx-card"; card.tabIndex = 0; card.role = "button"; card.title = item.load_name;
  card.appendChild(previewElement(item));
  const body = document.createElement("div");
  body.className = "workflowx-dmx-card-body";
  const filename = document.createElement("div");
  filename.className = "workflowx-dmx-filename"; filename.textContent = item.filename || normalizePath(item.load_name).split("/").pop() || item.load_name;
  const name = document.createElement("div");
  name.className = "workflowx-dmx-name"; name.textContent = item.display_name || item.file_stem || item.load_name;
  const path = document.createElement("div");
  path.className = "workflowx-dmx-path"; path.textContent = item.load_name;
  const meta = document.createElement("div");
  meta.className = "workflowx-dmx-meta";
  const chips = [item.base_model, formatFileSize(item.file_size), ...(item.tags || [])]
    .filter((value) => value && lower(value).replace(/[^a-z0-9]+/g, "") !== "diffusionmodel")
    .slice(0, 5);
  for (const value of chips) {
    const chip = document.createElement("span"); chip.className = "workflowx-dmx-chip"; chip.textContent = value; meta.appendChild(chip);
  }
  body.append(filename, name, path, meta); card.appendChild(body);
  const view = document.createElement("button");
  view.className = "workflowx-dmx-view"; view.textContent = "View"; view.type = "button";
  view.addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); onView(item); });
  card.appendChild(view);
  card.addEventListener("click", () => onSelect(item));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(item); }
  });
  return card;
}

async function openPicker(onSelect) {
  ensureStyles();
  activePicker?.remove?.();
  const backdrop = document.createElement("div");
  backdrop.className = "workflowx-dmx-backdrop";
  const picker = document.createElement("div");
  picker.className = "workflowx-dmx-picker";
  const top = document.createElement("div");
  top.className = "workflowx-dmx-top";
  const search = document.createElement("input");
  search.className = "workflowx-dmx-search"; search.placeholder = "Search model name, path, base model, or tag";
  const refresh = document.createElement("button");
  refresh.className = "workflowx-dmx-refresh"; refresh.textContent = "Refresh";
  const close = document.createElement("button");
  close.className = "workflowx-dmx-close"; close.textContent = "x";
  top.append(search, refresh, close);
  const body = document.createElement("div");
  body.className = "workflowx-dmx-body";
  const tree = document.createElement("div"); tree.className = "workflowx-dmx-tree";
  const results = document.createElement("div"); results.className = "workflowx-dmx-results";
  body.append(tree, results); picker.append(top, body); backdrop.appendChild(picker); document.body.appendChild(backdrop);
  activePicker = backdrop;

  let items = [];
  let treeRoot = createTreeRoot();
  let selectedFolder = "";
  let selectionBusy = false;
  const expanded = new Set([""]);
  const closePicker = () => { backdrop.remove(); if (activePicker === backdrop) activePicker = null; };
  const selectAndClose = async (item) => {
    if (selectionBusy) return false;
    selectionBusy = true;
    search.disabled = true; refresh.disabled = true; close.disabled = true; results.setAttribute("aria-busy", "true");
    try {
      const identified = await ensureModelIdentity(item);
      await onSelect(identified);
      closePicker();
      return true;
    } catch (error) {
      console.warn("[WorkflowX Load Diffusion Model X] Failed to identify selected model", error);
      showDmxToast(`Could not hash diffusion model: ${error.message || error}`, true);
      return false;
    } finally {
      selectionBusy = false;
      search.disabled = false; refresh.disabled = false; close.disabled = false; results.removeAttribute("aria-busy");
    }
  };
  const render = () => {
    const filtered = items.filter((item) => itemMatchesFolder(item, selectedFolder)).filter((item) => itemMatchesQuery(item, search.value));
    const visible = filtered.slice(0, 500);
    renderFolderTree(treeRoot, tree, items, selectedFolder, expanded, (folder) => { selectedFolder = folder; render(); });
    results.textContent = "";
    if (!visible.length) {
      const empty = document.createElement("div"); empty.className = "workflowx-dmx-empty"; empty.textContent = "No diffusion models found"; results.appendChild(empty); return;
    }
    for (const item of visible) results.appendChild(createCard(item, selectAndClose, (selected) => openDetails(selected, selectAndClose)));
    if (visible.length < filtered.length) {
      const more = document.createElement("div"); more.className = "workflowx-dmx-empty"; more.textContent = `Showing first ${visible.length} of ${filtered.length} matches`; results.appendChild(more);
    }
  };
  const reload = async (force = false) => {
    results.innerHTML = '<div class="workflowx-dmx-empty">Loading diffusion models...</div>';
    try { items = force ? await refreshCatalog() : await loadCatalog(false); treeRoot = buildTree(items); }
    catch (error) { console.warn("[WorkflowX Load Diffusion Model X] Catalog load failed", error); items = []; treeRoot = createTreeRoot(); }
    render();
  };
  close.addEventListener("click", closePicker);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closePicker(); });
  search.addEventListener("input", render);
  search.addEventListener("keydown", (event) => { if (event.key === "Escape") closePicker(); });
  refresh.addEventListener("click", () => reload(true));
  await reload(false);
  search.focus();
}

function drawBox(ctx, x, y, width, label, active = false) {
  ctx.fillStyle = active ? "#315a94" : "#252930";
  ctx.strokeStyle = active ? "#6f9cdf" : "#707782";
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x, y + 2, width, ROW_H - 4, 8); else ctx.rect(x, y + 2, width, ROW_H - 4);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = active ? "#fff" : "#c7cdd5"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(label, x + width / 2, y + ROW_H / 2);
}

function drawRadio(ctx, x, y, active) {
  ctx.beginPath(); ctx.arc(x + 9, y + ROW_H / 2, 7, 0, Math.PI * 2);
  ctx.fillStyle = "#1c2026"; ctx.fill(); ctx.strokeStyle = active ? "#78a7ec" : "#737b86"; ctx.stroke();
  if (active) { ctx.beginPath(); ctx.arc(x + 9, y + ROW_H / 2, 3.5, 0, Math.PI * 2); ctx.fillStyle = "#78a7ec"; ctx.fill(); }
}

function fitText(ctx, text, width) {
  const raw = String(text || "None");
  if (ctx.measureText(raw).width <= width) return raw;
  let output = raw;
  while (output.length > 4 && ctx.measureText(`${output.slice(0, -1)}...`).width > width) output = output.slice(0, -1);
  return `${output.slice(0, -1)}...`;
}

function createHeaderWidget() {
  return {
    name: "diffusion_model_header", type: "custom", __dmx: true, value: { type: "header" },
    computeSize: () => [MIN_W, HEADER_H], serializeValue: () => ({ type: "header" }),
    draw(ctx, node, width, y) {
      this.last_y = y; ctx.save(); ctx.globalAlpha = app.canvas?.editor_alpha ?? 1;
      ctx.fillStyle = "#aeb6c1"; ctx.textBaseline = "middle"; ctx.textAlign = "left";
      ctx.fillText("Active model", 18, y + HEADER_H / 2);
      drawBox(ctx, REMAP_X, y - 2, REMAP_W, node.__dmxRemapping ? "..." : "\u21bb", false);
      ctx.textAlign = "center"; ctx.fillText("Remove", width - 30, y + HEADER_H / 2);
      if (node.__dmxRemapHover) {
        const tooltip = "Remap moved diffusion models";
        ctx.font = "12px sans-serif";
        const tooltipWidth = ctx.measureText(tooltip).width + 16;
        ctx.fillStyle = "#11151a"; ctx.strokeStyle = "#596270"; ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(REMAP_X, y + HEADER_H + 2, tooltipWidth, 24, 5); else ctx.rect(REMAP_X, y + HEADER_H + 2, tooltipWidth, 24);
        ctx.fill(); ctx.stroke(); ctx.fillStyle = "#eef2f6"; ctx.textAlign = "left";
        ctx.fillText(tooltip, REMAP_X + 8, y + HEADER_H + 14);
      }
      ctx.restore();
    },
    mouse(event, pos, node) {
      if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
      if (pos[0] >= REMAP_X && pos[0] <= REMAP_X + REMAP_W) { remapModelRows(node); return true; }
      return false;
    },
  };
}

function rowWidgets(node) {
  return (node.widgets || []).filter((widget) => widget.__dmxRow);
}

function catalogModelByLoadName(items, loadName) {
  const key = lower(loadName);
  return (items || []).find((item) => lower(item?.load_name) === key) || null;
}

function updateModelRowIdentity(row, entry, catalogItems) {
  if (!row?.value || !entry) return;
  const old = normalizeModelRow(row.value);
  const catalogItem = catalogModelByLoadName(catalogItems, entry.load_name);
  let next = applyModelIdentity(old, catalogItem || entry);
  if (catalogItem) {
    const fresh = defaultModelRow(catalogItem, old.on);
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
  row.value = Object.assign(row.value, next);
}

async function remapModelRows(node) {
  if (node.__dmxRemapping) return;
  const rows = rowWidgets(node);
  if (!rows.length) { showDmxToast("No diffusion models to remap"); return; }

  const originalSize = node.size ? [Number(node.size[0]), Number(node.size[1])] : null;
  node.__dmxRemapping = true; node.__dmxRemapHover = false; markDirty(node);
  try {
    const items = await refreshCatalog();
    const pending = [];
    const counts = { remapped: 0, unchanged: 0, unresolved: 0, duplicates: 0 };
    for (const row of rows) {
      const value = normalizeModelRow(row.value);
      const current = catalogModelByLoadName(items, value.load_name);
      const storedHash = normalizeSha256(value.sha256);
      if (storedHash) {
        const matches = sortedModelHashMatches(items, storedHash);
        const currentHash = modelItemSha256(current);
        const currentMatches = Boolean(currentHash && currentHash === storedHash);
        const chosen = currentMatches ? current : !current ? matches[0] : null;
        if (chosen) {
          updateModelRowIdentity(row, chosen, items);
          counts[currentMatches ? "unchanged" : "remapped"] += 1;
          counts.duplicates += Math.max(0, matches.length - 1);
          continue;
        }
      } else if (current && modelItemSha256(current)) {
        updateModelRowIdentity(row, current, items);
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
      const response = await postJson(REMAP_ROUTE, { items: pending.map((item) => item.request) });
      const byRowId = new Map(pending.map((item) => [item.request.row_id, item.row]));
      for (const result of response.items || []) {
        const status = ["remapped", "unchanged", "unresolved"].includes(result.status) ? result.status : "unresolved";
        counts[status] += 1;
        counts.duplicates += Math.max(0, Number(result.duplicate_count || 0) - 1);
        if (result.entry && status !== "unresolved") updateModelRowIdentity(byRowId.get(result.row_id), result.entry, items);
      }
    }

    const duplicateText = counts.duplicates ? `, ${counts.duplicates} duplicate match${counts.duplicates === 1 ? "" : "es"}` : "";
    showDmxToast(`${counts.remapped} remapped, ${counts.unchanged} unchanged, ${counts.unresolved} unresolved${duplicateText}`);
  } catch (error) {
    console.warn("[WorkflowX Load Diffusion Model X] Remapping failed", error);
    showDmxToast(`Diffusion-model remapping failed: ${error.message || error}`, true);
  } finally {
    node.__dmxRemapping = false;
    if (originalSize && node.size) { node.size[0] = originalSize[0]; node.size[1] = originalSize[1]; }
    markDirty(node);
  }
}

function activateRow(node, row) {
  const rows = rowWidgets(node);
  const activeIndex = rows.indexOf(row);
  const values = activateModelRow(rows.map((widget) => widget.value), activeIndex);
  rows.forEach((widget, index) => { widget.value = values[index]; });
  markDirty(node);
}

function createRowWidget(name, value) {
  return {
    name, type: "custom", __dmx: true, __dmxRow: true, value: normalizeModelRow(value),
    computeSize: () => [MIN_W, ROW_H], serializeValue() { return normalizeModelRow(this.value); },
    draw(ctx, node, width, y) {
      this.last_y = y; ctx.save(); ctx.globalAlpha = app.canvas?.editor_alpha ?? 1;
      drawBox(ctx, 10, y, width - 20, "", this.value.on); drawRadio(ctx, 17, y, this.value.on);
      ctx.fillStyle = this.value.on ? "#f1f4f7" : "#9299a3"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
      const label = rowFilenameStem(this.value) || this.value.load_name || "None";
      ctx.fillText(fitText(ctx, label, width - 112), 48, y + ROW_H / 2);
      drawBox(ctx, width - 10 - REMOVE_W, y, REMOVE_W, "x", false); ctx.restore();
    },
    mouse(event, pos, node) {
      if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
      const x = Number(pos?.[0] || 0); const width = node.size?.[0] || MIN_W;
      if (event.button === 2) { rowMenu(node, this, event); return true; }
      if (x >= width - 10 - REMOVE_W) { removeRowWidget(node, this); return true; }
      if (x < 44) { activateRow(node, this); return true; }
      openRowDetails(node, this); return true;
    },
  };
}

function nodeWidth(node) {
  const width = Number(node?.size?.[0]);
  return Number.isFinite(width) && width > 0 ? width : MIN_W;
}

function restoreNodeWidth(node, width) {
  if (!node?.size || !Number.isFinite(width) || width <= 0 || node.size[0] === width) return;
  node.size[0] = width; markDirty(node);
}

function restoreNodeWidthSoon(node, width) {
  restoreNodeWidth(node, width);
  if (typeof queueMicrotask === "function") queueMicrotask(() => restoreNodeWidth(node, width));
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => restoreNodeWidth(node, width));
  window.setTimeout(() => restoreNodeWidth(node, width), 0);
}

function resizeNode(node, preservedWidth = null) {
  const requested = Number(preservedWidth); const hasPreserved = Number.isFinite(requested) && requested > 0;
  const targetWidth = hasPreserved ? requested : Math.max(MIN_W, nodeWidth(node));
  node.size = node.size || [targetWidth, 120]; node.size[0] = targetWidth;
  const computed = node.computeSize?.() || [targetWidth, node.size[1]];
  node.size[0] = hasPreserved ? targetWidth : Math.max(targetWidth, Number(computed?.[0]) || 0, MIN_W);
  node.size[1] = Math.max(120, Number(computed?.[1]) || node.size[1] || 120);
  if (hasPreserved) restoreNodeWidthSoon(node, targetWidth);
  markDirty(node);
}

function addCustomWidget(node, widget) {
  node.widgets = node.widgets || []; node.widgets.push(widget); return widget;
}

function nextRowName(node) {
  node.__dmxCounter = Number(node.__dmxCounter || 0) + 1;
  return `diffusion_model_${node.__dmxCounter}`;
}

function moveBeforeAddButton(node, widget) {
  const widgets = node.widgets || []; const buttonIndex = widgets.findIndex((candidate) => candidate.__dmxAddButton); const currentIndex = widgets.indexOf(widget);
  if (buttonIndex < 0 || currentIndex < 0 || currentIndex < buttonIndex) return;
  widgets.splice(currentIndex, 1); widgets.splice(buttonIndex, 0, widget);
}

function addRow(node, value, preservedWidth = nodeWidth(node)) {
  const existingRows = rowWidgets(node);
  for (const row of existingRows) row.value.on = false;
  const widget = addCustomWidget(node, createRowWidget(nextRowName(node), { ...normalizeModelRow(value), on: true }));
  moveBeforeAddButton(node, widget); resizeNode(node, preservedWidth); return widget;
}

function removeDmxWidgets(node) {
  node.widgets = (node.widgets || []).filter((widget) => !widget.__dmx);
}

function setupNode(node, rowValues = []) {
  const width = nodeWidth(node); removeDmxWidgets(node); node.serialize_widgets = true; node.__dmxCounter = 0;
  addCustomWidget(node, createHeaderWidget());
  const restored = restoreModelRows(rowValues);
  for (const value of restored) addCustomWidget(node, createRowWidget(nextRowName(node), value));
  const addButton = node.addWidget("button", "+ Add Diffusion Model", "", () => openPicker((item) => addRow(node, defaultModelRow(item, true))));
  addButton.__dmx = true; addButton.__dmxAddButton = true; resizeNode(node, width);
}

function setRowFromItem(node, row, item) {
  row.value = { ...defaultModelRow(item, row.value?.on !== false), on: row.value?.on !== false };
  markDirty(node);
}

function removeRowWidget(node, row) {
  const width = nodeWidth(node); const rows = rowWidgets(node); const index = rows.indexOf(row);
  const values = removeModelRow(rows.map((widget) => widget.value), index);
  setupNode(node, values); resizeNode(node, width);
}

function openRowDetails(node, row) {
  const value = normalizeModelRow(row.value);
  const loadName = normalizePath(value.load_name); const filename = loadName.split("/").pop() || loadName;
  openDetails({
    load_name: loadName, filename, file_stem: stripExtension(filename), display_name: stripExtension(filename),
    folder: normalizePath(value.path), full_path: normalizePath(value.metadata?.file_path), sha256: value.sha256,
    file_size: modelItemFileSize(value),
    preview_url: normalizePath(value.metadata?.preview_url), base_model: value.metadata?.base_model || "", sub_type: value.metadata?.sub_type || "diffusion_model",
    tags: Array.isArray(value.metadata?.tags) ? value.metadata.tags : [], metadata: value.metadata || {},
  }, (item) => setRowFromItem(node, row, item));
}

function rowMenu(node, row, event) {
  if (!window.LiteGraph?.ContextMenu) return;
  new LiteGraph.ContextMenu([
    { content: row.value.on ? "Active" : "Make Active", disabled: Boolean(row.value.on), callback: () => activateRow(node, row) },
    { content: "Replace", callback: () => openPicker((item) => setRowFromItem(node, row, item)) },
    null,
    { content: "Remove", callback: () => removeRowWidget(node, row) },
  ], { event, title: "Load Diffusion Model X" });
}

function dmxLocalPosition(node, pos) {
  let x = Number(pos?.[0] || 0); let y = Number(pos?.[1] || 0);
  const width = node.size?.[0] || MIN_W; const height = node.size?.[1] || 0;
  if (node.pos && (x > width || y > height)) { x -= node.pos[0]; y -= node.pos[1]; }
  return [x, y];
}

function updateDmxRemapHover(node, pos) {
  const header = (node.widgets || []).find((widget) => widget.name === "diffusion_model_header");
  if (!header || header.last_y == null) return;
  const [x, y] = dmxLocalPosition(node, pos);
  const hover = x >= REMAP_X && x <= REMAP_X + REMAP_W && y >= header.last_y && y <= header.last_y + HEADER_H;
  if (hover === Boolean(node.__dmxRemapHover)) return;
  node.__dmxRemapHover = hover; markDirty(node);
}

function handleRowClick(node, event, pos) {
  const [x, y] = dmxLocalPosition(node, pos); const width = node.size?.[0] || MIN_W;
  for (const widget of node.widgets || []) {
    if (!widget.__dmx || widget.last_y == null) continue;
    const height = widget.__dmxRow ? ROW_H : HEADER_H;
    if (y < widget.last_y || y > widget.last_y + height) continue;
    if (widget.name === "diffusion_model_header") {
      if (x >= REMAP_X && x <= REMAP_X + REMAP_W) { remapModelRows(node); return true; }
      return false;
    }
    if (!widget.__dmxRow) return false;
    if (event.button === 2) { rowMenu(node, widget, event); return true; }
    if (x >= width - 10 - REMOVE_W) { removeRowWidget(node, widget); return true; }
    if (x < 44) { activateRow(node, widget); return true; }
    const value = normalizeModelRow(widget.value); const loadName = normalizePath(value.load_name); const filename = loadName.split("/").pop() || loadName;
    openDetails({
      load_name: loadName, filename, file_stem: stripExtension(filename), display_name: stripExtension(filename), folder: normalizePath(value.path),
      full_path: normalizePath(value.metadata?.file_path), sha256: value.sha256, file_size: modelItemFileSize(value), preview_url: normalizePath(value.metadata?.preview_url),
      base_model: value.metadata?.base_model || "", sub_type: value.metadata?.sub_type || "diffusion_model", tags: value.metadata?.tags || [], metadata: value.metadata || {},
    }, (item) => setRowFromItem(node, widget, item));
    return true;
  }
  return false;
}

app.registerExtension({
  name: EXTENSION_NAME,
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_TYPE) return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function workflowXLoadDiffusionModelXCreated() {
      originalCreated?.apply(this, arguments); setupNode(this);
    };
    const originalConfigure = nodeType.prototype.configure;
    nodeType.prototype.configure = function workflowXLoadDiffusionModelXConfigure(info) {
      const values = restoreModelRows(info?.widgets_values);
      const nativeValues = Array.isArray(info?.widgets_values) ? info.widgets_values.filter((value) => typeof value !== "object").slice(0, 1) : [];
      const configureInfo = info && Array.isArray(info.widgets_values) ? { ...info, widgets_values: nativeValues } : info;
      const args = [...arguments]; args[0] = configureInfo;
      const result = originalConfigure?.apply(this, args); setupNode(this, values); return result;
    };
    const originalMouseDown = nodeType.prototype.onMouseDown;
    nodeType.prototype.onMouseDown = function workflowXLoadDiffusionModelXMouseDown(event, pos) {
      if (handleRowClick(this, event, pos || app.canvas?.graph_mouse || [0, 0])) return true;
      return originalMouseDown?.apply(this, arguments);
    };

    const originalMouseMove = nodeType.prototype.onMouseMove;
    nodeType.prototype.onMouseMove = function workflowXLoadDiffusionModelXMouseMove(event, pos) {
      updateDmxRemapHover(this, pos || app.canvas?.graph_mouse || [0, 0]);
      return originalMouseMove?.apply(this, arguments);
    };

    const originalMouseLeave = nodeType.prototype.onMouseLeave;
    nodeType.prototype.onMouseLeave = function workflowXLoadDiffusionModelXMouseLeave() {
      if (this.__dmxRemapHover) { this.__dmxRemapHover = false; markDirty(this); }
      return originalMouseLeave?.apply(this, arguments);
    };
  },
});
