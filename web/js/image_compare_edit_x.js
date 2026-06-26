import { app } from "../../scripts/app.js";

const NODE_TYPE = "KVGC_ImageCompareEditX";
const STATE_KEY = "workflowxImageCompareEditX";
const SAVE_ROUTE = "/workflowx_configurator/image_compare_edit_x/save";
const PREPARE_ROUTE = "/workflowx_configurator/image_compare_edit_x/prepare";

const BRAND = "#ff6847";
const GREEN = "#36c48f";
const AMBER = "#f6b44b";
const PANEL = "#191b1e";
const TEXT = "#e7eaee";
const MUTED = "#9aa3ad";

const PAD = 8;
const GAP = 4;
const ROW_H = 20;
const CONTROL_X = 118;
const MIN_W = 620;
const MIN_H = 520;
const PREVIEW_MAX = 1400;

const IMAGE_OPTIONS = [
  ["1", "Image 1"],
  ["2", "Image 2"],
  ["3", "Image 3"],
];
const VIEW_MODES = [
  ["single", "Single"],
  ["split", "Split"],
  ["overlay", "Overlay"],
  ["difference", "Difference"],
];
const SPLIT_MODES = [
  ["leftRight", "Left/Right"],
  ["rightLeft", "Right/Left"],
  ["upDown", "Up/Down"],
];

// Adjustment math and preset values are adapted from ComfyUI-Pixaroma's
// MIT-licensed composer fx_engine.mjs so Image Compare Edit X remains
// WorkflowX-owned while matching the familiar Pixaroma adjustment behavior.
const NEUTRAL = {
  brightness: 0,
  contrast: 0,
  exposure: 0,
  highlights: 0,
  shadows: 0,
  whites: 0,
  blacks: 0,
  saturation: 0,
  vibrance: 0,
  temperature: 0,
  tint: 0,
  hue: 0,
  sharpness: 0,
  clarity: 0,
  grain: 0,
  vignette: 0,
  fade: 0,
};

const PRESETS = {
  Original: {},
  Cinema: { contrast: 22, saturation: 8, vibrance: 14, temperature: -10, tint: 4, clarity: 8, blacks: 8 },
  Vivid: { saturation: 30, vibrance: 22, contrast: 14, clarity: 8 },
  Teal: { temperature: -30, tint: 6, saturation: 14, vibrance: 12, contrast: 8 },
  Amber: { temperature: 30, contrast: 14, saturation: 6, highlights: -8, grain: 22, fade: 8 },
  Sienna: { temperature: 26, saturation: -6, contrast: 6, fade: 24, blacks: 10, highlights: -10 },
  Safari: { temperature: 18, contrast: 16, saturation: 8, vibrance: 8, clarity: 12 },
  Tropic: { temperature: -8, saturation: 24, vibrance: 18, contrast: 12, clarity: 6, exposure: 3 },
  Bloom: { temperature: 8, saturation: 18, vibrance: 16, contrast: 10, clarity: 6 },
  Forest: { contrast: 24, blacks: 18, shadows: -10, saturation: -16, tint: 8, temperature: -6, vignette: 22, clarity: 8 },
  Emerald: { contrast: 14, saturation: -10, tint: 14, temperature: -6, blacks: 10, fade: 8 },
  Nordic: { contrast: 10, saturation: -8, temperature: -12, tint: 10, fade: 16, blacks: 8, highlights: -6 },
  Airy: { exposure: 6, brightness: 8, contrast: -8, fade: 18, blacks: 12, highlights: -8, saturation: -4 },
  Crisp: { contrast: 16, clarity: 16, sharpness: 12, saturation: 10, vibrance: 8 },
  Street: { contrast: 26, blacks: 20, saturation: -14, clarity: 12, sharpness: 8, vignette: 14 },
};

const FX_GROUPS = [
  ["Tone", ["brightness", "contrast", "exposure", "highlights", "shadows", "whites", "blacks"]],
  ["Color", ["saturation", "vibrance", "temperature", "tint", "hue"]],
  ["Detail", ["sharpness", "clarity", "grain"]],
  ["Effects", ["vignette", "fade"]],
];

const FX_RANGES = {
  hue: [-180, 180],
  sharpness: [0, 100],
  grain: [0, 100],
  vignette: [0, 100],
  fade: [0, 100],
};

const DEFAULTS = {
  pair: "1-2",
  mode: "show2",
  sourceA: "2",
  sourceB: "1",
  viewMode: "single",
  splitMode: "leftRight",
  layerOrder: "2over1",
  topOpacity: 0.65,
  splitX: 0.5,
  splitY: 0.5,
  tool: "brush",
  brushTarget: "blend",
  showMask: true,
  brush: {
    size: 64,
    hardness: 0.65,
    softness: 0.35,
    opacity: 0.85,
    flow: 0.65,
  },
  adjustments: { ...NEUTRAL },
  adjustmentPreset: "Original",
  adjustmentAmount: 1,
  adjustmentMode: "global",
  adjustmentLayers: [],
  selectedAdjustmentLayerId: "",
  maskData: "",
  adjustmentBrushData: "",
  images: [],
  editorZoom: 1,
  editorPanX: 0,
  editorPanY: 0,
  performanceMode: "fast",
  beforePreview: false,
  layoutVersion: 3,
};

const LR = 0.2126;
const LG = 0.7152;
const LB = 0.0722;

function cloneDefaults() {
  return {
    ...DEFAULTS,
    brush: { ...DEFAULTS.brush },
    adjustments: { ...NEUTRAL },
    adjustmentLayers: [],
    images: [],
  };
}

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

function clamp01(v) {
  return clamp(v, 0, 1);
}

