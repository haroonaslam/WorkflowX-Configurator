if (location.protocol === 'file:') {
  const main = document.createElement('main');
  const heading = document.createElement('h1'); heading.textContent = 'Launch Image Prompt Library';
  const text = document.createElement('p'); text.textContent = 'This HTML file is not the running app. Open the WorkflowX folder in File Explorer and double-click Launch Image Prompt Library.cmd, or run this command in PowerShell:';
  const command = document.createElement('pre');
  const launcher = decodeURIComponent(new URL('../../Launch Image Prompt Library.cmd', location.href).pathname).replace(/^\/(\w:)/, '$1').replaceAll('/', '\\');
  command.textContent = `& '${launcher.replaceAll("'", "''")}'`;
  const note = document.createElement('p'); note.textContent = 'The launcher opens an http://127.0.0.1 address with the server, styles, and image library ready.';
  main.append(heading, text, command, note); document.body.replaceChildren(main);
} else {
const $ = id => document.getElementById(id);
let token = location.hash.slice(1) || sessionStorage.getItem('library-token') || '';
sessionStorage.setItem('library-token', token);
history.replaceState(null, '', '/');
let page = 0, review = false, currentGroup = null, galleryPage = 0, editing = null, picker = null, requestNumber = 0;
let scanState = 'idle', searchTimer, blacklisted = false, blacklistBusy = false, blacklistDetail = null;
let duplicateIndex = 0, duplicateData = null, duplicatePair = null, duplicatePollBusy = false, duplicateRenderKey = '';
async function api(path, body) {
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers: {'X-Library-Token': token, 'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function notice(message) { $('notice').textContent = message; }
function safe(action) { return async () => { try { await action(); } catch (error) { notice(error.message); alertInDialog(error.message); } }; }
function alertInDialog(message) { if (document.querySelector('dialog[open]')) window.alert(message); }
function el(tag, text, cls) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; }
function button(text, action, cls) { const node = el('button', text, cls); node.onclick = safe(action); return node; }
function image(id, full = false) { const node = el('img'); node.src = `/api/${full ? 'image' : 'thumbnail'}?id=${id}&token=${encodeURIComponent(token)}`; node.loading = 'lazy'; node.alt = 'Generated image'; node.onerror = () => { node.alt = 'Preview unavailable'; }; return node; }
async function copy(text, trigger) {
  try { await navigator.clipboard.writeText(text); }
  catch { const field = el('textarea'); field.value = text; (document.querySelector('dialog[open]') || document.body).append(field); field.select(); const ok = document.execCommand('copy'); field.remove(); if (!ok) throw new Error('Clipboard unavailable. Select and copy the displayed prompt.'); }
  const previous = trigger.textContent; trigger.textContent = 'Copied'; setTimeout(() => trigger.textContent = previous, 1300);
}
async function load() {
  const request = ++requestNumber;
  const data = await api(blacklisted ? `/api/blacklist?q=${encodeURIComponent($('search').value)}&page=${page}` : `/api/prompts?q=${encodeURIComponent($('search').value)}&page=${page}&review=${review ? 1 : 0}`);
  if (request !== requestNumber) return;
  if (page > 0 && page * 60 >= data.total) { page = Math.max(0, Math.ceil(data.total / 60) - 1); return load(); }
  $('grid').replaceChildren();
  if (data.counts) $('counts').textContent = `${Object.values(data.counts).reduce((a,b) => a+b,0)} images indexed · ${data.counts.review || 0} need review · ${data.counts.ignored || 0} without metadata skipped · ${data.counts.dismissed || 0} ignored \u00b7 ${data.counts.blacklisted || 0} blacklisted`;
  if (data.counts) $('review').textContent = `Needs review (${data.counts.review || 0})`;
  for (const item of data.items) {
    const card = el('article', undefined, 'card'); if (item.id) card.append(image(item.id));
    const body = el('div', undefined, 'card-body');
    body.append(el('span', review ? 'NEEDS REVIEW' : `${item.count} IMAGE${item.count === 1 ? '' : 'S'}`, review ? 'badge warning' : 'badge'));
    body.append(el('p', item.positive || item.extraction?.issues.join(' · ') || 'No prompt recovered'));
    const row = el('div', undefined, 'row');
    if (blacklisted) { row.append(button('View prompt', () => { blacklistDetail = item; $('blacklist-full-text').textContent = item.positive; $('blacklist-detail').showModal(); }), button('Restore', () => restorePrompt(item))); }
    else if (review) row.append(button('Review extraction', () => openReview(item), 'primary'), button('Ignore', () => ignore(item)));
    else { const copyButton = button('Copy', () => copy(item.positive, copyButton)); row.append(copyButton, button('View all images', () => openGallery(item), 'primary'), button('Blacklist', () => blacklistPrompt(item)));  }
    body.append(row); card.append(body); $('grid').append(card);
  }
  if (!data.items.length) $('grid').append(el('div', blacklisted ? 'No blacklisted prompts.' : review ? 'Nothing needs review.' : 'No prompts found. Scan an image or folder to get started.', 'empty'));
  $('pages').textContent = `${data.total} ${review ? 'images' : 'unique prompts'} · Page ${page+1} of ${Math.max(1,Math.ceil(data.total/60))}`;
  $('previous').disabled = page === 0; $('next').disabled = (page+1)*60 >= data.total;
}
async function openGallery(item) { currentGroup = item; galleryPage = 0; $('gallery').showModal(); await loadGallery(); }
async function loadGallery() {
  const data = await api(`/api/images?group=${currentGroup.group_id}&page=${galleryPage}`);
  $('gallery-title').textContent = 'Images using this prompt'; $('gallery-count').textContent = `${data.total} images · Page ${galleryPage+1}`;
  $('full-prompt').textContent = currentGroup.positive; $('gallery-grid').replaceChildren();
  for (const item of data.items) {
    const article = el('article'); const preview = image(item.id); preview.onclick = () => window.open(`/api/image?id=${item.id}&token=${encodeURIComponent(token)}`, '_blank', 'noopener');
    article.append(preview, el('p', item.path, 'muted'));
    if (item.missing) article.append(el('p', 'Original missing. Restore the source and rescan.', 'warning'));
    if (item.correction !== null) article.append(el('p', 'Manually corrected prompt', 'badge'));
    article.append(button('Rescan source folder', async () => { await api('/api/scan', {path:item.folder, recursive:false}); $('path').value = item.folder; $('gallery').close(); await poll(); }));
    const details = el('details'); details.append(el('summary', 'Generation and extraction details'), el('pre', JSON.stringify(item.extraction, null, 2))); article.append(details); $('gallery-grid').append(article);
  }
  $('gallery-prev').disabled = galleryPage === 0; $('gallery-next').disabled = (galleryPage+1)*60 >= data.total;
}
function openReview(item) {
  editing = item; $('review-image').src = image(item.id).src; $('review-path').textContent = item.path;
  $('issues').replaceChildren(...item.extraction.issues.map(issue => el('li', issue)));
  $('correction').value = item.positive; $('evidence').textContent = JSON.stringify(item.extraction, null, 2); $('editor').showModal();
}
async function ignore(item) {
  const result = await api('/api/ignore', {id: item.id});
  if ($('editor').open && editing?.id === item.id) $('editor').close();
  notice(`Ignored ${result.ignored_count} image${result.ignored_count === 1 ? '' : 's'}. These entries stay out of Needs review unless their source files change.`);
  await load();
}
async function browse(path) {
  picker = await api(`/api/browse${path ? '?path='+encodeURIComponent(path) : ''}`); $('picker-path').value = picker.path;
  $('files').replaceChildren(...picker.items.map(item => button((item.folder ? 'Folder · ' : 'Image · ') + item.name, () => { if (item.folder) return browse(item.path); $('path').value = item.path; $('picker').close(); }, item.folder ? 'file folder' : 'file')));
  if (!$('picker').open) $('picker').showModal();
}
async function poll() {
  try {
    if ($('duplicates').open) await pollDuplicates();
    const job = await api('/api/scan');
    $('progress').textContent = job.state === 'idle' ? 'Ready to scan' : `${job.state} · ${job.processed} read · ${job.updated} updated · ${job.skipped} unchanged`;
    $('cancel').hidden = job.state !== 'running'; $('scan').disabled = job.state === 'running';
    $('errors').textContent = job.errors.length ? job.errors.map(e => `${e.path}\n${e.error}`).join('\n\n') : 'No file errors. Images with incomplete prompts appear in Needs review.';
    if (scanState === 'running' || job.state !== scanState) await load(); scanState = job.state;
  } catch (error) { notice(error.message); }
}
$('scan').onclick = safe(async () => { if (!$('path').value.trim()) throw new Error('Choose an image or folder first'); await api('/api/scan', {path: $('path').value.trim(), recursive: $('recursive').checked}); notice(''); await poll(); });
$('cancel').onclick = safe(() => api('/api/cancel', {}));
$('browse').onclick = safe(() => browse()); $('picker-go').onclick = safe(() => browse($('picker-path').value)); $('picker-up').onclick = safe(() => browse(picker.parent));
$('choose-folder').onclick = () => { $('path').value = picker.path; $('picker').close(); };
for (const name of ['gallery', 'editor', 'picker', 'duplicates', 'blacklist-detail']) $(`close-${name}`).onclick = () => $(name).close();
$('library').onclick = safe(async () => { blacklisted = false; $('blacklist-tab').classList.remove('active'); review = false; page = 0; $('library').classList.add('active'); $('review').classList.remove('active'); await load(); });
$('review').onclick = safe(async () => { blacklisted = false; $('blacklist-tab').classList.remove('active'); review = true; page = 0; $('review').classList.add('active'); $('library').classList.remove('active'); await load(); });
$('search').oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(safe(async () => { page = 0; await load(); }), 200); };
$('previous').onclick = safe(async () => { page--; await load(); }); $('next').onclick = safe(async () => { page++; await load(); });
$('gallery-prev').onclick = safe(async () => { galleryPage--; await loadGallery(); }); $('gallery-next').onclick = safe(async () => { galleryPage++; await loadGallery(); });
$('copy-gallery').onclick = safe(() => copy(currentGroup.positive, $('copy-gallery')));
$('save-correction').onclick = safe(async () => { const result = await api('/api/correct', {id: editing.id, text: $('correction').value}); $('editor').close(); notice(`Accepted ${result.accepted_count} image${result.accepted_count === 1 ? '' : 's'} into this prompt group.`); await load(); });
$('ignore-review').onclick = safe(() => ignore(editing));

async function restorePrompt(item) {
  const result = await api('/api/blacklist/restore', {group: item.group_id});
  $('blacklist-detail').close(); notice(`Restored blacklist rule for ${result.restored_count} images; previous review and ignore decisions are preserved.`);
  await load();
}
async function blacklistPrompt(item, keep = null) {
  if (blacklistBusy) return;
  blacklistBusy = true;
  const payload = {group: item.group_id};
  if (keep) Object.assign(payload, {keep: keep.group_id, job_id: duplicateData?.id, revision: duplicateData?.revision});
  for (const id of ['keep-left', 'keep-right', 'blacklist-gallery']) $(id).disabled = true;
  try {
    const result = await api('/api/blacklist', payload);
    if ($('gallery').open && currentGroup.group_id === item.group_id) $('gallery').close();
    notice(`Blacklisted ${result.blacklisted_count} images. Restore this prompt from Blacklist.`);
    duplicateRenderKey = ''; await load();
  } finally {
    blacklistBusy = false;
    $('blacklist-gallery').disabled = false;
    for (const id of ['keep-left', 'keep-right']) $(id).disabled = blacklistBusy || !duplicatePair;
  }
  if ($('duplicates').open) { await pollDuplicates(); await pollDuplicates(); }
}
async function pollDuplicates() {
  if (duplicatePollBusy) return;
  duplicatePollBusy = true;
  try {
    const data = await api(`/api/duplicates?page=${Math.floor(duplicateIndex / 20)}`);
    duplicateData = data;
    const running = data.state === 'running';
    $('detect').disabled = running; $('cancel-duplicates').hidden = !running;
    $('similarity').disabled = running; $('similarity-number').disabled = running;
    $('duplicate-status').textContent = data.state === 'complete'
      ? `${data.matches} matching pairs at ${data.threshold}% or above \u00b7 ${data.matches ? 'Pair '+(Math.min(duplicateIndex, data.matches-1)+1)+' of '+data.matches : 'No matches found'}`
      : data.state === 'running' ? `Comparing prompts \u00b7 ${data.processed} / ${data.total} pairs checked`
      : data.state === 'stale' ? 'Library changed. Run detection again to refresh suggestions.'
      : data.state === 'error' ? `Detection failed: ${data.error}`
      : data.state === 'cancelled' ? 'Detection cancelled. Run again when ready.'
      : 'Compare all visible Library prompts. Nothing is removed automatically.';
    if (data.state === 'complete' && duplicateIndex >= data.matches && duplicateIndex > 0) {
      duplicateIndex = Math.max(0, data.matches-1); duplicateRenderKey = ''; return;
    }
    duplicatePair = data.items[duplicateIndex % 20] || null;
    for (const id of ['keep-left', 'keep-right']) $(id).disabled = blacklistBusy || !duplicatePair;
    $('pair-prev').disabled = !duplicatePair || duplicateIndex === 0;
    $('pair-next').disabled = !duplicatePair || duplicateIndex+1 >= data.matches;
    const key = `${data.id}:${data.revision}:${data.state}:${duplicateIndex}`;
    if (key !== duplicateRenderKey) {
      duplicateRenderKey = key; $('duplicate-pair').replaceChildren();
      if (duplicatePair) {
        $('duplicate-pair').append(el('p', `${duplicatePair.score.toFixed(2)}% text similarity \u00b7 highlighted text differs`, 'badge'));
        const columns = el('div', undefined, 'compare-columns');
        for (const [index, item] of [duplicatePair.left, duplicatePair.right].entries()) {
          const column = el('section'); column.append(el('h3', `${index === 0 ? 'Left' : 'Right'} \u00b7 ${item.count} images`), image(item.id));
          const row = el('div', undefined, 'row'); const copyButton = button('Copy', () => copy(item.positive, copyButton));
          row.append(copyButton, button('View images', () => openGallery(item))); column.append(row);
          const text = el('pre');
          for (const part of duplicatePair.differences[index]) text.append(el(part.changed ? 'mark' : 'span', part.text));
          column.append(text); columns.append(column);
        }
        $('duplicate-pair').append(columns);
      }
    }
  } finally { duplicatePollBusy = false; }
}
$('blacklist-tab').onclick = safe(async () => { blacklisted = true; review = false; page = 0; $('library').classList.remove('active'); $('review').classList.remove('active'); $('blacklist-tab').classList.add('active'); await load(); });
$('restore-detail').onclick = safe(() => restorePrompt(blacklistDetail));
$('blacklist-gallery').onclick = safe(() => blacklistPrompt(currentGroup));
$('open-duplicates').onclick = safe(async () => {
  const settings = await api('/api/settings'); $('similarity').value = settings.threshold; $('similarity-number').value = settings.threshold;
  $('duplicates').showModal(); await pollDuplicates();
});
for (const [source, target] of [['similarity', 'similarity-number'], ['similarity-number', 'similarity']]) {
  $(source).oninput = () => { $(target).value = $(source).value; };
  $(source).onchange = safe(async () => { await api('/api/settings', {threshold: Number($(source).value)}); });
}
$('detect').onclick = safe(async () => { duplicateIndex = 0; duplicateRenderKey = ''; await api('/api/duplicates', {threshold: Number($('similarity-number').value)}); await pollDuplicates(); });
$('cancel-duplicates').onclick = safe(async () => { await api('/api/duplicates/cancel', {}); await pollDuplicates(); });
$('pair-prev').onclick = safe(async () => { duplicateIndex--; await pollDuplicates(); });
$('pair-next').onclick = safe(async () => { duplicateIndex++; await pollDuplicates(); });
$('keep-left').onclick = safe(async () => { if (duplicatePair) await blacklistPrompt(duplicatePair.right, duplicatePair.left); });
$('keep-right').onclick = safe(async () => { if (duplicatePair) await blacklistPrompt(duplicatePair.left, duplicatePair.right); });

$('quit').onclick = safe(async () => { await api('/api/quit', {}); clearInterval(timer); notice('App stopped. You can close this tab.'); });
const timer = setInterval(poll, 1800);
load().catch(error => notice(error.message)); poll();
}
