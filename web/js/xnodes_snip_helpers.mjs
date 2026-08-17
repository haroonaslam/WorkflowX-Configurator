function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function graphGroups(graph) {
  if (Array.isArray(graph?.groups)) return graph.groups;
  if (Array.isArray(graph?._groups)) return graph._groups;
  return [];
}

export function selectedXNodeItems(canvas) {
  const graph = canvas?.graph;
  const graphNodes = new Set(graph?._nodes || graph?.nodes || []);
  const graphGroupList = graphGroups(graph);
  const graphGroupSet = new Set(graphGroupList);
  const hasModernSelection = canvas?.selectedItems?.[Symbol.iterator] != null;

  if (hasModernSelection) {
    const selectedItems = Array.from(canvas.selectedItems || []);
    return {
      nodes: selectedItems.filter((item) => graphNodes.has(item)),
      groups: selectedItems.filter((item) => graphGroupSet.has(item)),
    };
  }

  const nodes = [];
  for (const node of Object.values(canvas?.selected_nodes || {})) {
    if (node && graphNodes.has(node) && !nodes.includes(node)) nodes.push(node);
  }
  if (canvas?.selected_node && graphNodes.has(canvas.selected_node) && !nodes.includes(canvas.selected_node)) {
    nodes.push(canvas.selected_node);
  }

  const groups = [];
  if (canvas?.selected_group && graphGroupSet.has(canvas.selected_group)) groups.push(canvas.selected_group);
  return { nodes, groups };
}

export function serializedGroupsForSelection(graphData, selectedGroups) {
  if (!selectedGroups?.length) return [];

  const selectedIds = new Set(selectedGroups.map((group) => String(group?.id)));
  const serialized = [];
  const matchedIds = new Set();
  for (const group of graphData?.groups || []) {
    const id = String(group?.id);
    if (!selectedIds.has(id)) continue;
    serialized.push(clone(group));
    matchedIds.add(id);
  }

  for (const group of selectedGroups) {
    const id = String(group?.id);
    if (matchedIds.has(id) || typeof group?.serialize !== "function") continue;
    serialized.push(clone(group.serialize()));
  }
  return serialized;
}

export function snipOrigin(payload) {
  let minX = Infinity;
  let minY = Infinity;

  for (const node of payload?.nodes || []) {
    const x = Number(node?.pos?.[0]);
    const y = Number(node?.pos?.[1]);
    if (Number.isFinite(x)) minX = Math.min(minX, x);
    if (Number.isFinite(y)) minY = Math.min(minY, y);
  }
  for (const group of payload?.groups || []) {
    const x = Number(group?.bounding?.[0]);
    const y = Number(group?.bounding?.[1]);
    if (Number.isFinite(x)) minX = Math.min(minX, x);
    if (Number.isFinite(y)) minY = Math.min(minY, y);
  }

  return [Number.isFinite(minX) ? minX : 0, Number.isFinite(minY) ? minY : 0];
}

export function addSerializedGroupsToGraph({ graph, LiteGraph, groups, dx = 0, dy = 0 }) {
  if (!groups?.length) return [];

  const Group = LiteGraph?.LGraphGroup;
  if (typeof Group !== "function") {
    throw new Error("ComfyUI's native LGraphGroup class is unavailable");
  }

  const created = [];
  for (const saved of groups) {
    if (!Array.isArray(saved?.bounding) || saved.bounding.length < 4) continue;

    const data = clone(saved);
    data.id = -1;
    data.bounding = [
      Number(saved.bounding[0]) + dx,
      Number(saved.bounding[1]) + dy,
      Number(saved.bounding[2]),
      Number(saved.bounding[3]),
    ];

    const group = new Group();
    group.configure(data);
    graph.add(group);
    created.push(group);
  }

  for (const group of created) group.recomputeInsideNodes?.();
  return created;
}
