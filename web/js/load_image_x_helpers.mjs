export function splitRelativePath(value) {
  const normalized = String(value || "").replace(/\\/g, "/");
  const index = normalized.lastIndexOf("/");
  if (index < 0) return { folder: "", name: normalized };
  return { folder: normalized.slice(0, index), name: normalized.slice(index + 1) };
}

export function groupCatalog(items) {
  const groups = new Map();
  for (const item of items || []) {
    const folder = String(item?.folder || "");
    if (!groups.has(folder)) groups.set(folder, []);
    groups.get(folder).push(item);
  }
  for (const entries of groups.values()) {
    entries.sort((a, b) => String(a.path).localeCompare(String(b.path), undefined, { sensitivity: "base" }));
  }
  return [...groups.entries()]
    .sort(([a], [b]) => {
      if (a === "") return b === "" ? 0 : -1;
      if (b === "") return 1;
      return a.localeCompare(b, undefined, { sensitivity: "base" });
    })
    .map(([folder, entries]) => ({ folder, items: entries }));
}

export function filterCatalog(items, query, folder = null) {
  const needle = String(query || "").trim().toLocaleLowerCase();
  return (items || []).filter((item) => {
    if (!needle && folder !== null && String(item.folder || "") !== folder) return false;
    if (!needle) return true;
    return `${item.path || ""}\n${item.name || ""}\n${item.folder || ""}`
      .toLocaleLowerCase()
      .includes(needle);
  });
}

export function thumbnailURL(item) {
  return `/workflowx_configurator/load_image_x/thumbnail?path=${encodeURIComponent(item.path)}&v=${encodeURIComponent(item.version)}`;
}

export function viewURL(item) {
  const { folder, name } = splitRelativePath(item.path);
  return `/view?filename=${encodeURIComponent(name)}&type=input&subfolder=${encodeURIComponent(folder)}&v=${encodeURIComponent(item.version || "")}`;
}

export function isSquareDimensions(width, height, tolerance = 1) {
  const numericWidth = Number(width);
  const numericHeight = Number(height);
  return numericWidth > 0
    && numericHeight > 0
    && Math.abs(numericWidth - numericHeight) <= Math.max(0, Number(tolerance) || 0);
}

export function higherNodeClipRects(node, nodes, titleHeight = 30) {
  const orderedNodes = Array.isArray(nodes) ? nodes : [];
  const nodeIndex = orderedNodes.indexOf(node);
  const originX = Number(node?.pos?.[0]) || 0;
  const originY = Number(node?.pos?.[1]) || 0;
  if (nodeIndex < 0) return [];

  return orderedNodes.slice(nodeIndex + 1).flatMap((other) => {
    if (!other || !other.pos || !other.size) return [];
    const bounds = other.boundingRect;
    const hasBounds = bounds && bounds.length >= 4;
    const x = hasBounds ? Number(bounds[0]) : Number(other.pos[0]);
    const y = hasBounds ? Number(bounds[1]) : Number(other.pos[1]) - titleHeight;
    const width = hasBounds ? Number(bounds[2]) : Number(other.size[0]);
    const height = hasBounds ? Number(bounds[3]) : Number(other.size[1]) + titleHeight;
    if (![x, y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) return [];

    // One extra pixel prevents antialiased image edges from leaking over a node border.
    return [{
      x: x - originX - 1,
      y: y - originY - 1,
      width: width + 2,
      height: height + 2,
    }];
  });
}
