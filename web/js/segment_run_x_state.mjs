import { buildGraphInventory } from "./key_config_graph.mjs";

export const RUN_TARGET = "WorkflowXRunTargetX";
export const SEGMENT_RUN = "Segment RunX";
export const TARGET_PROPERTY = "workflowx_run_output";
const RECOVERY_KEY = "workflowx.segment-run.recovery.v1";

export function outputTargets(root) {
  return buildGraphInventory(root).instances.filter(({ node }) =>
    node.constructor.nodeData?.output_node === true || node.constructor.output_node === true);
}

export function outputLabel(record) {
  const { node } = record;
  const name = [...record.ancestors.map(({ node: ancestor }) => ancestor.title || ancestor.type),
    node.title || node.type].join(" / ");
  return name;
}

export function selectedOutput(root, marker) {
  const selection = marker.properties?.[TARGET_PROPERTY];
  return outputTargets(root).find(({ executionId, node }) =>
    executionId === selection?.executionId && node.type === selection?.type);
}

export function segmentPrompt(output, targetId) {
  const result = {};
  const visiting = new Set();
  const visit = (id) => {
    if (visiting.has(id)) throw new Error("The selected output path contains a cycle.");
    if (Object.hasOwn(result, id)) return;
    const entry = output[id];
    if (!entry) throw new Error(`The output path contains a missing or unavailable node (#${id}).`);
    visiting.add(id);
    for (const input of Object.values(entry.inputs ?? {})) {
      if (Array.isArray(input) && input.length === 2 && Number.isInteger(input[1])) visit(String(input[0]));
    }
    result[id] = structuredClone(entry);
    visiting.delete(id);
  };
  visit(String(targetId));
  return result;
}

export function createSegmentRunner({ app, api, storage = globalThis.sessionStorage,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)) }) {
  let active = null;
  const statuses = new WeakMap();
  const rootGraph = () => app.rootGraph ?? app.graph;
  const status = (marker) => statuses.get(marker) ?? "Ready";

  function recover() {
    // One-time migration for snapshots left by the former visual-activation implementation.
    if (active) return;
    let saved;
    try { saved = JSON.parse(storage?.getItem(RECOVERY_KEY) ?? "null"); } catch { return; }
    const root = rootGraph();
    if (!root || !saved || saved.rootId !== (root.id ?? root.uuid)) return;
    const records = buildGraphInventory(root).instances;
    for (const entry of saved.snapshot ?? []) {
      const record = records.find((record) => (record.graph.uuid ?? record.graph.id) === entry.graphId
        && record.localId === entry.nodeId);
      if (record?.node.type === entry.type && Number.isInteger(entry.mode)) record.node.mode = entry.mode;
    }
    root.setDirtyCanvas?.(true, true);
    storage?.removeItem(RECOVERY_KEY);
  }

  function abandon() {
    const job = active;
    if (!job) return;
    job.abandoned = true;
    statuses.set(job.marker, "Monitoring stopped");
    active = null;
  }

  function complete(job, state) {
    if (active !== job || job.abandoned) return;
    job.terminal = state;
  }

  const listeners = [];
  for (const [event, state] of [
    ["execution_success", "Completed"],
    ["execution_error", "Failed"],
    ["execution_interrupted", "Interrupted"],
  ]) {
    const listener = ({ detail }) => {
      if (detail?.prompt_id === active?.promptId) complete(active, state);
    };
    api.addEventListener(event, listener);
    listeners.push([event, listener]);
  }

  async function monitor(job) {
    let missing = 0;
    while (!job.terminal && !job.abandoned) {
      if (rootGraph() !== job.root) {
        abandon();
        return "Monitoring stopped";
      }
      try {
        const response = await api.fetchApi(`/history/${encodeURIComponent(job.promptId)}`);
        if (!response.ok) throw new Error("History unavailable");
        const history = (await response.json())[job.promptId];
        if (history) {
          const failure = history.status?.messages?.find(([name]) =>
            name === "execution_error" || name === "execution_interrupted");
          if (failure) return failure[0] === "execution_interrupted" ? "Interrupted" : "Failed";
          if (history.status?.completed) return "Completed";
        }
        const queueResponse = await api.fetchApi("/queue");
        if (!queueResponse.ok) throw new Error("Queue unavailable");
        const queue = await queueResponse.json();
        const running = (queue.queue_running ?? []).some((item) => item[1] === job.promptId);
        const pending = (queue.queue_pending ?? []).some((item) => item[1] === job.promptId);
        missing = running || pending ? 0 : missing + 1;
        if (missing >= 2) return "Removed from queue";
        statuses.set(job.marker, running ? "Running" : "Queued");
      } catch {
        statuses.set(job.marker, "Connection lost. Waiting for job status…");
      }
      await sleep(1000);
    }
    return job.terminal ?? "Monitoring stopped";
  }

  async function run(marker) {
    if (active) throw new Error("Another Segment RunX job is already active in this workflow.");
    const root = rootGraph();
    const target = selectedOutput(root, marker);
    if (!target) throw new Error("Choose an existing output node in Run TargetX.");
    if (!app.workflowxCompileSegment) throw new Error("WorkflowX prompt routing is not ready. Refresh ComfyUI.");
    const job = { root, marker, abandoned: false };
    active = job;
    statuses.set(marker, "Preparing");
    try {
      const { result } = await app.workflowxCompileSegment(root, target.executionId);
      if (job.abandoned || rootGraph() !== root) return;
      const output = segmentPrompt(result.output, target.executionId);
      const queued = await api.queuePrompt(0, { workflow: result.workflow, output },
        { partialExecutionTargets: [target.executionId] });
      if (!queued?.prompt_id) throw new Error("ComfyUI did not return a prompt ID.");
      job.promptId = queued.prompt_id;
      if (job.abandoned) return;
      statuses.set(marker, "Queued");
      statuses.set(marker, await monitor(job));
    } catch (error) {
      statuses.set(marker, error.message || "Failed");
      throw error;
    } finally {
      if (active === job) active = null;
    }
  }

  return { run, status, recover, abandon, get busy() { return active !== null; },
    dispose() { abandon(); for (const [event, listener] of listeners) api.removeEventListener(event, listener); } };
}
