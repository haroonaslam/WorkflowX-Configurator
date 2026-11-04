/** Shared dock shell for every native BBox schema.
 *
 * The caller supplies the WorkflowX dock factory so this module stays
 * independent of ComfyUI globals. Native parsing and serialization remain in
 * unified_bbox_adapters.mjs; the editor itself always works with neutral
 * regions.
 */
export function createSharedBBoxDock({ createDockWindow, node, onClose }) {
  const dock = createDockWindow(node, "ideogram", "BBox layout editor X", {
    height: 470,
    matchNodeWidth: true,
  });
  dock.dock.__workflowXOnClose = onClose;
  return dock;
}
