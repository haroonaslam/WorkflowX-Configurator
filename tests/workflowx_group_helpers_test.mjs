import assert from "node:assert/strict";

import {
  addNodesToNativeGroup,
  nodesForGrouping,
} from "../web/js/workflowx_group_helpers.mjs";

const first = { id: 1 };
const second = { id: 2 };
const unselected = { id: 3 };
const canvas = {
  graph: { _nodes: [first, second, unselected] },
  selected_nodes: { 1: first },
  selectedItems: new Set([first, second, { id: "group" }]),
};

assert.deepEqual(nodesForGrouping(canvas, first), [first, second]);
assert.deepEqual(nodesForGrouping(canvas, unselected), [unselected]);
assert.deepEqual(nodesForGrouping(canvas, null), []);

class FakeGroup {
  resizeTo(nodes, padding) {
    this.resizeArgs = { nodes, padding };
  }

  recomputeInsideNodes() {
    this.recomputed = true;
  }
}

const graph = {
  add(group) {
    this.added = group;
  },
  change() {
    this.changed = true;
  },
};

const group = addNodesToNativeGroup({
  graph,
  nodes: [first, second],
  LiteGraph: { LGraphGroup: FakeGroup },
  padding: 24,
});

assert.equal(group, graph.added);
assert.deepEqual(group.resizeArgs, { nodes: [first, second], padding: 24 });
assert.equal(group.recomputed, true);
assert.equal(graph.changed, true);

assert.throws(
  () => addNodesToNativeGroup({ graph, nodes: [first], LiteGraph: null }),
  /LGraphGroup/,
);

console.log("workflowx_group_helpers tests passed");
