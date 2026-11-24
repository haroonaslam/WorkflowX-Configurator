export const STOP = "StopX";
export const SOURCE = "Image SourceX";
export const TARGET = "Image TargetX";
export const CONTROL = "WorkflowX_RunControls";
export const LOADERS = new Set(["LoadImage", "WorkflowX_LoadImageX", "WorkflowX_LoadImageXAdv"]);
export const SOURCES = new Set([...LOADERS, "SaveImage", "PreviewImage"]);
export const SELECT = "workflowx_selection";

export function upstream(prompt, id, result = new Set()) {
  if (result.has(id) || !prompt[id]) return result;
  result.add(id);
  for (const value of Object.values(prompt[id].inputs ?? {})) {
    if (Array.isArray(value) && value.length === 2 && Number.isInteger(value[1])) upstream(prompt, String(value[0]), result);
  }
  return result;
}

export function assertAcyclic(prompt, edges) {
  const dependencies = new Map(Object.keys(prompt).map((id) => [id, []]));
  for (const [id, node] of Object.entries(prompt)) {
    for (const value of Object.values(node.inputs ?? {})) {
      if (Array.isArray(value) && value.length === 2 && Number.isInteger(value[1])) dependencies.get(id).push(String(value[0]));
    }
  }
  for (const [source, target] of edges) dependencies.get(target)?.push(source);
  const visiting = new Set(), visited = new Set();
  function visit(id) {
    if (visiting.has(id)) throw new Error("Image TargetX / StopX ordering contains a cycle. Choose an earlier source or use Prepare next run.");
    if (visited.has(id)) return;
    visiting.add(id);
    for (const parent of dependencies.get(id) ?? []) visit(parent);
    visiting.delete(id); visited.add(id);
  }
  for (const id of dependencies.keys()) visit(id);
}

// Entries contain instance-qualified identities, so reused subgraphs stay distinct.
export function buildControls(prompt, records, { selective = false, workflow, nonce, outputIds = [] } = {}) {
  const find = (selection) => records.find((record) => record.executionId === selection?.executionId && record.node.type === selection?.type);
  const active = (record) => record && ![2, 4].includes(record.node.mode)
    && !(record.ancestors ?? []).some(({ node }) => [2, 4].includes(node.mode));
  const reachable = new Set(outputIds.flatMap((id) => [...upstream(prompt, id)]));
  const stops = selective ? [] : records.filter((r) => r.node.type === STOP && active(r))
    .map((r) => find(r.node.properties?.[SELECT])).filter((r) => active(r) && reachable.has(r.executionId)).map((r) => r.executionId);
  const transfers = [], targets = new Set();
  for (const marker of records.filter((r) => r.node.type === TARGET && active(r))) {
    const sourceMarker = find(marker.node.properties?.workflowx_source);
    const source = active(sourceMarker) && find(sourceMarker.node.properties?.[SELECT]);
    const target = find(marker.node.properties?.[SELECT]);
    if (!source || !target) continue;
    if (!SOURCES.has(source.node.type) || !LOADERS.has(target.node.type)) continue;
    // Muted/bypassed destinations are intentionally eligible. Only the source
    // must be executable; no canvas mode is ever changed here.
    if ((!selective && !active(source)) || !prompt[source.executionId]) continue;
    if (selective && !reachable.has(source.executionId) && !reachable.has(target.executionId)) continue;
    if (targets.has(target.executionId)) throw new Error("Only one Image TargetX may write to a loader in a queued run.");
    targets.add(target.executionId);
    const sameRun = marker.node.properties?.workflowx_transfer_mode === "same_run" && (selective || active(target)) && !!prompt[target.executionId];
    const transfer = { id: marker.executionId, source: source.executionId, source_type: source.node.type,
      target: target.executionId, target_type: target.node.type, same_run: sameRun };
    transfers.push(transfer);
  }
  const edges = transfers.flatMap((t) => [
    ...(t.same_run ? [[t.source, t.target]] : []),
    ...stops.filter((id) => id !== t.source).map((id) => [t.source, id]),
  ]);
  assertAcyclic(prompt, edges);
  for (const t of transfers.filter((t) => t.same_run)) {
    const original = prompt[t.target];
    prompt[t.target] = { class_type: t.target_type === "WorkflowX_LoadImageXAdv" ? "WorkflowX_ImageTransferLoaderAdv" : "WorkflowX_ImageTransferLoader",
      inputs: { transfer: t.id, settings: JSON.stringify(original), nonce }, _meta: original._meta };
  }
  if (!stops.length && !transfers.length) return null;
  let id = "workflowx_controls";
  while (prompt[id]) id += "_";
  prompt[id] = { class_type: CONTROL, inputs: { config: JSON.stringify({ workflow, nonce, stops: [...new Set(stops)], transfers }) } };
  return id;
}