function safeNumber(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function validImageKey(value, fallback = "1") {
  const key = String(value ?? "");
  return IMAGE_OPTIONS.some(([candidate]) => candidate === key) ? key : fallback;
}

function validViewMode(value, fallback = "single") {
  return VIEW_MODES.some(([candidate]) => candidate === value) ? value : fallback;
}

function validSplitMode(value, fallback = "leftRight") {
  return SPLIT_MODES.some(([candidate]) => candidate === value) ? value : fallback;
}

function splitPair(value) {
  const match = /^([123])-([123])$/.exec(String(value || ""));
  return match ? [match[1], match[2]] : ["1", "2"];
}

function syncLegacyState(s) {
  s.sourceA = validImageKey(s.sourceA, "2");
  s.sourceB = validImageKey(s.sourceB, s.sourceA === "1" ? "2" : "1");
  s.viewMode = validViewMode(s.viewMode, "single");
  s.splitMode = validSplitMode(s.splitMode, "leftRight");
  s.pair = `${s.sourceA}-${s.sourceB}`;
  if (s.viewMode === "single") s.mode = `show${s.sourceA}`;
  else if (s.viewMode === "split") s.mode = s.splitMode;
  else s.mode = s.viewMode;
}

function migrateCompactState(s, saved = {}) {
  const hasCompact =
    saved.sourceA != null ||
    saved.sourceB != null ||
    saved.viewMode != null ||
    saved.splitMode != null;

  if (!hasCompact) {
    const [a, b] = splitPair(saved.pair || s.pair);
    if (saved.mode === "show1" || saved.mode === "show2" || saved.mode === "show3") {
      s.sourceA = saved.mode.slice(-1);
      s.sourceB = s.sourceA === a ? b : a;
      s.viewMode = "single";
    } else if (saved.mode === "leftRight" || saved.mode === "rightLeft" || saved.mode === "upDown") {
      s.sourceA = a;
      s.sourceB = b;
      s.viewMode = "split";
      s.splitMode = saved.mode;
    } else if (saved.mode === "overlay" || saved.mode === "difference") {
      s.sourceA = a;
      s.sourceB = b;
      s.viewMode = saved.mode;
    }
  }

  syncLegacyState(s);
}

function mergeAdjustments(adj) {
  const out = { ...NEUTRAL };
  if (adj) {
    for (const key of Object.keys(NEUTRAL)) {
      if (adj[key] != null) out[key] = safeNumber(adj[key], 0);
    }
  }
  return out;
}

function isNeutral(adj, amount01) {
  if (amount01 <= 0) return true;
  const a = mergeAdjustments(adj);
  return Object.keys(a).every((key) => a[key] === 0);
}

function makeLayerId() {
  return `adj_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function createAdjustmentLayer(mode = "global", options = {}) {
  return {
    id: options.id || makeLayerId(),
    name: options.name || (mode === "brush" ? "Brush Adjustment" : "Global Adjustment"),
    visible: options.visible !== false,
    mode: options.mode === "brush" || mode === "brush" ? "brush" : "global",
    amount: clamp01(safeNumber(options.amount, 1)),
    preset: options.preset || "Original",
    adjustments: mergeAdjustments(options.adjustments),
    maskData: options.maskData || "",
    maskCanvas: options.maskCanvas || null,
    maskKey: options.maskKey || "",
  };
}

function serializeAdjustmentLayer(layer, includeCanvas = true) {
  return {
    id: layer.id || makeLayerId(),
    name: layer.name || "Adjustment",
    visible: layer.visible !== false,
    mode: layer.mode === "brush" ? "brush" : "global",
    amount: clamp01(safeNumber(layer.amount, 1)),
    preset: layer.preset || "Original",
    adjustments: mergeAdjustments(layer.adjustments),
    maskData: includeCanvas && layer.maskCanvas ? layer.maskCanvas.toDataURL("image/png") : layer.maskData || "",
  };
}

function normalizeAdjustmentLayers(saved = {}, fallbackState = null) {
  const source = Array.isArray(saved.adjustmentLayers) ? saved.adjustmentLayers : [];
  const layers = source
    .filter((layer) => layer && typeof layer === "object")
    .map((layer, index) =>
      createAdjustmentLayer(layer.mode, {
        ...layer,
        id: layer.id || `adj_${index + 1}`,
        name: layer.name || `Adjustment ${index + 1}`,
        amount: layer.amount,
        preset: layer.preset,
        adjustments: layer.adjustments,
        maskData: layer.maskData || "",
      }),
    )
    .filter(Boolean);

  if (layers.length) return layers;

  const oldMode = saved.adjustmentMode === "brush" ? "brush" : "global";
  return [
    createAdjustmentLayer(oldMode, {
      id: "adj_legacy_1",
      name: oldMode === "brush" ? "Brush Adjustment 1" : "Global Adjustment 1",
      visible: true,
      amount: safeNumber(saved.adjustmentAmount, fallbackState?.adjustmentAmount ?? 1),
      preset: saved.adjustmentPreset || fallbackState?.adjustmentPreset || "Original",
      adjustments: saved.adjustments || fallbackState?.adjustments || NEUTRAL,
      maskData: saved.adjustmentBrushData || fallbackState?.adjustmentBrushData || "",
    }),
  ];
}

function selectedAdjustmentLayer(s) {
  if (!Array.isArray(s.adjustmentLayers) || !s.adjustmentLayers.length) {
    s.adjustmentLayers = [createAdjustmentLayer("global", { id: "adj_1", name: "Global Adjustment 1" })];
  }
  let layer = s.adjustmentLayers.find((candidate) => candidate.id === s.selectedAdjustmentLayerId);
  if (!layer) {
    layer = s.adjustmentLayers[0];
    s.selectedAdjustmentLayerId = layer.id;
  }
  return layer;
}

function syncLegacyAdjustmentState(s) {
  const layer = selectedAdjustmentLayer(s);
  s.adjustments = mergeAdjustments(layer.adjustments);
  s.adjustmentPreset = layer.preset || "Original";
  s.adjustmentAmount = clamp01(safeNumber(layer.amount, 1));
  s.adjustmentMode = layer.mode === "brush" ? "brush" : "global";
  s.adjustmentBrushData = layer.maskData || "";
}

function hueMatrix(deg) {
  const a = (deg * Math.PI) / 180;
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [
    0.213 + c * 0.787 - s * 0.213,
    0.715 - c * 0.715 - s * 0.715,
    0.072 - c * 0.072 + s * 0.928,
    0.213 - c * 0.213 + s * 0.143,
    0.715 + c * 0.285 + s * 0.14,
    0.072 - c * 0.072 - s * 0.283,
    0.213 - c * 0.213 - s * 0.787,
    0.715 - c * 0.715 + s * 0.715,
    0.072 + c * 0.928 + s * 0.072,
  ];
}

function sharpenChannel(channel, width, height, strength) {
  const out = new Float32Array(channel.length);
  const at = (x, y) => channel[clamp(y, 0, height - 1) * width + clamp(x, 0, width - 1)];
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let sum = 0;
      for (let dy = -1; dy <= 1; dy += 1) {
        for (let dx = -1; dx <= 1; dx += 1) sum += at(x + dx, y + dy);
      }
      const i = y * width + x;
      const blur = sum / 9;
      out[i] = channel[i] + strength * (channel[i] - blur);
    }
  }
  return out;
}

function applyFx(rgba, width, height, adj, amount01, seed = 9167) {
  amount01 = clamp(safeNumber(amount01, 1), 0, 1);
  if (isNeutral(adj, amount01)) return rgba;

  const a = mergeAdjustments(adj);
  const n = width * height;
  const r = new Float32Array(n);
  const g = new Float32Array(n);
  const b = new Float32Array(n);
  const or = new Float32Array(n);
  const og = new Float32Array(n);
  const ob = new Float32Array(n);

  for (let i = 0, p = 0; i < n; i += 1, p += 4) {
    r[i] = or[i] = rgba[p] / 255;
    g[i] = og[i] = rgba[p + 1] / 255;
    b[i] = ob[i] = rgba[p + 2] / 255;
  }

  const matrix = a.hue ? hueMatrix(a.hue) : null;
  const toneOn = !!(a.exposure || a.brightness || a.contrast || a.blacks || a.shadows || a.highlights || a.whites);

  for (let i = 0; i < n; i += 1) {
    let cr = r[i];
    let cg = g[i];
    let cb = b[i];

    if (toneOn) {
      const lum = LR * cr + LG * cg + LB * cb;
      let target = lum;
      if (a.exposure) target *= 2 ** (a.exposure / 100);
      if (a.brightness) target += a.brightness / 200;
      if (a.contrast) target = (target - 0.5) * (1 + a.contrast / 100) + 0.5;
      if (a.blacks) target += (a.blacks / 100) * 0.5 * clamp(1 - 2 * target, 0, 1);
      if (a.shadows) target += (a.shadows / 100) * 0.5 * (1 - target) * (1 - target);
      if (a.highlights) target += (a.highlights / 100) * 0.5 * target * target;
      if (a.whites) target += (a.whites / 100) * 0.5 * clamp(2 * target - 1, 0, 1);
      const gain = clamp(target / Math.max(lum, 1e-4), 0, 4);
      cr *= gain;
      cg *= gain;
      cb *= gain;
    }

    if (a.temperature) {
      const offset = (a.temperature / 100) * 0.1;
      cr += offset;
      cb -= offset;
    }
    if (a.tint) cg += (a.tint / 100) * 0.1;
    if (a.saturation) {
      const lum = LR * cr + LG * cg + LB * cb;
      const factor = 1 + a.saturation / 100;
      cr = lum + (cr - lum) * factor;
      cg = lum + (cg - lum) * factor;
      cb = lum + (cb - lum) * factor;
    }
    if (a.vibrance) {
      const mx = Math.max(cr, cg, cb);
      const mn = Math.min(cr, cg, cb);
      const sat = mx <= 0 ? 0 : (mx - mn) / mx;
      const amount = (a.vibrance / 100) * (1 - sat);
      const lum = LR * cr + LG * cg + LB * cb;
      const factor = 1 + amount;
      cr = lum + (cr - lum) * factor;
      cg = lum + (cg - lum) * factor;
      cb = lum + (cb - lum) * factor;
    }
    if (matrix) {
      const nr = matrix[0] * cr + matrix[1] * cg + matrix[2] * cb;
      const ng = matrix[3] * cr + matrix[4] * cg + matrix[5] * cb;
      const nb = matrix[6] * cr + matrix[7] * cg + matrix[8] * cb;
      cr = nr;
      cg = ng;
      cb = nb;
    }
    if (a.clarity) {
      const lum = LR * cr + LG * cg + LB * cb;
      const mid = 1 - Math.abs(2 * lum - 1);
      const target = (lum - 0.5) * (1 + (a.clarity / 100) * 0.5 * mid) + 0.5;
      const gain = clamp(target / Math.max(lum, 1e-4), 0, 4);
      cr *= gain;
      cg *= gain;
      cb *= gain;
    }
    r[i] = cr;
    g[i] = cg;
    b[i] = cb;
  }

  if (a.sharpness) {
    const strength = a.sharpness / 100;
    r.set(sharpenChannel(r, width, height, strength));
    g.set(sharpenChannel(g, width, height, strength));
    b.set(sharpenChannel(b, width, height, strength));
  }

  const inv = 1 / 0.70710678;
  const am = amount01;
  const im = 1 - amount01;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = y * width + x;
      let cr = r[i];
      let cg = g[i];
      let cb = b[i];
      if (a.grain) {
        const d = x * 12.9898 + y * 78.233 + seed * 37.719;
        let hash = Math.sin(d) * 43758.5453;
        hash -= Math.floor(hash);
        const noise = (hash - 0.5) * (a.grain / 100) * 0.2;
        cr += noise;
        cg += noise;
        cb += noise;
      }
      if (a.vignette) {
        const dx = (x + 0.5) / width - 0.5;
        const dy = (y + 0.5) / height - 0.5;
        const radius = Math.sqrt(dx * dx + dy * dy) * inv;
        const v = clamp((radius - 0.5) / 0.5, 0, 1);
        const factor = 1 - (a.vignette / 100) * v * v;
        cr *= factor;
        cg *= factor;
        cb *= factor;
      }
      if (a.fade) {
        const m = 1 - (a.fade / 100) * 0.15;
        const o = (a.fade / 100) * 0.1;
        cr = cr * m + o;
        cg = cg * m + o;
        cb = cb * m + o;
      }
      const p = i * 4;
      rgba[p] = Math.round((or[i] * im + clamp01(cr) * am) * 255);
      rgba[p + 1] = Math.round((og[i] * im + clamp01(cg) * am) * 255);
      rgba[p + 2] = Math.round((ob[i] * im + clamp01(cb) * am) * 255);
    }
  }
  return rgba;
}

function getState(node) {
  if (node.__wfxIce) return node.__wfxIce;
  const saved = node.properties?.[STATE_KEY] || {};
  const state = {
    ...cloneDefaults(),
    ...saved,
    brush: { ...DEFAULTS.brush, ...(saved.brush || {}) },
    adjustments: mergeAdjustments(saved.adjustments),
    adjustmentLayers: normalizeAdjustmentLayers(saved, DEFAULTS),
    images: Array.isArray(saved.images) ? saved.images.slice(0, 2) : [],
    img1: null,
    img2: null,
    maskCanvas: null,
    maskKey: "",
    image3: null,
    renderCache: {},
    cacheRevision: 0,
    previewDraft: false,
    previewTimer: null,
    rects: [],
    splitDragging: false,
    opacityDragging: false,
    openDropdown: "",
    dropdownAnchors: {},
    hoverTip: null,
    drawing: false,
    panning: false,
    cursorPoint: null,
    lastPoint: null,
    panStart: null,
    undo: [],
    redo: [],
    toast: "",
    toastTimer: null,
    editor: null,
    layoutVersion: saved.layoutVersion || 0,
  };
  migrateCompactState(state, saved);
  state.brushTarget = state.brushTarget === "adjustment" ? "adjustment" : "blend";
  state.selectedAdjustmentLayerId =
    state.adjustmentLayers.find((layer) => layer.id === saved.selectedAdjustmentLayerId)?.id ||
    state.adjustmentLayers[0]?.id ||
    "";
  state.performanceMode = state.performanceMode === "quality" ? "quality" : "fast";
  state.showMask = state.showMask !== false;
  syncLegacyAdjustmentState(state);
  node.__wfxIce = state;
  return node.__wfxIce;
}

function persist(node, includeMask = false) {
  const s = getState(node);
  syncLegacyState(s);
  syncLegacyAdjustmentState(s);
  const adjustmentLayers = s.adjustmentLayers.map((layer) => serializeAdjustmentLayer(layer, includeMask));
  const selectedSerializedLayer = adjustmentLayers.find((layer) => layer.id === selectedAdjustmentLayer(s).id) || adjustmentLayers[0];
  if (selectedSerializedLayer) s.adjustmentBrushData = selectedSerializedLayer.maskData || "";
  node.properties = node.properties || {};
  node.properties[STATE_KEY] = {
    pair: s.pair,
    mode: s.mode,
    sourceA: s.sourceA,
    sourceB: s.sourceB,
    viewMode: s.viewMode,
    splitMode: s.splitMode,
    layerOrder: s.layerOrder,
    topOpacity: s.topOpacity,
    splitX: s.splitX,
    splitY: s.splitY,
    tool: s.tool,
    brushTarget: s.brushTarget,
    showMask: s.showMask !== false,
    brush: { ...s.brush },
    adjustments: mergeAdjustments(s.adjustments),
    adjustmentPreset: s.adjustmentPreset,
    adjustmentAmount: s.adjustmentAmount,
    adjustmentMode: s.adjustmentMode === "brush" ? "brush" : "global",
    adjustmentLayers,
    selectedAdjustmentLayerId: selectedAdjustmentLayer(s).id,
    maskData: includeMask && s.maskCanvas ? s.maskCanvas.toDataURL("image/png") : s.maskData || "",
    adjustmentBrushData: s.adjustmentBrushData || "",
    images: s.images || [],
    editorZoom: s.editorZoom,
    editorPanX: s.editorPanX,
    editorPanY: s.editorPanY,
    performanceMode: s.performanceMode === "quality" ? "quality" : "fast",
    layoutVersion: 3,
  };
}

function dirty(node) {
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

function normalizeNodeSize(node) {
  const s = getState(node);
  if (s.layoutVersion !== 3 && node.size?.[0] > 780) {
    node.size[0] = MIN_W;
    node.size[1] = Math.max(MIN_H, Math.min(node.size?.[1] || MIN_H, 760));
    s.layoutVersion = 3;
    persist(node, false);
    return;
  }
  s.layoutVersion = 3;
  node.size[0] = Math.max(node.size[0], MIN_W);
  node.size[1] = Math.max(node.size[1], MIN_H);
}

function flash(node, text) {
  const s = getState(node);
  s.toast = text;
  clearTimeout(s.toastTimer);
  s.toastTimer = setTimeout(() => {
    s.toast = "";
    dirty(node);
  }, 1200);
  dirty(node);
  if (s.editor?.setStatus) s.editor.setStatus(text);
}

function buildUrl(meta) {
  return `/view?filename=${encodeURIComponent(meta.filename)}&type=${encodeURIComponent(meta.type || "temp")}&subfolder=${encodeURIComponent(meta.subfolder || "")}&t=${Date.now()}`;
}

function loadImage(node, meta, slot) {
  if (!meta?.filename) return;
  const s = getState(node);
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    if (slot === 1) s.img1 = img;
    else s.img2 = img;
    ensureMask(s);
    ensureAdjustmentBrush(s);
    invalidateRenderCache(s);
    dirty(node);
    s.editor?.render?.();
  };
  img.onerror = () => dirty(node);
  img.src = buildUrl(meta);
}

function restoreImages(node) {
  const s = getState(node);
  if (!s.img1 && s.images?.[0]) loadImage(node, s.images[0], 1);
  if (!s.img2 && s.images?.[1]) loadImage(node, s.images[1], 2);
}

function imageW(img) {
  return img?.naturalWidth || img?.width || 0;
}

function imageH(img) {
  return img?.naturalHeight || img?.height || 0;
}

function fitRect(img, box) {
  const iw = imageW(img);
  const ih = imageH(img);
  if (!iw || !ih) return { x: box.x, y: box.y, w: box.w, h: box.h, scale: 1 };
  const scale = Math.min(box.w / iw, box.h / ih);
  const rw = iw * scale;
  const rh = ih * scale;
  return {
    x: box.x + (box.w - rw) / 2,
    y: box.y + (box.h - rh) / 2,
    w: rw,
    h: rh,
    scale,
  };
}

function drawFit(ctx, img, box) {
  if (!img) return;
  const rect = fitRect(img, box);
  ctx.drawImage(img, rect.x, rect.y, rect.w, rect.h);
}

function layers(s) {
  if (s.layerOrder === "1over2") return { top: s.img1, under: s.img2, topName: "1", underName: "2" };
  return { top: s.img2, under: s.img1, topName: "2", underName: "1" };
}

function outputSize(s) {
  const { top, under } = layers(s);
  const base = under || top;
  return { w: Math.max(1, imageW(base) || 1), h: Math.max(1, imageH(base) || 1) };
}

function invalidateRenderCache(s) {
  const working = s.renderCache?.working || {};
  s.cacheRevision = (s.cacheRevision || 0) + 1;
  s.renderCache = { working };
}

function workingCanvas(s, key, width, height) {
  s.renderCache = s.renderCache || {};
  s.renderCache.working = s.renderCache.working || {};
  let canvas = s.renderCache.working[key];
  if (!canvas) {
    canvas = document.createElement("canvas");
    s.renderCache.working[key] = canvas;
  }
  const w = Math.max(1, Math.round(width));
  const h = Math.max(1, Math.round(height));
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  return canvas;
}

function ensureMask(s) {
  const size = outputSize(s);
  const key = `${size.w}x${size.h}`;
  if (s.maskCanvas && s.maskKey === key) return s.maskCanvas;

  const old = s.maskCanvas;
  const canvas = document.createElement("canvas");
  canvas.width = size.w;
  canvas.height = size.h;
  const ctx = canvas.getContext("2d");
  if (old) {
    ctx.drawImage(old, 0, 0, canvas.width, canvas.height);
  } else if (s.maskData) {
    const img = new Image();
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      s.editor?.render?.();
    };
    img.src = s.maskData;
  }
  s.maskCanvas = canvas;
  s.maskKey = key;
  return canvas;
}

function ensureAdjustmentBrush(s, layer = selectedAdjustmentLayer(s)) {
  const size = outputSize(s);
  const key = `${size.w}x${size.h}`;
  if (layer.maskCanvas && layer.maskKey === key) return layer.maskCanvas;

  const old = layer.maskCanvas;
  const canvas = document.createElement("canvas");
  canvas.width = size.w;
  canvas.height = size.h;
  const ctx = canvas.getContext("2d");
  if (old) {
    ctx.drawImage(old, 0, 0, canvas.width, canvas.height);
  } else if (layer.maskData) {
    const img = new Image();
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      s.editor?.render?.();
    };
    img.src = layer.maskData;
  }
  layer.maskCanvas = canvas;
  layer.maskKey = key;
  return canvas;
}

function ensurePaintCanvas(s, target = s.brushTarget) {
  return target === "adjustment" ? ensureAdjustmentBrush(s) : ensureMask(s);
}

function syncPaintData(s, target = s.brushTarget) {
  const canvas = ensurePaintCanvas(s, target);
  if (target === "adjustment") {
    const layer = selectedAdjustmentLayer(s);
    layer.maskData = canvas.toDataURL("image/png");
    syncLegacyAdjustmentState(s);
  } else s.maskData = canvas.toDataURL("image/png");
}

function applySingleAdjustmentLayer(out, s, layer) {
  if (!layer?.visible || isNeutral(layer.adjustments, layer.amount)) return out;
  const ctx = out.getContext("2d", { willReadFrequently: true });
  if (layer.mode !== "brush") {
    const id = ctx.getImageData(0, 0, out.width, out.height);
    applyFx(id.data, out.width, out.height, layer.adjustments, layer.amount, 4517);
    ctx.putImageData(id, 0, 0);
    return out;
  }

  const adjusted = workingCanvas(s, "adjustedLayer", out.width, out.height);
  const actx = adjusted.getContext("2d", { willReadFrequently: true });
  actx.drawImage(out, 0, 0);
  const id = actx.getImageData(0, 0, adjusted.width, adjusted.height);
  applyFx(id.data, adjusted.width, adjusted.height, layer.adjustments, layer.amount, 4517);
  actx.putImageData(id, 0, 0);

  const area = ensureAdjustmentBrush(s, layer);
  const local = workingCanvas(s, "localAdjustment", out.width, out.height);
  const lctx = local.getContext("2d");
  lctx.drawImage(adjusted, 0, 0);
  lctx.globalCompositeOperation = "destination-in";
  lctx.drawImage(area, 0, 0, out.width, out.height);
  lctx.globalCompositeOperation = "source-over";
  ctx.drawImage(local, 0, 0);
  return out;
}

function applyAdjustmentLayers(out, s) {
  if (!Array.isArray(s.adjustmentLayers)) return out;
  for (let i = s.adjustmentLayers.length - 1; i >= 0; i -= 1) {
    applySingleAdjustmentLayer(out, s, s.adjustmentLayers[i]);
  }
  return out;
}

function previewScaleFor(size, options = {}) {
  if (!options.preview) return 1;
  return Math.min(1, PREVIEW_MAX / Math.max(size.w, size.h, 1));
}

function composeBaseComposite(s, options = {}) {
  const { top, under } = layers(s);
  const size = outputSize(s);
  const scale = previewScaleFor(size, options);
  const out = workingCanvas(s, "baseComposite", Math.max(1, Math.round(size.w * scale)), Math.max(1, Math.round(size.h * scale)));
  const ctx = out.getContext("2d", { willReadFrequently: true });
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, out.width, out.height);
  if (under) ctx.drawImage(under, 0, 0, out.width, out.height);

  if (top) {
    const layer = workingCanvas(s, "topLayerComposite", out.width, out.height);
    const lctx = layer.getContext("2d");
    const r = fitRect(top, { x: 0, y: 0, w: out.width, h: out.height });
    lctx.globalAlpha = clamp(s.topOpacity, 0, 1);
    lctx.drawImage(top, r.x, r.y, r.w, r.h);
    lctx.globalAlpha = 1;
    if (options.includeBlendMask !== false) {
      const mask = ensureMask(s);
      lctx.globalCompositeOperation = "destination-out";
      lctx.drawImage(mask, 0, 0, out.width, out.height);
      lctx.globalCompositeOperation = "source-over";
    }
    ctx.drawImage(layer, 0, 0);
  }
  return out;
}

function composeImage3(s, applyAdjustments = true, options = {}) {
  const out = composeBaseComposite(s, { ...options, includeBlendMask: true });

  if (applyAdjustments) applyAdjustmentLayers(out, s);

  s.image3 = out;
  return out;
}

function sourceImage(s, key) {
  if (key === "1") return s.img1;
  if (key === "2") return s.img2;
  if (key === "3") return s.img1 || s.img2 ? composeImage3(s) : null;
  return null;
}

function sourceSize(s, key) {
  if (key === "1") return s.img1 ? { w: imageW(s.img1), h: imageH(s.img1) } : null;
  if (key === "2") return s.img2 ? { w: imageW(s.img2), h: imageH(s.img2) } : null;
  if (key === "3" && (s.img1 || s.img2)) return outputSize(s);
  return null;
}

function sourceLabel(key) {
  return `Image ${validImageKey(key)}`;
}

function selectedImages(s) {
  syncLegacyState(s);
  return [sourceImage(s, s.sourceA), sourceImage(s, s.sourceB), s.sourceA, s.sourceB];
}

function roundRect(ctx, x, y, width, height, radius = 5) {
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x, y, width, height, radius);
  else ctx.rect(x, y, width, height);
}

function button(ctx, rect, label, active = false, disabled = false) {
  ctx.save();
  roundRect(ctx, rect.x, rect.y, rect.w, rect.h, 5);
  ctx.fillStyle = disabled ? "#191c20" : active ? BRAND : "#202429";
  ctx.strokeStyle = disabled ? "#252a30" : active ? BRAND : "#3b424a";
  ctx.lineWidth = 1;
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = disabled ? "#69717a" : active ? "#fff" : "#dce2e8";
  ctx.font = "11px Segoe UI, Arial, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, rect.x + rect.w / 2, rect.y + rect.h / 2);
  ctx.restore();
}

function addRect(s, action, rect, value = null, tooltip = "") {
  s.rects.push({ action, rect, value, tooltip });
}

function rowButtons(ctx, node, y, items, activeTest, x = PAD, width = node.size[0] - PAD * 2) {
  const s = getState(node);
  const available = Math.max(1, width - GAP * (items.length - 1));
  const bw = Math.floor(available / items.length);
  let bx = x;
  for (const item of items) {
    const rect = { x: bx, y, w: bw, h: ROW_H };
    button(ctx, rect, item.label, activeTest?.(item), item.disabled);
    if (!item.disabled) addRect(s, item.action, rect, item.value, item.tooltip || "");
    bx += bw + GAP;
  }
}

function drawSelectButton(ctx, rect, label, active = false) {
  ctx.save();
  roundRect(ctx, rect.x, rect.y, rect.w, rect.h, 5);
  ctx.fillStyle = active ? "#26303a" : "#202429";
  ctx.strokeStyle = active ? BRAND : "#3b424a";
  ctx.lineWidth = 1;
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#dce2e8";
  ctx.font = "11px Segoe UI, Arial, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(label, rect.x + 9, rect.y + rect.h / 2);
  ctx.fillStyle = "#9aa3ad";
  ctx.textAlign = "right";
  ctx.fillText("v", rect.x + rect.w - 9, rect.y + rect.h / 2 - 1);
  ctx.restore();
}

function drawDropdown(ctx, node, y, field, label, x, w) {
  const s = getState(node);
  const rect = { x, y, w, h: ROW_H };
  s.dropdownAnchors[field] = rect;
  drawSelectButton(ctx, rect, `${label}: ${sourceLabel(s[field])}`, s.openDropdown === field);
  addRect(
    s,
    "dropdown",
    rect,
    field,
    field === "sourceA"
      ? "Choose the primary image shown in Single mode and first image in compare modes."
      : "Choose the second image used for Split, Overlay, and Difference comparisons.",
  );
}

function drawSourceRow(ctx, node, y) {
  const s = getState(node);
  const controlW = Math.max(1, node.size[0] - CONTROL_X - PAD);
  const editorW = 92;
  const swapW = 28;
  const selectW = Math.max(110, Math.floor((controlW - editorW - swapW - GAP * 3) / 2));
  let x = CONTROL_X;
  drawDropdown(ctx, node, y, "sourceA", "A", x, selectW);
  x += selectW + GAP;
  const swapRect = { x, y, w: swapW, h: ROW_H };
  button(ctx, swapRect, "<>", false, false);
  addRect(s, "swapSources", swapRect, null, "Swap Source A and Source B.");
  x += swapW + GAP;
  drawDropdown(ctx, node, y, "sourceB", "B", x, selectW);
  x += selectW + GAP;
  button(ctx, { x, y, w: Math.max(82, node.size[0] - PAD - x), h: ROW_H }, "Open Editor", true, false);
  addRect(s, "openEditor", { x, y, w: Math.max(82, node.size[0] - PAD - x), h: ROW_H }, null, "Open the larger edit workspace with mask brush, layer, and adjustment controls.");
}

function drawModeRow(ctx, node, y) {
  const s = getState(node);
  const controlW = Math.max(1, node.size[0] - CONTROL_X - PAD);
  const modeTips = {
    single: "Show Source A only.",
    split: "Compare Source A and Source B with a draggable wipe line.",
    overlay: "Overlay Source B over Source A using the opacity slider.",
    difference: "Show pixel difference between Source A and Source B.",
  };
  const splitTips = {
    leftRight: "Split view. Hover and drag the image to wipe left to right.",
    rightLeft: "Split view. Hover and drag the image to wipe right to left.",
    upDown: "Split view. Hover and drag the image to wipe top to bottom.",
  };
  const modeItems = VIEW_MODES.map(([value, label]) => ({ label, action: "viewMode", value, tooltip: modeTips[value] }));
  if (s.viewMode !== "split") {
    rowButtons(ctx, node, y, modeItems, (item) => s.viewMode === item.value, CONTROL_X, controlW);
    return;
  }

  const modeW = Math.floor(controlW * 0.55);
  rowButtons(ctx, node, y, modeItems, (item) => s.viewMode === item.value, CONTROL_X, modeW);
  rowButtons(
    ctx,
    node,
    y,
    SPLIT_MODES.map(([value, label]) => ({ label, action: "splitMode", value, tooltip: splitTips[value] })),
    (item) => s.splitMode === item.value,
    CONTROL_X + modeW + GAP,
    controlW - modeW - GAP,
  );
}

function drawOpenDropdown(ctx, node) {
  const s = getState(node);
  const field = s.openDropdown;
  if (!field) return;
  const anchor = s.dropdownAnchors[field];
  if (!anchor) return;

  const optionH = 22;
  const y = anchor.y + anchor.h + 3;
  const h = optionH * IMAGE_OPTIONS.length;
  ctx.save();
  roundRect(ctx, anchor.x, y, anchor.w, h, 5);
  ctx.fillStyle = "#15191e";
  ctx.strokeStyle = BRAND;
  ctx.fill();
  ctx.stroke();
  IMAGE_OPTIONS.forEach(([value, label], index) => {
    const rect = { x: anchor.x, y: y + optionH * index, w: anchor.w, h: optionH };
    const active = s[field] === value;
    if (active) {
      roundRect(ctx, rect.x + 2, rect.y + 2, rect.w - 4, rect.h - 4, 4);
      ctx.fillStyle = "rgba(255,104,71,.24)";
      ctx.fill();
    }
    ctx.fillStyle = active ? "#fff" : "#dce2e8";
    ctx.font = "11px Segoe UI, Arial, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(label, rect.x + 9, rect.y + rect.h / 2);
    addRect(s, "selectSource", rect, { field, value }, `Use ${label} as ${field === "sourceA" ? "Source A" : "Source B"}.`);
  });
  ctx.restore();
}

function toolbarHeight(s) {
  const rows = s.viewMode === "overlay" ? 4 : 3;
  return PAD + rows * ROW_H + (rows - 1) * GAP + GAP;
}

function imageBox(node) {
  const s = getState(node);
  const y = toolbarHeight(s);
  return { x: PAD, y, w: node.size[0] - PAD * 2, h: node.size[1] - y - PAD };
}

function drawStageBackground(ctx, box) {
  ctx.save();
  ctx.fillStyle = "#151719";
  ctx.fillRect(box.x, box.y, box.w, box.h);
  ctx.strokeStyle = "#24292f";
  ctx.strokeRect(box.x + 0.5, box.y + 0.5, box.w - 1, box.h - 1);
  ctx.restore();
}

function drawCompare(ctx, node, box) {
  const s = getState(node);
  const [a, b, al, bl] = selectedImages(s);
  drawStageBackground(ctx, box);
  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x, box.y, box.w, box.h);
  ctx.clip();

  if (!a && !b) {
    ctx.fillStyle = "#646b73";
    ctx.font = "14px Segoe UI, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Connect images & run to compare", box.x + box.w / 2, box.y + box.h / 2);
    ctx.restore();
    return;
  }

  if (s.viewMode === "single") drawFit(ctx, a, box);
  else if (s.viewMode === "overlay") {
    drawFit(ctx, a, box);
    ctx.globalAlpha = clamp(s.topOpacity, 0, 1);
    drawFit(ctx, b, box);
    ctx.globalAlpha = 1;
  } else if (s.viewMode === "difference") {
    drawFit(ctx, a, box);
    ctx.globalCompositeOperation = "difference";
    drawFit(ctx, b, box);
    ctx.globalCompositeOperation = "source-over";
  } else if (s.splitMode === "upDown") {
    drawFit(ctx, a, box);
    const sy = box.y + box.h * s.splitY;
    ctx.save();
    ctx.beginPath();
    ctx.rect(box.x, box.y, box.w, sy - box.y);
    ctx.clip();
    drawFit(ctx, b, box);
    ctx.restore();
    ctx.strokeStyle = "rgba(255,255,255,.78)";
    ctx.beginPath();
    ctx.moveTo(box.x, sy);
    ctx.lineTo(box.x + box.w, sy);
    ctx.stroke();
  } else {
    const left = s.splitMode === "rightLeft" ? b : a;
    const right = s.splitMode === "rightLeft" ? a : b;
    drawFit(ctx, right, box);
    const sx = box.x + box.w * s.splitX;
    ctx.save();
    ctx.beginPath();
    ctx.rect(box.x, box.y, sx - box.x, box.h);
    ctx.clip();
    drawFit(ctx, left, box);
    ctx.restore();
    ctx.strokeStyle = "rgba(255,255,255,.78)";
    ctx.beginPath();
    ctx.moveTo(sx, box.y);
    ctx.lineTo(sx, box.y + box.h);
    ctx.stroke();
  }

  drawStageMeta(ctx, s, box, al, bl);
  ctx.restore();
}

function dimensionsText(s) {
  return `1: ${s.img1 ? `${imageW(s.img1)}x${imageH(s.img1)}` : "-"}    2: ${s.img2 ? `${imageW(s.img2)}x${imageH(s.img2)}` : "-"}`;
}

function dimensionsDiffer(s) {
  return !!(s.img1 && s.img2 && (imageW(s.img1) !== imageW(s.img2) || imageH(s.img1) !== imageH(s.img2)));
}

function dimensionLabel(img) {
  return img ? `${imageW(img)}x${imageH(img)}` : "";
}

function selectedSaveWhich(s) {
  syncLegacyState(s);
  return s.viewMode === "single" ? s.sourceA : "3";
}

function drawToast(ctx, node) {
  const s = getState(node);
  if (!s.toast) return;
  ctx.save();
  ctx.font = "12px Segoe UI, Arial, sans-serif";
  const tw = Math.max(110, ctx.measureText(s.toast).width + 24);
  const x = node.size[0] - tw - PAD;
  const y = node.size[1] - 38;
  roundRect(ctx, x, y, tw, 26, 6);
  ctx.fillStyle = "rgba(12,16,18,.94)";
  ctx.strokeStyle = GREEN;
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#e8fff6";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(s.toast, x + tw / 2, y + 13);
  ctx.restore();
}

function wrapTooltipLines(ctx, text, maxWidth) {
  const words = String(text || "").split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (line && ctx.measureText(next).width > maxWidth) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines.length ? lines : [String(text || "")];
}

function drawTooltip(ctx, node) {
  const s = getState(node);
  const tip = s.hoverTip;
  if (!tip?.text) return;

  ctx.save();
  ctx.font = "12px Segoe UI, Arial, sans-serif";
  const maxTextW = Math.max(160, Math.min(440, node.size[0] - PAD * 4));
  const lines = wrapTooltipLines(ctx, tip.text, maxTextW);
  const textW = Math.max(...lines.map((line) => ctx.measureText(line).width));
  const w = Math.ceil(textW + 22);
  const h = lines.length * 18 + 12;
  let x = tip.rect.x + Math.min(24, tip.rect.w / 2);
  let y = tip.rect.y + tip.rect.h + 10;
  if (x + w > node.size[0] - PAD) x = Math.max(PAD, node.size[0] - PAD - w);
  if (y + h > node.size[1] - PAD) y = Math.max(PAD, tip.rect.y - h - 10);

  roundRect(ctx, x, y, w, h, 2);
  ctx.fillStyle = "#ffffff";
  ctx.strokeStyle = "#8f8f8f";
  ctx.lineWidth = 1;
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#111111";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  lines.forEach((line, index) => ctx.fillText(line, x + 11, y + 7 + index * 18));
  ctx.restore();
}

function drawDimChip(ctx, x, y, number, text, warn = false) {
  if (!text) return;
  ctx.save();
  ctx.font = "11px Segoe UI, Arial, sans-serif";
  const w = Math.max(88, ctx.measureText(text).width + 35);
  roundRect(ctx, x, y, w, 20, 6);
  ctx.fillStyle = "rgba(10,12,14,.50)";
  ctx.strokeStyle = warn ? "#8d5f30" : "#2d343b";
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x + 12, y + 10, 8, 0, Math.PI * 2);
  ctx.fillStyle = BRAND;
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.font = "10px Segoe UI, Arial, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(number, x + 12, y + 10);
  ctx.fillStyle = warn ? "#ffbd7a" : "#c7ced6";
  ctx.font = "11px Segoe UI, Arial, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(text, x + 26, y + 10);
  ctx.restore();
}

function dimChipWidth(ctx, text) {
  ctx.save();
  ctx.font = "11px Segoe UI, Arial, sans-serif";
  const width = Math.max(88, ctx.measureText(text).width + 35);
  ctx.restore();
  return width;
}

function sizeText(size) {
  return size ? `${size.w}x${size.h}` : "";
}

function activeSourcesDiffer(s) {
  if (s.viewMode === "single") return false;
  const a = sourceSize(s, s.sourceA);
  const b = sourceSize(s, s.sourceB);
  return !!(a && b && (a.w !== b.w || a.h !== b.h));
}

function drawStageMeta(ctx, s, box, al, bl) {
  const title = s.viewMode === "single" ? sourceLabel(al) : `${al} vs ${bl}`;
  ctx.save();
  ctx.font = "11px Segoe UI, Arial, sans-serif";
  const titleW = Math.max(66, ctx.measureText(title).width + 22);
  roundRect(ctx, box.x + 8, box.y + 8, titleW, 22, 5);
  ctx.fillStyle = "rgba(0,0,0,.58)";
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(title, box.x + 8 + titleW / 2, box.y + 19);

  const warn = activeSourcesDiffer(s);
  const chips = s.viewMode === "single"
    ? [[al, sizeText(sourceSize(s, al))]]
    : [
        [al, sizeText(sourceSize(s, al))],
        [bl, sizeText(sourceSize(s, bl))],
      ];
  let x = box.x + box.w - 8;
  for (let i = chips.length - 1; i >= 0; i -= 1) {
    const [key, text] = chips[i];
    if (!text) continue;
    const w = dimChipWidth(ctx, text);
    x -= w;
    drawDimChip(ctx, x, box.y + 8, key, text, warn);
    x -= GAP;
  }
  ctx.restore();
}

function drawOpacityControl(ctx, node, y) {
  const s = getState(node);
  const width = node.size[0];
  const controlW = Math.max(1, width - CONTROL_X - PAD);
  const labelW = 50;
  const valueW = 38;
  const trackX = CONTROL_X + labelW + GAP;
  const trackW = Math.max(80, controlW - labelW - valueW - GAP * 3);
  const centerY = y + ROW_H / 2;

  ctx.save();
  ctx.font = "11px Segoe UI, Arial, sans-serif";
  ctx.fillStyle = "#aab2bb";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText("Opacity", CONTROL_X, centerY);

  roundRect(ctx, trackX, centerY - 4, trackW, 8, 4);
  ctx.fillStyle = "#262d34";
  ctx.fill();
  roundRect(ctx, trackX, centerY - 4, trackW * clamp(s.topOpacity, 0, 1), 8, 4);
  ctx.fillStyle = BRAND;
  ctx.fill();
  ctx.beginPath();
  ctx.arc(trackX + trackW * clamp(s.topOpacity, 0, 1), centerY, 7, 0, Math.PI * 2);
  ctx.fillStyle = "#fff";
  ctx.fill();
  ctx.strokeStyle = BRAND;
  ctx.stroke();

  ctx.fillStyle = "#cbd3da";
  ctx.textAlign = "left";
  ctx.fillText(`${Math.round(s.topOpacity * 100)}%`, trackX + trackW + GAP + 2, centerY);
  ctx.restore();

  addRect(s, "opacitySlider", { x: trackX - 8, y: y - 2, w: trackW + 16, h: ROW_H + 4 }, null, "Adjust overlay opacity.");
}

function drawNode(ctx, node) {
  const s = getState(node);
  s.rects = [];
  s.dropdownAnchors = {};
  const width = node.size[0];
  const which = selectedSaveWhich(s);

  ctx.save();
  ctx.fillStyle = "#151719";
  ctx.fillRect(0, 0, width, node.size[1]);

  const controlW = Math.max(1, width - CONTROL_X - PAD);

  drawSourceRow(ctx, node, PAD);
  drawModeRow(ctx, node, PAD + ROW_H + GAP);

  rowButtons(
    ctx,
    node,
    PAD + (ROW_H + GAP) * 2,
    [
      { label: `Save D${which}`, action: "saveD", tooltip: `Download Image ${which} through the browser save dialog.` },
      { label: `Save O${which}`, action: "saveO", tooltip: `Save Image ${which} to the ComfyUI output folder with workflow metadata.` },
      { label: `Copy ${which}`, action: "copy", tooltip: `Copy Image ${which} to the clipboard.` },
    ],
    () => false,
    CONTROL_X,
    controlW,
  );

  if (s.viewMode === "overlay") {
    drawOpacityControl(ctx, node, PAD + (ROW_H + GAP) * 3);
  }

  drawCompare(ctx, node, imageBox(node));
  drawOpenDropdown(ctx, node);
  drawToast(ctx, node);
  drawTooltip(ctx, node);
  ctx.restore();
}

function drawNodeFallback(ctx, node, err) {
  const width = Math.max(MIN_W, node.size?.[0] || MIN_W);
  const height = Math.max(MIN_H, node.size?.[1] || MIN_H);
  ctx.save();
  ctx.fillStyle = "#151719";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "#5e2f25";
  ctx.strokeRect(PAD + 0.5, PAD + 0.5, width - PAD * 2 - 1, height - PAD * 2 - 1);
  ctx.fillStyle = "#ffcabd";
  ctx.font = "12px Segoe UI, Arial, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("Image Compare Edit X draw error - hard refresh after update", width / 2, height / 2 - 8);
  ctx.fillStyle = "#9aa3ad";
  ctx.fillText(String(err?.message || err || "unknown error").slice(0, 120), width / 2, height / 2 + 14);
  ctx.restore();
}

async function dataUrlFor(node, which) {
  const s = getState(node);
  if (which === "3") return s.img1 || s.img2 ? composeImage3(s).toDataURL("image/png") : "";
  const img = which === "1" ? s.img1 : s.img2;
  if (!img?.src) return "";
  const resp = await fetch(img.src);
  if (!resp.ok) return "";
  const blob = await resp.blob();
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function dataUrlToBlob(dataUrl) {
  const [header, payload] = dataUrl.split(",");
  const mime = /data:(.*?);/.exec(header)?.[1] || "image/png";
  const bytes = Uint8Array.from(atob(payload), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: mime });
}

async function graphMeta() {
  try {
    const { workflow, output } = await app.graphToPrompt();
    return { workflow, prompt: output };
  } catch (_err) {
    return { workflow: app.graph?.serialize?.() || null, prompt: null };
  }
}

async function copyImage(node, which) {
  try {
    const url = await dataUrlFor(node, which);
    if (!url) return flash(node, "Run first");
    if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") return flash(node, "Clipboard unavailable");
    await navigator.clipboard.write([new ClipboardItem({ "image/png": dataUrlToBlob(url) })]);
    flash(node, `Copied ${which}`);
  } catch (err) {
    console.warn("[WorkflowX] Image Compare Edit X copy failed:", err);
    flash(node, "Copy failed");
  }
}

async function saveImage(node, which, toDisk) {
  try {
    const image_b64 = await dataUrlFor(node, which);
    if (!image_b64) return flash(node, "Run first");
    const { workflow, prompt } = await graphMeta();
    const resp = await fetch(toDisk ? PREPARE_ROUTE : SAVE_ROUTE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_b64, filename_prefix: `ImageCompareEditX_${which}`, workflow, prompt }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) return flash(node, "Save failed");
    if (toDisk) {
      const blob = dataUrlToBlob(data.image_b64);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = data.suggested_filename || `ImageCompareEditX_${which}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1200);
    }
    flash(node, toDisk ? `Saved D${which}` : `Saved O${which}`);
  } catch (err) {
    console.warn("[WorkflowX] Image Compare Edit X save failed:", err);
    flash(node, "Save failed");
  }
}

