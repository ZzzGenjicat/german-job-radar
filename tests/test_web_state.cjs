// Run: node tests/test_web_state.cjs [path/to/web/app.js]
// Uses the actual app handlers with a small DOM/network stub; no server or user data.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function main() {
  const script = process.argv[2] || path.resolve(__dirname, '../web/app.js');
  const elements = new Map(), documentListeners = {}, messages = [];
  const applyButton = { disabled: false };
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      id, value: '', checked: false, disabled: false, hidden: false,
      innerHTML: '', textContent: '', listeners: {},
      addEventListener(type, listener) { this.listeners[type] = listener; },
      querySelector(selector) { return id === 'apply-ai-keywords' && selector === 'button' ? applyButton : null; },
      querySelectorAll() {
        return id === 'source-settings' ? [{ dataset: { sourceToggle: 'ba' } }]
          : id === 'apply-ai-keywords' ? [{ value: 'Controlling' }] : [];
      },
      focus() {}, scrollIntoView() {}, close() {},
      classList: { add() {}, toggle() {} },
    });
    return elements.get(id);
  }
  const context = {
    console, structuredClone, Map, Set, URL, Intl, Date, setTimeout, clearTimeout,
    setInterval() {}, confirm: () => true,
    document: { getElementById: element, addEventListener(type, listener) { documentListeners[type] = listener; } },
    window: { addEventListener() {} },
  };
  vm.createContext(context);
  const source = fs.readFileSync(script, 'utf8');
  const bootstrap = 'load();const pollTimer=setInterval(load,5000);';
  assert.ok(source.includes(bootstrap), 'Update harness for changed application bootstrap');
  vm.runInContext(source.replace(bootstrap, 'const pollTimer=null;'), context, { filename: script });

  const saved = {
    search_revision: 'before', token: 'synthetic',
    profile: { role_types: ['regular'], fulltime_required: true, relocation: true,
      themes: [], exclusions: [], notes: '', locations: ['Deutschland'] },
    keywords: [{ term: 'HR', enabled: true }], sources: [{ id: 'ba', name: 'BA', enabled: true }],
    expansion: { enabled: false, status: 'pending', added: [] },
    learned_rules: [], cv: null, openai: {}, latest_attempt: null,
  };
  let releaseSave, pendingPayload, holdSave = true, revision = 0;
  context.initial = structuredClone(saved);
  context.messages = messages;
  context.fetch = async (url, options) => {
    if (url === '/api/search-settings') {
      pendingPayload = JSON.parse(options.body);
      if (holdSave) await new Promise(resolve => { releaseSave = resolve; });
      saved.keywords = pendingPayload.keywords;
      saved.profile = pendingPayload.profile;
      saved.search_revision = 'saved-' + ++revision;
    } else assert.equal(url, '/api/state');
    return { ok: true, json: async () => structuredClone(saved) };
  };
  // Leave actual save/apply/load/render-settings logic intact; omit unrelated job rendering.
  vm.runInContext('showHeader=()=>{};showJobs=()=>{};showSources=()=>{};toast=m=>messages.push(m);state=initial;showSettings();settingsDirty=true;', context);
  const submitSave = () => element('profile-form').listeners.submit({ preventDefault() {}, submitter: { value: '' } });
  const applySuggestion = () => documentListeners.submit({ preventDefault() {}, target: element('apply-ai-keywords') });

  const pending = submitSave();
  assert.deepEqual(pendingPayload.keywords, [{ term: 'HR', enabled: true }]);
  assert.equal(applyButton.disabled, true, 'AI apply button must be disabled while saving');
  // Explicitly call the handler too: a queued/programmatic submit must be guarded.
  applySuggestion();
  assert.equal(element('search-keywords').value, 'HR', 'Pending save must reject AI draft mutation');
  holdSave = false;
  releaseSave();
  await pending;
  assert.equal(element('search-keywords').value, 'HR');
  assert.equal(vm.runInContext('settingsDirty', context), false);
  assert.equal(applyButton.disabled, false, 'AI apply must be available after saving');

  applySuggestion();
  assert.equal(element('search-keywords').value, 'HR\nControlling');
  assert.equal(vm.runInContext('settingsDirty', context), true);
  await vm.runInContext('load()', context);
  assert.equal(element('search-keywords').value, 'HR\nControlling', 'Polling must retain the new draft');
  await submitSave();
  assert.deepEqual(saved.keywords.map(word => word.term), ['HR', 'Controlling']);
  assert.equal(vm.runInContext('settingsDirty', context), false);
  console.log('PASS: pending save blocks AI draft mutation; applying afterward survives polling and persists on the next save.');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
