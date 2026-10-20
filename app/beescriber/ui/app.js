/* BeeScriber UI. Talks to Python through window.pywebview.api; Python pushes events through BS.onEvents(). */
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
let LANG = 'en', APP = {}, SET = {}, FORMATS = [], MODELS = [];
const S = {
  cols: [],              // loaded collections: {type,id,title,channel,entries:[...],both,input}
  sel: new Set(),        // selected item keys
  jobs: new Map(),       // active jobs by id
  order: [],             // active job ids in queue order
  state: null,           // queue state from Python
  engine: {status: 'idle'},
  hist: [], histSel: new Set(),
  pv: {id: null, title: '', segs: [], draft: [], duration: null, live: false},
  tab: 'list', pausing: false, gpu: null,
};

/* ---------------------------------------------------------------- helpers */
function t(k, ...a) {
  let s = (I18N[LANG] && I18N[LANG][k] != null) ? I18N[LANG][k] : (I18N.en[k] != null ? I18N.en[k] : k);
  a.forEach((x, i) => { s = s.split('{' + i + '}').join(String(x)); });
  return s;
}
function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}
function api(name, ...args) {
  return window.pywebview.api[name](...args).then(r => {
    if (r && typeof r === 'object' && !Array.isArray(r) && r.error) throw r;
    return r;
  });
}
function errText(e) {
  if (!e) return t('e_unknown');
  const code = e.error || e.code || 'unknown';
  const s = t('e_' + code);
  return s === 'e_' + code ? t('e_unknown') + (e.detail ? '\n' + String(e.detail).slice(-300) : '') : s;
}
function toast(msg, kind, ms) {
  const d = el('div', {class: 'toast' + (kind ? ' ' + kind : ''), text: msg});
  $('#toasts').append(d);
  setTimeout(() => d.remove(), ms || (kind === 'err' ? 9000 : 4500));
}
function dur(sec) {
  if (sec == null || isNaN(sec)) return '–';
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
}
function eta(sec) {
  if (sec == null || !isFinite(sec)) return '–';
  sec = Math.round(sec);
  if (sec < 60) return `${sec} s`;
  const m = Math.round(sec / 60);
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}
const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const keyOf = it => it.video_id ? 'yt:' + it.video_id : (it.kind === 'file' ? 'f:' + String(it.source).toLowerCase() : it.source);

/* ---------------------------------------------------------------- i18n */
function applyI18n() {
  document.documentElement.lang = LANG;
  $$('[data-t]').forEach(e => { e.textContent = t(e.dataset.t); });
  $$('[data-tp]').forEach(e => { e.placeholder = t(e.dataset.tp); });
  $$('[data-tt]').forEach(e => { e.title = t(e.dataset.tt); });
  syncMaxIcon();
  $$('.lang button').forEach(b => b.classList.toggle('act', b.dataset.lang === LANG));
  fillLanguages();
  renderAll();
}
function fillLanguages() {
  const s = $('#language'), cur = SET.language || 'auto';
  s.innerHTML = '';
  s.append(el('option', {value: 'auto', text: t('lang_auto')}));
  for (const [k, v] of Object.entries(LANG_NAMES)) s.append(el('option', {value: k, text: v}));
  s.value = cur;
}

/* ---------------------------------------------------------------- settings */
function save(changes) {
  Object.assign(SET, changes);
  return api('save_settings', changes).then(s => { SET = s; renderSettings(); }).catch(e => toast(errText(e), 'err'));
}
function renderSettings() {
  $('#outDir').textContent = SET.output_dir_effective || SET.output_dir || '–';
  const chips = $('#fmtChips');
  chips.innerHTML = '';
  for (const f of FORMATS) {
    const on = (SET.formats || []).includes(f);
    chips.append(el('span', {class: 'chipT' + (on ? ' on' : ''), text: f.toUpperCase(), onclick: () => {
      let list = (SET.formats || []).slice();
      list = on ? list.filter(x => x !== f) : list.concat(f);
      if (!list.length) return;                       // at least one format
      save({formats: FORMATS.filter(x => list.includes(x))});
    }}));
  }
  $('#txtMode').value = SET.txt_mode;
  $('#tsSw').checked = !!SET.timestamps;
  $('#hdrSw').checked = !!SET.txt_header;
  $('#clipSw').checked = !!SET.clipboard_watch;
  $('#gpuLimit').value = String(SET.gpu_limit || 100);
  $('#diarSw').checked = !!SET.diarize;
  $('#spkF').hidden = !SET.diarize;
  $('#spkN').value = String(SET.speakers || 0);
  $('#plSw').checked = !!SET.playlist_subfolder;
  $('#nameTpl').value = SET.name_template || '';
  $('#plNameTpl').value = SET.playlist_name_template || '';
  const m = $('#model');
  if (!m.options.length) MODELS.forEach(x => m.append(el('option', {value: x, text: x})));
  m.value = SET.model;
  $('#customModel').value = SET.custom_model || '';
  $('#language').value = SET.language || 'auto';
  $('#device').value = SET.device || 'auto';
  $('#guardSw').checked = !!SET.punct_guard;
  $('#ckMode').value = SET.cookies_mode || 'none';
  $('#ckBrowser').value = SET.cookies_browser || 'firefox';
  $('#ckFile').textContent = SET.cookies_file || '–';
  $('#ckBrowser').hidden = SET.cookies_mode !== 'browser';
  $('#ckFileF').hidden = SET.cookies_mode !== 'file';
  $('#pauseAfterSw').checked = !!SET.pause_after_video;
}
function bindSettings() {
  $('#txtMode').onchange = e => save({txt_mode: e.target.value});
  $('#tsSw').onchange = e => save({timestamps: e.target.checked});
  $('#hdrSw').onchange = e => save({txt_header: e.target.checked});
  $('#clipSw').onchange = e => save({clipboard_watch: e.target.checked});
  $('#gpuLimit').onchange = e => save({gpu_limit: parseInt(e.target.value, 10)});
  $('#spkN').onchange = e => save({speakers: parseInt(e.target.value, 10)});
  $('#diarSetup').onclick = () => diarDialog(false);
  $('#diarSw').onchange = e => {
    if (!e.target.checked) return save({diarize: false});
    e.target.checked = false;
    api('diar_status').then(st => { if (st.installed && st.has_token) save({diarize: true}); else diarDialog(true); });
  };
  $('#plSw').onchange = e => save({playlist_subfolder: e.target.checked});
  $('#nameTpl').onchange = e => save({name_template: e.target.value.trim() || '{title}'});
  $('#plNameTpl').onchange = e => save({playlist_name_template: e.target.value.trim() || '{index:03} - {title}'});
  $('#model').onchange = e => save({model: e.target.value});
  $('#customModel').onchange = e => save({custom_model: e.target.value.trim()});
  $('#language').onchange = e => save({language: e.target.value});
  $('#device').onchange = e => save({device: e.target.value});
  $('#guardSw').onchange = e => save({punct_guard: e.target.checked});
  $('#ckMode').onchange = e => save({cookies_mode: e.target.value});
  $('#ckBrowser').onchange = e => save({cookies_browser: e.target.value});
  $('#pauseAfterSw').onchange = e => save({pause_after_video: e.target.checked});
  $('#outPick').onclick = () => api('pick_folder', SET.output_dir_effective || '').then(p => { if (p) save({output_dir: p}); });
  $('#outOpen').onclick = () => api('open_folder', null);
  $('#ckPick').onclick = () => api('pick_cookie_file').then(p => { if (p) save({cookies_file: p, cookies_mode: 'file'}); });
  $('#updBtn').onclick = () => {
    const b = $('#updBtn'); b.disabled = true; b.textContent = t('updating');
    api('update_ytdlp').then(r => { toast('yt-dlp ' + r.version, 'ok'); loadVersions(); })
      .catch(e => toast(errText(e), 'err')).finally(() => { b.disabled = false; b.textContent = t('updYt'); });
  };
}
function loadVersions() {
  api('tool_versions').then(v => {
    S.gpu = v.gpu;
    const parts = [`yt-dlp ${v['yt-dlp'] || '–'}`, `ffmpeg ${v.ffmpeg || '–'}`, `deno ${v.deno || '–'}`,
      `faster-whisper ${v.faster_whisper || '–'}`];
    if (v.gpu) parts.push(`${v.gpu.name}`);
    $('#toolVers').textContent = parts.join(' · ');
    renderStatus();
  }).catch(() => { $('#toolVers').textContent = '–'; });
}

