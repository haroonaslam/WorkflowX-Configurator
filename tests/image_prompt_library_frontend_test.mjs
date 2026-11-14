import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

test('opening the HTML file shows the launcher command without starting app APIs', () => {
  const makeElement = tag => ({tag, children: [], textContent: '', append(...nodes) { this.children.push(...nodes); }});
  const body = {children: [], replaceChildren(...nodes) { this.children = nodes; }};
  const context = {
    URL,
    location: {protocol: 'file:', href: 'file:///D:/My%20Apps/WorkflowX/image_prompt_library/static/index.html'},
    document: {body, createElement: makeElement},
    fetch() { throw new Error('File mode must not call HTTP APIs'); },
  };
  vm.runInNewContext(fs.readFileSync(new URL('../image_prompt_library/static/app.js', import.meta.url), 'utf8'), context);
  assert.equal(body.children.length, 1);
  const text = body.children[0].children.map(node => node.textContent).join('\n');
  assert.match(text, /This HTML file is not the running app/);
  assert.ok(text.includes("& 'D:\\My Apps\\WorkflowX\\Launch Image Prompt Library.cmd'"));
  assert.match(text, /http:\/\/127\.0\.0\.1/);
});


test('blacklist applies directly for cards, galleries and duplicate pairs without a confirmation dialog', async () => {
  const source = fs.readFileSync(new URL('../image_prompt_library/static/app.js', import.meta.url), 'utf8');
  const action = source.slice(source.indexOf('async function blacklistPrompt('), source.indexOf('async function pollDuplicates('));
  for (const mode of ['card', 'gallery', 'duplicates']) {
    const requests = [];
    const nodes = new Map();
    const context = {
      blacklistBusy: false, duplicateData: {id:'job', revision:7}, duplicatePair: {},
      currentGroup: {group_id:'remove'}, duplicateRenderKey:'old',
      $(id) {
        if (!nodes.has(id)) nodes.set(id, {disabled:false, open: mode === id,
          close() { this.open = false; }, showModal() { throw new Error('Unexpected confirmation dialog'); }});
        return nodes.get(id);
      },
      async api(path, body) { requests.push({path,body}); return {blacklisted_count:3}; },
      notice(message) { context.message = message; },
      async load() { context.loaded = true; },
      async pollDuplicates() { context.polled = true; },
    };
    vm.createContext(context); vm.runInContext(action, context);
    await context.blacklistPrompt({group_id:'remove'}, mode === 'duplicates' ? {group_id:'keep'} : null);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].path, '/api/blacklist');
    assert.equal(requests[0].body.group, 'remove');
    assert.equal(requests[0].body.keep, mode === 'duplicates' ? 'keep' : undefined);
    assert.ok(context.loaded);
    assert.match(context.message, /Restore this prompt from Blacklist/);
    if (mode === 'gallery') assert.equal(nodes.get('gallery').open, false);
    if (mode === 'duplicates') assert.ok(context.polled);
    assert.equal(context.blacklistBusy, false);
  }
});
