import assert from "node:assert/strict";
import test from "node:test";
import { STOP, SOURCE, TARGET, SELECT, buildControls } from "../web/js/workflowx_run_controls_state.mjs";

function fixture(mode = 0, sameRun = false) {
  const record = (id, type, properties = {}, mode = 0) => ({ executionId: id, node: { type, mode, properties }, ancestors: [] });
  const selection = (id, type) => ({ executionId: id, type });
  const records = [record("1", "PreviewImage"), record("2", "LoadImage", {}, mode),
    record("3", "ImageInvert"), record("s", SOURCE, { [SELECT]: selection("1", "PreviewImage") }),
    record("t", TARGET, { [SELECT]: selection("2", "LoadImage"), workflowx_source: selection("s", SOURCE), workflowx_transfer_mode: sameRun ? "same_run" : "next_run" }),
    record("stop", STOP, { [SELECT]: selection("3", "ImageInvert") })];
  const prompt = { 1: { class_type: "PreviewImage", inputs: {} },
    3: { class_type: "ImageInvert", inputs: {} }, 4: { class_type: "PreviewImage", inputs: { images: ["3", 0] } } };
  if (!mode) prompt[2] = { class_type: "LoadImage", inputs: { image: "keep.png" } };
  return { records, prompt, options: { outputIds: ["1", "4"], nonce: "fixture", workflow: "fixture" } };
}

for (const mode of [0, 2, 4]) for (const sameRun of [false, true]) {
  test(`copy remains eligible for destination mode ${mode}, same-run ${sameRun}`, () => {
    const { records, prompt, options } = fixture(mode, sameRun);
    const original = structuredClone(records);
    const id = buildControls(prompt, records, options);
    const config = JSON.parse(prompt[id].inputs.config);
    assert.equal(config.transfers.length, 1);
    assert.equal(config.transfers[0].same_run, sameRun && mode === 0);
    assert.deepEqual(records, original);
    assert.deepEqual(config.stops, ["3"]);
    if (sameRun && !mode) assert.equal(JSON.parse(prompt[2].inputs.settings).inputs.image, "keep.png");
    if (!sameRun && !mode) assert.equal(prompt[2].inputs.image, "keep.png");
  });
}

test("selective runs omit StopX while keeping included transfers", () => {
  const { records, prompt, options } = fixture(4);
  const id = buildControls(prompt, records, { ...options, selective: true });
  assert.deepEqual(JSON.parse(prompt[id].inputs.config).stops, []);
  assert.equal(JSON.parse(prompt[id].inputs.config).transfers.length, 1);
});

test("rejects a same-run cycle before replacing original loader settings", () => {
  const { records, prompt, options } = fixture(0, true);
  prompt[1].inputs.images = ["2", 0];
  assert.throws(() => buildControls(prompt, records, options), /cycle/);
  assert.equal(prompt[2].class_type, "LoadImage");
});

test("rejects transfers that must execute after the stop point", () => {
  const { records, prompt, options } = fixture();
  prompt[1].inputs.images = ["3", 0];
  assert.throws(() => buildControls(prompt, records, options), /cycle/);
});

test("multiple writers to one loader fail before queue", () => {
  const { records, prompt, options } = fixture();
  records.push({ ...structuredClone(records.find((r) => r.executionId === "t")), executionId: "t2" });
  assert.throws(() => buildControls(prompt, records, options), /Only one/);
});

test("inactive source markers and stale selections do not execute", () => {
  const { records, prompt, options } = fixture();
  records.find((r) => r.executionId === "s").node.mode = 2;
  const id = buildControls(prompt, records, options);
  assert.deepEqual(JSON.parse(prompt[id].inputs.config).transfers, []);
});

test("Segment RunX copies from a source that is active only in its submitted prompt", () => {
  const { records, prompt, options } = fixture(4, true);
  records.find((r) => r.executionId === "1").node.mode = 2;
  const id = buildControls(prompt, records, { ...options, selective: true });
  assert.equal(JSON.parse(prompt[id].inputs.config).transfers.length, 1);
});
