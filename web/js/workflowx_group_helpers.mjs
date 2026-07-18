export function nodesForGrouping(canvas, sourceNode) {
  if (!sourceNode) return [];

  const legacySelection = Object.values(canvas?.selected_nodes || {}).filter(Boolean);
  const graphNodes = new Set(canvas?.graph?._nodes || []);
  const modernSelection = Array.from(canvas?.selectedItems || []).filter((item) => graphNodes.has(item));
  const selectedNodes = [...new Set(modernSelection.length ? modernSelection : legacySelection)];
  return selectedNodes.includes(sourceNode) ? selectedNodes : [sourceNode];
}

export function addNodesToNativeGroup({ graph, nodes, LiteGraph, padding = 10 }) {
  if (!graph || !Array.isArray(nodes) || nodes.length === 0) return null;

  const Group = LiteGraph?.LGraphGroup;
  if (typeof Group !== "function") {
    throw new Error("ComfyUI's native LGraphGroup class is unavailable");
  }

  const group = new Group();
  group.resizeTo(nodes, padding);
  graph.add(group);
  graph.change?.();
  group.recomputeInsideNodes?.();
  return group;
}
