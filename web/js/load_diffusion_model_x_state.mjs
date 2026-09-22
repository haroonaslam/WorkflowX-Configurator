function asBool(value, fallback = true) {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") return !["", "0", "false", "no", "off"].includes(value.trim().toLowerCase());
  return Boolean(value);
}

export function modelFilenameStem(value) {
  const candidate = typeof value === "object" && value !== null
    ? value.filename || value.file_name || value.load_name || value.loadName || value.unet_name || value.unetName
    : value;
  const normalized = String(candidate || "").replace(/\\/g, "/").trim();
  const filename = normalized.split("/").pop() || normalized;
  return filename.replace(/\.[^./]+$/u, "");
}

export function normalizeSha256(value) {
  const digest = String(value || "").trim().toLowerCase();
  return /^[0-9a-f]{64}$/.test(digest) ? digest : "";
}

export function normalizeFileSize(value) {
  const size = Number(value || 0);
  return Number.isFinite(size) && size >= 0 ? Math.trunc(size) : 0;
}

export function modelItemSha256(item) {
  return normalizeSha256(item?.sha256 || item?.metadata?.sha256);
}

export function modelItemFileSize(item) {
  return normalizeFileSize(item?.file_size ?? item?.metadata?.file_size);
}

export function sortedModelHashMatches(items, sha256) {
  const digest = normalizeSha256(sha256);
  if (!digest) return [];
  return (Array.isArray(items) ? items : [])
    .filter((item) => modelItemSha256(item) === digest)
    .sort((a, b) => String(a?.load_name || "").localeCompare(String(b?.load_name || ""), undefined, { sensitivity: "base" }));
}

export function applyModelIdentity(row, item) {
  const current = row && typeof row === "object" ? row : {};
  const identity = item && typeof item === "object" ? item : {};
  const loadName = identity.load_name || current.load_name || current.unet_name || null;
  return {
    ...current,
    load_name: loadName,
    unet_name: loadName,
    path: identity.folder ?? current.path ?? null,
    display_name: modelFilenameStem(identity) || current.display_name || loadName,
    sha256: modelItemSha256(identity) || normalizeSha256(current.sha256),
    file_size: modelItemFileSize(identity) || normalizeFileSize(current.file_size),
  };
}

export function defaultModelRow(item = null, active = true) {
  const loadName = item?.load_name || item?.unet_name || null;
  const filenameStem = modelFilenameStem(item) || modelFilenameStem(loadName);
  return {
    on: Boolean(active),
    load_name: loadName,
    unet_name: loadName,
    display_name: filenameStem || loadName,
    path: item?.folder || null,
    sha256: modelItemSha256(item),
    file_size: modelItemFileSize(item),
    metadata: item
      ? {
          preview_url: item.preview_url || "",
          file_path: item.full_path || item.metadata?.file_path || "",
          file_size: Number(item.file_size || item.metadata?.file_size || 0),
          base_model: item.base_model || item.metadata?.base_model || "",
          sub_type: item.sub_type || item.metadata?.sub_type || "diffusion_model",
          tags: Array.isArray(item.tags) ? item.tags : [],
        }
      : {},
  };
}

export function normalizeModelRow(value) {
  const row = defaultModelRow(null, true);
  if (!value || typeof value !== "object") return row;
  const loadName = value.load_name || value.loadName || value.unet_name || value.unetName || value.diffusion_model || value.name || null;
  row.on = asBool(value.on ?? value.enabled ?? value.active, true);
  row.load_name = loadName;
  row.unet_name = loadName;
  row.display_name = modelFilenameStem(value) || modelFilenameStem(loadName) || value.display_name || value.displayName || value.model_name || loadName;
  row.path = value.path || value.folder || null;
  row.sha256 = normalizeSha256(value.sha256 || value.hash || value.metadata?.sha256);
  row.file_size = modelItemFileSize(value);
  row.metadata = value.metadata && typeof value.metadata === "object" ? { ...value.metadata } : {};
  return row;
}

export function restoreModelRows(values) {
  if (!Array.isArray(values)) return [];
  const rows = values
    .filter((value) => value && typeof value === "object" && (value.load_name || value.loadName || value.unet_name || value.unetName || value.diffusion_model))
    .map(normalizeModelRow);
  const activeIndex = rows.findIndex((row) => row.on && row.load_name);
  const selectedIndex = activeIndex >= 0 ? activeIndex : (rows.length ? 0 : -1);
  if (selectedIndex >= 0) rows.forEach((row, index) => { row.on = index === selectedIndex; });
  return rows;
}

export function activateModelRow(rows, activeIndex) {
  return rows.map((value, index) => ({ ...normalizeModelRow(value), on: index === activeIndex }));
}

export function removeModelRow(rows, removeIndex) {
  const normalized = rows.map(normalizeModelRow);
  const removedWasActive = Boolean(normalized[removeIndex]?.on);
  normalized.splice(removeIndex, 1);
  if (normalized.length && (removedWasActive || !normalized.some((row) => row.on))) {
    const nextIndex = Math.min(removeIndex, normalized.length - 1);
    normalized.forEach((row, index) => { row.on = index === nextIndex; });
  }
  return normalized;
}
