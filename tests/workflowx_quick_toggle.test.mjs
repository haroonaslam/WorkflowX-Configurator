import assert from "node:assert/strict";
import test from "node:test";
import { buildGraphInventory } from "../web/js/key_config_graph.mjs";
import {
  TOGGLE_CONTROLLER,
  TOGGLE_SELECTION,
  installToggleControllerHooks,
  pruneToggleInputs,
  selectToggleInput,
  toggleRows,
} from "../web/js/workflowx_quick_toggle.mjs";

function fixture() {
  const first = { id: "1", title: "Load model", outputs: [{ name: "MODEL" }] };
  const second = { id: "2", title: "Load model", outputs: [{ name: "MODEL" }] };
  const links = new Map([
    ["51", { id: "51", origin_id: "1", origin_slot: 0 }],
    ["52", { id: "52", origin_id: "2", origin_slot: 0 }],
  ]);
  const controller = {
    id: "3", type: TOGGLE_CONTROLLER, title: "Models", properties: {},
    inputs: [{ name: "choices.input0", link: "51" }, { name: "choices.input1", link: "52" }],
    getInputLink(index) { return links.get(this.inputs[index].link); },
  };
  const graph = {
    id: "root", nodes: [first, second, controller],
    getNodeById(id) { return this.nodes.find((node) => node.id === id); },
  };
  controller.graph = graph;
  return { graph, controller, first, second, links };
}

test("list choices by node title, disambiguate duplicate titles and retain the chosen link across slot moves", () => {
  const { graph, controller, second } = fixture();
  const initial = toggleRows(graph)[0];
  assert.deepEqual(initial.choices.map(({ label }) => label), ["Load model · MODEL · #1", "Load model · MODEL · #2"]);
  assert.equal(initial.selected, "");
  selectToggleInput(graph, null, controller, "52");
  second.title = "New model";
  controller.inputs = [{ name: "choices.input0", link: "52" }];
  const [row] = toggleRows(graph);
  assert.equal(row.selected, "52");
  assert.equal(row.choices[0].label, "New model");
  assert.deepEqual(controller.properties[TOGGLE_SELECTION], { link: "52", source: "2", slot: 0 });
});

test("replacement clears the effective choice and serialization never binds a reused slot or wrong source", () => {
  const { graph, controller, links } = fixture();
  selectToggleInput(graph, null, controller, "52");
  links.set("52", { id: "52", origin_id: "1", origin_slot: 0 });
  assert.equal(toggleRows(graph)[0].selected, "");
  const data = { properties: { ...controller.properties } };
  const hooks = { getInputLink: controller.getInputLink };
  installToggleControllerHooks(hooks);
  hooks.onSerialize.call(controller, data);
  assert.deepEqual(data.properties, {});
  assert.equal(hooks.getInputLink.call({ graph: null }, 0), null);
});

test("shared definitions have one dashboard row and prune the same choice from every instance", () => {
  const { graph: subgraph, controller } = fixture();
  subgraph.name = "Models";
  const root = { id: "root-workflow", nodes: [{ id: "10", subgraph }, { id: "11", subgraph }] };
  assert.equal(toggleRows(root).length, 1);
  assert.equal(toggleRows(root)[0].path, "Models");
  selectToggleInput(root, null, controller, "52");
  const prompts = {
    "10:3": { class_type: TOGGLE_CONTROLLER, inputs: { "choices.input0": ["10:1", 0], "choices.input1": ["10:2", 0] } },
    "11:3": { class_type: TOGGLE_CONTROLLER, inputs: { "choices.input0": ["11:1", 0], "choices.input1": ["11:2", 0] } },
    other: { class_type: "Other", inputs: { image: ["11:1", 0] } },
  };
  pruneToggleInputs({ output: prompts }, buildGraphInventory(root));
  assert.deepEqual(prompts["10:3"].inputs, { "choices.input1": ["10:2", 0] });
  assert.deepEqual(prompts["11:3"].inputs, { "choices.input1": ["11:2", 0] });
  assert.deepEqual(prompts.other.inputs, { image: ["11:1", 0] });
});
