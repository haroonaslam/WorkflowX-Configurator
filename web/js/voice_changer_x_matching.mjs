export const VOICE_NODE = "WorkflowX_VoiceChangerX";
export const CONTROL_NAMES = ["pitch_shift", "formant_shift", "timbre", "breathiness", "pitch_variation", "output_gain"];

export function audioOnlyInputs(node) {
  for (let index = (node.inputs?.length || 0) - 1; index >= 0; index--) {
    if (CONTROL_NAMES.includes(node.inputs[index].name)) node.removeInput?.(index);
  }
  const source = node.inputs?.find(input => ["audio", "source_audio"].includes(input.name));
  if (source) { source.name = "source_audio"; source.label = "source audio"; }
  let reference = node.inputs?.find(input => input.name === "reference_audio");
  if (!reference && node.addInput) reference = node.addInput("reference_audio", "AUDIO");
  if (reference) reference.label = "reference audio";
}

/** Preserve the old source connection while dropping obsolete parameter links. */
export function migrateVoiceWorkflow(graph) {
  if (!graph) return;
  const removed = new Set();
  const indexMaps = new Map();
  for (const node of graph.nodes || []) {
    if (node.type !== VOICE_NODE) continue;
    const map = new Map();
    const inputs = [];
    for (const [oldIndex, input] of (node.inputs || []).entries()) {
      if (CONTROL_NAMES.includes(input.name)) {
        if (input.link != null) removed.add(String(input.link));
        continue;
      }
      if (input.name === "audio") input.name = "source_audio";
      if (["source_audio", "reference_audio"].includes(input.name)) {
        input.label = input.name.replace("_", " ");
        map.set(oldIndex, inputs.length);
        inputs.push(input);
      }
    }
    node.inputs = inputs;
    indexMaps.set(String(node.id), map);
  }
  graph.links = (graph.links || []).filter(link => {
    const id = Array.isArray(link) ? link[0] : link.id;
    if (removed.has(String(id))) return false;
    const target = String(Array.isArray(link) ? link[3] : link.target_id);
    const slot = Array.isArray(link) ? link[4] : link.target_slot;
    if (indexMaps.has(target) && indexMaps.get(target).has(slot)) {
      if (Array.isArray(link)) link[4] = indexMaps.get(target).get(slot);
      else link.target_slot = indexMaps.get(target).get(slot);
    }
    return true;
  });
  for (const node of graph.nodes || []) {
    for (const output of node.outputs || []) {
      if (output.links) output.links = output.links.filter(id => !removed.has(String(id)));
    }
    if (node.subgraph) migrateVoiceWorkflow(node.subgraph);
  }
  for (const child of graph.definitions?.subgraphs || []) migrateVoiceWorkflow(child);
}

export function resolveVoiceTarget(rootGraph, node, output) {
  const candidates = [];
  const visit = (graph, path = [], ancestors = new Set()) => {
    if (!graph || ancestors.has(graph)) return;
    const seen = new Set([...ancestors, graph]);
    for (const item of graph._nodes || graph.nodes || []) {
      const id = [...path, String(item.id)].join(":");
      if (item === node && output[id]?.class_type === VOICE_NODE) candidates.push(id);
      if (item.subgraph) visit(item.subgraph, [...path, String(item.id)], seen);
    }
  };
  visit(rootGraph);
  if (candidates.length !== 1) throw new Error("Cannot uniquely resolve this Voice ChangerX. Use an active node outside a shared subgraph.");
  return candidates[0];
}

