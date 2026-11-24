import assert from "node:assert/strict";
import test from "node:test";
import {
  RUN_TARGET, TARGET_PROPERTY, createSegmentRunner, outputTargets, segmentPrompt,
} from "../web/js/segment_run_x_state.mjs";
import { segmentExecutionGraph } from "../web/js/segment_run_x_graph.mjs";

function fixture() {
  class Output {}
  Output.nodeData = { output_node: true };
  const source = { id: 1, type: "Source", mode: 2 };
  const target = { id: 2, type: "Output", mode: 4, constructor: Output };
  const unrelated = { id: 3, type: "Source", mode: 4 };
  const marker = { id: 4, type: RUN_TARGET, properties: {
    [TARGET_PROPERTY]: { executionId: "2", type: "Output" },
  } };
  const root = {
    id: "fixture-root", nodes: [source, target, unrelated, marker],
    serialize() { return { nodes: this.nodes.map((node) => ({ id: node.id, type: node.type, mode: node.mode })) }; },
  };
  for (const node of root.nodes) node.graph = root;
  const output = {
    1: { class_type: "Source", inputs: {} },
    2: { class_type: "Output", inputs: { value: ["1", 0] } },
    3: { class_type: "Source", inputs: {} },
  };
  const app = { rootGraph: root, workflowxCompileSegment: async () => ({ result: { output, workflow: root.serialize() } }) };
  const events = new EventTarget();
  const api = {
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
    queuePrompt: async () => ({ prompt_id: "fixture-job" }),
    fetchApi: async () => ({ ok: true, json: async () => ({
      "fixture-job": { status: { completed: true } },
    }) }),
  };
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key),
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const runner = createSegmentRunner({ app, api, storage, sleep: async () => {} });
  return { root, source, target, unrelated, marker, output, app, api, storage, values, runner };
}

test("selected prompt includes required dependencies and detects a missing node or cycle", () => {
  const { output } = fixture();
  assert.deepEqual(Object.keys(segmentPrompt(output, "2")), ["1", "2"]);
  assert.throws(() => segmentPrompt(output, "missing"), /missing/);
  output[1].inputs.value = ["2", 0];
  assert.throws(() => segmentPrompt(output, "2"), /cycle/);
});

test("execution graph exposes active nodes while concurrent canvas reads and serialization retain real modes", () => {
  const f = fixture();
  f.root.computeExecutionOrder = () => f.root.nodes;
  f.root.getNodeById = (id) => f.root.nodes.find((node) => node.id === id);
  const view = segmentExecutionGraph(f.root);
  const source = view.getNodeById(1);
  assert.equal(source.mode, 0);
  assert.equal(view.computeExecutionOrder()[0], source);
  assert.equal(source.graph, view);
  source.mode = 4;
  assert.equal(f.root.nodes[0].mode, 2);
  assert.equal(f.root.serialize().nodes[0].mode, 2);
  assert.equal(view.serialize().nodes[0].mode, 2);
  f.root.nodes[0].mode = 4;
  assert.equal(source.mode, 0);
  assert.equal(f.root.nodes[0].mode, 4);
});

test("segment queues an executable branch without changing canvas modes or later manual edits", async () => {
  const f = fixture();
  f.api.queuePrompt = async (_position, prompt, options) => {
    assert.equal(f.source.mode, 2);
    assert.equal(f.target.mode, 4);
    assert.equal(f.unrelated.mode, 4);
    assert.deepEqual(Object.keys(prompt.output), ["1", "2"]);
    assert.deepEqual(options.partialExecutionTargets, ["2"]);
    assert.equal(prompt.workflow.nodes[0].mode, 2);
    assert.equal(prompt.workflow.nodes[1].mode, 4);
    f.source.mode = 4;
    return { prompt_id: "fixture-job" };
  };
  await f.runner.run(f.marker);
  assert.equal(f.source.mode, 4);
  assert.equal(f.target.mode, 4);
  assert.equal(f.runner.status(f.marker), "Completed");
  assert.equal(f.values.size, 0);
});

