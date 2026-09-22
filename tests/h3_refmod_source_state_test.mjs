import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const source=await readFile(new URL('../web/js/h3_refmod/source_state.js',import.meta.url),'utf8');
const {readSourceSelection}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('non-list and broken serialized source selections open a recoverable draft',()=>{
 for(const input of ['{}','null','16','"text"','{broken',{},null,16]){
  const result=readSourceSelection(input);assert.deepEqual(result.entries,[]);assert.match(result.warning,/Cancel leaves/);
 }
});
test('valid source order, exclusions and ranges are preserved without mutation',()=>{
 const input=[{source:'clip.mp4',start:2,duration:3,enabled:false},{source:'picture.png'}];
 for(const value of [input,JSON.stringify(input)]){
  const result=readSourceSelection(value);assert.deepEqual(result.entries,input);assert.equal(result.warning,'');result.entries[0].start=99;assert.equal(input[0].start,2);
 }
});
test('invalid rows are reported and valid rows are retained',()=>{
 const result=readSourceSelection([null,{},1,[],{source:''},{source:'photo.png'}]);assert.deepEqual(result.entries,[{source:'photo.png'}]);assert.ok(result.warning);
});
test('new empty selection is valid',()=>{
 for(const input of [undefined,'','[]',[]])assert.deepEqual(readSourceSelection(input),{entries:[],warning:''});
});