function editorSnapshot(s) {
  return {
    layerOrder: s.layerOrder,
    topOpacity: s.topOpacity,
    maskData: s.maskCanvas ? s.maskCanvas.toDataURL("image/png") : s.maskData || "",
    adjustmentLayers: s.adjustmentLayers.map((layer) => serializeAdjustmentLayer(layer)),
    selectedAdjustmentLayerId: selectedAdjustmentLayer(s).id,
  };
}

function pushUndo(s) {
  s.undo.push(editorSnapshot(s));
  if (s.undo.length > 30) s.undo.shift();
  s.redo = [];
}

function restoreEditorSnapshot(node, snapshot, after) {
  const s = getState(node);
  s.layerOrder = snapshot?.layerOrder || s.layerOrder;
  s.topOpacity = clamp01(safeNumber(snapshot?.topOpacity, s.topOpacity));
  s.maskData = snapshot?.maskData || "";
  s.maskCanvas = null;
  s.maskKey = "";
  s.adjustmentLayers = normalizeAdjustmentLayers({ adjustmentLayers: snapshot?.adjustmentLayers || [] }, s);
  s.selectedAdjustmentLayerId =
    s.adjustmentLayers.find((layer) => layer.id === snapshot?.selectedAdjustmentLayerId)?.id ||
    s.adjustmentLayers[0]?.id ||
    "";
  syncLegacyAdjustmentState(s);
  persist(node, true);
  dirty(node);
  after?.();
}

