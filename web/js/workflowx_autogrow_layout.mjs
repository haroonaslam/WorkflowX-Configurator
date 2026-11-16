export function installAutogrowLayoutHooks(proto) {
  const getInputLink = proto.getInputLink;
  if (getInputLink) {
    proto.getInputLink = function (slot) {
      // Native Autogrow can compact inputs on the frame after graph teardown.
      return this.graph ? getInputLink.call(this, slot) : null;
    };
  }
  const connectionsChange = proto.onConnectionsChange;
  proto.onConnectionsChange = function (direction, _slot, connected) {
    const graph = this.graph;
    const height = this.size?.[1];
    const preserveHeight = graph && direction === globalThis.LiteGraph?.INPUT && !connected
      && height > this.computeSize()[1];
    const result = connectionsChange?.apply(this, arguments);
    if (preserveHeight) {
      // Run after native Autogrow's deferred compaction.
      queueMicrotask(() => requestAnimationFrame(() => {
        if (this.graph !== graph || this.size[1] >= height || this.size[1] !== this.computeSize()[1]) return;
        this.setSize([this.size[0], height]);
        graph.setDirtyCanvas?.(true, true);
      }));
    }
    return result;
  };
}
