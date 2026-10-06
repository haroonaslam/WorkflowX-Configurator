import test from "node:test";
import assert from "node:assert/strict";

import {
  buildGraphInventory,
  candidateTier,
  canonicalGroupName,
  effectiveRecordState,
  resolveCandidates,
} from "../web/js/key_config_graph.mjs";

function group(title, bounding) {
  return { title, bounding };
}

function node(id, type, pos, subgraph = null, mode = 0) {
  return { id, type, pos, size: [80, 40], mode, subgraph };
}

function graph(id, nodes = [], groups = [], name = id) {
  return { id, _nodes: nodes, _groups: groups, name };
}

test("inventory deduplicates logical groups and expands shared instances", () => {
  const child = graph("child", [node(2, "KVGC_SetInt", [10, 10])], [group("Nested", [0, 0, 100, 100])], "Child");
  const root = graph("root", [node(10, "child", [0, 0], child), node(20, "child", [200, 0], child)]);
  const inventory = buildGraphInventory(root);
  assert.equal(inventory.groups.length, 1);
  assert.deepEqual(
    inventory.instances.filter((item) => item.node.type === "KVGC_SetInt").map((item) => item.executionId),
    ["10:2", "20:2"],
  );
});

test("logical definitions deduplicate by persistent graph UUID", () => {
  const first = graph("shared", [node(2, "KVGC_SetInt", [10, 10])], [group("Nested", [0, 0, 100, 100])]);
  const second = graph("shared", [node(2, "KVGC_SetInt", [10, 10])], [group("Nested", [0, 0, 100, 100])]);
  const root = graph("root", [node(10, "shared", [0, 0], first), node(20, "shared", [200, 0], second)]);
  const inventory = buildGraphInventory(root);
  assert.equal(inventory.groups.length, 1);
  assert.deepEqual(
    inventory.instances.filter((item) => item.node.type === "KVGC_SetInt").map((item) => item.executionId),
    ["10:2", "20:2"],
  );
});

test("inventory finds nested definitions and stops circular traversal", () => {
  const inner = graph("inner", [node(3, "KVGC_SetInt", [0, 0])], [group("Inner", [0, 0, 100, 100])]);
  const outer = graph("outer", [node(2, "inner", [0, 0], inner)], [group("Outer", [0, 0, 100, 100])]);
  inner._nodes.push(node(4, "outer", [120, 0], outer));
  const root = graph("root", [node(1, "outer", [0, 0], outer)]);
  const inventory = buildGraphInventory(root);
  assert.deepEqual(inventory.groups.map((item) => item.name).sort(), ["Inner", "Outer"]);
  assert.equal(inventory.cycles.length, 1);
});

test("duplicate names are normalized but shared instances are not duplicates", () => {
  const child = graph("child", [], [group(" Sampling ", [0, 0, 10, 10])]);
  const root = graph("root", [node(1, "child", [0, 0], child), node(2, "child", [20, 0], child)], [
    group("SAMPLING", [0, 0, 10, 10]),
  ]);
  const inventory = buildGraphInventory(root);
  assert.equal(canonicalGroupName(" Sampling "), canonicalGroupName("SAMPLING"));
  assert.equal(inventory.duplicateGroups.length, 1);
  assert.equal(inventory.duplicateGroups[0].length, 2);
});

test("group breadcrumbs omit the redundant root canvas label", () => {
  const child = graph("child", [], [group("Nested Group", [0, 0, 10, 10])], "Upscaler");
  const root = graph(
    "root",
    [node(1, "child", [0, 0], child)],
    [group("Root Group", [0, 0, 10, 10])],
  );
  const locations = buildGraphInventory(root).groups.map(({ location }) => location);
  assert.deepEqual(locations, ["Root Group", "Upscaler / Nested Group"]);
});

test("group breadcrumbs strip a Canvas prefix supplied by a subgraph label", () => {
  const child = graph(
    "child",
    [],
    [group("Sampling", [0, 0, 10, 10])],
    "Canvas / Image Edit (Qwen Image 2.1)",
  );
  const root = graph("root", [node(1, "child", [0, 0], child)]);
  assert.equal(
    buildGraphInventory(root).groups[0].location,
    "Image Edit (Qwen Image 2.1) / Sampling",
  );
});

test("candidate tiers follow root ungrouped, root grouped, subgraph order", () => {
  const child = graph("child", [node(3, "KVGC_SetInt", [0, 0])]);
  const root = graph(
    "root",
    [node(1, "KVGC_SetInt", [200, 0]), node(2, "KVGC_SetInt", [10, 10]), node(9, "child", [400, 0], child)],
    [group("Root Group", [0, 0, 100, 100])],
  );
  const records = buildGraphInventory(root).instances.filter((item) => item.node.type === "KVGC_SetInt");
  const modes = { "Root Group": "Active" };
  assert.deepEqual(records.map((record) => candidateTier(record, modes)), [0, 1, 2]);
});

test("legacy non-recursive modes do not control groups inside subgraphs", () => {
  const child = graph(
    "child",
    [node(3, "KVGC_SetInt", [10, 10])],
    [group("Legacy Root Group", [0, 0, 100, 100])],
  );
  const root = graph("root", [node(9, "child", [400, 0], child)]);
  const record = buildGraphInventory(root).instances.find((item) => item.executionId === "9:3");
  const state = effectiveRecordState(record, { "Legacy Root Group": "Mute" }, false);
  assert.equal(state.inactive, false);
  assert.equal(candidateTier(record, { "Legacy Root Group": "Mute" }, false), 2);
});

test("ancestor inactivity excludes nested candidates", () => {
  const child = graph("child", [node(2, "KVGC_SetInt", [0, 0])]);
  const root = graph("root", [node(1, "child", [10, 10], child)], [group("Wrapper", [0, 0, 100, 100])]);
  const nested = buildGraphInventory(root).instances.find((item) => item.executionId === "1:2");
  assert.equal(effectiveRecordState(nested, { Wrapper: "Mute" }).inactive, true);
  assert.equal(candidateTier(nested, { Wrapper: "Mute" }), null);
});

test("a Set intersecting multiple controlled groups is invalid", () => {
  const root = graph(
    "root",
    [node(1, "KVGC_SetInt", [20, 20])],
    [group("First", [0, 0, 100, 100]), group("Second", [10, 10, 100, 100])],
  );
  const record = buildGraphInventory(root).instances[0];
  const state = effectiveRecordState(record, { First: "Active", Second: "Active" });
  assert.equal(state.overlap, true);
  assert.deepEqual(state.controlledGroups.map(({ name }) => name), ["First", "Second"]);
});

test("resolver errors only for duplicates in the winning tier", () => {
  const candidates = [
    { executionId: "1", tier: 0 },
    { executionId: "2:1", tier: 2 },
    { executionId: "3:1", tier: 2 },
  ];
  const result = resolveCandidates(candidates, "Int", "seed");
  assert.equal(result.candidate.executionId, "1");
  assert.equal(result.warnings.length, 1);
  assert.throws(
    () => resolveCandidates(candidates.slice(1), "Int", "seed"),
    /Multiple active Int Sets.*2:1, 3:1/,
  );
});
