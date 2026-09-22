import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../web/js/h3_refmod/selection_state.js',import.meta.url),'utf8');
const {readSelection}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('invalid positional values recover without changing saved data',()=>{
 for(const v of ['Original','null','32','[]','{"character_id":"a","modes":{"Pictures only":{}}}']){const r=readSelection(v,'a');assert.equal(r.reset,true);assert.deepEqual(r.draft,{character_id:'a',modes:{}});}
});
test('valid settings preserve all modes and remain a draft',()=>{
 const d={character_id:'a',modes:{'Pictures only':{selected:['one'],order:['one'],defaults:{image:'small'},overrides:{},budget:0}}};
 const saved=JSON.stringify(d),r=readSelection(saved,'a');assert.deepEqual(r.draft,d);assert.equal(r.reset,false);r.draft.modes['Pictures only'].selected=[];assert.equal(JSON.stringify(d),saved);
 assert.deepEqual(readSelection(saved,'b').draft,{character_id:'b',modes:{}});
});