export function buildMatchPrompt(output, targetId, requestId = "") {
  const target = output[targetId];
  if (target?.class_type !== VOICE_NODE) throw new Error("Voice ChangerX is missing or bypassed.");
  const isLink = value => Array.isArray(value) && value.length === 2 && Number.isInteger(value[1]) && output[String(value[0])];
  for (const name of ["source_audio", "reference_audio"]) {
    if (!isLink(target.inputs?.[name])) throw new Error(`Connect ${name.replace("_", " ")} before matching.`);
  }
  const result = {}, visiting = new Set();
  const visit = id => {
    if (visiting.has(id)) throw new Error("The audio connections contain a cycle.");
    if (result[id]) return;
    visiting.add(id);
    const entry = output[id];
    if (!entry) throw new Error("An upstream audio node is missing.");
    for (const value of Object.values(entry.inputs || {})) if (isLink(value)) visit(String(value[0]));
    result[id] = structuredClone(entry);
    visiting.delete(id);
  };
  visit(String(targetId));
  if (requestId) result[targetId].inputs.match_request = requestId;
  return result;
}

export function matchFingerprint(prompt, targetId) {
  return JSON.stringify(Object.entries(prompt).sort(([a], [b]) => a.localeCompare(b)).map(([id, node]) => {
    const inputs = Object.entries(node.inputs || {}).filter(([key]) => key !== "match_request" && !(id === targetId && CONTROL_NAMES.includes(key)));
    return [id, node.class_type, inputs.sort(([a], [b]) => a.localeCompare(b))];
  }));
}

export async function waitForReference(api, promptId, requestId, isCancelled, sleep = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  let missing = 0;
  for (let poll = 0; poll < 1800; poll++) {
    if (isCancelled()) throw new Error("Reference matching was abandoned because the node was removed.");
    const response = await api.fetchApi(`/history/${encodeURIComponent(promptId)}`);
    if (!response.ok) throw new Error("Could not read reference analysis status. Check the ComfyUI connection.");
    const history = (await response.json())[promptId];
    if (history) {
      for (const output of Object.values(history.outputs || {})) {
        const report = output.voice_reference_match?.find(item => item.request_id === requestId);
        if (report) {
          if (report.error) throw new Error(report.error);
          return report;
        }
      }
      const error = history.status?.messages?.find(([name]) => ["execution_error", "execution_interrupted"].includes(name));
      if (error) throw new Error(error[1]?.exception_message || "Reference analysis was interrupted.");
      if (history.status?.completed) throw new Error("Reference analysis finished without a result. Restart ComfyUI and refresh the browser.");
    }
    // Detect jobs cleared from the queue instead of leaving the button busy forever.
    if (poll > 0 && poll % 5 === 0) {
      const queueResponse = await api.fetchApi("/queue");
      if (queueResponse.ok) {
        const queue = await queueResponse.json();
        const exists = [...(queue.queue_running || []), ...(queue.queue_pending || [])].some(item => item[1] === promptId);
        missing = exists ? 0 : missing + 1;
        if (missing >= 2) throw new Error("Reference analysis was removed from the queue or the server restarted.");
      }
    }
    await sleep(1000);
  }
  throw new Error("Reference analysis timed out. Check the queue; existing slider values were retained.");
}

export async function runReferenceMatch(app, api, node, isCancelled) {
  const graph = node.graph;
  const data = await app.graphToPrompt();
  const root = app.rootGraph || app.graph;
  const targetId = resolveVoiceTarget(root, node, data.output);
  const requestId = crypto.randomUUID();
  const output = buildMatchPrompt(data.output, targetId, requestId);
  const fingerprint = matchFingerprint(output, targetId);
  const queued = await api.queuePrompt(0, { workflow: data.workflow, output }, { partialExecutionTargets: [targetId] });
  const report = await waitForReference(api, queued.prompt_id, requestId, isCancelled);
  if (isCancelled() || node.graph !== graph || (app.rootGraph || app.graph) !== root) throw new Error("Workflow changed during matching; estimates were not applied.");
  const current = await app.graphToPrompt();
  if (fingerprint !== matchFingerprint(buildMatchPrompt(current.output, targetId), targetId)) throw new Error("Source or reference inputs changed during matching. Click Match Reference again.");
  return report;
}
