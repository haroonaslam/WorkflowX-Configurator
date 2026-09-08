import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { mountVoiceControls } from "./voice_changer_x_controls.mjs";
import { migrateVoiceWorkflow, runReferenceMatch } from "./voice_changer_x_matching.mjs";

app.registerExtension({
  name: "WorkflowX.VoiceChangerX",
  beforeConfigureGraph(graph) { migrateVoiceWorkflow(graph); },
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "WorkflowX_VoiceChangerX") return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function (...args) {
      const result = created?.apply(this, args);
      mountVoiceControls(this, nodeData.input.required, (node, cancelled) => runReferenceMatch(app, api, node, cancelled));
      return result;
    };
  },
});
