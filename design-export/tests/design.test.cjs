const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
function setup(route = 'dashboard') {
  const errors = [];
  const dom = new JSDOM(html, { url: `http://localhost:3200/#/${route}`, runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  w.structuredClone = structuredClone;
  w.scrollTo = () => {};
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  w.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
  w.HTMLFormElement.prototype.reportValidity = () => true;
  w.addEventListener('error', e => errors.push(e.error));
  w.eval(script);
  return { w, d: w.document, api: w.ResearchPilotDesign, errors, close: () => dom.window.close() };
}
function click(d, selector) {
  const el = d.querySelector(selector); assert.ok(el, `Missing control: ${selector}`); el.click();
}
function submit(w, form) { form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true })); }

test('all sixteen route variants render with a main landmark and no execution errors', () => {
  const t = setup();
  for (const screen of t.api.getScreens()) {
    t.w.history.replaceState(null, '', `#/${screen.path}`); t.api.render();
    assert.ok(t.d.querySelector('main'), screen.label);
    assert.ok(t.d.querySelector('h1,h2'), screen.label);
    assert.doesNotMatch(t.d.querySelector('#app').textContent, /Page not found/, screen.label);
    assert.equal(t.errors.length, 0, `${screen.label}: ${t.errors}`);
  }
  t.close();
});

test('all application routes expose five recovery and progress state layouts', () => {
  const t = setup();
  for (const route of ['dashboard','projects','project/p1','library','document/d1','chat','literature','gaps','writing','references','exports','settings']) {
    t.w.history.replaceState(null, '', '#/' + route); t.api.render();
    for (const state of ['empty','loading','processing','failure','success','ready']) {
      const control = t.d.querySelector('#state-select'); control.value = state;
      control.dispatchEvent(new t.w.Event('change', { bubbles: true }));
      assert.ok(t.d.querySelector('main').textContent.trim());
      assert.equal(t.errors.length, 0, `${route}/${state}: ${t.errors}`);
    }
  }
  t.close();
});

test('library filters, table/grid controls, and source selection change the visible data', () => {
  const t = setup('library');
  const search = t.d.querySelector('#library-search'); search.value = 'Morgan'; search.dispatchEvent(new t.w.Event('input', { bubbles:true }));
  assert.equal(t.d.querySelectorAll('.data-table tbody tr').length, 1);
  click(t.d, '[data-view="grid"]');
  assert.equal(t.d.querySelectorAll('.document-card').length, 1);
  const filter = t.d.querySelector('#library-filter'); filter.value = 'Failed'; filter.dispatchEvent(new t.w.Event('change', { bubbles:true }));
  assert.match(t.d.querySelector('#library-results').textContent, /No matching papers/);
  assert.equal(t.errors.length,0); t.close();
});

test('project creation stores an escaped local record and opens its detail view', () => {
  const t = setup('projects'); click(t.d, '[data-action="new-project"]');
  const form = t.d.querySelector('#project-form'); form.elements.title.value = '<img src=x onerror=alert(1)>Study'; form.elements.description.value = 'New local project'; form.elements.question.value = 'What is supported?';
  submit(t.w, form);
  assert.equal(t.api.getState().projects.length,4);
  assert.equal(t.d.querySelectorAll('img').length,0);
  assert.match(t.d.querySelector('h1').textContent, /<img/);
  assert.equal(t.errors.length,0); t.close();
});

test('citation drawer names the source, excerpt, page and synthetic evidence boundary', () => {
  const t = setup('literature'); click(t.d,'[data-evidence="d1"]');
  const drawer = t.d.querySelector('#evidence'); assert.ok(drawer.hasAttribute('open'));
  assert.match(drawer.textContent,/Morgan & Lee/); assert.match(drawer.textContent,/Page 8/); assert.match(drawer.textContent,/Fictional content/);
  click(t.d,'[data-close="evidence"]'); assert.ok(!drawer.hasAttribute('open'));
  t.close();
});

test('matrix edits persist while citation evidence stays unchanged', () => {
  const t = setup('literature'); const cell=t.d.querySelector('[data-cell="d1:finding"]');cell.textContent='My reviewed interpretation';cell.dispatchEvent(new t.w.Event('input',{bubbles:true}));
  assert.equal(t.api.getState().matrixEdits['d1:finding'],'My reviewed interpretation');
  t.api.render();assert.equal(t.d.querySelector('[data-cell="d1:finding"]').textContent,'My reviewed interpretation');
  click(t.d,'[data-evidence="d1"]'); assert.match(t.d.querySelector('#evidence').textContent,/did not establish/);
  t.close();
});

