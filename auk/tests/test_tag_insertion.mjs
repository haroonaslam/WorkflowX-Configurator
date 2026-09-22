import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { activeLine, editLine, parameterValue, conversionSummary } from '../../web/js/auk/chain_editor.mjs';
const catalog = JSON.parse(readFileSync(new URL('../../web/js/auk/tags.json', import.meta.url)));
const original = 'First line.\n  [Shy][c-whisper][c-speed:1.25] Hello (there)! (3s)\nLast line.';
const caret = original.indexOf('there');
const style = editLine(original, caret, {type:'style', tag:'Happy'});
assert.equal(style.value, original.replace('[Shy]', '[Happy]'));
assert.equal(style.value.slice(style.caret, style.caret + 5), 'there');
assert.deepEqual(activeLine(original, caret).tags, ['Shy', 'c-whisper', 'c-speed:1.25']);
assert.equal(activeLine(original, caret).number, 2);
const moved = editLine(original, caret, {type:'move', index:1, offset:-1});
assert.equal(moved.value, original.replace('[c-whisper][c-speed:1.25]', '[c-speed:1.25][c-whisper]'));
assert.equal(editLine(original, caret, {type:'edit', index:1, tag:'c-speed:0.837'}).value, original.replace('1.25','0.837'));
assert.equal(editLine(original, caret, {type:'remove', index:0}).value, original.replace('[c-whisper]',''));
assert.equal(editLine('[Shy][Happy] Words', 18, {type:'style',tag:'Calm'}).value, '[Calm] Words');
assert.equal(editLine('Hello\n', 6, {type:'add',tag:'c-laugh'}).value, 'Hello\n[c-laugh] ');
assert.equal(editLine('  Hello', 0, {type:'style',tag:'Shy'}).value, '  [Shy] Hello');
assert.equal(editLine('[Happy] Hello', 0, {type:'style',tag:null}).value, 'Hello');
for (const [name, value, expected] of [['c-speed','.837','.837'], ['c-volume','-6.25DB','-6.25'], ['c-pitch','+3.5','+3.5']]) {
  assert.equal(parameterValue(catalog.conversions.find(i=>i.tag===name),value),expected);
}
for (const value of ['', '0','-1','NaN','Infinity','1e3']) assert.throws(()=>parameterValue(catalog.conversions.find(i=>i.tag==='c-speed'),value));
assert.equal(conversionSummary('c-speed:1.25',catalog.conversions).effect,'faster');
assert.equal(conversionSummary('c-volume:0db',catalog.conversions).effect,'unchanged');
console.log('Editor checks passed: replacement, caret, ordering, removal, blank lines, decimals, validation, summaries.');
const dialogue='@voice2[Shy][c-speed:1.25] Hello there.\nContinue speaking.';
const position=dialogue.indexOf('there');
assert.equal(activeLine(dialogue,dialogue.length).voice,2);
assert.equal(activeLine(dialogue.replace('@voice2','@voice1'),dialogue.length).voice,1);
const replacement=editLine(dialogue,position,{type:'style',tag:'Happy'});
assert.equal(replacement.value,'@voice2 [Happy][c-speed:1.25] Hello there.\nContinue speaking.');
assert.equal(replacement.value.slice(replacement.caret,replacement.caret+5),'there');
assert.equal(editLine(dialogue,position,{type:'speaker',voice:1}).value,'@voice1 [Shy][c-speed:1.25] Hello there.\nContinue speaking.');
assert.equal(editLine(dialogue,position,{type:'speaker',voice:null}).value,'[Shy][c-speed:1.25] Hello there.\nContinue speaking.');
assert.equal(editLine(dialogue,position,{type:'remove',index:0}).value,'@voice2 [Shy] Hello there.\nContinue speaking.');
assert.equal(editLine('Hello',0,{type:'speaker',voice:2}).value,'@voice2 Hello');
console.log('Speaker editing and inheritance checks passed.');
import {inlineAt, editInline} from '../../web/js/auk/chain_editor.mjs';
const inlineScript = '@voice2 [Happy] Hello my friend (3s)';
const selection = inlineScript.indexOf('my friend');
const wrapped = editInline(inlineScript, selection, selection+9, 'c-speed:1.25');
assert.equal(wrapped.value,'@voice2 [Happy] Hello <c-speed:1.25>my friend</c-speed> (3s)');
assert.equal(inlineAt(wrapped.value, wrapped.value.indexOf('friend'))[2],'1.25');
assert.equal(editInline(wrapped.value,wrapped.value.indexOf('friend'),wrapped.value.indexOf('friend'),'sad').value,'@voice2 [Happy] Hello <sad>my friend</sad> (3s)');
assert.equal(editInline(wrapped.value,wrapped.value.indexOf('friend'),wrapped.value.indexOf('friend'),null).value,inlineScript);
assert.throws(()=>editInline(inlineScript,0,7,'sad'),/spoken words/);
assert.throws(()=>editInline('hello\nworld',0,11,'sad'),/one line/);
console.log('Inline selection, replacement, removal and boundary tests passed.');

const { editPresets } = await import('../../web/js/auk/chain_editor.mjs');
const presets = editPresets(catalog);
assert.equal(presets.find(p => p.label === 'Excited').tag, 'c-emotion:excited');
assert.equal(presets.find(p => p.label === 'laughs').tag, 'c-delivery:speaking while laughing');
for (const preset of presets) {
  assert.ok(preset.tag.startsWith('c-'));
  const wrapped = editInline('Before hello after', 7, 12, preset.tag);
  assert.equal(wrapped.value, `Before <${preset.tag}>hello</${preset.tag.split(':')[0]}> after`);
}
console.log('Edit presets emit c-tags with matching parameter-free closures.');

const { customPreset } = await import('../../web/js/auk/chain_editor.mjs');
const custom = customPreset(catalog,{label:'Desperate',group:'Emotion',operation:'c-emotion',value:'desperate'});
assert.equal(custom.tag,'c-emotion:desperate');
assert.equal(editInline('Please stay',0,11,custom.tag).value,'<c-emotion:desperate>Please stay</c-emotion>');
assert.equal(customPreset(catalog,{label:'Slow',group:'Acoustics',operation:'c-speed',value:'0.85'}).tag,'c-speed:0.85');
assert.equal(customPreset(catalog,{label:'Quiet',group:'Acoustics',operation:'c-volume',value:'-3db'}).tag,'c-volume:-3db');
assert.equal(customPreset(catalog,{label:'Hopeful',group:'Emotion',value:'hopeful'},true).tag,'hopeful');
assert.deepEqual(JSON.parse(JSON.stringify(custom)),custom);
for (const bad of [
 {label:'',group:'Emotion',operation:'c-emotion',value:'sad'},
 {label:'Bad',group:'Emotion',operation:'c-unknown',value:'sad'},
 {label:'Bad',group:'Acoustics',operation:'c-speed',value:'0'},
 {label:'Bad',group:'Emotion',operation:'c-emotion',value:'<sad>'},
]) assert.throws(()=>customPreset(catalog,bad));
console.log('Custom choices: styles, emotions, numeric values, inline insertion, serialization and validation passed.');
