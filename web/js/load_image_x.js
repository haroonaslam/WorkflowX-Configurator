import { app } from "/scripts/app.js";
import {
  filterCatalog,
  groupCatalog,
  higherNodeClipRects,
  isSquareDimensions,
  thumbnailURL,
  viewURL,
} from "./load_image_x_helpers.mjs";

const CATALOG_URL = "/workflowx_configurator/load_image_x/images";
const BATCH_SIZE = 80;
const BROWSE_WIDGET_HEIGHT = 50;
const PREVIEW_WIDGET_NAME = "$$canvas-image-preview";
const catalogCache = { items: null, etag: "", promise: null };
const previewContextPatches = new WeakMap();
let cssInstalled = false;

function installCSS() {
  if (cssInstalled) return;
  cssInstalled = true;
  const style = document.createElement("style");
  style.textContent = `
    .workflowx-lix-button {
      width:100%; padding:8px; cursor:pointer; background:#3a3a3a; color:#eee;
      border:1px solid #555; border-radius:4px; font:12px ui-sans-serif,system-ui,sans-serif;
    }
    .workflowx-lix-button:hover { border-color:#7aa2f7; background:#414141; }
    .workflowx-lix-overlay {
      position:fixed; inset:0; z-index:99999; display:flex; align-items:center;
      justify-content:center; background:rgba(0,0,0,.76); font-family:ui-sans-serif,system-ui,sans-serif;
    }
    .workflowx-lix-modal {
      width:80vw; max-width:1040px; height:min(80vh,760px); min-height:420px;
      display:flex; flex-direction:column; gap:10px; box-sizing:border-box; padding:16px;
      color:#eee; background:#262626; border:1px solid #494949; border-radius:9px;
      box-shadow:0 24px 70px rgba(0,0,0,.55);
    }
    .workflowx-lix-header, .workflowx-lix-searchrow { display:flex; gap:8px; align-items:center; }
    .workflowx-lix-title { flex:1; font-size:16px; font-weight:700; }
    .workflowx-lix-iconbtn {
      border:1px solid #4b4b4b; border-radius:4px; background:#333; color:#ccc;
      min-width:34px; height:32px; padding:0 10px; cursor:pointer;
    }
    .workflowx-lix-iconbtn:hover { color:#fff; border-color:#7aa2f7; }
    .workflowx-lix-iconbtn:disabled { cursor:wait; opacity:.55; }
    .workflowx-lix-search {
      flex:1; box-sizing:border-box; padding:8px 11px; background:#171717; color:#eee;
      border:1px solid #444; border-radius:4px; outline:none; font-size:13px;
    }
    .workflowx-lix-search:focus { border-color:#7aa2f7; }
    .workflowx-lix-body { min-height:0; flex:1; display:flex; border:1px solid #3c3c3c; border-radius:6px; overflow:hidden; }
    .workflowx-lix-folders { width:176px; flex:none; overflow:auto; background:#181818; border-right:1px solid #383838; }
    .workflowx-lix-folder {
      display:flex; gap:8px; align-items:center; padding:9px 10px; color:#aaa; cursor:pointer;
      font-size:11px; border-left:3px solid transparent;
    }
    .workflowx-lix-folder:hover { color:#eee; background:#252525; }
    .workflowx-lix-folder.active { color:#a9c1ff; background:rgba(122,162,247,.15); border-left-color:#7aa2f7; }
    .workflowx-lix-folder-name { min-width:0; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .workflowx-lix-folder-count { color:#777; font-size:10px; }
    .workflowx-lix-grid {
      position:relative; min-width:0; flex:1; overflow-y:auto; align-content:start;
      display:grid; grid-template-columns:repeat(auto-fill,minmax(128px,1fr)); gap:8px; padding:9px;
      background:#202020;
    }
    .workflowx-lix-cell {
      min-width:0; display:flex; flex-direction:column; align-items:center; padding:6px;
      box-sizing:border-box; cursor:pointer; background:#181818; border:2px solid transparent;
      border-radius:6px; transition:border-color .12s,background .12s;
    }
    .workflowx-lix-cell:hover { border-color:#777; background:#1c1c1c; }
    .workflowx-lix-cell.current { border-color:#7aa2f7; }
    .workflowx-lix-thumb {
      width:112px; height:112px; display:flex; align-items:center; justify-content:center;
      box-sizing:border-box; border-radius:4px; overflow:hidden;
      background:#111; color:#555; font-size:22px;
    }
    .workflowx-lix-thumb.non-square { padding:5px; }
    .workflowx-lix-thumb img { width:100%; height:100%; display:block; object-fit:contain; }
    .workflowx-lix-label {
      width:100%; margin-top:5px; color:#ccc; font-size:10px; line-height:1.25;
      text-align:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    }
    .workflowx-lix-empty { grid-column:1/-1; align-self:center; justify-self:center; color:#888; padding:30px; }
    .workflowx-lix-sentinel { grid-column:1/-1; height:1px; }
    .workflowx-lix-footer { color:#888; font-size:10px; text-align:center; min-height:14px; }
    @media (max-width:700px) {
      .workflowx-lix-modal { width:94vw; height:88vh; }
      .workflowx-lix-folders { width:126px; }
    }
  `;
  document.head.appendChild(style);
}