/* ---------------------------------------------------------------- loading sources */
function loadSources(text, asVideo) {
  text = (text != null ? text : $('#src').value).trim();
  if (!text) return;
  const b = $('#loadBtn');
  S.loading = (S.loading || 0) + 1;
  S.loadingText = text.split('\n')[0];
  b.disabled = true; b.innerHTML = ''; b.append(el('span', {class: 'spin'}), t('loading'));
  showTab('list'); renderList();
  return api('load_input', text, !!asVideo).then(addResult).catch(e => toast(errText(e), 'err'))
    .finally(() => {
      S.loading = Math.max(0, S.loading - 1);
      if (!S.loading) { b.disabled = false; b.textContent = t('load'); }
      renderList();
    });
}
function loadingRow() {
  return el('div', {class: 'loadrow'}, el('span', {class: 'spin big'}),
    el('div', {}, el('b', {text: t('loadingList')}), el('div', {class: 'hint', text: S.loadingText || ''})));
}
function addResult(r) {
  for (const er of r.errors || []) toast(`${er.input}\n${errText(er)}`, 'err');
  let added = 0;
  for (const c of r.collections || []) {
    if (c.type === 'files') {                        // files go into one shared collection
      let fc = S.cols.find(x => x.type === 'files');
      if (!fc) { fc = {type: 'files', id: null, title: null, entries: []}; S.cols.push(fc); }
      const have = new Set(fc.entries.map(keyOf));
      for (const e of c.entries) if (!have.has(keyOf(e))) { fc.entries.push(e); preselect(e); added++; }
      continue;
    }
    S.cols = S.cols.filter(x => !(x.id && x.id === c.id && x.type === c.type));
    S.cols.push(c);
    c.entries.forEach(preselect);
    added += c.entries.length;
  }
  if (!added && !(r.errors || []).length) toast(t('noneLoaded'));
  showTab('list');
  renderList();
}
function preselect(e) {
  if (e.status === 'ok' && !e.in_queue && !(SET.skip_done && e.done_before)) S.sel.add(keyOf(e));
}
function visible(e) {
  const f = norm($('#flt').value);
  return !f || norm(e.title).includes(f) || norm(e.channel).includes(f);
}
function selectable(e) { return e.status === 'ok' && !e.in_queue; }
function renderList() {
  const box = $('#listBox');
  const total = S.cols.reduce((n, c) => n + c.entries.length, 0);
  $('#cntList').textContent = total;
  $('#listBar').hidden = $('#listFoot').hidden = !total;
  box.innerHTML = '';
  if (S.loading) box.append(loadingRow());
  if (!total) {
    if (!S.loading) box.append(el('div', {class: 'empty', text: t('listEmpty')}));
    updateSelInfo();
    return;
  }
  for (const c of S.cols) {
    const sum = c.entries.reduce((n, e) => n + (e.duration || 0), 0);
    const head = el('div', {class: 'colhead'},
      el('span', {class: 'grow', style: 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap',
        text: c.type === 'files' ? t('addFiles').replace('…', '') : (c.title || c.input || '')}),
      el('span', {class: 'muted', text: [c.channel, t('videos', c.entries.length), dur(sum)].filter(Boolean).join(' · ')}),
      el('button', {class: 'ib x', type: 'button', title: t('clearList'), text: '✕', onclick: () => {
        c.entries.forEach(e => S.sel.delete(keyOf(e))); S.cols = S.cols.filter(x => x !== c); renderList(); }}));
    box.append(head);
    if (c.both) {
      box.append(el('div', {class: 'note', style: 'margin:8px 14px'}, t('bothNote') + ' ',
        el('button', {class: 'btn xs', type: 'button', text: t('onlyVideo'), onclick: () => {
          S.cols = S.cols.filter(x => x !== c); loadSources(c.input, true); }})));
    }
    const tb = el('table', {class: 'items'});
    for (const e of c.entries) {
      if (!visible(e)) continue;
      const k = keyOf(e), can = selectable(e);
      const cb = el('input', {type: 'checkbox', disabled: !can});
      cb.checked = can && S.sel.has(k);
      cb.onchange = () => { cb.checked ? S.sel.add(k) : S.sel.delete(k); updateSelInfo(); };
      const badges = el('td', {class: 'bd'});
      if (e.status !== 'ok') badges.append(el('span', {class: 'badge bad', text: t('b_' + e.status)}));
      else if (e.in_queue) badges.append(el('span', {class: 'badge q', text: t('b_queue')}));
      else if (e.done_before) badges.append(el('span', {class: 'badge done', text: '✓ ' + t('b_done')}));
      const tr = el('tr', {class: can ? '' : 'off'},
        el('td', {class: 'ck'}, cb), el('td', {class: 'ix', text: c.type === 'playlist' ? e.index : ''}),
        el('td', {title: e.title, text: e.title}), el('td', {class: 'du', text: dur(e.duration)}), badges);
      tr.onclick = ev => { if (ev.target !== cb && can) { cb.checked = !cb.checked; cb.onchange(); } };
      tb.append(tr);
    }
    box.append(tb);
  }
  updateSelInfo();
}
function selectedItems() {
  const out = [];
  for (const c of S.cols) {
    const items = c.entries.filter(e => selectable(e) && S.sel.has(keyOf(e)));
    if (items.length) out.push({col: c, items});
  }
  return out;
}
function updateSelInfo() {
  let n = 0, d = 0;
  for (const g of selectedItems()) for (const e of g.items) { n++; d += e.duration || 0; }
  $('#selInfo').textContent = t('selected', n, dur(d));
  $('#addQ').disabled = $('#addGo').disabled = !n;
}
function setSel(fn) {
  for (const c of S.cols) for (const e of c.entries) {
    if (!visible(e) || !selectable(e)) continue;
    fn(e) ? S.sel.add(keyOf(e)) : S.sel.delete(keyOf(e));
  }
  renderList();
}
async function enqueueSelected(start) {
  const groups = selectedItems();
  if (!groups.length) return toast(t('nothingSel'));
  let n = 0;
  try {
    for (const g of groups) {
      const meta = g.col.type === 'playlist' ? {type: 'playlist', id: g.col.id, title: g.col.title} : null;
      const r = await api('enqueue', g.items, meta, false);
      n += r.ids.length;
      g.items.forEach(e => { e.in_queue = true; S.sel.delete(keyOf(e)); });
      setJobs(r.jobs, r.state);
    }
    toast(n ? t('added', n) : t('addedNone'), n ? 'ok' : '');
    if (start && n) await api('start').then(st => { S.state = st; renderStatus(); });
  } catch (e) { toast(errText(e), 'err'); }
  renderList();
}

