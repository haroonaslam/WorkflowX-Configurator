export const DEFAULT_ADV_STATE = Object.freeze({
  version: 1,
  mode: "off",
  max_mp: 1,
  longest_side: 1024,
  scale_factor: 1,
  fit_w: 1024,
  fit_h: 1024,
  cover_w: 1024,
  cover_h: 1024,
  cover_action: "fill",
  crop_anchor: "center",
  ratio_preset: "1:1",
  ratio_w: 1,
  ratio_h: 1,
  pad_color: "#808080",
  pad_top: 0,
  pad_bottom: 0,
  pad_left: 0,
  pad_right: 0,
  output_snap: 0,
  resample: "auto",
  allow_upscale: false,
  crop_enabled: false,
  crop_snap: 0,
  crop_rect: null,
});

const VALID_MODES = new Set([
  "off", "max_mp", "longest_side", "scale_factor", "fit_inside", "cover", "match_ratio", "pad",
]);
const VALID_RESAMPLE = new Set(["auto", "nearest", "bilinear", "bicubic", "lanczos"]);
const VALID_SNAPS = new Set([0, 8, 16, 32, 64]);

function finiteNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function boundedDimension(value, fallback = 1024) {
  return clamp(Math.round(finiteNumber(value, fallback)), 8, 16384);
}

function snapDown(value, snap) {
  return snap > 0 ? Math.max(8, Math.floor(value / snap) * snap) : value;
}

function snapNearest(value, snap, limit) {
  if (!(snap > 0)) return clamp(Math.round(value), 1, limit);
  if (limit < snap) return limit;
  const nearest = Math.max(snap, Math.round(value / snap) * snap);
  return Math.min(nearest, Math.floor(limit / snap) * snap);
}

export function normalizeAdvState(value) {
  let parsed = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      parsed = {};
    }
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) parsed = {};
  const state = { ...DEFAULT_ADV_STATE };
  for (const key of Object.keys(DEFAULT_ADV_STATE)) {
    if (Object.hasOwn(parsed, key)) state[key] = parsed[key];
  }
  if (!VALID_MODES.has(state.mode)) state.mode = "off";
  if (!VALID_RESAMPLE.has(state.resample)) state.resample = "auto";
  for (const key of ["output_snap", "crop_snap"]) {
    const numeric = Number(state[key]);
    state[key] = VALID_SNAPS.has(numeric) ? numeric : 0;
  }
  if (!state.crop_rect || typeof state.crop_rect !== "object") state.crop_rect = null;
  state.allow_upscale = Boolean(state.allow_upscale);
  state.crop_enabled = Boolean(state.crop_enabled);
  return state;
}

