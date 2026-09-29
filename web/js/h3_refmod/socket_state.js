// Run only after native Autogrow's deferred connection work has settled.
const dynamicName = /^(.*(?:character_|reference_|ref_image_|ref_video_audio_|ref_video_|ref_audio_))(\d+)$/;
const getLink=(graph,id)=>graph?._links?.get(id)??graph?.links?.[id];
const same=(a,b)=>String(a)===String(b);
function validSource(graph,link){return graph?.getNodeById(link.origin_id)?.outputs?.[link.origin_slot]?.links?.includes(link.id);}

export function contractEmptySockets(node) {
 if(node.h3rcContracting||!node.inputs)return;
 node.h3rcContracting=true;
 try {
  const graph=node.graph,groups=new Map();
  for(const input of node.inputs){
   const match=input.name.match(dynamicName);if(!match)continue;
   const group=groups.get(match[1])||[];group.push(input);groups.set(match[1],group);
   const link=input.link!=null?getLink(graph,input.link):null;
   if(graph&&input.link!=null&&(!link||!same(link.target_id,node.id)||!validSource(graph,link)))input.link=null;
  }
  // Recover a wire left without its input pointer by the earlier cleanup race.
  // Source output + graph link must agree; never invent a connection from a label.
  const links=graph?._links?[...graph._links.values()]:Object.values(graph?.links||{});
  for(const link of links){
   if(!same(link.target_id,node.id)||!validSource(graph,link)||node.inputs.some(i=>i.link===link.id))continue;
   const type=link.type;
   if(!['H3RC_CHARACTER','H3RC_REFERENCE'].includes(type))continue;
   const pair=[...groups].find(([,inputs])=>inputs[0].type===type);if(!pair)continue;
   const [prefix,inputs]=pair;let input=node.inputs[link.target_slot];
   if(!inputs.includes(input)||input.link!=null)input=inputs.find(i=>i.link==null);
   if(!input){input={name:prefix+inputs.length,type,link:null,shape:inputs[0].shape};inputs.push(input);}
   input.link=link.id;
  }
  const replacements=new Map();
  for(const [prefix,inputs] of groups){
   const connected=inputs.filter(i=>i.link!=null);
   const lastConnected=Math.max(-1,...connected.map(i=>node.inputs.indexOf(i)));
   const empty=inputs.find(i=>i.link==null&&node.inputs.indexOf(i)>lastConnected);
   const groupName=prefix.slice(0,prefix.lastIndexOf('.'));
   const max=node.comfyDynamic?.autogrow?.[groupName]?.max??Infinity;
   const spare=connected.length<max?(empty||{name:prefix+connected.length,type:inputs[0].type,link:null,shape:inputs[0].shape}):null;
   const ordered=[...connected,...(spare?[spare]:[])];
   ordered.forEach((input,index)=>{input.name=prefix+index;});
   replacements.set(prefix,ordered);
  }
  // Use native slot mutations: current ComfyUI also stores widget connections
  // outside node.inputs. Splicing/reordering that array leaves saved link indices stale.
  const keep=new Set([...replacements.values()].flat());
  for(let index=node.inputs.length-1;index>=0;index--){
   const input=node.inputs[index];
   if(dynamicName.test(input.name)&&!keep.has(input)){
    if(node.removeInput)node.removeInput(index);else node.inputs.splice(index,1);
   }
  }
  for(const inputs of replacements.values())for(const input of inputs)if(!node.inputs.includes(input)){
   if(node.addInput)node.addInput(input.name,input.type,input);else node.inputs.push(input);
  }
  for(let index=0;index<node.inputs.length;index++){const input=node.inputs[index],link=input.link!=null?getLink(graph,input.link):null;if(link&&same(link.target_id,node.id))link.target_slot=index;}
  node._setConcreteSlots?.();node.setDirtyCanvas?.(true,true);
 } finally {node.h3rcContracting=false;}
}

export function scheduleSocketSync(node,after){
 const revision=node.h3rcSocketRevision=(node.h3rcSocketRevision||0)+1;
 // Native Autogrow captures a slot index for its next animation frame. Do not
 // shift slots in a setTimeout before that callback, or keep nonzero ordinals.
 requestAnimationFrame(()=>requestAnimationFrame(()=>{
  if(revision!==node.h3rcSocketRevision||!node.graph)return;
  contractEmptySockets(node);refreshSocketLabels(node);after?.();
 }));
}

export function refreshSocketLabels(node,resolved={}){
 for(const input of node.inputs||[]){
  const name=input.name.split('.').pop();if(!dynamicName.test(input.name))continue;
  const link=input.link!=null?getLink(node.graph,input.link):null;
  const source=link&&same(link.target_id,node.id)?node.graph?.getNodeById(link.origin_id):null;
  const settings=Object.fromEntries((source?.widgets||[]).map(w=>[w.name,w.value]));
  let label;
  if(name.startsWith('reference_')){
   const tag=String(settings.tag||'').trim().replace(/^@+/,'').toLowerCase();
   label=source&&tag?'@'+tag:'named reference';
  }else if(name.startsWith('character_')){
   const tag=source?.h3rcCharacter?.alias||source?.h3rcAlias;
   label=tag?'@'+String(tag).replace(/^@/,''):'character';
  }else label=name.startsWith('ref_video_audio_')?'video soundtrack '+(Number(name.split('_').pop())+1):name.startsWith('ref_image_')?'image':name.startsWith('ref_video_')?'video':'audio';
  if(source&&resolved[name]&&(!label.startsWith('@')||resolved[name].startsWith(label+' / ')||resolved[name]===label))label=resolved[name]+(name.startsWith('ref_video_audio_')?' - video soundtrack':'');
  input.label=label;
 }
 node.graph?.setDirtyCanvas(true,true);
}
