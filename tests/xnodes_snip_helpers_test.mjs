import assert from "node:assert/strict";

import {
  addSerializedGroupsToGraph,
  selectedXNodeItems,
  serializedGroupsForSelection,
  snipOrigin,
} from "../web/js/xnodes_snip_helpers.mjs";

const first = { id: 1 };
const second = { id: 2 };
const outside = { id: 3 };
const outer = { id: 10 };
const inner = { id: 11 };
const unselectedGroup = { id: 12 };
const canvas = {
  graph: {
    _nodes: [first, second, outside],
    groups: [outer, inner, unselectedGroup],
  },
  selectedItems: new Set([first, second, outer, inner]),
};

assert.deepEqual(selectedXNodeItems(canvas), {
  nodes: [first, second],
  groups: [outer, inner],
});

const graphData = {
  groups: [
    { id: 10, title: "Outer", bounding: [-20, -10, 500, 400], color: "#123", flags: { pinned: true } },
    { id: 11, title: "Inner", bounding: [40, 50, 200, 120], color: "#456", flags: {} },
    { id: 12, title: "Other", bounding: [900, 900, 100, 100], color: "#789", flags: {} },
  ],
};
const savedGroups = serializedGroupsForSelection(graphData, [outer, inner]);
assert.deepEqual(savedGroups, graphData.groups.slice(0, 2));
savedGroups[0].title = "Changed clone";
assert.equal(graphData.groups[0].title, "Outer");
savedGroups[0].title = "Outer";

assert.deepEqual(snipOrigin({
  nodes: [{ pos: [0, 20] }, { pos: [100, 80] }],
  groups: savedGroups,
}), [-20, -10]);
assert.deepEqual(snipOrigin({ nodes: [{ pos: [25, 35] }] }), [25, 35]);

class FakeGroup {
  configure(data) {
    Object.assign(this, data);
  }

  recomputeInsideNodes() {
    this.recomputed = true;
  }
}

const inserted = [];
const graph = {
  add(group) {
    group.id = 1000 + inserted.length;
    inserted.push(group);
  },
};
const created = addSerializedGroupsToGraph({
  graph,
  LiteGraph: { LGraphGroup: FakeGroup },
  groups: savedGroups,
  dx: 520,
  dy: 310,
});

assert.equal(created.length, 2);
assert.deepEqual(created.map((group) => group.id), [1000, 1001]);
assert.deepEqual(created[0].bounding, [500, 300, 500, 400]);
assert.deepEqual(created[1].bounding, [560, 360, 200, 120]);
assert.equal(created[0].title, "Outer");
assert.equal(created[0].color, "#123");
assert.deepEqual(created[0].flags, { pinned: true });
assert.equal(created[0].recomputed, true);
assert.equal(created[1].recomputed, true);

assert.deepEqual(addSerializedGroupsToGraph({ graph, LiteGraph: null, groups: [] }), []);
assert.throws(
  () => addSerializedGroupsToGraph({ graph, LiteGraph: null, groups: savedGroups }),
  /LGraphGroup/,
);

console.log("xnodes_snip_helpers tests passed");
