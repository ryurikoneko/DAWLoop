const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('research/preview_onset_observer.js', 'utf8');
function setup(existing = false) {
  let tick = 100;
  let callback;
  let disconnected = false;
  const node = {textContent: 'DAWLoop Native Add Experimental add-only preview.',
    children: [], getClientRects: () => node.visible ? [{}] : [], visible: existing};
  const doc = {body: {}, documentElement: {}, visibilityState: 'visible',
    querySelectorAll: selector => selector === '*' ? [node] : [],
    addEventListener() {}, removeEventListener() {}};
  const context = vm.createContext({window: {}, document: doc,
    performance: {now: () => tick++},
    getComputedStyle: () => ({display: 'block', visibility: 'visible', opacity: '1'}),
    MutationObserver: class {
      constructor(cb) {callback = cb;}
      observe() {}
      disconnect() {disconnected = true;}
    }});
  const installed = vm.runInContext(source, context);
  return {context, installed, node, mutate: () => callback(),
    get disconnected() {return disconnected;}};
}
const absent = setup();
assert.equal(absent.installed.installed, true);
const a = absent.context.window.__dawloopPreviewOnsetObservation;
absent.mutate();
assert.equal(a.snapshot().first_candidate, null);
absent.node.visible = true;
absent.mutate();
assert.equal(a.snapshot().first_candidate, 'OBSERVED_IN_MUTATION_CALLBACK');
assert.equal(a.snapshot().certified_preview_onset_ms, null);
assert.equal(a.snapshot().inventory.preview_identity_certified, false);
assert.equal(a.snapshot().events.filter(e => e.event === 'preview_candidate_first_detected').length, 1);
assert.equal(vm.runInContext(source, absent.context).installed, false);
for (let i = 0; i < 300; i++) absent.mutate();
assert.equal(a.snapshot().events.length, 256);
assert.equal(JSON.stringify(a.snapshot()).includes('DAWLoop Native Add'), false);
a.dispose();
assert.equal(absent.disconnected, true);
const count = a.snapshot().mutation_batches;
absent.mutate();
assert.equal(a.snapshot().mutation_batches, count);
const existing = setup(true).context.window.__dawloopPreviewOnsetObservation;
assert.equal(existing.snapshot().first_candidate, 'EXISTED_AT_INSTALL');
assert.equal(existing.snapshot().certified_preview_onset_ms, null);
console.log('候选检测、未认证、已存在、事件上限、脱敏及卸载检查通过');