for (const name of ["execution_error", "execution_interrupted"]) {
  test(`${name} reports the job result while retaining canvas modes`, async () => {
    const f = fixture();
    f.api.fetchApi = async () => ({ ok: true, json: async () => ({
      "fixture-job": { status: { messages: [[name, {}]], completed: false } },
    }) });
    await f.runner.run(f.marker);
    assert.equal(f.source.mode, 2);
    assert.equal(f.target.mode, 4);
    assert.equal(f.runner.status(f.marker), name === "execution_error" ? "Failed" : "Interrupted");
  });
}

test("submission failure, queue removal and temporary connection loss retain canvas modes", async () => {
  const f = fixture();
  f.api.queuePrompt = async () => { throw new Error("Rejected"); };
  await assert.rejects(f.runner.run(f.marker), /Rejected/);
  assert.equal(f.source.mode, 2);
  f.api.queuePrompt = async () => ({ prompt_id: "fixture-job" });
  let polls = 0;
  f.api.fetchApi = async () => {
    if (polls++ === 0) throw new Error("Offline");
    return { ok: true, json: async () => ({ queue_running: [], queue_pending: [] }) };
  };
  await f.runner.run(f.marker);
  assert.equal(f.runner.status(f.marker), "Removed from queue");
  assert.equal(f.source.mode, 2);
});

test("workflow switch stops monitoring and leaves both workflows' modes intact", async () => {
  const f = fixture();
  let release;
  f.api.queuePrompt = () => new Promise((resolve) => { release = resolve; });
  const running = f.runner.run(f.marker);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(f.source.mode, 2);
  await assert.rejects(f.runner.run(f.marker), /already active/);
  f.runner.abandon();
  f.app.rootGraph = { id: "another", nodes: [{ id: 1, type: "Source", mode: 4 }] };
  release({ prompt_id: "fixture-job" });
  await running;
  assert.equal(f.source.mode, 2);
  assert.equal(f.app.rootGraph.nodes[0].mode, 4);
});

test("legacy recovery uses workflow identity and restores a previous version's saved modes once", () => {
  const f = fixture();
  f.values.set("workflowx.segment-run.recovery.v1", JSON.stringify({ rootId: f.root.id,
    snapshot: [
      { graphId: f.root.id, nodeId: "1", type: f.source.type, mode: 2 },
      { graphId: f.root.id, nodeId: "2", type: f.target.type, mode: 4 },
    ],
  }));
  f.source.mode = 0;
  f.target.mode = 0;
  f.runner.recover();
  assert.equal(f.source.mode, 2);
  assert.equal(f.target.mode, 4);
  assert.equal(f.values.size, 0);
});

test("nested outputs expose instance execution IDs", () => {
  const f = fixture();
  const nested = { id: "definition", nodes: [f.target] };
  const root = { id: "root", nodes: [{ id: 7, subgraph: nested }, { id: 8, subgraph: nested }] };
  assert.deepEqual(outputTargets(root).map(({ executionId }) => executionId), ["7:2", "8:2"]);
});

test("virtual nodes on a resolved dependency path retain their canvas modes", async () => {
  const f = fixture();
  const reroute = { id: 5, type: "Reroute", isVirtualNode: true, graph: f.root, mode: 4,
    getInputLink: () => ({ origin_id: 1, origin_slot: 0 }) };
  f.root.nodes.push(reroute);
  f.root.getNodeById = (id) => f.root.nodes.find((node) => String(node.id) === String(id));
  f.target.inputs = [{ name: "value" }];
  f.target.getInputLink = () => ({ origin_id: 5, origin_slot: 0 });
  f.api.queuePrompt = async () => {
    assert.equal(reroute.mode, 4);
    return { prompt_id: "fixture-job" };
  };
  await f.runner.run(f.marker);
  assert.equal(reroute.mode, 4);
});

test("restoration leaves a replacement node with a reused ID alone", async () => {
  const f = fixture();
  const replacement = { ...f.source, mode: 4, graph: f.root };
  f.api.queuePrompt = async () => {
    f.source.graph = null;
    f.root.nodes[0] = replacement;
    return { prompt_id: "fixture-job" };
  };
  await f.runner.run(f.marker);
  assert.equal(replacement.mode, 4);
});