async function fetchCatalog(force = false) {
  if (catalogCache.promise) return catalogCache.promise;
  catalogCache.promise = (async () => {
    const headers = {};
    if (catalogCache.etag) headers["If-None-Match"] = catalogCache.etag;
    const response = await fetch(`${CATALOG_URL}${force ? "?refresh=1" : ""}`, { headers });
    if (response.status === 304 && catalogCache.items) return catalogCache.items;
    if (!response.ok) throw new Error(`Catalog request failed (${response.status})`);
    const payload = await response.json();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    catalogCache.items = items;
    catalogCache.etag = response.headers.get("ETag") || "";
    return items;
  })();
  try {
    return await catalogCache.promise;
  } finally {
    catalogCache.promise = null;
  }
}

function updateWidgetOptions(imageWidget, items) {
  if (!imageWidget.options) imageWidget.options = {};
  imageWidget.options.values = items.map((item) => item.path);
}

function loadNodePreview(node, item) {
  if (!item?.path) return;
  node._workflowxLixPreviewRequest = (node._workflowxLixPreviewRequest | 0) + 1;
  const requestId = node._workflowxLixPreviewRequest;
  const preview = new Image();
  preview.onload = () => {
    if (node._workflowxLixPreviewRequest !== requestId) return;
    node.imageIndex = 0;
    node.imgs = [preview];
    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
    ensureNativeCanvasPreviewPatched(node);
  };
  preview.src = viewURL(item);
}

function patchDeferredPreviewContext(ctx, node, widget, width) {
  let state = previewContextPatches.get(ctx);
  if (!state) {
    const originalDrawImage = ctx.drawImage;
    state = {
      originalDrawImage,
      rules: new Map(),
      restoreQueued: false,
      wrappedDrawImage(source, ...args) {
        const rule = state.rules.get(source);
        if (!rule) return originalDrawImage.call(this, source, ...args);
        this.save();
        this.beginPath();
        this.rect(0, rule.y, rule.width, rule.height);
        for (const clipRect of rule.clipRects) {
          this.rect(clipRect.x, clipRect.y, clipRect.width, clipRect.height);
        }
        this.clip("evenodd");
        originalDrawImage.call(this, source, ...args);
        this.restore();
      },
    };
    ctx.drawImage = state.wrappedDrawImage;
    previewContextPatches.set(ctx, state);
  }

  const clipRects = higherNodeClipRects(
    node,
    node.graph?._nodes || node.graph?.nodes || [],
    globalThis.LiteGraph?.NODE_TITLE_HEIGHT || 30,
  );
  const rule = {
    y: Number(widget.y) || 0,
    width: Number(width) || Number(node.size?.[0]) || 1,
    height: Number(widget.computedHeight) || 220,
    clipRects,
  };
  for (const image of node.imgs || []) state.rules.set(image, rule);

  return () => {
    if (state.restoreQueued) return;
    state.restoreQueued = true;
    // The native preview has already queued ComfyUI's deferred image pass.
    // Restore drawImage in the following microtask, after that pass completes.
    queueMicrotask(() => {
      if (ctx.drawImage === state.wrappedDrawImage) ctx.drawImage = state.originalDrawImage;
      previewContextPatches.delete(ctx);
    });
  };
}

function ensureNativeCanvasPreviewPatched(node, attempt = 0) {
  const widget = node.widgets?.find((candidate) => candidate.name === PREVIEW_WIDGET_NAME);
  if (widget?.drawWidget) {
    if (widget._workflowxLoadImageXPatched) return;
    widget._workflowxLoadImageXPatched = true;
    const originalDrawWidget = widget.drawWidget;
    widget.drawWidget = function (ctx, options) {
      const scheduleRestore = patchDeferredPreviewContext(ctx, node, this, options?.width);
      try {
        return originalDrawWidget.apply(this, arguments);
      } finally {
        scheduleRestore();
      }
    };
    node.setDirtyCanvas?.(true, true);
    return;
  }
  if (attempt < 60 && node.graph) {
    setTimeout(() => ensureNativeCanvasPreviewPatched(node, attempt + 1), 50);
  }
}

