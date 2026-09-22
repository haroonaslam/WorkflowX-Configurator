import assert from 'node:assert/strict';
import {editorQueue,insertSourceLine} from '../../web/js/auk/segment_editor.mjs';
const graph={
 model:{class_type:'Loader',inputs:{}},
 text:{class_type:'TextGenerator',inputs:{model:['model',0]}},
 clone:{class_type:'WorkflowXAuKChainedClone',inputs:{model:['model',0],script:['text',0],review_each_line:true}},
 preview:{class_type:'PreviewAudio',inputs:{audio:['clone',0]}},
 save:{class_type:'SaveAudio',inputs:{audio:['preview',0]}},
 report:{class_type:'PreviewAny',inputs:{source:['clone',1]}},
 unrelated:{class_type:'SaveImage',inputs:{image:['model',0]}},
};
const final=editorQueue(graph,'clone','finalize',.25);
assert.deepEqual(Object.keys(final.prompt).sort(),['clone','preview','report','save']);
assert.deepEqual(final.prompt.clone.inputs,{gap_seconds:.25});
assert.equal(final.prompt.clone.class_type,'WorkflowXAuKSegmentFinalize');
assert.equal(graph.clone.class_type,'WorkflowXAuKChainedClone');
const regenerate=editorQueue(graph,'clone','regenerate',0);
assert.deepEqual(Object.keys(regenerate.prompt).sort(),['clone','model','preview','report','save','text']);
assert.equal(regenerate.prompt.clone.class_type,'WorkflowXAuKChainedCloneReviewStep');
assert.deepEqual(regenerate.prompt.clone.inputs.script,['text',0]);
assert.deepEqual(regenerate.targets.sort(),['clone','preview','report','save']);
assert.equal(insertSourceLine('One\n\nTwo\nThree\nFour',2,'Added',4),'One\n\nTwo\nThree\nAdded\nFour');
assert.throws(()=>insertSourceLine('One\nTwo',0,'Added',3),/structure changed/);
assert.throws(()=>insertSourceLine('One',0,'Two\nThree',1),/one nonblank/);
assert.throws(()=>insertSourceLine('One',null,'Two',1),/structure changed/);
console.log('Segment editor checks passed: queue isolation, assembly-only dependency pruning, connected source links, insertion and structural validation.');