/* ---------------------------------------------------------------- queue */
function setJobs(list, state) {
  S.jobs = new Map(list.map(j => [j.id, j]));
  S.order = list.map(j => j.id);
  if (state) S.state = state;
  const run = list.find(j => j.status === 'running');
  if (run && S.pv.id !== run.id) startPreview(run);
  renderQueue();
  renderStatus();
}
function upsertJob(j) {
  if (j.status === 'done') {
    S.jobs.delete(j.id); S.order = S.order.filter(x => x !== j.id);
    loadHistory();
    const k = keyOf(j);
    let hit = false;
    for (const c of S.cols) for (const e of c.entries) if (keyOf(e) === k) { e.done_before = true; e.in_queue = false; hit = true; }
    if (hit) renderList();
  } else {
    if (!S.jobs.has(j.id)) S.order.push(j.id);
    S.jobs.set(j.id, j);
  }
  if (j.status === 'running' && S.pv.id !== j.id) startPreview(j);
  if (S.pv.id === j.id) { S.pv.live = j.status === 'running'; renderPvHead(); }
  renderQueueItem(j);
  renderQueueHead();
}
function jobEl(j) {
  const frac = j.duration ? Math.min(1, (j.pos || 0) / j.duration) : 0;
  const acts = el('span', {class: 'acts'});
  const b = (txt, title, fn, cls) => el('button', {class: 'ib' + (cls ? ' ' + cls : ''), type: 'button', title, text: txt,
    onclick: ev => { ev.stopPropagation(); fn(); }});
  if (j.status === 'error') acts.append(b('↻', t('jRetry'), () => api('job_resume', j.id)));
  if (j.status === 'paused') acts.append(b('▶', t('jResume'), () => api('job_resume', j.id)));
  if (j.status === 'queued' || j.status === 'running') acts.append(b('❚❚', t('jPause'), () => api('job_pause', j.id)));
  if (j.status !== 'running') acts.append(b('⤒', t('jTop'), () => moveJob(j.id, 0)));
  acts.append(b('✕', t('jRemove'), () => api('job_remove', [j.id]), 'x'));
  const meta = [dur(j.duration)];
  if (j.pos > 0 && j.status !== 'running') meta.push(`${Math.round(frac * 100)}%`);
  if (j.lang) meta.push(j.lang);
  const node = el('div', {class: 'job ' + j.status, 'data-id': j.id, draggable: j.status !== 'running' ? 'true' : null},
    el('div', {class: 'jt'}, el('span', {class: 'handle', text: '⋮⋮'}), el('b', {title: j.title || j.source, text: j.title || j.source})),
    el('div', {class: 'jm'}, el('span', {class: 'st', text: t('s_' + j.status)}), el('span', {text: meta.join(' · ')}), acts),
    (j.status === 'running' || j.pos > 0) ? el('div', {class: 'pbar'}, el('i', {style: `width:${(frac * 100).toFixed(1)}%`})) : null,
    j.status === 'error' ? el('div', {class: 'jerr', text: errText({error: j.error_code, detail: j.error})}) : null);
  node.onclick = () => { if (S.pv.id !== j.id) startPreview(j); showTab('preview'); };
  bindDrag(node, j);
  return node;
}
function renderQueueItem(j) {
  const list = $('#qList');
  const old = list.querySelector(`.job[data-id="${j.id}"]`);
  if (!S.jobs.has(j.id)) { if (old) old.remove(); }
  else if (old) old.replaceWith(jobEl(j));
  else list.append(jobEl(j));
  $('#qEmpty').hidden = S.jobs.size > 0;
}
function renderQueue() {
  const list = $('#qList');
  list.innerHTML = '';
  for (const id of S.order) { const j = S.jobs.get(id); if (j) list.append(jobEl(j)); }
  $('#qEmpty').hidden = S.jobs.size > 0;
  renderQueueHead();
}
function renderQueueHead() {
  const jobs = S.order.map(id => S.jobs.get(id)).filter(Boolean);
  const total = jobs.reduce((n, j) => n + (j.duration || 0), 0);
  const done = jobs.reduce((n, j) => n + Math.min(j.pos || 0, j.duration || 0), 0);
  $('#qCount').textContent = jobs.length ? `(${jobs.length})` : '';
  $('#qBar').style.width = total ? `${(done / total * 100).toFixed(1)}%` : '0';
  const st = S.state || {};
  $('#qInfo').textContent = jobs.length ? t('qLeft', dur(total - done), st.speed ? eta((total - done) / st.speed) : '–') : '';
  const unfinished = jobs.filter(j => j.status === 'queued' && j.pos > 0).length;
  $('#qUnfinished').hidden = !(unfinished && !(st.running));
  $('#qUnfinished').textContent = t('unfinished', unfinished);
  $('#retryAll').hidden = !jobs.some(j => j.status === 'error');
  $('#clearQ').hidden = !jobs.some(j => j.status !== 'running');
}
function moveJob(id, idx) {
  api('job_move', id, idx).then(order => {
    S.order = order; renderQueue();
  });
}
let dragId = null;
function bindDrag(node, j) {
  node.addEventListener('dragstart', e => { dragId = j.id; node.classList.add('drag'); e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/x-job', String(j.id)); });
  node.addEventListener('dragend', () => { dragId = null; node.classList.remove('drag'); $$('.job.over').forEach(x => x.classList.remove('over')); });
  node.addEventListener('dragover', e => { if (dragId != null && dragId !== j.id) { e.preventDefault(); node.classList.add('over'); } });
  node.addEventListener('dragleave', () => node.classList.remove('over'));
  node.addEventListener('drop', e => {
    if (dragId == null) return;
    e.preventDefault(); e.stopPropagation(); node.classList.remove('over');
    moveJob(dragId, S.order.indexOf(j.id));
  });
}

/* ---------------------------------------------------------------- header status */
function renderStatus() {
  const st = S.state || {}, eng = S.engine || {};
  const running = !!st.running || st.current != null;
  const queued = S.order.map(id => S.jobs.get(id)).filter(j => j && j.status === 'queued');
  const go = $('#goBtn');
  go.textContent = queued.some(j => j.pos > 0) ? t('resume') : t('start');
  go.disabled = running || !queued.length;
  const pb = $('#pauseBtn');
  pb.disabled = !running;
  pb.textContent = S.pausing && running ? t('pausing') : t('pause');
  if (!running) S.pausing = false;
  // the header box shows only the load meters; engine notes appear under the queue progress
  const box = $('#statbox'), line = $('#state');
  let s = '', cls = '';
  if (eng.status === 'error') { s = t('stEngineErr'); cls = 'err'; }
  else if (eng.status === 'model_download') s = t('stDownloadModel') + (eng.total ? ` ${Math.floor(eng.done / eng.total * 100)}%` : '');
  else if (eng.status === 'loading' || eng.status === 'model_load') s = t('stLoading');
  else if ((APP.missing || []).length) { s = t('stNoTools'); cls = 'warn'; }
  line.textContent = s;
  line.className = 'state' + (cls ? ' ' + cls : '');
  line.hidden = !s;
  const tip = [];
  if (S.gpu) tip.push(S.gpu.name);
  if (eng.info) tip.push(`${eng.info.model} · ${eng.info.device} / ${eng.info.compute}`);
  if (st.speed && running) tip.push(`${t('stWorking')} · ${Math.round(st.speed)}×`);
  box.title = tip.join('\n');
}

/* ---------------------------------------------------------------- live preview */
function startPreview(j) {
  S.pv = {id: j.id, title: j.title || j.source, segs: [], draft: [], duration: j.duration, pos: j.pos || 0,
    live: j.status === 'running', speed: null, lang: j.lang, redo: 0, full: '', shown: 0};
  renderPvHead();
  renderPvText();
  const id = j.id;
  const loader = j.status === 'done' ? Promise.resolve(null) : api('job_text', id);
  loader.then(segs => { if (segs && segs.length && S.pv.id === id && !S.pv.segs.length) { S.pv.segs = segs; pvUpdate(true); } })
    .catch(() => {});
}
function showDoneText(h) {
  S.pv = {id: h.id, title: h.title, segs: [], draft: [], duration: h.duration, pos: h.duration, live: false, lang: h.lang,
    full: '', shown: 0};
  renderPvHead();
  renderPvText();
  showTab('preview');
  api('job_text', h.id).then(segs => { if (S.pv.id === h.id) { S.pv.segs = segs || []; pvUpdate(true); } });
}
function renderPvHead() {
  const p = S.pv;
  $('#pvTitle').textContent = p.id ? p.title : '–';
  $('#pvBar').style.width = p.duration ? `${Math.min(100, (p.pos || 0) / p.duration * 100).toFixed(1)}%` : '0';
  const meta = [];
  if (p.id) meta.push(`${dur(p.pos)} / ${dur(p.duration)}`);
  if (p.live && p.speed) meta.push(t('speed', p.speed));
  if (p.live && p.eta != null) meta.push(t('left', eta(p.eta)));
  if (p.lang) meta.push(t('lang', LANG_NAMES[p.lang] || p.lang));
  if (p.redo) meta.push(`${t('redo')}: ${p.redo}`);
  if (p.extra) meta.push(p.extra);
  $('#pvMeta').textContent = meta.join(' · ');
}
function paraBreak(prev, seg, curLen) {
  if (!prev) return false;
  const ended = /[.!?…]["”’)\]]*$/.test(prev.text.trim());
  return ended && ((seg.start - prev.end) >= 1.4 || curLen > 650);
}
/* The preview "types" the text at the pace it arrives: new text is revealed gradually (faster when more is
   waiting), and the view glides down instead of jumping. Grey = still being worked on (may change a little). */
function pvCompose() {
  const p = S.pv;
  let out = '', len = 0, prev = null;
  const add = s => {
    const txt = String(s.text || '').trim();
    if (!txt) return;
    if (prev && paraBreak(prev, s, len)) { out += '\n\n'; len = 0; } else if (out) out += ' ';
    out += txt; len += txt.length; prev = s;
  };
  p.segs.forEach(add);
  const commitLen = out.length;
  p.draft.forEach(add);
  return {text: out, commitLen};
}
function pvUpdate(instant) {
  const p = S.pv, c = pvCompose(), old = p.full || '';
  let lcp = 0;
  const lim = Math.min(p.shown || 0, c.text.length, old.length);
  while (lcp < lim && old.charCodeAt(lcp) === c.text.charCodeAt(lcp)) lcp++;
  p.full = c.text; p.commitLen = c.commitLen;
  p.shown = instant ? c.text.length : lcp;
  if (instant) { pvRender(); pvJump(); }
  pvKick();
}
let pvRaf = null, pvLast = 0, pvGliding = false, pvAuto = false;
function pvKick() { if (!pvRaf) { pvLast = performance.now(); pvRaf = requestAnimationFrame(pvTick); } }
function pvTick(now) {
  const p = S.pv, dt = Math.min(0.1, (now - pvLast) / 1000);
  pvLast = now;
  const backlog = (p.full || '').length - (p.shown || 0);
  if (backlog > 0) {
    const rate = Math.max(40, backlog / 1.5);          // drains what is waiting in ~1.5 s, never slower than 40 char/s
    p.carry = (p.carry || 0) + rate * dt;
    const n = Math.floor(p.carry);
    if (n > 0) { p.carry -= n; p.shown = Math.min(p.full.length, p.shown + n); pvRender(); }
  }
  pvGlide(dt);
  pvRaf = (backlog > 0 || pvGliding) ? requestAnimationFrame(pvTick) : null;
}
function pvRender() {
  const box = $('#pvText'), p = S.pv;
  if (!p.id || !p.full) {
    box.innerHTML = ''; p._els = [];
    box.append(el('div', {class: 'empty', text: t('pvEmpty')}));
    return;
  }
  const empty = box.querySelector('.empty');
  if (empty) empty.remove();
  const paras = p.full.slice(0, p.shown).split('\n\n');
  p._els = p._els || [];
  let off = 0;
  paras.forEach((txt, i) => {
    const c = Math.max(0, Math.min(txt.length, p.commitLen - off));
    const key = c + '|' + txt;
    let e = p._els[i];
    if (!e) { e = el('p'); box.append(e); p._els[i] = e; }
    if (e._k !== key) {
      e._k = key; e.textContent = '';
      e.append(document.createTextNode(txt.slice(0, c)));
      if (c < txt.length) e.append(el('span', {class: 'draft', text: txt.slice(c)}));
    }
    off += txt.length + 2;
  });
  while (p._els.length > paras.length) p._els.pop().remove();
}
function renderPvText() {                             // full redraw (new job, language change)
  const p = S.pv;
  $('#pvText').innerHTML = ''; p._els = [];
  if (p.full == null) { p.full = ''; p.shown = 0; }
  pvRender();
}
function pvGlide(dt) {
  const b = $('#pvText');
  if (!$('#pvFollow').checked) { pvGliding = false; return; }
  const d = b.scrollHeight - b.clientHeight - b.scrollTop;
  if (d > 1) { pvAuto = true; b.scrollTop += Math.max(1, d * Math.min(1, dt * 5)); pvGliding = true; }
  else pvGliding = false;
}
function pvJump() { if ($('#pvFollow').checked) { const b = $('#pvText'); pvAuto = true; b.scrollTop = b.scrollHeight; } }
function bindPreviewScroll() {
  const b = $('#pvText');
  b.addEventListener('wheel', e => { if (e.deltaY < 0) $('#pvFollow').checked = false; }, {passive: true});
  b.addEventListener('scroll', () => {
    if (pvAuto) { pvAuto = false; return; }
    if (b.scrollHeight - b.clientHeight - b.scrollTop < 24) $('#pvFollow').checked = true;
  });
  $('#pvFollow').addEventListener('change', () => { if ($('#pvFollow').checked) pvKick(); });
}

/* ---------------------------------------------------------------- history */
let histTimer = null;
function loadHistory() {
  clearTimeout(histTimer);
  histTimer = setTimeout(() => api('history').then(h => { S.hist = h; renderHistory(); }), 300);
}
function renderHistory() {
  $('#cntHist').textContent = S.hist.length;
  const box = $('#histBox');
  box.innerHTML = '';
  const f = norm($('#hFlt').value);
  const rows = S.hist.filter(h => !f || norm(h.title).includes(f) || norm(h.channel).includes(f) || norm(h.playlist_title).includes(f));
  if (!rows.length) { box.append(el('div', {class: 'empty', text: t('hEmpty')})); }
  else {
    const tb = el('table', {class: 'hist'});
    for (const h of rows) {
      const cb = el('input', {type: 'checkbox'});
      cb.checked = S.histSel.has(h.id);
      cb.onchange = () => { cb.checked ? S.histSel.add(h.id) : S.histSel.delete(h.id); $('#hDelSel').disabled = !S.histSel.size; };
      const fm = el('td', {class: 'fm'});
      for (const p of h.outputs || []) {
        const ext = p.split('.').pop().toUpperCase();
        fm.append(el('span', {class: 'fmt', title: p, text: ext, onclick: () => api('open_path', p)}));
      }
      const when = h.finished ? new Date(h.finished * 1000).toLocaleString(LANG === 'hu' ? 'hu-HU' : 'en-GB',
        {year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'}) : '';
      const title = el('td', {class: 'ttl', title: [h.title, h.playlist_title].filter(Boolean).join('\n')},
        el('a', {href: '#', text: h.title || h.source, onclick: e => { e.preventDefault(); showDoneText(h); }}));
      tb.append(el('tr', {}, el('td', {class: 'ck'}, cb), title, el('td', {class: 'when', text: when}),
        el('td', {class: 'du', text: dur(h.duration)}), fm,
        el('td', {class: 'ac'},
          el('button', {class: 'btn xs', type: 'button', text: t('folderBtn'), onclick: () => api('open_folder', (h.outputs || [])[0] || null)}), ' ',
          el('button', {class: 'btn xs', type: 'button', text: t('export'), onclick: () => exportDialog(h)}))));
    }
    box.append(tb);
  }
  $('#hDelSel').disabled = !S.histSel.size;
  $('#hDelAll').disabled = !S.hist.length;
}
function exportDialog(h) {
  const pick = new Set();
  const chips = el('div', {class: 'chips'});
  for (const f of FORMATS) {
    const c = el('span', {class: 'chipT', text: f.toUpperCase()});
    c.onclick = () => { pick.has(f) ? pick.delete(f) : pick.add(f); c.classList.toggle('on'); };
    chips.append(c);
  }
  modal(t('exportTitle'), el('div', {}, el('p', {text: h.title}), chips), [
    {label: t('cancel')},
    {label: t('exportDo'), cls: 'pri', fn: () => {
      if (!pick.size) return false;
      api('reexport', h.id, FORMATS.filter(f => pick.has(f))).then(out => {
        toast(t('exported', out.map(p => p.split(/[\\/]/).pop()).join(', ')), 'ok'); loadHistory(); })
        .catch(e => toast(errText(e), 'err'));
    }}]);
}
async function deleteHistory(ids) {
  const n = ids ? ids.length : S.hist.length;
  if (!n) return;
  if (!await confirmBox(t('hDelAll'), t('hDelConfirm', n))) return;
  api('delete_history', ids).then(() => { S.histSel.clear(); loadHistory(); refreshDoneFlags(); });
}
function refreshDoneFlags() {
  // ask Python again which loaded items are done / queued (after history changes)
  api('history').then(h => {
    const done = new Set(h.map(keyOf));
    for (const c of S.cols) for (const e of c.entries) e.done_before = done.has(keyOf(e));
    renderList();
  });
}

/* ---------------------------------------------------------------- dialogs */
function modal(title, body, buttons) {
  $('#modalTitle').textContent = title;
  const mb = $('#modalBody');
  mb.innerHTML = '';
  typeof body === 'string' ? (mb.innerHTML = body) : mb.append(body);
  const foot = $('#modalFoot');
  foot.innerHTML = '';
  foot.hidden = !buttons;
  for (const b of buttons || []) {
    foot.append(el('button', {class: 'btn' + (b.cls ? ' ' + b.cls : ''), type: 'button', text: b.label, onclick: () => {
      if (b.fn && b.fn() === false) return;
      closeModal();
    }}));
  }
  $('#modal').classList.add('open');
  mb.querySelectorAll('a[data-url]').forEach(a => a.onclick = e => { e.preventDefault(); api('open_url', a.dataset.url); });
}
function closeModal() { DIAR = null; $('#modal').classList.remove('open'); if (closeModal.resolve) { closeModal.resolve(false); closeModal.resolve = null; } }
function confirmBox(title, text) {
  return new Promise(res => {
    modal(title, el('p', {text}), [{label: t('cancel'), fn: () => { closeModal.resolve = null; res(false); }},
      {label: t('yes'), cls: 'stop', fn: () => { closeModal.resolve = null; res(true); }}]);
    closeModal.resolve = res;
  });
}
function about() {
  const html = ABOUT[LANG](APP.name).split('{VER}').join(APP.version).split('{COFFEE}').join(APP.coffee);
  modal(t('aboutTitle', APP.name), html, null);
}

/* ---------------------------------------------------------------- tabs */
function showTab(name) {
  S.tab = name;
  $$('.tab').forEach(b => b.classList.toggle('act', b.dataset.tab === name));
  for (const v of ['list', 'preview', 'history']) $('#v-' + v).hidden = v !== name;
  if (name === 'history') loadHistory();
  if (name === 'preview') { pvJump(); pvKick(); }
}
function renderAll() {
  renderSettings(); renderList(); renderQueue(); renderStatus(); renderPvHead(); renderPvText(); renderHistory();
  renderTools();
}

/* ---------------------------------------------------------------- tools */
function renderTools() {
  const miss = APP.missing || [];
  $('#toolsNote').hidden = !miss.length;
  $('#toolsText').textContent = t('toolsMissing', miss.join(', '));
}

/* ---------------------------------------------------------------- events from Python */
window.BS = {
  onEvents(batch) {
    let reQueue = false;
    for (const e of batch) {
      try { handle(e); } catch (err) { console.error(err, e); }
      if (e.ev === 'reordered') reQueue = true;
    }
    if (reQueue) renderQueue();
  },
};
function handle(e) {
  const p = S.pv;
  switch (e.ev) {
    case 'job': upsertJob(e.job); break;
    case 'removed': S.jobs.delete(e.id); S.order = S.order.filter(x => x !== e.id);
      renderQueueItem({id: e.id}); renderQueueHead(); renderStatus();
      for (const c of S.cols) for (const x of c.entries) x.in_queue = false;
      api('jobs').then(r => { const keys = new Set(r.jobs.map(keyOf));
        for (const c of S.cols) for (const x of c.entries) x.in_queue = keys.has(keyOf(x)); renderList(); });
      break;
    case 'reordered': S.order = e.order; break;
    case 'queue': S.state = e.state; renderStatus(); renderQueueHead();
      if (e.finished) toast(t('queueDone'), 'ok');
      break;
    case 'progress':
      S.state = e.state || S.state;
      { const j = S.jobs.get(e.id); if (j) { j.pos = e.pos; renderQueueItem(j); } }
      if (p.id === e.id) { p.pos = e.pos; p.speed = e.speed; p.eta = e.eta; renderPvHead(); }
      renderQueueHead(); renderStatus();
      break;
    // grey draft text is only ever replaced by newer text for the same time, so nothing jumps back and forth
    case 'redo': if (p.id === e.id) { p.redo = (p.redo || 0) + 1; renderPvHead(); } break;
    case 'draft': if (p.id === e.id) {
      // replace only the older grey pieces this one overlaps in time; later ones stay until they are redone
      p.draft = p.draft.filter(d => d.start < e.start - 0.01 || d.start >= e.end - 0.01);
      p.draft.push(e);
      p.draft.sort((a, b) => a.start - b.start);
      pvUpdate();
    } break;
    case 'accepted': if (p.id === e.id) {
      p.segs = p.segs.concat(e.segs);
      const end = e.segs.length ? e.segs[e.segs.length - 1].end : (p.segs.length ? p.segs[p.segs.length - 1].end : 0);
      p.draft = p.draft.filter(d => d.start >= end - 0.01);
      pvUpdate();
    } break;
    case 'resumed': if (p.id === e.id) { p.segs = e.segs; pvUpdate(true); } break;
    case 'language': if (p.id === e.id) { p.lang = e.lang; renderPvHead(); } break;
    case 'engine':
      S.engine = Object.assign({}, S.engine, {status: e.status});
      if (e.info) S.engine.info = e.info;
      if (e.status === 'model_download') { S.engine.done = e.done; S.engine.total = e.total; }
      if (e.status === 'ready') S.engine.status = 'ready';
      if (e.status === 'error') toast(t('stEngineErr') + ':\n' + String(e.error || '').slice(-500), 'err', 15000);
      renderStatus();
      break;
    case 'tools':
      if (e.status === 'progress') $('#toolsProg').textContent = `${e.name}: ${(e.got / 1e6).toFixed(0)}${e.total ? ' / ' + (e.total / 1e6).toFixed(0) : ''} MB`;
      else if (e.status === 'downloading') $('#toolsProg').textContent = e.name + '…';
      else if (e.status === 'error') { toast(`${e.name}: ${e.detail}`, 'err'); $('#toolsGet').disabled = false; }
      else if (e.status === 'done') { APP.missing = e.missing || []; renderTools(); renderStatus(); loadVersions();
        if (!APP.missing.length) toast(t('toolsDone'), 'ok'); $('#toolsGet').disabled = false; }
      break;
    case 'dropped': addResult(e.result); break;
    case 'addon':
      if (!DIAR) { if (e.status === 'done') toast(t('dInstalled'), 'ok'); if (e.status === 'error') toast(String(e.detail).slice(-400), 'err'); break; }
      if (e.status === 'progress') DIAR.s1msg.textContent = t('dInstalling', e.step, e.steps, e.line || e.label);
      else if (e.status === 'done') { DIAR.state = e.state; DIAR.s1msg.textContent = ''; DIAR.s1btn.replaceWith(el('div', {class: 'okline', text: t('dInstalled')})); }
      else if (e.status === 'error') { DIAR.s1msg.textContent = String(e.detail).slice(-400); DIAR.s1msg.className = 'hint errline'; DIAR.s1btn.disabled = false; }
      break;
    case 'speakers':
      if (e.status === 'running' && p.id === e.id) { p.extra = t('spkRunning'); renderPvHead(); }
      if (e.status === 'done' && p.id === e.id) { p.extra = t('spkDone', e.count); renderPvHead(); }
      if (e.status === 'error') toast(t('spkError'), 'err');
      if (e.status === 'unavailable' && !S.spkWarned) { S.spkWarned = true; toast(t('spkUnavailable'), 'err'); }
      break;
    case 'history': loadHistory(); break;
  }
}

/* ---------------------------------------------------------------- load meters */
function setMeter(id, pct, text) {
  const m = $(id);
  if (pct == null) { m.hidden = true; return; }
  m.hidden = false;
  m.querySelector('.mv').textContent = text;
  m.querySelector('b').style.width = Math.max(0, Math.min(100, pct)) + '%';
  m.classList.toggle('hot', pct >= 95);
}
function bindMeters() {
  const nf = new Intl.NumberFormat(LANG === 'hu' ? 'hu-HU' : 'en-GB', {maximumFractionDigits: 1, minimumFractionDigits: 1});
  const tick = () => {
    if (document.hidden) return;
    api('usage').then(u => {
      setMeter('#mGpu', u.gpu, u.gpu == null ? '' : u.gpu + '%');
      const vp = u.vram_total ? 100 * u.vram_used / u.vram_total : null;
      setMeter('#mVram', vp, vp == null ? '' : `${nf.format(u.vram_used / 1024)} / ${Math.round(u.vram_total / 1024)} GB`);
      setMeter('#mCpu', u.cpu, u.cpu == null ? '' : u.cpu + '%');
    }).catch(() => {});
  };
  tick();
  setInterval(tick, 2000);
}

/* ---------------------------------------------------------------- speaker add-on dialog */
let DIAR = null;                      // the open dialog's elements
function diarDialog(enableAfter) {
  api('diar_status').then(st => {
    const link = (url, text) => el('a', {href: '#', text, onclick: ev => { ev.preventDefault(); api('open_url', url); }});
    const s1 = el('div', {class: 'dstep'});
    const s1btn = el('button', {class: 'btn sm pri', type: 'button', text: t('dInstall')});
    const s1msg = el('div', {class: 'hint'});
    s1.append(el('h3', {text: t('dStep1')}), el('p', {class: 'hint', text: t('dStep1Text')}));
    if (st.installed) s1.append(el('div', {class: 'okline', text: t('dInstalled')}));
    else if (!st.can_install) s1.append(el('p', {text: t('dNotInstallable')}));
    else { s1.append(el('div', {class: 'row'}, s1btn), s1msg); }
    s1btn.onclick = () => { s1btn.disabled = true; s1msg.textContent = t('dInstalling', 1, 2, ''); api('diar_install'); };
    const s2 = el('div', {class: 'dstep'});
    const tok = el('input', {type: 'text', placeholder: t(st.has_token ? 'dTokenPhSaved' : 'dTokenPh'), spellcheck: 'false'});
    const chk = el('button', {class: 'btn sm', type: 'button', text: t('dCheck')});
    const s2msg = el('div', {class: st.has_token ? 'okline' : 'hint', text: st.has_token ? t('dHasToken') : ''});
    s2.append(el('h3', {text: t('dStep2')}), el('p', {class: 'hint', text: t('dStep2Text')}),
      el('ol', {}, el('li', {}, link(st.join_url, t('dLinkJoin'))), el('li', {}, link(st.model_url, t('dLinkModel'))),
        el('li', {}, link(st.token_url, t('dLinkToken')))),
      el('div', {class: 'row nw'}, tok, chk), s2msg);
    chk.onclick = () => {
      chk.disabled = true; chk.textContent = t('dChecking');
      api('diar_token', tok.value).then(r => {
        s2msg.textContent = r.ok ? t('dTokOk') : t('dTok_' + (r.code || 'unknown'));
        s2msg.className = r.ok ? 'okline' : 'hint errline';
        if (r.ok) { tok.value = ''; DIAR.state.has_token = true; }
        else if (r.code === 'terms') { tok.value = ''; }   // the token itself is saved; only "Agree" is missing
      }).finally(() => { chk.disabled = false; chk.textContent = t('dCheck'); });
    };
    DIAR = {s1, s1btn, s1msg, state: st};
    modal(t('dTitle'), el('div', {class: 'diar'}, s1, s2), [
      {label: t('close'), fn: () => { DIAR = null; }},
      {label: t('dEnable'), cls: 'pri', fn: () => {
        if (!(DIAR.state.installed && DIAR.state.has_token)) { toast(t('dNeedBoth')); return false; }
        save({diarize: true}); DIAR = null;
      }}]);
  });
}

/* ---------------------------------------------------------------- own window frame */
let WIN = {custom: false, max: false};
function syncMaxIcon() {
  const b = $('#wMax');
  if (!b) return;
  document.body.classList.toggle('maxed', WIN.max);
  b.title = t(WIN.max ? 'wRestore' : 'wMax');
  b.innerHTML = WIN.max
    ? '<svg viewBox="0 0 10 10"><rect x="1.5" y="3" width="5.5" height="5.5"/><path d="M3 3V1.5h5.5V7H7"/></svg>'
    : '<svg viewBox="0 0 10 10"><rect x="1.5" y="1.5" width="7" height="7"/></svg>';
}
function refreshWin() { return api('win_state').then(w => { WIN = w; syncMaxIcon(); }).catch(() => {}); }
function bindWindow() {
  refreshWin().then(() => {
    if (!WIN.custom) return;
    document.body.classList.add('framed');
    $('#winbtns').hidden = false;
  });
  const bar = $('#titlebar');
  const interactive = e => e.target.closest('button,a,input,select,textarea,.lang,.winbtns');
  bar.addEventListener('mousedown', e => { if (e.button === 0 && WIN.custom && !interactive(e) && e.detail === 1) api('win_drag'); });
  bar.addEventListener('dblclick', e => { if (WIN.custom && !interactive(e)) api('win_max').then(() => setTimeout(refreshWin, 250)); });
  $$('.edge').forEach(x => x.addEventListener('mousedown', e => { if (e.button === 0) { e.preventDefault(); api('win_resize', x.dataset.e); } }));
  $('#wMin').onclick = () => api('win_min');
  $('#wMax').onclick = () => api('win_max').then(() => setTimeout(refreshWin, 250));
  $('#wClose').onclick = () => api('win_close');
  window.addEventListener('resize', () => { clearTimeout(bindWindow.t); bindWindow.t = setTimeout(refreshWin, 200); });
}

/* ---------------------------------------------------------------- right-click menu (cut / copy / paste) */
let ctxTarget = null;
function bindContextMenu() {
  const menu = $('#ctx');
  document.addEventListener('contextmenu', e => {
    e.preventDefault();
    const field = e.target.closest('textarea, input[type=text], input[type=search], input:not([type])');
    const selText = String(getSelection() || '');
    if (!field && !selText) { menu.hidden = true; return; }
    ctxTarget = field;
    const hasSel = field ? field.selectionEnd > field.selectionStart : !!selText;
    menu.querySelector('[data-a=cut]').disabled = !field || !hasSel || field.readOnly;
    menu.querySelector('[data-a=copy]').disabled = !hasSel;
    menu.querySelector('[data-a=paste]').disabled = !field || field.readOnly;
    menu.querySelector('[data-a=all]').disabled = false;
    menu.hidden = false;
    const w = menu.offsetWidth, h = menu.offsetHeight;
    menu.style.left = Math.min(e.clientX, innerWidth - w - 6) + 'px';
    menu.style.top = Math.min(e.clientY, innerHeight - h - 6) + 'px';
  });
  document.addEventListener('mousedown', e => { if (!e.target.closest('#ctx')) menu.hidden = true; });
  window.addEventListener('blur', () => { menu.hidden = true; });
  menu.addEventListener('mousedown', e => e.preventDefault());   // keep the field's selection
  menu.addEventListener('click', async e => {
    const a = e.target.dataset.a;
    if (!a) return;
    menu.hidden = true;
    const f = ctxTarget;
    if (a === 'all') { if (f) { f.focus(); f.select(); } else { const r = document.createRange(); r.selectNodeContents($('#pvText')); getSelection().removeAllRanges(); getSelection().addRange(r); } return; }
    if (a === 'copy' || a === 'cut') {
      const txt = f ? f.value.slice(f.selectionStart, f.selectionEnd) : String(getSelection());
      await api('clipboard_set', txt);
      if (a === 'cut' && f) { f.setRangeText('', f.selectionStart, f.selectionEnd, 'end'); f.dispatchEvent(new Event('input', {bubbles: true})); f.dispatchEvent(new Event('change', {bubbles: true})); }
      return;
    }
    if (a === 'paste' && f) {
      const txt = await api('clipboard_get');
      f.focus();
      f.setRangeText(txt || '', f.selectionStart, f.selectionEnd, 'end');
      f.dispatchEvent(new Event('input', {bubbles: true}));
      f.dispatchEvent(new Event('change', {bubbles: true}));
    }
  });
}

/* ---------------------------------------------------------------- clipboard watch */
function loadedInputs() {
  const set = new Set();
  for (const c of S.cols) { if (c.input) set.add(c.input.trim()); if (c.id) set.add(c.id); }
  return set;
}
function bindClipboardWatch() {
  let busy = false;
  const check = () => {
    if (busy || !SET.clipboard_watch) return;
    busy = true;
    api('clipboard_link').then(link => {
      if (!link) return;
      const have = loadedInputs();
      const fresh = link.split('\n').filter(l => !have.has(l.trim()));
      if (!fresh.length) return;
      const src = $('#src');
      if (!src.value.includes(fresh[0])) src.value = (src.value.trim() ? src.value.trim() + '\n' : '') + fresh.join('\n');
      toast(t('clipLoaded'));
      return loadSources(fresh.join('\n'));
    }).catch(() => {}).finally(() => { busy = false; });
  };
  window.addEventListener('focus', check);
  setInterval(check, 1500);
  check();
}

/* ---------------------------------------------------------------- wiring */
function bind() {
  $$('.lang button').forEach(b => b.onclick = () => { LANG = b.dataset.lang; applyI18n(); save({ui_lang: LANG}); });
  $('#aboutBtn').onclick = about;
  $('#coffee').onclick = e => { e.preventDefault(); api('open_url', APP.coffee); };
  $('#modalClose').onclick = closeModal;
  $('#modal').onclick = e => { if (e.target.id === 'modal') closeModal(); };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
  $('#goBtn').onclick = () => api('start').then(st => { S.state = st; renderStatus(); showTab('preview'); });
  $('#pauseBtn').onclick = () => { S.pausing = true; renderStatus(); api('pause', true).then(st => { S.state = st; renderStatus(); }); };
  $('#loadBtn').onclick = () => loadSources();
  $('#src').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) loadSources(); });
  $('#filesBtn').onclick = () => api('pick_files').then(addResult).catch(e => toast(errText(e), 'err'));
  $('#flt').oninput = () => renderList();
  $('#selAll').onclick = () => setSel(() => true);
  $('#selNone').onclick = () => setSel(() => false);
  $('#selNew').onclick = () => setSel(e => !e.done_before);
  $('#clearList').onclick = () => { S.cols = []; S.sel.clear(); renderList(); };
  $('#addQ').onclick = () => enqueueSelected(false);
  $('#addGo').onclick = () => enqueueSelected(true);
  $$('.tab').forEach(b => b.onclick = () => showTab(b.dataset.tab));
  $('#pvCopy').onclick = () => {
    const txt = (S.pv.full || '').trim();
    if (!txt) return;
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(() => toast(t('copied'), 'ok'))
      .catch(() => { const r = document.createRange(); r.selectNodeContents($('#pvText'));
        const s = getSelection(); s.removeAllRanges(); s.addRange(r); document.execCommand('copy'); toast(t('copied'), 'ok'); });
  };
  $('#hFlt').oninput = () => renderHistory();
  $('#hDelSel').onclick = () => deleteHistory([...S.histSel]);
  $('#hDelAll').onclick = () => deleteHistory(null);
  $('#retryAll').onclick = () => api('retry_errors');
  $('#clearQ').onclick = async () => {
    const ids = S.order.filter(id => (S.jobs.get(id) || {}).status !== 'running');
    if (ids.length && await confirmBox(t('clearQueue'), `${t('clearQueue')}: ${ids.length}?`)) api('job_remove', ids);
  };
  $('#toolsGet').onclick = () => { $('#toolsGet').disabled = true; api('install_tools'); };
  // drop overlay (the files themselves are taken by Python, which knows their full paths)
  let depth = 0;
  window.addEventListener('dragenter', e => { if ([...(e.dataTransfer.types || [])].includes('Files')) { depth++; $('#dropOv').classList.add('on'); } });
  window.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) $('#dropOv').classList.remove('on'); });
  window.addEventListener('drop', () => { depth = 0; $('#dropOv').classList.remove('on'); });
  window.addEventListener('dragover', e => { if ([...(e.dataTransfer.types || [])].includes('Files')) e.preventDefault(); });
  bindSettings();
  bindWindow();
  bindContextMenu();
  bindPreviewScroll();
}

async function boot() {
  try {
    const init = await api('init');
    APP = Object.assign({}, init.app, {missing: init.missing_tools});
    SET = init.settings; FORMATS = init.formats; MODELS = init.models;
    LANG = SET.ui_lang === 'hu' ? 'hu' : 'en';
    document.title = APP.name;
    $('#appName').textContent = APP.name;
    $('#author').textContent = APP.author;
    $('#ver').textContent = 'v' + APP.version;
    bind();
    S.state = init.state;
    setJobs(init.jobs, init.state);
    $('#cntHist').textContent = init.history_count;
    applyI18n();
    loadHistory();
    loadVersions();
    bindClipboardWatch();
    bindMeters();
    $('#boot').remove();
    if (init.open_speakers) { save({speaker_intro: true}); diarDialog(true); }
  } catch (e) {
    $('#boot').textContent = 'Start-up failed.\n\n' + (e && (e.detail || e.message) || e);
  }
}
if (window.pywebview && window.pywebview.api && window.pywebview.api.init) boot();
else window.addEventListener('pywebviewready', boot, {once: true});
