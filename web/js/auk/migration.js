import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

// Restore older browser-local workflows only when standalone AuK is absent.
// When upstream AuK is installed, its workflows keep their original node IDs.
const original = await api.fetchApi('/object_info/AuKModelLoader').then(r => r.json());
const names = ['AuKModelLoader','AuKEncoderLoader','AuKVAELoader','AuKInstructionEncode','AuKGenerateEdit','AuKInstructionBuilder','AuKWhisperTranscribe','AuKPromptEnhance','AuKChainedClone','AuKChainedCloneReviewStep'];
const ids = Object.fromEntries(names.map(name => [name, 'WorkflowX' + name]));
const ports = {AUK_MODEL:'WORKFLOWX_AUK_MODEL', AUK_ENCODER:'WORKFLOWX_AUK_ENCODER'};
app.registerExtension({
  name:'WorkflowX.AuK.Migration',
  beforeConfigureGraph(graph) {
    if (original.AuKModelLoader) return;
    for (const node of graph.nodes ?? []) {
      if (!ids[node.type]) continue;
      node.type = ids[node.type];
      for (const socket of [...(node.inputs ?? []), ...(node.outputs ?? [])]) socket.type = ports[socket.type] ?? socket.type;
      node.properties ??= {};
      node.properties['Node name for S&R'] = node.type;
      node.properties.cnr_id = 'workflowx-configurator';
      delete node.properties.ver;
      delete node.properties.auk_review_id;
    }
    for (const link of graph.links ?? []) {
      if (Array.isArray(link)) link[5] = ports[link[5]] ?? link[5];
      else link.type = ports[link.type] ?? link.type;
    }
  },
});
