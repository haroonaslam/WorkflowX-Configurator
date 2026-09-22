// Invalid saved widget values must never prevent opening the chooser.
export function readSelection(value, characterId) {
 const empty=()=>({character_id:characterId,modes:{}});
 try {
  const data=JSON.parse(value||'{}');
  if(!data||typeof data!=='object'||Array.isArray(data))throw Error();
  if(data.character_id!==characterId)return {draft:empty(),reset:false};
  if(!data.modes||typeof data.modes!=='object'||Array.isArray(data.modes))throw Error();
  for(const c of Object.values(data.modes)){
   if(!c||!Array.isArray(c.selected)||!Array.isArray(c.order)||!c.defaults||typeof c.defaults!=='object'||Array.isArray(c.defaults)||!c.overrides||typeof c.overrides!=='object'||Array.isArray(c.overrides))throw Error();
  }
  return {draft:data,reset:false};
 } catch {return {draft:empty(),reset:true};}
}
