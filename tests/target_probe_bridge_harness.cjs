const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const crypto = require('crypto');
const source = fs.readFileSync(process.argv[2], 'utf8');
const probe = fs.readFileSync(process.argv[3], 'utf8');
const hash = crypto.createHash('sha256').update(probe).digest('hex');
const helper = {};
const window = {flHelper: helper};
const host = {};
const dispatches = [];
Object.defineProperty(host, 'runJson', {set(value) {
  dispatches.push(JSON.parse(value));
  helper.onRunJson('ACK_ONLY');
}});
const context = vm.createContext({window, script_handler: host,
  crypto: {randomUUID: () => 'target-context'}, setTimeout: () => 1, clearTimeout: () => {}});
(async () => {
  vm.runInContext(source, context);
  const bridge = window.__dawloopReadonlyBridgeV1;
  assert.equal((await bridge.invoke('call', 'run_piano_roll_script', {source: probe}, 1000)).code, 'READ_ONLY_BACKEND');
  for (const args of [['wrong', hash, probe], ['target_semantics_v1', '0'.repeat(64), probe],
                      ['target_semantics_v1', hash, probe + '\n']]) {
    assert.equal((await bridge.invokeFixedTargetProbe(...args, 1, 1000)).code, 'FIXED_PROBE_MISMATCH');
  }
  assert.equal(dispatches.length, 0);
  assert.equal((await bridge.invokeFixedTargetProbe('target_semantics_v1', hash, probe, 2, 1000)).code, 'PROBE_BUDGET_EXHAUSTED');
  assert.equal((await bridge.invokeFixedTargetProbe('target_semantics_v1', hash, probe, 1, 1000)).ok, true);
  assert.equal(dispatches.length, 1);
  assert.equal(dispatches[0].params.arguments.source, probe);
  assert.equal((await bridge.invokeFixedTargetProbe('target_semantics_v1', hash, probe, 2, 1000)).code, 'PROBE_SESSION_NOT_READY');
  bridge.acknowledge('target-context');
  bridge.dispose();
  vm.runInContext(source, context);
  assert.equal((await window.__dawloopReadonlyBridgeV1.invokeFixedTargetProbe('target_semantics_v1', hash, probe, 1, 1000)).code, 'PROBE_BUDGET_EXHAUSTED');
  assert.equal((await window.__dawloopReadonlyBridgeV1.invokeFixedTargetProbe('target_semantics_v1', hash, probe, 2, 1000)).ok, true);
  window.__dawloopReadonlyBridgeV1.acknowledge('target-context');
  assert.equal((await window.__dawloopReadonlyBridgeV1.invokeFixedTargetProbe('target_semantics_v1', hash, probe, 3, 1000)).code, 'PROBE_BUDGET_EXHAUSTED');
  assert.equal(dispatches.length, 2);
  let timeout;
  let timedDispatches = 0;
  const timedHost = {};
  Object.defineProperty(timedHost, 'runJson', {set() { timedDispatches++; }});
  const timedWindow = {flHelper: {}};
  const timedContext = vm.createContext({window: timedWindow, script_handler: timedHost,
    crypto: {randomUUID: () => 'timeout-context'}, setTimeout: fn => {timeout = fn; return 1;}, clearTimeout() {}});
  vm.runInContext(source, timedContext);
  const timedBridge = timedWindow.__dawloopReadonlyBridgeV1;
  const pending = timedBridge.invokeFixedTargetProbe('target_semantics_v1', hash, probe, 1, 1000);
  timeout();
  assert.equal((await pending).dispatched, true);
  assert.equal((await timedBridge.invokeFixedTargetProbe('target_semantics_v1', hash, probe, 2, 1000)).code, 'PROBE_SESSION_NOT_READY');
  assert.equal(timedDispatches, 1);
  console.log('固定写入字节、顺序、重连预算与通用拒绝通过');
})().catch(error => {console.error(error); process.exitCode = 1;});
