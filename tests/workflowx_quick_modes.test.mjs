import assert from "node:assert/strict";
import test from "node:test";

import {
  QUICK_MODES,
  addQuickTarget,
  quickTargetRows,
  removeQuickTarget,
  setQuickTargetMode,
} from "../web/js/workflowx_quick_modes.mjs";

const [mute, bypass] = QUICK_MODES;

function makeNode(type, id, fields = {}) {
  return { type, id, title: type, pos: [10, 30], size: [150, 120], mode: 0, properties: {}, ...fields };
}

function makeGraph(id, ...nodes) {
  const graph = {
    id,
    nodes: [],
    transactions: [],
    add(node) {
      this.nodes.push(node);
      node.graph = this;
    },
    beforeChange() { this.transactions.push("before"); },
    afterChange() { this.transactions.push("after"); },
  };
  for (const node of nodes) graph.add(node);
  return graph;
}

const createNode = (type) => makeNode(type, 10);

test("add creates or reuses a controller without changing the target mode", () => {
  const first = makeNode("First", 1, { mode: 4 });
  const second = makeNode("Second", 2);
  const graph = makeGraph("root", first, second);
  const { controller, added } = addQuickTarget(graph, first, mute, createNode);
  assert.equal(added, true);
  assert.equal(first.mode, 4);
  assert.deepEqual(controller.pos, [192, 30]);
  assert.deepEqual(addQuickTarget(graph, first, mute, createNode), { controller, added: false });
  assert.equal(addQuickTarget(graph, second, mute, createNode).controller, controller);
  assert.equal(quickTargetRows(graph, controller).length, 2);
  assert.deepEqual(graph.transactions, ["before", "after", "before", "after"]);
});

test("graph and node IDs resolve distinct targets across save, reopen and shared definitions", () => {
  const local = makeNode("Target", 1);
  const wing = makeGraph("wing", makeNode("Target", 1));
  const other = makeGraph("other", makeNode("Target", 1));
  wing.name = "Wing";
  other.name = "Other";
  const wrapper = makeNode("Subgraph", 2, { subgraph: wing, pos: [300, 400] });
  const graph = makeGraph(
    "root", local, wrapper,
    makeNode("Subgraph", 3, { subgraph: wing }),
    makeNode("Subgraph", 4, { subgraph: other }),
  );
  const { controller } = addQuickTarget(graph, wing.nodes[0], bypass, createNode);
  assert.deepEqual(controller.pos, [482, 400]);
  addQuickTarget(graph, local, bypass, createNode);
  addQuickTarget(graph, other.nodes[0], bypass, createNode);

  const restoredWingNode = makeNode("Target", 1, { title: "Renamed" });
  const restoredWing = makeGraph("wing", restoredWingNode);
  restoredWing.name = "Renamed Wing";
  const restoredOtherNode = makeNode("Target", 1);
  const restoredLocalNode = makeNode("Target", 1);
  const restoredController = makeNode(bypass.type, 10, {
    properties: JSON.parse(JSON.stringify(controller.properties)),
  });
  const restoredGraph = makeGraph(
    "root", restoredLocalNode, restoredController,
    makeNode("Subgraph", 2, { subgraph: restoredWing }),
    makeNode("Subgraph", 3, { subgraph: restoredWing }),
    makeNode("Subgraph", 4, { subgraph: makeGraph("other", restoredOtherNode) }),
  );
  const rows = quickTargetRows(restoredGraph, restoredController);
  assert.deepEqual(rows.map(({ node }) => node), [restoredWingNode, restoredLocalNode, restoredOtherNode]);
  assert.equal(rows[0].title, "Renamed");
  assert.equal(rows[0].path, "Renamed Wing");
  setQuickTargetMode(restoredGraph, restoredController, rows[0].ref, bypass.mode, false);
  assert.equal(restoredWingNode.mode, 4);
  assert.equal(restoredLocalNode.mode, 0);
  assert.equal(restoredOtherNode.mode, 0);
  setQuickTargetMode(restoredGraph, restoredController, rows[0].ref, bypass.mode, true);
  assert.equal(restoredWingNode.mode, 0);
});

test("mode changes and removing a row respect native modes and missing targets", () => {
  const target = makeNode("Target", 1, { mode: 4 });
  const graph = makeGraph("root", target);
  const { controller } = addQuickTarget(graph, target, mute, createNode);
  const [{ ref }] = quickTargetRows(graph, controller);
  setQuickTargetMode(graph, controller, ref, mute.mode, true);
  assert.equal(target.mode, 0);
  setQuickTargetMode(graph, controller, ref, mute.mode, false);
  assert.equal(target.mode, 2);
  setQuickTargetMode(graph, controller, ref, mute.mode, true);
  assert.equal(target.mode, 0);
  setQuickTargetMode(graph, controller, ref, mute.mode, false);
  removeQuickTarget(graph, controller, ref);
  assert.equal(target.mode, 2);

  addQuickTarget(graph, target, mute, createNode);
  graph.nodes[0] = makeNode("Replacement", 1);
  const [missing] = quickTargetRows(graph, controller);
  assert.equal(missing.node, undefined);
  assert.equal(missing.title, "Target");
  setQuickTargetMode(graph, controller, missing.ref, mute.mode, true);
  assert.equal(graph.nodes[0].mode, 0);
  removeQuickTarget(graph, controller, missing.ref);
  assert.deepEqual(quickTargetRows(graph, controller), []);
});
