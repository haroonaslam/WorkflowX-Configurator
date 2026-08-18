export function normalizePath(value) {
  return String(value || "").replace(/\\/g, "/").trim();
}

export function searchTerms(query) {
  return String(query || "")
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .map((term) => term.trim())
    .filter(Boolean);
}

export function itemSearchFields(item) {
  const metadata = item?.metadata || {};
  return [
    item?.load_name,
    item?.folder,
    item?.filename,
    item?.file_stem,
    item?.display_name,
    item?.full_path,
    item?.extension,
    item?.base_model,
    item?.sub_type,
    metadata.model_name,
    metadata.file_name,
    metadata.folder,
    metadata.file_path,
    metadata.base_model,
    metadata.sub_type,
    ...(Array.isArray(item?.tags) ? item.tags : []),
    ...(Array.isArray(metadata.tags) ? metadata.tags : []),
  ]
    .map((field) => String(field || "").toLowerCase())
    .filter(Boolean);
}

export function itemMatchesQuery(item, query) {
  const terms = searchTerms(query);
  if (!terms.length) return true;
  const fields = itemSearchFields(item);
  return terms.every((term) => fields.some((field) => field.includes(term)));
}