function drawBrush(s, point) {
  const target = s.brushTarget === "adjustment" ? "adjustment" : "blend";
  const canvas = ensurePaintCanvas(s, target);
  if (point.x < -s.brush.size || point.y < -s.brush.size || point.x > canvas.width + s.brush.size || point.y > canvas.height + s.brush.size) return;
  const ctx = canvas.getContext("2d");
  const radius = Math.max(1, s.brush.size / 2);
  const alpha = clamp(s.brush.opacity * s.brush.flow, 0, 1);
  const hardness = clamp(s.brush.hardness, 0, 1);
  ctx.save();
  if (s.tool === "eraser") ctx.globalCompositeOperation = "destination-out";
  if (hardness >= 0.995) {
    ctx.fillStyle = `rgba(255,255,255,${alpha})`;
  } else {
    const hard = hardness * radius;
    const grad = ctx.createRadialGradient(point.x, point.y, hard, point.x, point.y, radius);
    grad.addColorStop(0, `rgba(255,255,255,${alpha})`);
    grad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = grad;
  }
  ctx.beginPath();
  ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  invalidateRenderCache(s);
}

function strokeBrush(s, from, to) {
  const dist = Math.hypot(to.x - from.x, to.y - from.y);
  const steps = Math.max(1, Math.ceil(dist / Math.max(1, s.brush.size * 0.18)));
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    drawBrush(s, { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t });
  }
}