function selectImage(node, imageWidget, item) {
  const values = imageWidget.options?.values || [];
  if (!values.includes(item.path)) {
    values.push(item.path);
    values.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  }
  imageWidget.value = item.path;
  imageWidget.callback?.(item.path);
  loadNodePreview(node, item);
  node.graph?.setDirtyCanvas?.(true, true);
}

function openPicker(node, imageWidget) {
  document.querySelector(".workflowx-lix-overlay")?._workflowxClose?.();

  const overlay = document.createElement("div");
  overlay.className = "workflowx-lix-overlay";
  const modal = document.createElement("div");
  modal.className = "workflowx-lix-modal";
  overlay.appendChild(modal);

  const header = document.createElement("div");
  header.className = "workflowx-lix-header";
  const title = document.createElement("div");
  title.className = "workflowx-lix-title";
  title.textContent = "Select Image";
  const refreshButton = document.createElement("button");
  refreshButton.className = "workflowx-lix-iconbtn";
  refreshButton.textContent = "Refresh";
  refreshButton.title = "Rescan ComfyUI input folders";
  const closeButton = document.createElement("button");
  closeButton.className = "workflowx-lix-iconbtn";
  closeButton.textContent = "✕";
  closeButton.title = "Close";
  header.append(title, refreshButton, closeButton);

  const searchRow = document.createElement("div");
  searchRow.className = "workflowx-lix-searchrow";
  const search = document.createElement("input");
  search.className = "workflowx-lix-search";
  search.type = "search";
  search.placeholder = "Filter images or folders…";
  searchRow.appendChild(search);

  const body = document.createElement("div");
  body.className = "workflowx-lix-body";
  const folders = document.createElement("div");
  folders.className = "workflowx-lix-folders";
  const grid = document.createElement("div");
  grid.className = "workflowx-lix-grid";
  body.append(folders, grid);

  const footer = document.createElement("div");
  footer.className = "workflowx-lix-footer";
  modal.append(header, searchRow, body, footer);
  document.body.appendChild(overlay);

  let items = catalogCache.items || [];
  let activeFolder = null;
  let filteredItems = [];
  let renderedCount = 0;
  let closed = false;

  const imageObserver = typeof IntersectionObserver === "function"
    ? new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const image = entry.target;
          imageObserver.unobserve(image);
          image.src = image.dataset.src;
        }
      }, { root: grid, rootMargin: "300px" })
    : null;

  const sentinel = document.createElement("div");
  sentinel.className = "workflowx-lix-sentinel";
  const batchObserver = typeof IntersectionObserver === "function"
    ? new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) renderMore();
      }, { root: grid, rootMargin: "500px" })
    : null;

  const close = () => {
    if (closed) return;
    closed = true;
    imageObserver?.disconnect();
    batchObserver?.disconnect();
    document.removeEventListener("keydown", onKeyDown, true);
    overlay.remove();
  };
  overlay._workflowxClose = close;
  const onKeyDown = (event) => {
    if (event.key === "Escape") close();
  };

  function makeFolder(key, label, count) {
    const entry = document.createElement("div");
    entry.className = `workflowx-lix-folder${activeFolder === key && !search.value.trim() ? " active" : ""}`;
    entry.title = label;
    const name = document.createElement("span");
    name.className = "workflowx-lix-folder-name";
    name.textContent = label;
    const number = document.createElement("span");
    number.className = "workflowx-lix-folder-count";
    number.textContent = String(count);
    entry.append(name, number);
    entry.addEventListener("click", () => {
      activeFolder = key;
      search.value = "";
      render();
    });
    return entry;
  }

  function renderFolders() {
    folders.replaceChildren();
    folders.appendChild(makeFolder(null, "All", items.length));
    for (const group of groupCatalog(items)) {
      folders.appendChild(makeFolder(group.folder, group.folder || "root", group.items.length));
    }
  }

  function makeCell(item) {
    const cell = document.createElement("div");
    cell.className = `workflowx-lix-cell${imageWidget.value === item.path ? " current" : ""}`;
    cell.title = item.path;
    const thumbnail = document.createElement("div");
    thumbnail.className = "workflowx-lix-thumb";
    const glyph = document.createElement("span");
    glyph.textContent = "▧";
    const image = document.createElement("img");
    image.alt = "";
    image.decoding = "async";
    image.loading = "lazy";
    image.dataset.src = thumbnailURL(item);
    image.addEventListener("load", () => {
      glyph.remove();
      thumbnail.classList.toggle(
        "non-square",
        !isSquareDimensions(image.naturalWidth, image.naturalHeight),
      );
    });
    image.addEventListener("error", () => { image.remove(); glyph.textContent = "×"; });
    thumbnail.append(glyph, image);
    const label = document.createElement("div");
    label.className = "workflowx-lix-label";
    label.textContent = item.name;
    cell.append(thumbnail, label);
    cell.addEventListener("click", () => {
      selectImage(node, imageWidget, item);
      close();
    });
    if (imageObserver) imageObserver.observe(image);
    else image.src = image.dataset.src;
    return cell;
  }

  function renderMore() {
    const end = Math.min(renderedCount + BATCH_SIZE, filteredItems.length);
    batchObserver?.unobserve(sentinel);
    sentinel.remove();
    for (const item of filteredItems.slice(renderedCount, end)) grid.appendChild(makeCell(item));
    renderedCount = end;
    if (renderedCount < filteredItems.length) {
      grid.appendChild(sentinel);
      batchObserver?.observe(sentinel);
    }
    footer.textContent = `${filteredItems.length} image${filteredItems.length === 1 ? "" : "s"}${search.value.trim() ? " · search" : activeFolder === null ? " · all" : ` · ${activeFolder || "root"}`}`;
  }

  function render() {
    imageObserver?.disconnect();
    batchObserver?.disconnect();
    grid.replaceChildren();
    renderFolders();
    filteredItems = filterCatalog(items, search.value, activeFolder);
    renderedCount = 0;
    if (!filteredItems.length) {
      const empty = document.createElement("div");
      empty.className = "workflowx-lix-empty";
      empty.textContent = items.length ? "No matching images" : "No images found in ComfyUI input folders";
      grid.appendChild(empty);
      footer.textContent = "0 images";
      return;
    }
    renderMore();
  }

  async function refresh(force) {
    refreshButton.disabled = true;
    refreshButton.textContent = "Loading…";
    try {
      items = await fetchCatalog(force);
      updateWidgetOptions(imageWidget, items);
      if (!closed) render();
    } catch (error) {
      console.error("[Load ImageX] catalog refresh failed", error);
      if (!closed && !items.length) {
        grid.replaceChildren();
        const empty = document.createElement("div");
        empty.className = "workflowx-lix-empty";
        empty.textContent = "Could not load the image catalog";
        grid.appendChild(empty);
        footer.textContent = String(error?.message || error);
      }
    } finally {
      if (!closed) {
        refreshButton.disabled = false;
        refreshButton.textContent = "Refresh";
      }
    }
  }

  closeButton.addEventListener("click", close);
  refreshButton.addEventListener("click", () => refresh(true));
  overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });
  search.addEventListener("input", render);
  search.addEventListener("keydown", (event) => event.stopPropagation());
  document.addEventListener("keydown", onKeyDown, true);

  if (items.length) {
    updateWidgetOptions(imageWidget, items);
    render();
  } else {
    const loading = document.createElement("div");
    loading.className = "workflowx-lix-empty";
    loading.textContent = "Loading images…";
    grid.appendChild(loading);
  }
  refresh(true);
  queueMicrotask(() => search.focus());
}

app.registerExtension({
  name: "WorkflowX.LoadImageX",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "WorkflowX_LoadImageX") return;
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalCreated?.apply(this, arguments);
      if (this._workflowxLoadImageXSetup) return result;
      this._workflowxLoadImageXSetup = true;
      installCSS();
      queueMicrotask(() => {
        const imageWidget = this.widgets?.find((widget) => widget.name === "image");
        if (!imageWidget) return;
        const button = document.createElement("button");
        button.className = "workflowx-lix-button";
        button.textContent = "▧ Browse Thumbnails";
        button.addEventListener("click", () => openPicker(this, imageWidget));
        this.addDOMWidget("workflowx_load_image_x_browse", "button", button, {
          getMinHeight: () => BROWSE_WIDGET_HEIGHT,
          getMaxHeight: () => BROWSE_WIDGET_HEIGHT,
        });
        if (!this.imgs?.length && imageWidget.value) {
          loadNodePreview(this, { path: String(imageWidget.value), version: "" });
        } else if (this.imgs?.length) {
          ensureNativeCanvasPreviewPatched(this);
        }
      });
      return result;
    };
  },
});
