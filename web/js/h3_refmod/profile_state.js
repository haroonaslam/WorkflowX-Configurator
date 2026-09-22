export function readProfileSettings(value) {
 let data;
 try{data=typeof value==='string'?JSON.parse(value):value;}catch{return null;}
 if(!data||typeof data!=='object'||Array.isArray(data))return null;
 for(const group of ['picture','video','combined']){
  if(!Array.isArray(data[group]))return null;
  if(data[group].some(p=>!p||typeof p!=='object'||Array.isArray(p)||typeof p.id!=='string'||typeof p.name!=='string'||!Number.isInteger(p.size)||p.size<0))return null;
 }
 return data;
}