function inside(pos, rect) {
  return pos[0] >= rect.x && pos[0] <= rect.x + rect.w && pos[1] >= rect.y && pos[1] <= rect.y + rect.h;
}

function hit(node, pos) {
  const rects = getState(node).rects;
  for (let i = rects.length - 1; i >= 0; i -= 1) {
    if (inside(pos, rects[i].rect)) return rects[i];
  }
  return null;
}

function setHoverTip(node, hitRect) {
  const s = getState(node);
  const next = hitRect?.tooltip ? { text: hitRect.tooltip, rect: hitRect.rect } : null;
  const same =
    (!next && !s.hoverTip) ||
    (next &&
      s.hoverTip &&
      next.text === s.hoverTip.text &&
      next.rect.x === s.hoverTip.rect.x &&
      next.rect.y === s.hoverTip.rect.y &&
      next.rect.w === s.hoverTip.rect.w &&
      next.rect.h === s.hoverTip.rect.h);
  if (same) return;
  s.hoverTip = next;
  dirty(node);
}

function handleNodeAction(node, action, value, pos = null) {
  const s = getState(node);
  if (action === "viewMode") {
    s.viewMode = value;
    s.openDropdown = "";
  } else if (action === "splitMode") {
    s.splitMode = value;
    s.openDropdown = "";
  } else if (action === "dropdown") {
    s.openDropdown = s.openDropdown === value ? "" : value;
  } else if (action === "selectSource") {
    s[value.field] = value.value;
    s.openDropdown = "";
  } else if (action === "swapSources") {
    const nextA = s.sourceB;
    s.sourceB = s.sourceA;
    s.sourceA = nextA;
    s.openDropdown = "";
  } else if (action === "mode") {
    s.mode = value;
    migrateCompactState(s, { mode: value, pair: s.pair });
  } else if (action === "pair") {
    s.pair = value;
    migrateCompactState(s, { mode: s.mode, pair: value });
  } else if (action === "openEditor") openEditor(node);
  else if (action === "copy") copyImage(node, selectedSaveWhich(s));
  else if (action === "saveD") saveImage(node, selectedSaveWhich(s), true);
  else if (action === "saveO") saveImage(node, selectedSaveWhich(s), false);
  else if (action === "opacitySlider") {
    s.opacityDragging = true;
    if (pos) updateOpacityFromNode(node, pos);
  }
  persist(node, false);
  dirty(node);
}

function updateOpacityFromNode(node, pos) {
  const s = getState(node);
  const rect = s.rects.find((entry) => entry.action === "opacitySlider")?.rect;
  if (!rect) return;
  s.topOpacity = clamp((pos[0] - rect.x) / Math.max(1, rect.w), 0, 1);
  persist(node, false);
  dirty(node);
  s.editor?.render?.();
}

function updateSplitFromNode(node, pos) {
  const s = getState(node);
  const box = imageBox(node);
  if (s.splitMode === "leftRight" || s.splitMode === "rightLeft") s.splitX = clamp((pos[0] - box.x) / box.w, 0, 1);
  if (s.splitMode === "upDown") s.splitY = clamp((pos[1] - box.y) / box.h, 0, 1);
  persist(node, false);
  dirty(node);
}