test('writing suggestions require acceptance and preserve the previous draft as a revision', () => {
  const t = setup('writing'); const before=t.d.querySelector('#manuscript').textContent;
  click(t.d,'[data-action="writing-proposal"]');assert.equal(t.d.querySelector('#manuscript').textContent,before);
  click(t.d,'[data-action="accept-proposal"]');assert.equal(t.api.getState().revisions.length,1);assert.match(t.d.querySelector('#manuscript').textContent,/Illustrative AI-assisted passage/);
  assert.equal(t.errors.length,0);t.close();
});

test('chat records a question without claiming generation or sending it to a provider', () => {
  const t=setup('chat');const form=t.d.querySelector('#chat-form');form.elements.question.value='What can the sample support?';submit(t.w,form);
  assert.match(t.d.querySelector('#messages').textContent,/No AI provider is connected/);
  assert.equal(t.api.getState().messages.length,1);assert.equal(t.errors.length,0);t.close();
});

test('auth preview never persists passwords or entered email', () => {
  const t=setup('register');const form=t.d.querySelector('#auth-form');form.elements.name.value='Synthetic';form.elements.email.value='synthetic@example.com';form.elements.password.value='never-store-this-password';submit(t.w,form);
  const stored=t.w.localStorage.getItem('researchpilot-design-v1')||'';
  assert.doesNotMatch(stored,/never-store-this-password|synthetic@example.com/);assert.equal(t.errors.length,0);t.close();
});

test('editor strips active content and CSV escapes formula-like user text', () => {
  const t=setup();const clean=t.api.cleanEditor('<script>secret()</script><p onclick="bad()">Safe <strong>text</strong><img src=x onerror="bad()"></p>');
  assert.doesNotMatch(clean,/script|secret|onclick|onerror|<img/);assert.match(clean,/<strong>text<\/strong>/);
  assert.equal(t.api.csvValue('=SUM(1,2)'), '"\'=SUM(1,2)"');assert.equal(t.api.csvValue('a"b'),'"a""b"');t.close();
});

test('export dialog offers actual local formats and labels unimplemented formats', () => {
  const t=setup('exports');click(t.d,'[data-action="export-dialog"]');
  assert.deepEqual([...t.d.querySelectorAll('input[name=format]')].map(v=>v.value),['csv','html']);
  assert.match(t.d.querySelector('#modal').textContent,/not offered as working formats/);t.close();
});

test('changing source scope removes the prewritten answer instead of claiming new grounding', () => {
  const t=setup('chat');click(t.d,'[data-action="select-sources"]');
  const form=t.d.querySelector('#source-form');form.querySelector('input[value=d2]').checked=false;submit(t.w,form);
  assert.doesNotMatch(t.d.querySelector('#messages').textContent,/Reflection matters/);
  assert.match(t.d.querySelector('#messages').textContent,/changing sources never generates/);
  assert.equal(t.errors.length,0);t.close();
});

test('matrix deletion persists as an intentional empty value', () => {
  const t=setup('literature');const cell=t.d.querySelector('[data-cell="d1:finding"]');cell.textContent='';cell.dispatchEvent(new t.w.Event('input',{bubbles:true}));
  t.api.render();assert.equal(t.d.querySelector('[data-cell="d1:finding"]').textContent,'');t.close();
});

test('gap analysis does not reuse findings from a different project', () => {
  const t=setup('project/p2');t.w.history.replaceState(null,'','#/gaps');t.api.render();
  assert.match(t.d.querySelector('main').textContent,/No gap analysis for this project/);
  assert.doesNotMatch(t.d.querySelector('main').textContent,/Longer-term changes/);t.close();
});

test('manual reference is visible but never presented as a ready paper', () => {
  const t=setup('references');click(t.d,'[data-action="new-reference"]');const form=t.d.querySelector('#reference-form');
  form.elements.title.value='My unverified reference';form.elements.authors.value='Local author';form.elements.year.value='2025';submit(t.w,form);
  assert.match(t.d.querySelector('main').textContent,/My unverified reference/);
  assert.equal(t.api.getState().docs.at(-1).status,'Local only');assert.equal(t.errors.length,0);t.close();
});

test('project research questions stay with their project', () => {
  const t=setup('project/p2');click(t.d,'[data-action="add-question"]');const form=t.d.querySelector('#question-form');form.elements.question.value='A project-specific question';submit(t.w,form);
  assert.match(t.d.querySelector('main').textContent,/A project-specific question/);
  t.w.history.replaceState(null,'','#/project/p1');t.api.render();assert.doesNotMatch(t.d.querySelector('main').textContent,/A project-specific question/);t.close();
});
