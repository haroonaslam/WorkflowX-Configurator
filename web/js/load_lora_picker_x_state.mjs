export function normalizePickerPath(value) {
  return String(value || "").replaceAll("\\", "/").trim();
}

export function sanitizePickerRow(value = {}) {
  const loadName = normalizePickerPath(value.load_name ?? value.loadName ?? value.lora ?? value.path);
  const modelStrength = Number(value.strength_model ?? value.model_strength ?? 1);
  const clipStrength = Number(value.strength_clip ?? value.clip_strength ?? 1);
  return {
    on: value.on !== false && value.enabled !== false,
    load_name: loadName,
    display_name: String(value.display_name || value.filename || loadName.split("/").pop() || ""),
    filename: String(value.filename || loadName.split("/").pop() || ""),
    source: value.source === "registered" ? "registered" : "external",
    strength_model: Number.isFinite(modelStrength) ? modelStrength : 1,
    strength_clip: Number.isFinite(clipStrength) ? clipStrength : 1,
    trigger_words: Array.isArray(value.trigger_words) ? value.trigger_words.map(String) : [],
  };
}

export function pickerRowFromInspection(inspection, previous = {}) {
  const selected = inspection?.selected || {};
  const old = sanitizePickerRow(previous);
  return {
    ...old,
    load_name: normalizePickerPath(selected.load_name),
    display_name: String(selected.display_name || selected.filename || selected.load_name || ""),
    filename: String(selected.filename || ""),
    source: selected.source === "registered" ? "registered" : "external",
  };
}

export function pickerRowRestoreKey(value) {
  const row = sanitizePickerRow(value);
  return JSON.stringify({
    on: row.on,
    load_name: row.load_name,
    strength_model: row.strength_model,
    strength_clip: row.strength_clip,
  });
}

export function compactPickerVersionLabel(option) {
  const label = String(option?.label || "").trim();
  if (!label) return "Choose";
  if (/^(?:final|single)$/i.test(label)) return label;
  const digits = label.match(/(\d+)\s*$/)?.[1];
  if (!digits) return label;
  const prefix = {
    epoch: "E",
    step: "S",
    checkpoint: "#",
    number: "#",
  }[String(option?.epoch_kind || "").toLowerCase()] || "#";
  return `${prefix}${digits}`;
}