export function pixelRectFromState(width, height, stateValue) {
  const state = normalizeAdvState(stateValue);
  if (!state.crop_enabled || !state.crop_rect || width < 1 || height < 1) return null;
  const source = state.crop_rect;
  const x = clamp(finiteNumber(source.x, 0), 0, 1);
  const y = clamp(finiteNumber(source.y, 0), 0, 1);
  const w = clamp(finiteNumber(source.w, 0), 0, 1 - x);
  const h = clamp(finiteNumber(source.h, 0), 0, 1 - y);
  if (w <= 0 || h <= 0) return null;
  let x0 = clamp(Math.round(x * width), 0, width - 1);
  let y0 = clamp(Math.round(y * height), 0, height - 1);
  let x1 = clamp(Math.round((x + w) * width), x0 + 1, width);
  let y1 = clamp(Math.round((y + h) * height), y0 + 1, height);
  const cropWidth = snapNearest(x1 - x0, state.crop_snap, width);
  const cropHeight = snapNearest(y1 - y0, state.crop_snap, height);
  x0 = Math.min(x0, width - cropWidth);
  y0 = Math.min(y0, height - cropHeight);
  x1 = x0 + cropWidth;
  y1 = y0 + cropHeight;
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

export function normalizedRect(rect, width, height) {
  if (!rect || width < 1 || height < 1 || rect.w < 1 || rect.h < 1) return null;
  return {
    x: Number((rect.x / width).toFixed(6)),
    y: Number((rect.y / height).toFixed(6)),
    w: Number((rect.w / width).toFixed(6)),
    h: Number((rect.h / height).toFixed(6)),
  };
}

export function snapCropRect(rect, width, height, snap, fixedCorner = "top-left") {
  if (!rect || width < 1 || height < 1) return null;
  const rawW = Math.max(1, Math.abs(finiteNumber(rect.w, 1)));
  const rawH = Math.max(1, Math.abs(finiteNumber(rect.h, 1)));
  const snappedW = snapNearest(rawW, Number(snap) || 0, width);
  const snappedH = snapNearest(rawH, Number(snap) || 0, height);
  const right = finiteNumber(rect.x, 0) + rawW;
  const bottom = finiteNumber(rect.y, 0) + rawH;
  let x = finiteNumber(rect.x, 0);
  let y = finiteNumber(rect.y, 0);
  if (fixedCorner.includes("right")) x = right - snappedW;
  if (fixedCorner.includes("bottom")) y = bottom - snappedH;
  x = clamp(Math.round(x), 0, Math.max(0, width - snappedW));
  y = clamp(Math.round(y), 0, Math.max(0, height - snappedH));
  return { x, y, w: snappedW, h: snappedH };
}

export function clearCropForImageChange(stateValue) {
  return { ...normalizeAdvState(stateValue), crop_rect: null };
}

export function cropSnapVisible(stateValue) {
  return normalizeAdvState(stateValue).crop_enabled;
}

export function computeOutputDimensions(sourceWidth, sourceHeight, stateValue) {
  const state = normalizeAdvState(stateValue);
  const crop = pixelRectFromState(sourceWidth, sourceHeight, state);
  let width = crop?.w || sourceWidth;
  let height = crop?.h || sourceHeight;
  const allowUpscale = state.allow_upscale;

  const applyFactor = (factor) => {
    if (!allowUpscale) factor = Math.min(factor, 1);
    factor = Math.min(Math.max(factor, 0.01), 8);
    width = Math.max(1, Math.round(width * factor));
    height = Math.max(1, Math.round(height * factor));
  };

  if (state.mode === "max_mp") {
    const target = clamp(finiteNumber(state.max_mp, 1), 0.01, 64) * 1024 * 1024;
    applyFactor(Math.sqrt(target / Math.max(1, width * height)));
  } else if (state.mode === "longest_side") {
    applyFactor(boundedDimension(state.longest_side) / Math.max(width, height));
  } else if (state.mode === "scale_factor") {
    applyFactor(clamp(finiteNumber(state.scale_factor, 1), 0.01, 8));
  } else if (state.mode === "fit_inside") {
    applyFactor(Math.min(boundedDimension(state.fit_w) / width, boundedDimension(state.fit_h) / height));
  } else if (state.mode === "cover") {
    const targetW = boundedDimension(state.cover_w);
    const targetH = boundedDimension(state.cover_h);
    if (state.cover_action === "crop") {
      width = Math.min(targetW, width);
      height = Math.min(targetH, height);
    } else {
      const factor = Math.max(targetW / width, targetH / height);
      if (!allowUpscale && factor > 1) {
        applyFactor(Math.min(targetW / width, targetH / height, 1));
      } else {
        width = targetW;
        height = targetH;
      }
    }
  } else if (state.mode === "match_ratio") {
    const ratioW = Math.max(0.01, finiteNumber(state.ratio_w, 1));
    const ratioH = Math.max(0.01, finiteNumber(state.ratio_h, 1));
    const target = ratioW / ratioH;
    if (width / height > target) width = Math.max(1, Math.round(height * target));
    else height = Math.max(1, Math.round(width / target));
  } else if (state.mode === "pad") {
    width = Math.min(16384, width
      + clamp(Math.trunc(finiteNumber(state.pad_left, 0)), 0, 8192)
      + clamp(Math.trunc(finiteNumber(state.pad_right, 0)), 0, 8192));
    height = Math.min(16384, height
      + clamp(Math.trunc(finiteNumber(state.pad_top, 0)), 0, 8192)
      + clamp(Math.trunc(finiteNumber(state.pad_bottom, 0)), 0, 8192));
  }

  width = clamp(snapDown(width, state.output_snap), 8, 16384);
  height = clamp(snapDown(height, state.output_snap), 8, 16384);
  return { width, height, crop };
}
