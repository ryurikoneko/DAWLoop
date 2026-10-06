const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const crypto = require('crypto');
const source = fs.readFileSync(process.argv[2], 'utf8');
const fixture = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
function setup(timeout = false) {
  let writes = 0, timer;
  const window = {flHelper: {}};
  const host = {};
  Object.defineProperty(host, 'runJson', {set(value) {
    writes++;
    assert.equal(JSON.parse(value).params.arguments.source, fixture.source);
    if (!timeout) window.flHelper.onRunJson('ACK');
  }});
  const context = vm.createContext({window, script_handler: host,
    performance: {now: () => Number(process.hrtime.bigint()) / 1000000},
    crypto: {randomUUID: () => 'epoch', subtle: crypto.webcrypto.subtle}, TextEncoder,
    setTimeout(fn) {timer = fn; return 1;}, clearTimeout() {}});
  vm.runInContext(source, context);
  return {window, context, writes: () => writes, timeout: () => timer()};
}
(async () => {
  const s = setup();
  const b = s.window.__dawloopReadonlyBridgeV1;
  assert.equal(b.configureDiagnostics('trace', 'op-1', 'generation'), true);
  const call = (rows, hash = fixture.hash, text = fixture.source, epoch = 'epoch') =>
    b.invokeBatchAdd('op-1', rows, hash, text, epoch, 1000);
  assert.equal((await b.invoke('call', 'run_piano_roll_script', {}, 1000)).code, 'READ_ONLY_BACKEND');
  assert.equal((await call(fixture.rows, fixture.hash, fixture.source + '\n')).code, 'SOURCE_TEMPLATE_MISMATCH');
  assert.equal((await call(fixture.rows, '0'.repeat(64))).code, 'SOURCE_HASH_MISMATCH');
  assert.equal((await call(Array(129).fill(fixture.rows[0]))).code, 'CAPABILITY_LIMIT_EXCEEDED');
  assert.equal((await call([[true, 0, 1, 1]])).code, 'INVALID_BATCH_NOTE');
  assert.equal((await call(fixture.rows, fixture.hash, fixture.source, 'other')).code, 'INVALID_BATCH_OPERATION');
  assert.equal(s.writes(), 0);
  const both = await Promise.all([call(fixture.rows), call(fixture.rows)]);
  assert.equal(both.filter(r => r.ok).length, 1);
  assert.equal(s.writes(), 1);
  const events = b.diagnostics.events;
  assert(events.some(e => e.event === 'script_handler_assignment_return'));
  assert(events.some(e => e.event === 'host_callback_received'));
  assert(events.every(e => e.clock_domain === 'webview_performance' && e.trace_id === 'trace'));
  b.acknowledge('epoch'); b.dispose(); vm.runInContext(source, s.context);
  assert.equal((await s.window.__dawloopReadonlyBridgeV1.invokeBatchAdd('op-2', fixture.rows,
    fixture.hash, fixture.source, 'epoch', 1000)).code, 'PROBE_BUDGET_EXHAUSTED');
  const t = setup(true), bridge = t.window.__dawloopReadonlyBridgeV1;
  const pending = bridge.invokeBatchAdd('op-3', fixture.rows, fixture.hash, fixture.source, 'epoch', 1000);
  await new Promise(resolve => setTimeout(resolve, 20));
  t.timeout();
  assert.equal((await pending).code, 'EXECUTION_TIMEOUT');
  t.window.flHelper.onRunJson('LATE');
  assert.equal((await bridge.invokeBatchAdd('op-4', fixture.rows, fixture.hash,
    fixture.source, 'epoch', 1000)).code, 'PROBE_SESSION_NOT_READY');
  assert.equal(t.writes(), 1);
})().catch(error => {console.error(error); process.exitCode = 1;});
