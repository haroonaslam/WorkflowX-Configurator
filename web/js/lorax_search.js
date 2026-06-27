const LORA_EXT_RE = /\.(safetensors|ckpt|pt|bin)$/i;

export function normalizePath(value) {
  return String(value || "").replace(/\\/g, "/").trim();
}

export function compactArray(values) {
  if (!Array.isArray(values)) return [];
  return values.map((value) => String(value || "").trim()).filter(Boolean);
}

export function searchTerms(query) {
  return String(query || "")
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .map((term) => term.trim())
    .filter(Boolean);
}

export function trainedWords(item) {
  const words = item?.civitai?.trainedWords || item?.trained_words || item?.trigger_words || [];
  if (Array.isArray(words)) return compactArray(words);
  if (typeof words === "string") {
    return words
      .replace(/,,/g, ",")
      .split(",")
      .map((word) => word.trim())
      .filter(Boolean);
  }
  return [];
}

export function creatorName(item) {
  return normalizePath(item?.civitai?.creator?.username || item?.creator?.username || item?.creator || "");
}

function lowerFields(fields) {
  return fields.map((field) => String(field || "").toLowerCase()).filter(Boolean);
}

export function broadSearchFields(item) {
  const metadata = item?.metadata || {};
  return lowerFields([
    item?.load_name,
    item?.folder,
    item?.filename,
    item?.file_stem,
    item?.full_path,
    item?.display_name,
    item?.model_name,
    item?.base_model,
    item?.sub_type,
    item?.creator,
    metadata.model_name,
    metadata.file_name,
    metadata.folder,
    metadata.file_path,
    metadata.base_model,
    metadata.sub_type,
    creatorName(metadata),
    ...compactArray(item?.tags),
    ...compactArray(item?.auto_tags),
    ...trainedWords(item),
    ...compactArray(metadata.tags),
    ...compactArray(metadata.auto_tags),
    ...trainedWords(metadata),
  ]);
}

export function strictSearchFields(item) {
  const metadata = item?.metadata || {};
  const canonicalName = item?.canonical_display_name || item?.file_stem || normalizePath(item?.filename).replace(LORA_EXT_RE, "");
  return lowerFields([
    item?.load_name,
    item?.folder,
    item?.filename,
    item?.file_stem,
    item?.full_path,
    canonicalName,
    item?.base_model,
    metadata.file_name,
    metadata.folder,
    metadata.file_path,
    metadata.base_model,
  ]);
}

export function itemMatchesQuery(item, query, strict = false) {
  const terms = searchTerms(query);
  if (!terms.length) return true;
  const fields = strict ? strictSearchFields(item) : broadSearchFields(item);
  return terms.every((term) => fields.some((field) => field.includes(term)));
}