function injectEditorStyles() {
  if (document.getElementById("wfx-ice-styles")) return;
  const style = document.createElement("style");
  style.id = "wfx-ice-styles";
  style.textContent = `
    .wfx-ice-overlay{position:fixed;inset:0;z-index:99999;background:#101214;color:${TEXT};font:12px "Segoe UI",Arial,sans-serif;display:grid;grid-template-rows:42px 1fr;letter-spacing:0}
    .wfx-ice-topbar{height:42px;display:flex;align-items:center;gap:8px;padding:0 10px;border-bottom:1px solid #24282d;background:#121416;box-sizing:border-box}
    .wfx-ice-brand{display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;color:#fff;white-space:nowrap}
    .wfx-ice-dot{width:9px;height:9px;border-radius:999px;background:${BRAND};box-shadow:0 0 0 3px rgba(255,104,71,.16)}
    .wfx-ice-status{color:${MUTED};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:100px}
    .wfx-ice-spacer{flex:1}
    .wfx-ice-shell{display:grid;grid-template-columns:288px minmax(320px,1fr) 304px;min-height:0}
    .wfx-ice-side{background:${PANEL};border-right:1px solid #262b30;overflow:auto;padding:8px;box-sizing:border-box}
    .wfx-ice-right{border-right:0;border-left:1px solid #262b30}
    .wfx-ice-stage{position:relative;min-width:0;min-height:0;background:#111315;overflow:hidden}
    .wfx-ice-canvas{width:100%;height:100%;display:block;cursor:none}
    .wfx-ice-panel{border:1px solid #30363d;background:#17191c;margin-bottom:8px}
    .wfx-ice-panel h3{display:flex;align-items:center;justify-content:space-between;margin:0;padding:7px 8px;border-bottom:1px solid #2b3036;color:${BRAND};font-size:11px;line-height:1;text-transform:uppercase;font-weight:700}
    .wfx-ice-panel-body{padding:8px}
    .wfx-ice-row{display:flex;align-items:center;gap:6px;margin-bottom:7px}
    .wfx-ice-row:last-child{margin-bottom:0}
    .wfx-ice-label{width:82px;color:#c5ccd3;white-space:nowrap}
    .wfx-ice-value{width:36px;text-align:right;color:#cbd2d9;font-variant-numeric:tabular-nums}
    .wfx-ice-btn,.wfx-ice-chip{height:24px;border:1px solid #3a4148;background:#202429;color:#dce2e8;border-radius:4px;padding:0 9px;font:600 11px "Segoe UI",Arial,sans-serif;cursor:pointer;box-sizing:border-box}
    .wfx-ice-btn:hover,.wfx-ice-chip:hover{background:#293039;border-color:#4a545f}
    .wfx-ice-btn.active,.wfx-ice-chip.active{background:${BRAND};border-color:${BRAND};color:#fff}
    .wfx-ice-btn.primary{background:${BRAND};border-color:${BRAND};color:#fff}
    .wfx-ice-btn.danger{background:#4d241d;border-color:#753426;color:#ffcabd}
    .wfx-ice-btn:disabled{opacity:.45;cursor:not-allowed}
    .wfx-ice-seg{display:grid;grid-template-columns:1fr 1fr;gap:5px;width:100%}
    .wfx-ice-seg.three{grid-template-columns:1fr 1fr 1fr}
    .wfx-ice-seg.four{grid-template-columns:1fr 1fr 1fr 1fr}
    .wfx-ice-presets{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;margin-bottom:8px}
    .wfx-ice-presets .wfx-ice-chip{height:22px;padding:0 4px;font-size:10px}
    .wfx-ice-slider{flex:1;min-width:0;accent-color:${BRAND}}
    .wfx-ice-number{width:38px;height:20px;background:#111315;border:1px solid #333a41;color:#e8edf2;border-radius:3px;font:11px "Segoe UI",Arial,sans-serif;text-align:right;padding:0 4px;box-sizing:border-box}
    .wfx-ice-select{flex:1;height:24px;background:#111315;border:1px solid #333a41;color:#e8edf2;border-radius:4px;font:11px "Segoe UI",Arial,sans-serif;padding:0 7px;box-sizing:border-box}
    .wfx-ice-actions{display:grid;grid-template-columns:1fr 1fr;gap:6px}
    .wfx-ice-actions.three{grid-template-columns:1fr 1fr 1fr}
    .wfx-ice-layer-list{display:grid;gap:5px;margin-bottom:8px}
    .wfx-ice-layer{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:6px;min-height:28px;padding:5px 7px;border:1px solid #30363d;background:#111315;border-radius:4px;box-sizing:border-box}
    .wfx-ice-layer.selected{border-color:${BRAND};box-shadow:0 0 0 1px rgba(255,104,71,.28) inset}
    .wfx-ice-layer strong{font-size:11px;color:#edf1f5}
    .wfx-ice-layer span{font-size:10px;color:${MUTED};white-space:nowrap}
    .wfx-ice-layer.adjustments{border-color:#5f4420;background:#1e1a13}
    .wfx-ice-layer.top{border-color:#694032;background:#211815}
    .wfx-ice-layer-pick{display:grid;gap:1px;min-width:0;text-align:left;cursor:pointer}
    .wfx-ice-layer-actions{display:flex;align-items:center;gap:3px}
    .wfx-ice-icon-btn{width:22px;height:20px;border:1px solid #343b42;background:#202429;color:#dce2e8;border-radius:3px;padding:0;font:700 10px "Segoe UI",Arial,sans-serif;cursor:pointer}
    .wfx-ice-icon-btn:hover{background:#293039;border-color:#4a545f}
    .wfx-ice-icon-btn.active{background:${BRAND};border-color:${BRAND};color:#fff}
    .wfx-ice-meta{font-size:11px;color:${MUTED};line-height:1.55}
    .wfx-ice-warn{color:#ffb36b}
    @media(max-width:1050px){.wfx-ice-shell{grid-template-columns:240px minmax(240px,1fr) 260px}.wfx-ice-label{width:68px}.wfx-ice-presets{grid-template-columns:repeat(3,1fr)}}
  `;
  document.head.appendChild(style);
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function makeButton(label, onClick, options = {}) {
  const btn = el("button", `wfx-ice-btn${options.primary ? " primary" : ""}${options.danger ? " danger" : ""}`, label);
  btn.type = "button";
  btn.onclick = onClick;
  if (options.title) btn.title = options.title;
  return btn;
}

function makePanel(title) {
  const panel = el("section", "wfx-ice-panel");
  const heading = el("h3", "", title);
  const body = el("div", "wfx-ice-panel-body");
  panel.append(heading, body);
  return { panel, body, heading };
}

function labelForKey(key) {
  return key.charAt(0).toUpperCase() + key.slice(1);
}

function imagePointFromEditor(s, transform, x, y) {
  return { x: (x - transform.x) / transform.scale, y: (y - transform.y) / transform.scale };
}

function editorTransform(s, canvas, imgOrSize) {
  const iw = imageW(imgOrSize) || imgOrSize?.w || imgOrSize?.width || 0;
  const ih = imageH(imgOrSize) || imgOrSize?.h || imgOrSize?.height || 0;
  const pad = 52;
  if (!iw || !ih) return { x: 0, y: 0, scale: 1 };
  const base = Math.min((canvas.clientWidth - pad * 2) / iw, (canvas.clientHeight - pad * 2) / ih);
  const scale = Math.max(0.02, base * clamp(s.editorZoom, 0.1, 12));
  return {
    x: canvas.clientWidth / 2 - (iw * scale) / 2 + s.editorPanX,
    y: canvas.clientHeight / 2 - (ih * scale) / 2 + s.editorPanY,
    scale,
  };
}

function openEditor(node) {
  const s = getState(node);
  if (s.editor?.root?.isConnected) return;
  injectEditorStyles();

  const root = el("div", "wfx-ice-overlay");
  const topbar = el("div", "wfx-ice-topbar");
  const brand = el("div", "wfx-ice-brand");
  brand.append(el("span", "wfx-ice-dot"), document.createTextNode("Image Compare Edit X"));
  const status = el("div", "wfx-ice-status", "Ready");
  const zoomLabel = el("div", "wfx-ice-status", "100%");
  const body = el("div", "wfx-ice-shell");
  const left = el("aside", "wfx-ice-side");
  const stage = el("main", "wfx-ice-stage");
  const right = el("aside", "wfx-ice-side wfx-ice-right");
  const canvas = el("canvas", "wfx-ice-canvas");

  let raf = 0;
  let transform = { x: 0, y: 0, scale: 1 };

  const setStatus = (text) => {
    status.textContent = text;
  };

  const scheduleRender = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(render);
  };

  const markPreviewDraft = () => {
    if (s.performanceMode !== "fast") return;
    s.previewDraft = true;
    clearTimeout(s.previewTimer);
    s.previewTimer = setTimeout(() => {
      s.previewDraft = false;
      scheduleRender();
    }, 180);
  };

  const invalidateAndRender = (draft = true) => {
    invalidateRenderCache(s);
    if (draft) markPreviewDraft();
    dirty(node);
    scheduleRender();
  };

  const setAndRefresh = (fn, includeMask = false, options = {}) => {
    if (options.history) pushUndo(s);
    fn();
    persist(node, includeMask);
    syncControls();
    invalidateAndRender(options.draft !== false);
  };

  const beforeButton = makeButton("Before", () => setAndRefresh(() => {
    s.beforePreview = !s.beforePreview;
  }, false, { draft: false }));
  beforeButton.dataset.beforeToggle = "1";
  const performanceButton = makeButton("Fast", () => setAndRefresh(() => {
    s.performanceMode = s.performanceMode === "quality" ? "fast" : "quality";
    s.previewDraft = false;
  }, false, { draft: false }));
  performanceButton.dataset.performanceToggle = "1";

  const topButtons = [
    beforeButton,
    performanceButton,
    makeButton("Fit", () => setAndRefresh(() => {
      s.editorZoom = 1;
      s.editorPanX = 0;
      s.editorPanY = 0;
    })),
    makeButton("100%", () => setAndRefresh(() => {
      s.editorZoom = 1;
    })),
    makeButton("+", () => setAndRefresh(() => {
      s.editorZoom = clamp(s.editorZoom * 1.2, 0.1, 12);
    })),
    makeButton("-", () => setAndRefresh(() => {
      s.editorZoom = clamp(s.editorZoom / 1.2, 0.1, 12);
    })),
    makeButton("Undo", () => undoMask()),
    makeButton("Redo", () => redoMask()),
    makeButton("Close", () => closeEditor(), { danger: true }),
  ];

  topbar.append(brand, status, el("div", "wfx-ice-spacer"), zoomLabel, ...topButtons);
  stage.append(canvas);
  body.append(left, stage, right);
  root.append(topbar, body);
  document.body.appendChild(root);

  const cleanup = () => {
    cancelAnimationFrame(raf);
    clearTimeout(s.previewTimer);
    window.removeEventListener("resize", scheduleRender);
    window.removeEventListener("keydown", onKeyDown);
    root.remove();
    s.editor = null;
    dirty(node);
  };

  const closeEditor = () => cleanup();

  s.editor = { root, render: scheduleRender, setStatus };

  function onKeyDown(event) {
    if (event.key === "Escape") closeEditor();
  }
  window.addEventListener("keydown", onKeyDown);

  function segmented(parent, options, getValue, setValue, cols = "", config = {}) {
    const wrap = el("div", `wfx-ice-seg ${cols}`.trim());
    for (const [value, label] of options) {
      const btn = makeButton(label, () => setAndRefresh(() => setValue(value), config.persistMask, { history: !!config.history }));
      btn.dataset.value = value;
      btn.dataset.groupValue = "1";
      btn.__getValue = getValue;
      wrap.appendChild(btn);
    }
    parent.appendChild(wrap);
  }

  function selectRow(parent, label, options, getValue, setValue) {
    const row = el("div", "wfx-ice-row");
    const lab = el("div", "wfx-ice-label", label);
    const select = el("select", "wfx-ice-select");
    for (const [value, text] of options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    }
    select.__sync = () => {
      select.value = getValue();
    };
    select.addEventListener("change", () => setAndRefresh(() => setValue(select.value)));
    row.append(lab, select);
    parent.appendChild(row);
    return select;
  }

  function sliderRow(parent, label, min, max, valueGetter, valueSetter, options = {}) {
    const row = el("div", "wfx-ice-row");
    const lab = el("div", "wfx-ice-label", label);
    const input = el("input", "wfx-ice-slider");
    input.type = "range";
    input.min = String(min);
    input.max = String(max);
    input.step = String(options.step ?? 1);
    const number = el("input", "wfx-ice-number");
    number.type = "number";
    number.min = String(min);
    number.max = String(max);
    number.step = String(options.step ?? 1);
    input.__sync = () => {
      const v = valueGetter();
      input.value = String(v);
      number.value = String(Math.round(v));
    };
    let historyOpen = false;
    const beginHistory = () => {
      if (!options.history || historyOpen) return;
      pushUndo(s);
      historyOpen = true;
    };
    const endHistory = () => {
      historyOpen = false;
      s.previewDraft = false;
      scheduleRender();
    };
    const commit = (raw) => {
      const v = clamp(safeNumber(raw, valueGetter()), min, max);
      setAndRefresh(() => valueSetter(v), options.persistMask);
    };
    input.addEventListener("pointerdown", beginHistory);
    input.addEventListener("input", () => {
      beginHistory();
      commit(input.value);
    });
    input.addEventListener("change", endHistory);
    input.addEventListener("pointerup", endHistory);
    number.addEventListener("change", () => {
      if (options.history) pushUndo(s);
      commit(number.value);
    });
    number.addEventListener("dblclick", () => {
      if (options.history) pushUndo(s);
      commit(options.defaultValue ?? 0);
    });
    row.append(lab, input, number);
    parent.appendChild(row);
    return input;
  }

  const compare = makePanel("Compare");
  selectRow(compare.body, "Source A", IMAGE_OPTIONS, () => s.sourceA, (v) => {
    s.sourceA = v;
  });
  selectRow(compare.body, "Source B", IMAGE_OPTIONS, () => s.sourceB, (v) => {
    s.sourceB = v;
  });
  const swapRow = el("div", "wfx-ice-row");
  swapRow.append(
    el("div", "wfx-ice-label", ""),
    makeButton("Swap A/B", () => setAndRefresh(() => {
      const nextA = s.sourceB;
      s.sourceB = s.sourceA;
      s.sourceA = nextA;
    })),
  );
  compare.body.appendChild(swapRow);
  segmented(
    compare.body,
    VIEW_MODES,
    () => s.viewMode,
    (v) => {
      s.viewMode = v;
    },
    "four",
  );
  compare.body.appendChild(el("div", "wfx-ice-row"));
  segmented(
    compare.body,
    SPLIT_MODES,
    () => s.splitMode,
    (v) => {
      s.splitMode = v;
      s.viewMode = "split";
    },
    "three",
  );
  left.appendChild(compare.panel);

  const activeAdjustment = () => selectedAdjustmentLayer(s);
  const adjust = makePanel("Adjustment Controls");
  const presetWrap = el("div", "wfx-ice-presets");
  for (const name of Object.keys(PRESETS)) {
    const chip = el("button", "wfx-ice-chip", name);
    chip.type = "button";
    chip.dataset.preset = name;
    chip.onclick = () => setAndRefresh(() => {
      const layer = activeAdjustment();
      layer.adjustments = { ...NEUTRAL, ...PRESETS[name] };
      layer.preset = name;
      syncLegacyAdjustmentState(s);
    }, true, { history: true });
    presetWrap.appendChild(chip);
  }
  adjust.body.appendChild(presetWrap);
  const adjustActions = el("div", "wfx-ice-actions");
  adjustActions.append(
    makeButton("Reset Layer", () => setAndRefresh(() => {
      const layer = activeAdjustment();
      layer.adjustments = { ...NEUTRAL };
      layer.amount = 1;
      layer.preset = "Original";
      layer.maskData = "";
      layer.maskCanvas = null;
      layer.maskKey = "";
      syncLegacyAdjustmentState(s);
    }, true, { history: true })),
    makeButton("Clear All", () => clearAdjustmentLayers()),
  );
  adjust.body.appendChild(adjustActions);
  sliderRow(adjust.body, "Amount", 0, 100, () => Math.round(activeAdjustment().amount * 100), (v) => {
    activeAdjustment().amount = v / 100;
    syncLegacyAdjustmentState(s);
  }, { defaultValue: 100, history: true });
  for (const [group, keys] of FX_GROUPS) {
    const groupRow = el("div", "wfx-ice-row");
    groupRow.style.marginTop = "9px";
    groupRow.append(el("div", "wfx-ice-label", group), makeButton("reset", () => setAndRefresh(() => {
      const layer = activeAdjustment();
      for (const key of keys) layer.adjustments[key] = 0;
      layer.preset = "Custom";
      syncLegacyAdjustmentState(s);
    }, true, { history: true })));
    adjust.body.appendChild(groupRow);
    for (const key of keys) {
      const [min, max] = FX_RANGES[key] || [-100, 100];
      sliderRow(adjust.body, labelForKey(key), min, max, () => activeAdjustment().adjustments[key] ?? 0, (v) => {
        const layer = activeAdjustment();
        layer.adjustments[key] = Math.round(v);
        layer.preset = "Custom";
        syncLegacyAdjustmentState(s);
      }, { history: true });
    }
  }
  left.appendChild(adjust.panel);

  const info = makePanel("Images");
  const meta = el("div", "wfx-ice-meta");
  info.body.appendChild(meta);
  left.appendChild(info.panel);

  const layerPanel = makePanel("Layers");
  const layerList = el("div", "wfx-ice-layer-list");
  const topLayer = el("div", "wfx-ice-layer top");
  topLayer.append(el("span", "", ""), el("div", "wfx-ice-layer-pick"));
  const topLayerName = el("strong", "", "Top Image");
  const topLayerMeta = el("span", "", "Image 2");
  topLayer.children[1].append(topLayerName, topLayerMeta);
  const underLayer = el("div", "wfx-ice-layer");
  underLayer.append(el("span", "", ""), el("div", "wfx-ice-layer-pick"));
  const underLayerName = el("strong", "", "Under Image");
  const underLayerMeta = el("span", "", "Image 1");
  underLayer.children[1].append(underLayerName, underLayerMeta);
  layerList.append(topLayer, underLayer);
  layerPanel.body.appendChild(layerList);
  const layerActions = el("div", "wfx-ice-actions");
  layerActions.append(
    makeButton("Add Global", () => addAdjustmentLayer("global")),
    makeButton("Add Brush", () => addAdjustmentLayer("brush")),
    makeButton("Duplicate", () => duplicateSelectedLayer()),
    makeButton("Delete", () => deleteSelectedLayer()),
  );
  layerPanel.body.appendChild(layerActions);
  segmented(layerPanel.body, [["2over1", "Image 2 over 1"], ["1over2", "Image 1 over 2"]], () => s.layerOrder, (v) => {
    s.layerOrder = v;
    s.maskCanvas = null;
    for (const layer of s.adjustmentLayers) {
      layer.maskCanvas = null;
      layer.maskKey = "";
    }
  }, "", { history: true, persistMask: true });
  sliderRow(layerPanel.body, "Opacity", 0, 100, () => Math.round(s.topOpacity * 100), (v) => {
    s.topOpacity = v / 100;
  }, { defaultValue: 65, history: true });
  segmented(layerPanel.body, [["global", "Global"], ["brush", "Brush"]], () => activeAdjustment().mode, (v) => {
    activeAdjustment().mode = v;
    if (v === "brush") s.brushTarget = "adjustment";
    syncLegacyAdjustmentState(s);
  }, "", { history: true, persistMask: true });
  right.appendChild(layerPanel.panel);

  const maskPanel = makePanel("Brush");
  segmented(maskPanel.body, [["blend", "Blend Brush"], ["adjustment", "Adjustment Brush"]], () => s.brushTarget, (v) => {
    s.brushTarget = v;
    if (v === "adjustment") {
      activeAdjustment().mode = "brush";
      syncLegacyAdjustmentState(s);
    }
  });
  segmented(maskPanel.body, [["brush", "Brush"], ["eraser", "Eraser"], ["pan", "Pan"]], () => s.tool, (v) => {
    s.tool = v;
  }, "three");
  sliderRow(maskPanel.body, "Size", 1, 300, () => Math.round(s.brush.size), (v) => {
    s.brush.size = v;
  }, { defaultValue: 64 });
  sliderRow(maskPanel.body, "Hardness", 0, 100, () => Math.round(s.brush.hardness * 100), (v) => {
    s.brush.hardness = v / 100;
  }, { defaultValue: 65 });
  sliderRow(maskPanel.body, "Opacity", 0, 100, () => Math.round(s.brush.opacity * 100), (v) => {
    s.brush.opacity = v / 100;
  }, { defaultValue: 85 });
  sliderRow(maskPanel.body, "Flow", 1, 100, () => Math.max(1, Math.round(s.brush.flow * 100)), (v) => {
    s.brush.flow = clamp(v / 100, 0.01, 1);
  }, { defaultValue: 65 });
  const maskActions = el("div", "wfx-ice-actions");
  const showMaskButton = makeButton("Show Mask", () => setAndRefresh(() => {
    s.showMask = !s.showMask;
  }));
  showMaskButton.dataset.maskToggle = "1";
  maskActions.append(
    showMaskButton,
    makeButton("Reset Area", () => resetPaintArea()),
    makeButton("Invert Area", () => invertPaintArea()),
  );
  maskPanel.body.appendChild(maskActions);
  right.appendChild(maskPanel.panel);

  const savePanel = makePanel("Save / Copy");
  const saveActions = el("div", "wfx-ice-actions three");
  saveActions.append(
    makeButton("Save O3", () => saveImage(node, "3", false), { primary: true }),
    makeButton("Save D3", () => saveImage(node, "3", true)),
    makeButton("Copy 3", () => copyImage(node, "3")),
  );
  savePanel.body.appendChild(saveActions);
  right.appendChild(savePanel.panel);

  function addAdjustmentLayer(mode) {
    setAndRefresh(() => {
      const layer = createAdjustmentLayer(mode, {
        name: `${mode === "brush" ? "Brush" : "Global"} Adjustment ${s.adjustmentLayers.length + 1}`,
      });
      s.adjustmentLayers.unshift(layer);
      s.selectedAdjustmentLayerId = layer.id;
      if (mode === "brush") s.brushTarget = "adjustment";
      syncLegacyAdjustmentState(s);
    }, true, { history: true });
  }

  function duplicateSelectedLayer() {
    setAndRefresh(() => {
      const current = selectedAdjustmentLayer(s);
      const index = Math.max(0, s.adjustmentLayers.findIndex((layer) => layer.id === current.id));
      const copy = createAdjustmentLayer(current.mode, {
        ...serializeAdjustmentLayer(current),
        id: makeLayerId(),
        name: `${current.name || "Adjustment"} Copy`,
      });
      s.adjustmentLayers.splice(index, 0, copy);
      s.selectedAdjustmentLayerId = copy.id;
      syncLegacyAdjustmentState(s);
    }, true, { history: true });
  }

  function deleteSelectedLayer() {
    setAndRefresh(() => {
      const current = selectedAdjustmentLayer(s);
      const index = s.adjustmentLayers.findIndex((layer) => layer.id === current.id);
      if (s.adjustmentLayers.length <= 1) {
        s.adjustmentLayers = [createAdjustmentLayer("global", { name: "Global Adjustment 1" })];
        s.selectedAdjustmentLayerId = s.adjustmentLayers[0].id;
      } else {
        const removeIndex = index >= 0 ? index : 0;
        s.adjustmentLayers.splice(removeIndex, 1);
        s.selectedAdjustmentLayerId = s.adjustmentLayers[Math.min(removeIndex, s.adjustmentLayers.length - 1)].id;
      }
      syncLegacyAdjustmentState(s);
    }, true, { history: true });
  }

  function clearAdjustmentLayers() {
    setAndRefresh(() => {
      s.adjustmentLayers = [createAdjustmentLayer("global", { name: "Global Adjustment 1" })];
      s.selectedAdjustmentLayerId = s.adjustmentLayers[0].id;
      s.brushTarget = "blend";
      syncLegacyAdjustmentState(s);
    }, true, { history: true });
  }

  function renderLayerStack() {
    layerList.replaceChildren();
    for (const layer of s.adjustmentLayers) {
      const row = el("div", `wfx-ice-layer adjustments${layer.id === s.selectedAdjustmentLayerId ? " selected" : ""}`);
      const visible = el("button", `wfx-ice-icon-btn${layer.visible !== false ? " active" : ""}`, layer.visible !== false ? "V" : "-");
      visible.type = "button";
      visible.title = layer.visible !== false ? "Hide adjustment layer" : "Show adjustment layer";
      visible.onclick = (event) => {
        event.stopPropagation();
        setAndRefresh(() => {
          layer.visible = layer.visible === false;
          syncLegacyAdjustmentState(s);
        }, true, { history: true });
      };
      const pick = el("div", "wfx-ice-layer-pick");
      pick.append(
        el("strong", "", layer.name || "Adjustment"),
        el("span", "", `${layer.mode === "brush" ? "Brush" : "Global"}  ${Math.round(layer.amount * 100)}%`),
      );
      pick.onclick = () => setAndRefresh(() => {
        s.selectedAdjustmentLayerId = layer.id;
        syncLegacyAdjustmentState(s);
      }, false, { draft: false });
      const marker = el("span", "", layer.id === s.selectedAdjustmentLayerId ? "Selected" : "");
      row.append(visible, pick, marker);
      layerList.appendChild(row);
    }
    layerList.append(topLayer, underLayer);
  }

  function syncControls() {
    syncLegacyState(s);
    syncLegacyAdjustmentState(s);
    renderLayerStack();
    root.querySelectorAll("[data-group-value]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.value === btn.__getValue?.());
    });
    root.querySelectorAll("[data-mask-toggle]").forEach((btn) => {
      btn.classList.toggle("active", s.showMask !== false);
    });
    root.querySelectorAll("[data-before-toggle]").forEach((btn) => {
      btn.classList.toggle("active", !!s.beforePreview);
    });
    root.querySelectorAll("[data-performance-toggle]").forEach((btn) => {
      btn.textContent = s.performanceMode === "quality" ? "Quality" : "Fast";
      btn.classList.toggle("active", s.performanceMode === "quality");
    });
    root.querySelectorAll("[data-preset]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.preset === activeAdjustment().preset);
    });
    root.querySelectorAll(".wfx-ice-select").forEach((select) => select.__sync?.());
    root.querySelectorAll(".wfx-ice-slider").forEach((input) => input.__sync?.());
    const { topName, underName } = layers(s);
    const size = outputSize(s);
    topLayerMeta.textContent = `Image ${topName}  ${Math.round(s.topOpacity * 100)}%`;
    underLayerMeta.textContent = `Image ${underName}`;
    canvas.style.cursor = s.tool === "pan" ? (s.panning ? "grabbing" : "grab") : "none";
    const warning = dimensionsDiffer(s) ? `<span class="wfx-ice-warn">Source sizes differ. Image 3 uses image ${underName}'s canvas.</span>` : "Source sizes match.";
    meta.innerHTML = `
      <div>Image 1: ${s.img1 ? `${imageW(s.img1)} x ${imageH(s.img1)}` : "not run"}</div>
      <div>Image 2: ${s.img2 ? `${imageW(s.img2)} x ${imageH(s.img2)}` : "not run"}</div>
      <div>Image 3: ${size.w} x ${size.h}</div>
      <div>Top: image ${topName}, Under: image ${underName}</div>
      <div>${warning}</div>
    `;
    zoomLabel.textContent = `${Math.round(s.editorZoom * 100)}%`;
  }

  function resizeCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(1, stage.clientWidth);
    const h = Math.max(1, stage.clientHeight);
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
  }

  function drawChecker(ctx, width, height) {
    ctx.fillStyle = "#111315";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "#171a1d";
    const size = 22;
    for (let y = 0; y < height; y += size) {
      for (let x = 0; x < width; x += size) {
        if (((x / size + y / size) & 1) === 0) ctx.fillRect(x, y, size, size);
      }
    }
  }

  function drawPaintTint(ctx, paintCanvas, fillStyle, alphaScale, dw, dh) {
    if (!paintCanvas) return;
    const tint = workingCanvas(s, "paintTint", paintCanvas.width, paintCanvas.height);
    const tctx = tint.getContext("2d");
    tctx.fillStyle = fillStyle;
    tctx.fillRect(0, 0, tint.width, tint.height);
    tctx.globalCompositeOperation = "destination-in";
    tctx.drawImage(paintCanvas, 0, 0);
    tctx.globalCompositeOperation = "source-in";
    tctx.globalAlpha = alphaScale;
    tctx.fillStyle = fillStyle;
    tctx.fillRect(0, 0, tint.width, tint.height);
    tctx.globalAlpha = 1;
    tctx.globalCompositeOperation = "source-over";
    ctx.drawImage(tint, transform.x, transform.y, dw, dh);
  }

  function drawBrushCursor(ctx) {
    if (!s.cursorPoint || s.tool === "pan" || !s.img1 || !s.img2) return;
    const radius = Math.max(2, (s.brush.size * transform.scale) / 2);
    const hardRadius = Math.max(1, radius * clamp(s.brush.hardness, 0, 1));
    const accent = s.tool === "eraser" ? "#ff6f61" : s.brushTarget === "adjustment" ? AMBER : GREEN;
    const label = s.tool === "eraser" ? "E" : s.brushTarget === "adjustment" ? "A" : "B";

    ctx.save();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "rgba(0,0,0,.72)";
    ctx.beginPath();
    ctx.arc(s.cursorPoint.x, s.cursorPoint.y, radius + 1, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(s.cursorPoint.x, s.cursorPoint.y, hardRadius + 1, 0, Math.PI * 2);
    ctx.stroke();

    if (s.tool === "eraser") ctx.setLineDash([5, 4]);
    ctx.strokeStyle = accent;
    ctx.beginPath();
    ctx.arc(s.cursorPoint.x, s.cursorPoint.y, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = "rgba(255,255,255,.86)";
    ctx.beginPath();
    ctx.arc(s.cursorPoint.x, s.cursorPoint.y, hardRadius, 0, Math.PI * 2);
    ctx.stroke();

    ctx.font = "10px Segoe UI, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "rgba(0,0,0,.65)";
    ctx.beginPath();
    ctx.arc(s.cursorPoint.x, s.cursorPoint.y, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.fillText(label, s.cursorPoint.x, s.cursorPoint.y + 0.5);
    ctx.restore();
  }

  function render() {
    raf = 0;
    resizeCanvas();
    syncControls();
    const dpr = window.devicePixelRatio || 1;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const cw = canvas.clientWidth;
    const ch = canvas.clientHeight;
    drawChecker(ctx, cw, ch);

    if (!s.img1 || !s.img2) {
      ctx.fillStyle = "#747d87";
      ctx.font = "15px Segoe UI, Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("Run the node with image1 and image2 to edit image3", cw / 2, ch / 2);
      setStatus("Waiting for images");
      return;
    }

    const fullSize = outputSize(s);
    const useDraft = s.performanceMode === "fast" && s.previewDraft;
    const img = s.beforePreview
      ? composeBaseComposite(s, { includeBlendMask: false, preview: useDraft })
      : composeImage3(s, true, { preview: useDraft });
    transform = editorTransform(s, canvas, fullSize);
    const dw = fullSize.w * transform.scale;
    const dh = fullSize.h * transform.scale;

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, transform.x, transform.y, dw, dh);

    const mask = ensureMask(s);
    if (!s.beforePreview && mask && s.showMask !== false) drawPaintTint(ctx, mask, GREEN, 1, dw, dh);
    const activeLayer = activeAdjustment();
    if (!s.beforePreview && s.brushTarget === "adjustment" && activeLayer.mode === "brush") {
      drawPaintTint(ctx, ensureAdjustmentBrush(s, activeLayer), AMBER, 0.72, dw, dh);
    }

    ctx.strokeStyle = BRAND;
    ctx.lineWidth = 1;
    ctx.strokeRect(Math.round(transform.x) + 0.5, Math.round(transform.y) + 0.5, Math.round(dw), Math.round(dh));
    drawBrushCursor(ctx);
    setStatus(`${s.beforePreview ? "Before" : "Image 3"}: ${fullSize.w} x ${fullSize.h}${useDraft ? "  Fast preview" : ""}`);
  }

  function resetPaintArea() {
    setAndRefresh(() => {
      pushUndo(s);
      const target = s.brushTarget === "adjustment" ? "adjustment" : "blend";
      const canvas = ensurePaintCanvas(s, target);
      canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
      if (target === "adjustment") s.adjustmentBrushData = "";
      else s.maskData = "";
    }, true);
  }

  function invertPaintArea() {
    setAndRefresh(() => {
      pushUndo(s);
      const target = s.brushTarget === "adjustment" ? "adjustment" : "blend";
      const canvas = ensurePaintCanvas(s, target);
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < data.data.length; i += 4) {
        data.data[i] = 255;
        data.data[i + 1] = 255;
        data.data[i + 2] = 255;
        data.data[i + 3] = 255 - data.data[i + 3];
      }
      ctx.putImageData(data, 0, 0);
      syncPaintData(s, target);
    }, true);
  }

  function undoMask() {
    if (!s.undo.length) return;
    s.redo.push(editorSnapshot(s));
    restoreEditorSnapshot(node, s.undo.pop(), () => {
      syncControls();
      scheduleRender();
    });
  }

  function redoMask() {
    if (!s.redo.length) return;
    s.undo.push(editorSnapshot(s));
    restoreEditorSnapshot(node, s.redo.pop(), () => {
      syncControls();
      scheduleRender();
    });
  }

  function canvasPoint(event) {
    const rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    const before = canvasPoint(event);
    const old = s.editorZoom;
    const next = clamp(old * (event.deltaY < 0 ? 1.1 : 0.9), 0.1, 12);
    if (next === old) return;
    s.editorPanX = before.x - canvas.clientWidth / 2 - ((before.x - canvas.clientWidth / 2 - s.editorPanX) * next) / old;
    s.editorPanY = before.y - canvas.clientHeight / 2 - ((before.y - canvas.clientHeight / 2 - s.editorPanY) * next) / old;
    s.editorZoom = next;
    persist(node, false);
    scheduleRender();
  }, { passive: false });

  canvas.addEventListener("pointerdown", (event) => {
    if (!s.img1 || !s.img2) return;
    canvas.setPointerCapture?.(event.pointerId);
    const p = canvasPoint(event);
    s.cursorPoint = p;
    if (s.tool === "pan" || event.altKey || event.button === 1 || event.getModifierState?.("Space")) {
      s.panning = true;
      s.panStart = { x: p.x, y: p.y, panX: s.editorPanX, panY: s.editorPanY };
      return;
    }
    if (s.brushTarget === "adjustment") {
      activeAdjustment().mode = "brush";
      syncLegacyAdjustmentState(s);
    }
    pushUndo(s);
    s.drawing = true;
    s.previewDraft = s.performanceMode === "fast";
    s.lastPoint = imagePointFromEditor(s, transform, p.x, p.y);
    drawBrush(s, s.lastPoint);
    scheduleRender();
  });

  canvas.addEventListener("pointermove", (event) => {
    const p = canvasPoint(event);
    s.cursorPoint = p;
    if (s.panning && s.panStart) {
      s.editorPanX = s.panStart.panX + p.x - s.panStart.x;
      s.editorPanY = s.panStart.panY + p.y - s.panStart.y;
      persist(node, false);
      scheduleRender();
      return;
    }
    if (s.drawing) {
      const next = imagePointFromEditor(s, transform, p.x, p.y);
      strokeBrush(s, s.lastPoint || next, next);
      s.lastPoint = next;
      scheduleRender();
    } else {
      scheduleRender();
    }
  });

  const finishStroke = () => {
    if (s.drawing) syncPaintData(s);
    s.previewDraft = false;
    s.drawing = false;
    s.panning = false;
    s.lastPoint = null;
    s.panStart = null;
    persist(node, true);
    dirty(node);
    scheduleRender();
  };
  canvas.addEventListener("pointerup", finishStroke);
  canvas.addEventListener("pointercancel", finishStroke);
  canvas.addEventListener("pointerleave", () => {
    if (!s.drawing && !s.panning) {
      s.cursorPoint = null;
      scheduleRender();
    }
  });
  window.addEventListener("resize", scheduleRender);

  syncControls();
  scheduleRender();
}

