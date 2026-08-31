import {
  DEFAULT_ADV_STATE,
  computeOutputDimensions,
  normalizeAdvState,
  normalizedRect,
  pixelRectFromState,
  snapCropRect,
} from "./load_image_x_adv_helpers.mjs";

export { computeOutputDimensions, normalizedRect, pixelRectFromState, snapCropRect };

export const DEFAULT_VIDEO_STATE = Object.freeze({
  ...DEFAULT_ADV_STATE,
  version: 1,
  trim_start: 0,
  trim_end: null,
  requested_outputs: [],
});

export function isNativeVideoPreviewWidgetName(value) {
  return String(value || "").toLowerCase().replaceAll("-", "").replaceAll("_", "") === "videopreview";
}

const MEDIA_OUTPUT_NAMES = ["video", "video_frames", "audio"];

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

export function normalizeVideoState(value) {
  let parsed = value;
  if (typeof parsed === "string") {
    try { parsed = JSON.parse(parsed); } catch { parsed = {}; }
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) parsed = {};
  const geometry = normalizeAdvState(parsed);
  const state = { ...DEFAULT_VIDEO_STATE, ...geometry };
  state.version = 1;
  state.trim_start = Math.max(0, number(parsed.trim_start, 0));
  state.trim_end = parsed.trim_end == null ? null : Math.max(state.trim_start, number(parsed.trim_end, state.trim_start));
  state.requested_outputs = Array.isArray(parsed.requested_outputs)
    ? [...new Set(parsed.requested_outputs.filter((name) => MEDIA_OUTPUT_NAMES.includes(name)))]
    : [];
  return state;
}

export function clearForVideoChange(value) {
  return { ...normalizeVideoState(value), crop_rect: null, trim_start: 0, trim_end: null, requested_outputs: [] };
}

export function normalizeTrimRange(metadata, stateValue, wiredSeconds = null, moved = "end") {
  const state = normalizeVideoState(stateValue);
  const duration = Math.max(0, number(metadata?.duration, 0));
  const fps = Math.max(0.001, number(metadata?.fps, 30));
  const snap = (value) => clamp(Math.round(value * fps) / fps, 0, duration);
  let start = snap(state.trim_start);
  let end = snap(state.trim_end == null ? duration : state.trim_end);
  if (end < start) [start, end] = [end, start];

  const fixed = number(wiredSeconds, 0);
  if (fixed > 0) {
    const length = Math.max(1 / fps, Math.round(fixed * fps) / fps);
    if (moved === "start") end = start + length;
    else start = end - length;
    if (start < 0) { start = 0; end = length; }
    if (end > duration && duration > 0) {
      end = duration;
      start = Math.max(0, end - length);
    }
    if (length > duration && duration > 0) { start = 0; end = duration; }
  }
  return { start: Number(start.toFixed(6)), end: Number(Math.max(start, end).toFixed(6)), fixed: fixed > 0 };
}

export function requestedOutputsFromPrompt(output, sourceId) {
  const wanted = new Set();
  const source = String(sourceId);
  const visit = (value) => {
    if (Array.isArray(value)) {
      if (value.length === 2 && String(value[0]) === source && Number.isInteger(Number(value[1]))) {
        const index = Number(value[1]);
        if (index >= 0 && index < MEDIA_OUTPUT_NAMES.length) wanted.add(MEDIA_OUTPUT_NAMES[index]);
        return;
      }
      value.forEach(visit);
    } else if (value && typeof value === "object") {
      Object.values(value).forEach(visit);
    }
  };
  for (const entry of Object.values(output || {})) {
    visit(entry?.inputs || {});
  }
  return MEDIA_OUTPUT_NAMES.filter((name) => wanted.has(name));
}

export function withRequestedOutputsState(value, requestedOutputs) {
  return JSON.stringify({
    ...normalizeVideoState(value),
    requested_outputs: MEDIA_OUTPUT_NAMES.filter((name) => requestedOutputs?.includes(name)),
  });
}

export function videoViewURL(path, version = "") {
  const normalized = String(path || "").replaceAll("\\", "/");
  const slash = normalized.lastIndexOf("/");
  const subfolder = slash >= 0 ? normalized.slice(0, slash) : "";
  const filename = slash >= 0 ? normalized.slice(slash + 1) : normalized;
  const query = new URLSearchParams({ filename, type: "input", subfolder });
  if (version) query.set("v", String(version));
  return `/view?${query}`;
}
