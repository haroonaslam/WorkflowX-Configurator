// Queue only the editor target, its downstream nodes, and dependencies they need.
export function editorQueue(output, id, action, gap) {
  id = String(id);
  if (!output[id]) throw Error('Enable this node before using the Segment editor.');
  const prompt = {...output, [id]: action === 'finalize'
    ? {class_type:'WorkflowXAuKSegmentFinalize',inputs:{gap_seconds:gap}}
    : {...output[id],class_type:'WorkflowXAuKChainedCloneReviewStep'}};
  const dependencies = data => Object.values(data.inputs ?? {}).filter(v => Array.isArray(v) && v.length === 2 && typeof v[1] === 'number' && prompt[String(v[0])]).map(v => String(v[0]));
  const targets = new Set([id]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const [key, data] of Object.entries(prompt)) {
      if (!targets.has(key) && dependencies(data).some(dep => targets.has(dep))) {targets.add(key); changed = true;}
    }
  }
  const needed = new Set(targets), pending = [...targets];
  while (pending.length) for (const dep of dependencies(prompt[pending.pop()])) {
    if (!needed.has(dep)) {needed.add(dep); pending.push(dep);}
  }
  return {prompt:Object.fromEntries(Object.entries(prompt).filter(([key]) => needed.has(key))), targets:[...targets]};
}

export function insertSourceLine(text, sourceIndex, raw, expectedCount) {
  if (!raw.trim() || /[\r\n]/.test(raw)) throw Error('Enter exactly one nonblank line.');
  const rows=text.split('\n'), nonblank=rows.map((s,i)=>s.trim()?i:-1).filter(i=>i>=0);
  if(nonblank.length!==expectedCount || sourceIndex==null || nonblank[sourceIndex]==null) throw Error('The source structure changed. Start a full Run before adding lines.');
  rows.splice(nonblank[sourceIndex]+1,0,raw);
  return rows.join('\n');
}