app.registerExtension({
  name: "workflowx.image_compare_edit_x.canvas",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_TYPE) return;

    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      try {
        origCreated?.apply(this, arguments);
        getState(this);
        this.hideOutputImages = true;
        normalizeNodeSize(this);
        restoreImages(this);
      } catch (err) {
        console.warn("[WorkflowX] Image Compare Edit X create hook failed:", err);
      }
    };

    const origConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = origConfigure?.apply(this, arguments);
      try {
        getState(this);
        normalizeNodeSize(this);
        restoreImages(this);
      } catch (err) {
        console.warn("[WorkflowX] Image Compare Edit X configure hook failed:", err);
      }
      return result;
    };

    nodeType.prototype.onExecuted = function (output) {
      try {
        this.imgs = null;
        const s = getState(this);
        if (!output?.images || output.images.length < 2) return;
        s.images = output.images.slice(0, 2).map((img) => ({
          filename: img.filename,
          subfolder: img.subfolder || "",
          type: img.type || "temp",
        }));
        persist(this, false);
        loadImage(this, s.images[0], 1);
        loadImage(this, s.images[1], 2);
      } catch (err) {
        console.warn("[WorkflowX] Image Compare Edit X execution hook failed:", err);
      }
    };

    nodeType.prototype.onDrawBackground = function () {
      if (this.imgs) this.imgs = null;
    };

    const origDraw = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      origDraw?.call(this, ctx);
      if (this.flags?.collapsed) return;
      normalizeNodeSize(this);
      try {
        drawNode(ctx, this);
      } catch (err) {
        console.warn("[WorkflowX] Image Compare Edit X draw failed:", err);
        drawNodeFallback(ctx, this, err);
      }
    };

    const origDown = nodeType.prototype.onMouseDown;
    nodeType.prototype.onMouseDown = function (event, pos) {
      const hitRect = hit(this, pos);
      if (hitRect) {
        setHoverTip(this, null);
        handleNodeAction(this, hitRect.action, hitRect.value, pos);
        return true;
      }
      const s = getState(this);
      if (s.openDropdown) {
        s.openDropdown = "";
        dirty(this);
        return true;
      }
      const box = imageBox(this);
      if (inside(pos, box) && s.viewMode === "split") {
        s.splitDragging = true;
        updateSplitFromNode(this, pos);
        return true;
      }
      return origDown?.call(this, event, pos);
    };

    const origMove = nodeType.prototype.onMouseMove;
    nodeType.prototype.onMouseMove = function (event, pos) {
      const s = getState(this);
      if (s.opacityDragging) {
        setHoverTip(this, null);
        updateOpacityFromNode(this, pos);
        return true;
      }
      if (s.splitDragging) {
        setHoverTip(this, null);
        updateSplitFromNode(this, pos);
        return true;
      }
      setHoverTip(this, hit(this, pos));
      return origMove?.call(this, event, pos);
    };

    const origLeave = nodeType.prototype.onMouseLeave;
    nodeType.prototype.onMouseLeave = function (event, pos) {
      setHoverTip(this, null);
      return origLeave?.call(this, event, pos);
    };

    const origUp = nodeType.prototype.onMouseUp;
    nodeType.prototype.onMouseUp = function (event, pos) {
      const s = getState(this);
      s.splitDragging = false;
      s.opacityDragging = false;
      persist(this, false);
      return origUp?.call(this, event, pos);
    };

  },
});
