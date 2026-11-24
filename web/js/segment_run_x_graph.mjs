// Present active execution modes to ComfyUI's compiler without writing canvas state.
export function segmentExecutionGraph(root) {
  const graphs = new WeakMap();
  const nodes = new WeakMap();

  function graphView(graph) {
    if (!graph) return graph;
    if (graphs.has(graph)) return graphs.get(graph);
    const view = new Proxy(graph, {
      get(target, key, receiver) {
        if (key === "computeExecutionOrder") {
          return (...args) => target.computeExecutionOrder(...args).map(nodeView);
        }
        if (key === "serialize") return target.serialize.bind(target);
        if (key === "getNodeById") return (id) => nodeView(target.getNodeById(id));
        if (key === "nodes" || key === "_nodes") return (target[key] ?? []).map(nodeView);
        if (key === "rootGraph") return graphView(target.rootGraph);
        return Reflect.get(target, key, receiver);
      },
    });
    graphs.set(graph, view);
    return view;
  }

  function nodeView(node) {
    if (!node) return node;
    if (nodes.has(node)) return nodes.get(node);
    const view = new Proxy(node, {
      get(target, key, receiver) {
        if (key === "mode") return 0;
        if (key === "graph" || key === "subgraph" || key === "rootGraph") return graphView(target[key]);
        if (key === "resolveVirtualOutput" && target.resolveVirtualOutput) {
          return (...args) => {
            const source = target.resolveVirtualOutput.apply(receiver, args);
            return source ? { ...source, node: nodeView(source.node) } : source;
          };
        }
        return Reflect.get(target, key, receiver);
      },
      set(target, key, value, receiver) {
        if (key === "mode") return true;
        return Reflect.set(target, key, value, receiver);
      },
    });
    nodes.set(node, view);
    return view;
  }

  return graphView(root);
}
