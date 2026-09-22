export function normalizeSha256(value) {
  const digest = String(value || "").trim().toLowerCase();
  return /^[0-9a-f]{64}$/.test(digest) ? digest : "";
}

export function normalizeFileSize(value) {
  const size = Number(value || 0);
  return Number.isFinite(size) && size >= 0 ? Math.trunc(size) : 0;
}

export function itemSha256(item) {
  return normalizeSha256(item?.sha256 || item?.metadata?.sha256);
}

export function itemFileSize(item) {
  return normalizeFileSize(item?.file_size ?? item?.metadata?.file_size);
}

export function sortedHashMatches(items, sha256) {
  const digest = normalizeSha256(sha256);
  if (!digest) return [];
  return (Array.isArray(items) ? items : [])
    .filter((item) => itemSha256(item) === digest)
    .sort((a, b) => String(a?.load_name || "").localeCompare(String(b?.load_name || ""), undefined, { sensitivity: "base" }));
}

export function applyIdentity(row, item) {
  const current = row && typeof row === "object" ? row : {};
  const identity = item && typeof item === "object" ? item : {};
  const loadName = identity.load_name || current.load_name || current.lora || null;
  return {
    ...current,
    load_name: loadName,
    lora: loadName,
    path: identity.folder ?? current.path ?? null,
    display_name: identity.display_name || identity.file_stem || current.display_name || loadName,
    sha256: itemSha256(identity) || normalizeSha256(current.sha256),
    file_size: itemFileSize(identity) || normalizeFileSize(current.file_size),
  };
}
