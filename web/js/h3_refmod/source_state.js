// Opening the editor never replaces serialized selections. Save selection commits the draft.
export function readSourceSelection(value) {
 const warning='The saved source selection could not be read completely. Review the sources below, then Save selection to replace it. Cancel leaves the saved settings unchanged.';
 let parsed=value;
 if(value===undefined||value==='')return {entries:[],warning:''};
 if(typeof value==='string'){
  try{parsed=JSON.parse(value);}catch{return {entries:[],warning};}
 }
 if(!Array.isArray(parsed))return {entries:[],warning};
 const entries=parsed.filter(e=>e&&typeof e==='object'&&!Array.isArray(e)&&typeof e.source==='string'&&e.source.trim());
 return {entries:entries.map(e=>({...e})),warning:entries.length===parsed.length?'':warning};
}
