import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../web/js/h3_refmod/ui_state.js',import.meta.url),'utf8');
const {rememberDetails,rememberHeight}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
globalThis.ResizeObserver=class{observe(){} disconnect(){}};
class Element extends EventTarget{open=false;isConnected=true;style={};offsetHeight=0;}
const make=()=>({properties:{},graph:{setDirtyCanvas(){}},onConfigure(){},onSerialize(){}});
const save=n=>{const info={properties:structuredClone(n.properties)};n.onSerialize?.(info);return JSON.parse(JSON.stringify(info));};
const n=make(),group=new Element(),text=new Element();rememberDetails(n,group,'group',true);rememberHeight(n,text,'text',64,42,500);
group.open=false;text.style.height='151px'; // Save before observers/toggle callbacks; group may already be hidden.
const saved=save(n);assert.equal(saved.properties.h3rcUI.group,false);assert.equal(saved.properties.h3rcUI.text,151);
const reloaded=make(),g2=new Element(),t2=new Element();rememberDetails(reloaded,g2,'group',true);rememberHeight(reloaded,t2,'text',64,42,500);
reloaded.properties=saved.properties;reloaded.onConfigure(saved);assert.equal(g2.open,false);assert.equal(t2.style.height,'151px');
g2.dispatchEvent(new Event('toggle'));assert.equal(reloaded.properties.h3rcUI.group,false,'delayed restoration event must not overwrite saved state');
g2.open=true;g2.dispatchEvent(new Event('toggle'));assert.equal(reloaded.properties.h3rcUI.group,true);
const previous=reloaded.onConfigure,modal=new Element();rememberDetails(reloaded,modal,'modal',false,false);assert.equal(reloaded.onConfigure,previous,'modal renders must not retain configure closures');
modal.open=true;modal.dispatchEvent(new Event('toggle'));const reopened=new Element();rememberDetails(reloaded,reopened,'modal',false,false);assert.equal(reopened.open,true);
modal.isConnected=false;modal.open=false;modal.dispatchEvent(new Event('toggle'));assert.equal(reloaded.properties.h3rcUI.modal,true);
console.log('PASS H3 UI state: immediate save, hidden resize, reload, delayed toggles and modal lifecycle');
