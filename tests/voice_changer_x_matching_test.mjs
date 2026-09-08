import assert from "node:assert/strict";
import test from "node:test";
import { buildMatchPrompt, matchFingerprint, migrateVoiceWorkflow, resolveVoiceTarget, waitForReference } from "../web/js/voice_changer_x_matching.mjs";

const prompt=()=>({
  '1':{class_type:'LoadAudio',inputs:{audio:'source.wav'}},
  '2':{class_type:'LoadAudio',inputs:{audio:'reference.wav'}},
  '3':{class_type:'WorkflowX_VoiceChangerX',inputs:{source_audio:['1',0],reference_audio:['2',0],pitch_shift:4}},
  '4':{class_type:'PreviewAudio',inputs:{audio:['3',0]}},
  '5':{class_type:'UnrelatedGeneration',inputs:{seed:42}},
});

test('match queue includes only the two audio branches and target',()=>{
  const original=prompt(), result=buildMatchPrompt(original,'3','request');
  assert.deepEqual(Object.keys(result),['1','2','3']);
  assert.equal(result['3'].inputs.match_request,'request');
  assert.equal(original['3'].inputs.match_request,undefined);
  delete original['3'].inputs.reference_audio;
  assert.throws(()=>buildMatchPrompt(original,'3'),/Connect reference audio/);
});

test('fingerprint catches upstream changes but ignores target controls',()=>{
  const source=buildMatchPrompt(prompt(),'3'),before=matchFingerprint(source,'3');
  source['3'].inputs.pitch_shift=2;
  assert.equal(matchFingerprint(source,'3'),before);
  source['2'].inputs.audio='new-reference.wav';
  assert.notEqual(matchFingerprint(source,'3'),before);
});

test('migration preserves source audio and removes only obsolete parameter links',()=>{
  const graph={nodes:[
    {id:1,outputs:[{links:[10]}]}, {id:2,outputs:[{links:[11,12]}]},
    {id:3,type:'WorkflowX_VoiceChangerX',inputs:[{name:'audio',link:10},{name:'pitch_shift',link:11},{name:'reference_audio',link:12}],widgets_values:[4.37,0,0,0,100,0]},
  ],links:[[10,1,0,3,0,'AUDIO'],[11,2,0,3,1,'FLOAT'],[12,2,0,3,2,'AUDIO']]};
  migrateVoiceWorkflow(graph);
  assert.deepEqual(graph.nodes[2].inputs.map(i=>i.name),['source_audio','reference_audio']);
  assert.deepEqual(graph.links,[[10,1,0,3,0,'AUDIO'],[12,2,0,3,1,'AUDIO']]);
  assert.deepEqual(graph.nodes[1].outputs[0].links,[12]);
  assert.equal(graph.nodes[2].widgets_values[0],4.37);
  const saved=JSON.stringify(graph);migrateVoiceWorkflow(graph);assert.equal(JSON.stringify(graph),saved);
});

test('target resolution handles nested nodes and rejects ambiguous shared instances',()=>{
  const node={id:3},root={_nodes:[node]};
  assert.equal(resolveVoiceTarget(root,node,prompt()),'3');
  const child={_nodes:[node]},nested={_nodes:[{id:7,subgraph:child}]};
  const output={'7:3':prompt()['3'],'8:3':prompt()['3']};
  assert.equal(resolveVoiceTarget(nested,node,output),'7:3');
  nested._nodes.push({id:8,subgraph:child});
  assert.throws(()=>resolveVoiceTarget(nested,node,output),/uniquely/);
});

test('history result is correlated with its request token',async()=>{
  const report={request_id:'mine',settings:{pitch_shift:2}};
  const api={fetchApi:async()=>({ok:true,json:async()=>({p:{outputs:{3:{voice_reference_match:[{request_id:'old'},report]}}}})})};
  assert.equal(await waitForReference(api,'p','mine',()=>false),report);
});

test('history failures and cleared jobs release the caller',async()=>{
  const failed={fetchApi:async()=>({ok:true,json:async()=>({p:{status:{messages:[['execution_error',{exception_message:'upstream failed'}]]}}})})};
  await assert.rejects(waitForReference(failed,'p','mine',()=>false),/upstream failed/);
  const cleared={fetchApi:async()=>({ok:true,json:async()=>({})})};
  await assert.rejects(waitForReference(cleared,'p','mine',()=>false,async()=>{}),/removed from the queue/);
});
