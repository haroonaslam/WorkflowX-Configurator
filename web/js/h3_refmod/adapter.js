import { app } from '../../../scripts/app.js';
app.registerExtension({name:'WorkflowX.RefModXAdapter',beforeRegisterNodeDef(NodeType,data){
 if(data.name!=='RefModXAdapter')return;
 const created=NodeType.prototype.onNodeCreated;
 NodeType.prototype.onNodeCreated=function(){created?.apply(this,arguments);const node=this;
  const update=()=>{const video=node.widgets.find(w=>w.name==='compatibility_mode')?.value==='Video frames';
   for(const input of node.inputs||[])if(input.name==='vae'){input.label=video?'vae':'vae (unused)';input.tooltip='Full H3 visual VAE; used only to decode Video frames.';}
   if(node.outputs?.[0])node.outputs[0].label=video?'reference frames':'reference frames (inactive)';
   if(node.outputs?.[1])node.outputs[1].label=video?'refmods (inactive)':'refmods';
   node.setDirtyCanvas?.(true,true);
  };
  const mode=node.widgets.find(w=>w.name==='compatibility_mode'),changed=mode.callback;
  mode.callback=function(){changed?.apply(this,arguments);update();};
  const configured=node.onConfigure;node.onConfigure=function(){configured?.apply(this,arguments);update();};update();
 };
}});
