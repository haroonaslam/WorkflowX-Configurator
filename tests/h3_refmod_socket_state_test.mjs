import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const source=await readFile(new URL('../web/js/h3_refmod/socket_state.js',import.meta.url),'utf8');
const {contractEmptySockets,refreshSocketLabels,scheduleSocketSync}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
function fixture(){
 const nodes=new Map(),graph={_links:new Map(),getNodeById:id=>nodes.get(id),setDirtyCanvas(){}};
 const n={id:1,graph,inputs:[{name:'clip',type:'CLIP',link:null}],comfyDynamic:{autogrow:{named_references:{max:32}}}};nodes.set(1,n);
 const add=(ordinal,linkId,tag)=>{const input={name:'named_references.reference_'+ordinal,type:'H3RC_REFERENCE',link:linkId};n.inputs.push(input);if(linkId!=null){const origin=linkId+10;nodes.set(origin,{outputs:[{links:[linkId]}],widgets:[{name:'tag',value:tag}]});graph._links.set(linkId,{id:linkId,type:'H3RC_REFERENCE',origin_id:origin,origin_slot:0,target_id:1,target_slot:n.inputs.length-1});}return input;};
 return {n,graph,add};
}
test('compaction retains wires and contiguous native ordinals',()=>{const {n,graph,add}=fixture();add(0,null);add(1,1,'one');add(2,2,'two');add(3,null);contractEmptySockets(n);assert.deepEqual(n.inputs.slice(1).map(i=>[i.name,i.link]),[['named_references.reference_0',1],['named_references.reference_1',2],['named_references.reference_2',null]]);assert.equal(graph._links.get(2).target_slot,2);});
test('recover orphaned input pointer from mutually confirmed graph and source wire',()=>{const {n,add}=fixture();const i=add(3,1,'one');i.link=null;add(4,null);contractEmptySockets(n);assert.equal(n.inputs[1].link,1);assert.equal(n.inputs.length,3);});
test('recover multiple wires without overwriting another connection',()=>{const {n,add}=fixture();const a=add(0,1,'one'),b=add(1,2,'two');a.link=null;n.inputs.splice(n.inputs.indexOf(a),1);contractEmptySockets(n);assert.deepEqual(new Set(n.inputs.map(i=>i.link).filter(x=>x!=null)),new Set([1,2]));});
test('labels do not depend on successful backend preview and reject stale tags',()=>{const {n,add}=fixture();add(4,1,'NewName');add(5,null);refreshSocketLabels(n,{'reference_4':'@old / <Picture 1>'});assert.equal(n.inputs[1].label,'@newname');assert.equal(n.inputs[2].label,'named reference');});
test('cleanup waits for native animation frame work',()=>{const frames=[];globalThis.requestAnimationFrame=fn=>frames.push(fn);const {n,add}=fixture();add(0,null);add(1,null);let done=false;scheduleSocketSync(n,()=>done=true);assert.equal(n.inputs.length,3);frames.shift()();assert.equal(n.inputs.length,3);frames.shift()();assert.equal(n.inputs.length,2);assert.equal(done,true);});
test('stale input pointer cannot create a connection from its label',()=>{const {n,add}=fixture();const i=add(7,null);i.link=99;i.label='@old / <Picture 1>';contractEmptySockets(n);refreshSocketLabels(n);assert.equal(n.inputs[1].link,null);assert.equal(n.inputs[1].label,'named reference');});
