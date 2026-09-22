// Edits are confined to the active line's leading tags.
export function activeLine(value, caret) {
  caret = Math.max(0, Math.min(caret, value.length));
  const start = caret ? value.lastIndexOf("\n", caret - 1) + 1 : 0;
  const end = value.indexOf("\n", caret);
  const line = value.slice(start, end < 0 ? value.length : end);
  const header = line.match(/^[\t ]*(?:@voice[12](?=[\t ]|\[|$)[\t ]*)?(?:\[[^\[\]\r\n]+\][\t ]*)*/i)[0];
  const prefix = header.match(/^[\t ]*(@voice[12])/i)?.[1] ?? "";
  const tags = [...header.matchAll(/\[([^\[\]]+)\]/g)].map((m) => m[1].trim());
  let voice = 1;
  for (const prior of value.slice(0, start).split("\n")) {
    const match = prior.match(/^\s*@voice([12])(?=\s|\[|$)/i);
    if (match) voice = Number(match[1]);
  }
  if (prefix) voice = Number(prefix.at(-1));
  return { start, header, tags, prefix, voice, number: value.slice(0, start).split("\n").length };
}

export const isConversion = (tag) => tag.toLowerCase().startsWith("c-");

export function editLine(value, caret, action) {
  const line = activeLine(value, caret);
  let tags = [...line.tags];
  const indices = tags.map((tag, i) => isConversion(tag) ? i : -1).filter((i) => i >= 0);
  if (action.type === "style") tags = [...(action.tag ? [action.tag] : []), ...tags.filter(isConversion)];
  if (action.type === "add") tags.push(action.tag);
  if (action.type === "edit") tags[indices[action.index]] = action.tag;
  if (action.type === "remove") tags.splice(indices[action.index], 1);
  if (action.type === "move") {
    const a = indices[action.index], b = indices[action.index + action.offset];
    if (a !== undefined && b !== undefined) [tags[a], tags[b]] = [tags[b], tags[a]];
  }
  const indent = line.header.match(/^[\t ]*/)[0];
  const prefix = action.type === "speaker" ? (action.voice ? `@voice${action.voice}` : "") : line.prefix;
  const replacement = indent + (prefix ? prefix + " " : "") + tags.map((tag) => `[${tag}]`).join("") + (tags.length ? " " : "");
  const end = line.start + line.header.length;
  return {
    start: line.start, end, replacement,
    value: value.slice(0, line.start) + replacement + value.slice(end),
    caret: caret >= end ? caret + replacement.length - line.header.length : line.start + replacement.length,
  };
}

export function parameterValue(item, raw) {
  let value = String(raw).trim();
  if (item.tag === "c-volume") value = value.replace(/db$/i, "").trim();
  if (item.parameter === "number") {
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value) || !Number.isFinite(Number(value))) throw Error("Enter a finite decimal number.");
    if (item.tag === "c-speed" && Number(value) <= 0) throw Error("Speed must be greater than zero.");
  } else if (!value || /[\[\]\r\n]/.test(value)) throw Error("Enter a description without brackets or line breaks.");
  return value;
}

export function conversionSummary(tag, catalog) {
  const colon = tag.indexOf(":");
  const name = (colon < 0 ? tag : tag.slice(0, colon)).trim().toLowerCase();
  const item = catalog.find((entry) => entry.tag === name);
  const raw = colon < 0 ? "" : tag.slice(colon + 1).trim();
  if (!item) return { label: tag, effect: "Unknown change", help: "Choose a supported change from Add conversion." };
  let effect = item.effect ?? (item.group === "Sounds" ? "at beginning" : "");
  let label = item.label;
  if (item.parameter) {
    label += ` ${raw.replace(/db$/i, "").trim()}${item.unit ? ` ${item.unit}` : ""}`;
    if (item.parameter === "number") {
      const number = Number(raw.replace(/db$/i, "").trim());
      effect = name === "c-speed" ? (number === 1 ? "unchanged" : number > 1 ? "faster" : "slower") : name === "c-volume" ? (number === 0 ? "unchanged" : number > 0 ? "louder" : "quieter") : (number === 0 ? "unchanged" : number > 0 ? "higher voice" : "lower voice");
    } else effect = "";
  }
  return { item, raw, label, effect, help: item.help };
}
// Inline edits use one balanced span on one line; no nesting.
export const inlinePattern = /<([A-Za-z][A-Za-z0-9_-]*(?: +[A-Za-z][A-Za-z0-9_-]*)*)(?::([^<>\r\n]*))?>([^<>\r\n]*)<\/\1>/gi;
export function inlineAt(value, caret) {
  return [...value.matchAll(inlinePattern)].find(m => caret >= m.index && caret <= m.index + m[0].length) ?? null;
}
export function editInline(value, start, end, tag) {
  const span = inlineAt(value, start);
  let body;
  if (span && end <= span.index + span[0].length) {
    start = span.index; end = start + span[0].length; body = span[3];
  } else {
    body = value.slice(start, end);
    if (!body.trim() || /[<>\r\n]/.test(body)) throw Error('Select spoken words on one line, without other inline edits.');
    const headerEnd = activeLine(value, start).start + activeLine(value, start).header.length;
    if (start < headerEnd) throw Error('Select spoken words after the speaker and line tags.');
  }
  const replacement = tag ? `<${tag}>${body}</${tag.split(':')[0]}>` : body;
  return {start, end, replacement, value: value.slice(0,start)+replacement+value.slice(end), caret:start+replacement.length};
}

// Edit presets share the style labels, but always emit explicit audio edits.
export function editPresets(catalog) {
  return catalog.styles.map(item => ({
    tag: item.edit_tag, label: item.tag, group: item.group,
    help: item.inline_help,
  }));
}

export function customPreset(catalog, {label, group, operation, value}, style = false) {
  label = String(label ?? '').trim();
  if (!label) throw Error('Enter a name for this saved choice.');
  if (!(group in catalog.categories)) throw Error('Choose a category.');
  let tag;
  if (style) {
    if (!['Emotion', 'Delivery', 'Expressive delivery'].includes(group)) throw Error('Choose a voice style category.');
    tag = String(value ?? '').trim();
    if (!tag || /[<>\[\]\r\n]/.test(tag) || isConversion(tag)) throw Error('Enter a starting tone without brackets or a c- prefix.');
  } else {
    const item = catalog.conversions.find(item => item.tag === operation);
    if (!item) throw Error('Choose a supported effect.');
    tag = item.tag + (item.parameter ? ':' + parameterValue(item, value) + (item.suffix ?? '') : '');
    if (/[<>\r\n]/.test(tag)) throw Error('Enter a value without angle brackets or line breaks.');
  }
  return {label, group, tag, style, help: `Use ${label}: ${tag}.`};
}
