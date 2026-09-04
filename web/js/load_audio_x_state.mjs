export const LOAD_AUDIO_X_DEFAULTS = Object.freeze({
  version: 1, file: "", start: 0, length: 5, when_unwired: "whole", when_short: "silence",
  format: "wav", wav_depth: "16-bit", mp3_bitrate: "192k", channels: "Source",
  sample_rate: "Source", repair_mode: "auto", filters: [], gain_db: 0, normalize: "Off",
  target_lufs: -16, limiter: false, trim_silence: false, silence_threshold_db: -50,
  minimum_silence: .1, fade_in: 0, fade_out: 0, save_output: false,
  filename_prefix: "audio/LoadAudioX",
});

const oneOf = (value, choices, fallback) => choices.includes(value) ? value : fallback;
const finite = (value, fallback, low, high) => {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(low, Math.min(high, number)) : fallback;
};
const milliseconds = (value, fallback, low, high) => Math.round(finite(value, fallback, low, high) * 1000) / 1000;

export function normalizeAudioXState(value) {
  let raw = value;
  if (typeof raw === "string") {
    try { raw = JSON.parse(raw); } catch { raw = {}; }
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) raw = {};
  const state = { ...LOAD_AUDIO_X_DEFAULTS, ...raw };
  state.version = 1;
  state.file = typeof raw.file === "string" ? raw.file : "";
  state.start = milliseconds(raw.start, 0, 0, 86400);
  state.length = milliseconds(raw.length, 5, 0, 86400);
  state.when_unwired = oneOf(raw.when_unwired, ["whole", "length"], "whole");
  state.when_short = oneOf(raw.when_short, ["silence", "loop"], "silence");
  state.format = String(raw.format || "").toLowerCase() === "mp3" ? "mp3" : "wav";
  state.wav_depth = oneOf(raw.wav_depth, ["16-bit", "24-bit", "32-bit float"], "16-bit");
  state.mp3_bitrate = oneOf(raw.mp3_bitrate, ["64k", "96k", "128k", "160k", "192k", "256k", "320k"], "192k");
  state.channels = oneOf(raw.channels, ["Source", "Mono", "Stereo"], "Source");
  state.sample_rate = oneOf(raw.sample_rate, ["Source", "8 kHz", "16 kHz", "22.05 kHz", "24 kHz", "32 kHz", "44.1 kHz", "48 kHz", "96 kHz"], "Source");
  state.repair_mode = raw.repair_mode === "off" ? "off" : "auto";
  const knownFilters = ["Denoise light", "De-click", "High-pass rumble cut", "Low-pass hiss cut", "De-esser light", "Presence boost", "Warmth", "Brightness", "Speech clarity", "Stereo widen", "Voice compressor", "Noise gate"];
  state.filters = knownFilters.filter((name) => Array.isArray(raw.filters) && raw.filters.includes(name));
  state.gain_db = finite(raw.gain_db, 0, -24, 24);
  state.normalize = oneOf(raw.normalize, ["Off", "Peak", "EBU R128"], "Off");
  state.target_lufs = finite(raw.target_lufs, -16, -30, -5);
  state.limiter = raw.limiter === true;
  state.trim_silence = raw.trim_silence === true;
  state.silence_threshold_db = finite(raw.silence_threshold_db, -50, -90, -10);
  state.minimum_silence = finite(raw.minimum_silence, .1, 0, 10);
  state.fade_in = finite(raw.fade_in, 0, 0, 60);
  state.fade_out = finite(raw.fade_out, 0, 0, 60);
  state.save_output = raw.save_output === true;
  state.filename_prefix = String(raw.filename_prefix || LOAD_AUDIO_X_DEFAULTS.filename_prefix).slice(0, 512);
  return state;
}

export function selectedRange(stateValue, duration, wiredSeconds = null) {
  const state = normalizeAudioXState(stateValue);
  const total = Math.max(0, Number(duration) || 0);
  const start = Math.min(total, state.start);
  const hasWire = wiredSeconds !== null && wiredSeconds !== undefined && Number.isFinite(Number(wiredSeconds)) && Number(wiredSeconds) >= 0;
  const fixed = Number(wiredSeconds);
  const requested = hasWire ? fixed : state.when_unwired === "length" ? state.length : total - start;
  return { start, length: Math.max(0, requested), end: Math.min(total, start + Math.max(0, requested)), fixed: hasWire };
}

export function injectAudioXState(promptEntry, stateValue) {
  if (!promptEntry || typeof promptEntry !== "object") return promptEntry;
  promptEntry.inputs ||= {};
  promptEntry.inputs.LoadAudioXState = JSON.stringify(normalizeAudioXState(stateValue));
  return promptEntry;
}

export function timelineDragMode(pointerRatio, startRatio, endRatio, widthPixels, wired = false) {
  const threshold = Math.min(.08, 12 / Math.max(1, Number(widthPixels) || 1));
  const pointer = Math.max(0, Math.min(1, Number(pointerRatio) || 0));
  if (wired && pointer >= startRatio - threshold && pointer <= endRatio + threshold) return "move";
  if (Math.abs(pointer - startRatio) <= threshold) return "start";
  if (Math.abs(pointer - endRatio) <= threshold) return "end";
  if (pointer > startRatio && pointer < endRatio) return "move";
  return Math.abs(pointer - startRatio) < Math.abs(pointer - endRatio) ? "start" : "end";
}

export function movedRangeStart(originalStart, length, pointerDelta, duration) {
  const total = Math.max(0, Number(duration) || 0);
  const size = Math.max(0, Number(length) || 0);
  return Math.max(0, Math.min(Math.max(0, total - size), (Number(originalStart) || 0) + (Number(pointerDelta) || 0)));
}
