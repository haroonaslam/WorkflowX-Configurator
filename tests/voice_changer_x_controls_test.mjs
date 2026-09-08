import assert from "node:assert/strict";
import test from "node:test";
import { mountVoiceControls, normalizeValue } from "../web/js/voice_changer_x_controls.mjs";

class Element {
  style = {}; children = []; handlers = {}; value = "";
  append(...children) { this.children.push(...children); }
  setAttribute() {}
  addEventListener(name, fn) { (this.handlers[name] ??= []).push(fn); }
  async fire(name) { for (const fn of this.handlers[name] || []) await fn({ stopPropagation() {} }); }
}
globalThis.document = { createElement: () => new Element(), activeElement: null };
const definitions = {
  pitch_shift: ["FLOAT", { min: -24, max: 24, step: 0.01, default: 0 }],
  timbre: ["FLOAT", { min: -12, max: 12, step: 0.1, default: 0 }],
  pitch_variation: ["FLOAT", { min: 0, max: 200, step: 1, default: 100 }],
};
function setup(saved, matching) {
  const history = [];
  const node = {
    widgets: Object.entries(definitions).map(([name, [, spec]], index) => ({ name, type: "number", value: saved?.[index] ?? spec.default })),
    inputs: [{name:"source_audio",type:"AUDIO",link:1},{name:"reference_audio",type:"AUDIO",link:2},
             ...Object.keys(definitions).map(name=>({name,type:"FLOAT",widget:{name},link:null}))],
    graph: { beforeChange: () => history.push("before"), afterChange: () => history.push("after") },
    addDOMWidget() { return {}; },
    removeInput(index) { this.inputs.splice(index,1); },
    addInput(name,type) { const input={name,type,link:null};this.inputs.push(input);return input; },
    onConfigure(data) { data.forEach((value, index) => { this.widgets[index].value = value; }); },
  };
  return { node, history, ui: mountVoiceControls(node, definitions, matching) };
}

test("decimal values, bounds, and invalid edits", () => {
  const spec = definitions.pitch_shift[1];
  assert.equal(normalizeValue("4.37", spec, 0), 4.37);
  assert.equal(normalizeValue("-3.126", spec, 0), -3.13);
  assert.equal(normalizeValue("99", spec, 0), 24);
  for (const invalid of ["", "NaN", "Infinity"]) assert.equal(normalizeValue(invalid, spec, 2.75), 2.75);
});

test("slider and number edit one canonical widget, grouping slider drag history", () => {
  const { node, history, ui } = setup();
  const row = ui.rows[0];
  for (const value of ["1.23", "2.34", "3.45"]) { row.slider.value = value; row.slider.fire("input"); }
  row.slider.fire("change");
  assert.deepEqual(history, ["before", "after"]);
  assert.equal(node.widgets[0].value, 3.45);
  assert.equal(row.number.value, "3.45");
  row.number.value = "-2.57"; row.number.fire("change");
  assert.equal(row.slider.value, "-2.57");
  assert.equal(node.widgets[0].value, -2.57);
});

test("workflow restore, duplication, undo and redo restore displayed decimals", () => {
  const { node, ui } = setup();
  node.onConfigure([4.37, -1.2, 123]);
  assert.equal(ui.rows[0].number.value, "4.37");
  const saved = JSON.parse(JSON.stringify(node.widgets.map(w => w.value)));
  const duplicate = setup(saved);
  assert.equal(duplicate.ui.rows[0].slider.value, "4.37");
  node.onConfigure([0, 0, 100]);
  assert.equal(ui.rows[0].number.value, "0");
  node.onConfigure(saved);
  assert.equal(ui.rows[0].number.value, "4.37");
});

test("only audio sockets remain and reset clears all controls", () => {
  const { node, ui, history } = setup([3.21, 2.1, 145]);
  assert.deepEqual(node.inputs.map(input=>input.name),["source_audio","reference_audio"]);
  ui.reset.fire("click");
  assert.deepEqual(node.widgets.map(w => w.value), [0, 0, 100]);
  assert.deepEqual(history, ["before", "after"]);
});

test("workflow restoration removes obsolete numeric sockets", () => {
  const { node, ui } = setup();
  node.inputs = [{ name: "pitch_shift", link: null, widget: { name: "pitch_shift" } }];
  node.onConfigure([0,0,100]);
  assert.ok(!node.inputs.some(input=>input.name==='pitch_shift'));
  assert.equal(node.widgets[0].type, "number");
  assert.equal(ui.rows[0].number.value, '0');
});

test("match applies all settings as one undoable edit", async () => {
  const {node,ui,history}=setup(undefined,async()=>({settings:{pitch_shift:4.37,timbre:1.2,pitch_variation:125},warnings:[]}));
  await ui.match.fire("click");
  assert.deepEqual(node.widgets.map(w=>w.value),[4.37,1.2,125]);
  assert.deepEqual(history,["before","after"]);
  assert.equal(ui.match.disabled,false);
  assert.match(ui.status.textContent,/match applied/);
});

test("failed matching and malformed results do not overwrite edits", async () => {
  for (const matching of [async()=>{throw new Error('Reference is silent');},async()=>({settings:{pitch_shift:2}})]) {
    const {node,ui}=setup([3.2,2,110],matching);
    await ui.match.fire("click");
    assert.deepEqual(node.widgets.map(w=>w.value),[3.2,2,110]);
    assert.equal(ui.match.disabled,false);
  }
});

test("late results never overwrite manual edits or a removed node", async () => {
  for(const mode of ['custom','external','remove']) {
    let finish;
    const {node,ui}=setup(undefined,()=>new Promise(resolve=>{finish=resolve;}));
    const pending=ui.match.fire("click");
    assert.equal(ui.match.disabled,true);
    if(mode==='remove') node.onRemoved();
    else if(mode==='external') node.widgets[0].value=6.25;
    else {ui.rows[0].number.value='6.25';await ui.rows[0].number.fire('change');}
    finish({settings:{pitch_shift:4,timbre:2,pitch_variation:130}});
    await pending;
    assert.equal(node.widgets[0].value,mode==='remove'?0:6.25);
    assert.equal(node.widgets[1].value,0);
  }
});
