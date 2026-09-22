import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const source=await readFile(new URL('../web/js/h3_refmod/profile_state.js',import.meta.url),'utf8');
const {readProfileSettings}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('wrong positional values and malformed profiles are rejected without rendering a partial group',()=>{
 for(const v of [32,'32','1024','{}','null',null,undefined,'invalid','[]',{picture:32,video:[],combined:[]},{picture:[null],video:[],combined:[]}])assert.equal(readProfileSettings(v),null);
});
test('valid enabled and disabled profile lists are retained without substitution',()=>{
 const p={id:'custom',name:'Custom detail',size:768,enabled:false};const data={picture:[p],video:[],combined:[{...p,id:'combined'}]};
 assert.deepEqual(readProfileSettings(JSON.stringify(data)),data);
 assert.deepEqual(readProfileSettings({picture:[],video:[],combined:[]}),{picture:[],video:[],combined:[]});
});
