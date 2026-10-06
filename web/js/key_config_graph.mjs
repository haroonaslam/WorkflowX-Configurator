export const INACTIVE_MODES = new Set([2, 4]);

export function canonicalGroupName(value) {
  return String(value ?? "").normalize("NFKC").trim().toLowerCase();
}

export function graphNodes(graph) {
  return graph?.nodes ?? graph?._nodes ?? [];
}

export function graphGroups(graph) {
  return graph?._groups ?? graph?.groups ?? [];
}

export function groupTitle(group) {
  return String(group?.title ?? "").trim();
}

function graphLabel(graph, fallback = "Subgraph") {
  const label = String(graph?.name ?? graph?.title ?? fallback).trim() || fallback;
  return label.replace(/^Canvas\s*\/\s*/i, "");
}

function graphIdentity(graph) {
  const persistentId = graph?.uuid ?? graph?.id;
  return persistentId === undefined || persistentId === null || String(persistentId) === ""
    ? graph
    : `graph:${String(persistentId)}`;
}

function rectFrom(item) {
  const bounding = item?.bounding;
  if (Array.isArray(bounding) && bounding.length >= 4) {
    return { x: Number(bounding[0]), y: Number(bounding[1]), w: Number(bounding[2]), h: Number(bounding[3]) };
  }
  const [x, y] = item?.pos ?? [0, 0];
  const [w, h] = item?.size ?? [0, 0];
  return { x: Number(x), y: Number(y), w: Number(w), h: Number(h) };
}

export function intersects(first, second) {
  const a = rectFrom(first);
  const b = rectFrom(second);
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function logicalGraphs(rootGraph) {
  const records = [];
  const seen = new Set();

  function visit(graph, path) {
    const identity = graphIdentity(graph);
    if (!graph || seen.has(identity)) return;
    seen.add(identity);
    records.push({ graph, path, isRoot: graph === rootGraph });
    for (const node of graphNodes(graph)) {
      if (node?.subgraph) visit(node.subgraph, [...path, graphLabel(node.subgraph, node.title ?? node.type)]);
    }
  }

  visit(rootGraph, []);
  return records;
}

export function buildGraphInventory(rootGraph) {
  const graphs = logicalGraphs(rootGraph);
  const groups = [];
  const names = new Map();

  for (const graphRecord of graphs) {
    for (const group of graphGroups(graphRecord.graph)) {
      const name = groupTitle(group);
      if (!name) continue;
      const record = {
        ...graphRecord,
        group,
        name,
        canonicalName: canonicalGroupName(name),
        location: [...graphRecord.path, name].join(" / "),
      };
      groups.push(record);
      const matches = names.get(record.canonicalName) ?? [];
      matches.push(record);
      names.set(record.canonicalName, matches);
    }
  }

  const duplicateGroups = [...names.values()].filter((matches) => matches.length > 1);
  const instances = [];
  const cycles = [];

  function expand(graph, prefix, depth, ancestors, stack) {
    const identity = graphIdentity(graph);
    if (stack.has(identity)) {
      cycles.push(prefix || "Canvas");
      return;
    }
    const nextStack = new Set(stack);
    nextStack.add(identity);
    const localGroups = graphGroups(graph);
    for (const node of graphNodes(graph)) {
      const localId = String(node?.id ?? "");
      if (!localId) continue;
      const executionId = prefix ? `${prefix}:${localId}` : localId;
      const containingGroups = localGroups
        .map((group) => ({ group, name: groupTitle(group) }))
        .filter(({ name, group }) => name && intersects(node, group));
      const record = {
        node,
        graph,
        localId,
        executionId,
        depth,
        isRoot: depth === 0,
        ancestors,
        containingGroups,
      };
      instances.push(record);
      if (node?.subgraph) expand(node.subgraph, executionId, depth + 1, [...ancestors, record], nextStack);
    }
  }

  expand(rootGraph, "", 0, [], new Set());
  return { graphs, groups, duplicateGroups, instances, cycles };
}

export function describeDuplicateGroups(duplicates) {
  return duplicates.map((matches) => `${matches[0].name}: ${matches.map((item) => item.location).join(", ")}`);
}

export function effectiveRecordState(record, modes, recursive = true) {
  if (record.ancestors.some((ancestor) => effectiveRecordState(ancestor, modes, recursive).inactive)) {
    return { inactive: true, controlledGroups: [] };
  }

  const controlledGroups = recursive || record.isRoot
    ? record.containingGroups.filter(
        ({ name }) => Object.hasOwn(modes ?? {}, name) && modes[name] !== "Ignore",
      )
    : [];
  if (controlledGroups.length > 1) return { inactive: false, controlledGroups, overlap: true };
  if (controlledGroups.length === 1) {
    return {
      inactive: modes[controlledGroups[0].name] !== "Active",
      controlledGroups,
      overlap: false,
    };
  }
  return { inactive: INACTIVE_MODES.has(Number(record.node?.mode ?? 0)), controlledGroups, overlap: false };
}

export function candidateTier(record, modes, recursive = true) {
  const state = effectiveRecordState(record, modes, recursive);
  if (state.inactive) return null;
  if (!record.isRoot) return 2;
  return state.controlledGroups.length ? 1 : 0;
}

export function resolveCandidates(candidates, family, key) {
  const tiers = [0, 1, 2].map((tier) => candidates.filter((candidate) => candidate.tier === tier));
  const winningTier = tiers.findIndex((items) => items.length > 0);
  if (winningTier < 0) return { candidate: null, warnings: [] };
  const winners = tiers[winningTier];
  if (winners.length > 1) {
    const locations = winners
      .map((item) => {
        const groups = item.groupLocations ?? item.groupNames ?? [];
        return groups.length ? `${item.executionId} [${groups.join(", ")}]` : item.executionId;
      })
      .join(", ");
    throw new Error(`Multiple active ${family} Sets found for key "${key}" at tier ${winningTier + 1}: ${locations}. Leave only one active Set at this tier.`);
  }
  const warnings = [];
  for (let tier = winningTier + 1; tier < tiers.length; tier += 1) {
    if (tiers[tier].length > 1) {
      warnings.push(`Shadowed ${family} key "${key}" has ${tiers[tier].length} active Sets at tier ${tier + 1}.`);
    }
  }
  return { candidate: winners[0], warnings };
}

export function applyModeToNamedGroup(inventory, groupName, mode, skipNode = () => false) {
  let changed = 0;
  for (const record of inventory.groups) {
    if (record.name !== groupName) continue;
    for (const node of graphNodes(record.graph)) {
      if (skipNode(node) || !intersects(node, record.group)) continue;
      if (node.mode === mode) continue;
      node.mode = mode;
      node.setDirtyCanvas?.(true, true);
      changed += 1;
    }
  }
  return changed;
}
