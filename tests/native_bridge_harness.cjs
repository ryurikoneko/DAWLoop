const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[2], 'utf8');
let timers = new Map(), timerId = 0, originalCalls = 0, mode = 'immediate';
const original = () => { originalCalls += 1; };
const helper = {onRunJson: original, onMCPTools: original};
const window = {flHelper: helper};
const host = {};
let dispatches = 0;
Object.defineProperty(host, 'runJson', {set: function(value) {
  dispatches += 1;
  if (mode === 'immediate') helper.onRunJson(JSON.stringify({result: JSON.parse(value).params.name}));
}});
Object.defineProperty(host, 'MCPTools', {set: function(value) { helper.onMCPTools('[]'); }});
const context = vm.createContext({window, script_handler: host,
  crypto: {randomUUID: () => 'document-1'},
  setTimeout: (fn) => { const id = ++timerId; timers.set(id, fn); return id; },
  clearTimeout: id => timers.delete(id)});
async function main() {
  let state = vm.runInContext(source, context);
  assert.equal(state.poisoned, false);
  let bridge = window.__dawloopReadonlyBridgeV1;
  const a = await bridge.invoke('call', 'get_tempo', {}, 1);
  assert.equal((await bridge.invoke('call', 'get_tempo', {}, 1)).code, 'RESULT_NOT_ACKNOWLEDGED');
  assert.equal(bridge.acknowledge('document-1'), true);
  const b = await bridge.invoke('call', 'list_channel_names', {}, 1);
  assert.equal(bridge.acknowledge('document-1'), true);
  assert.equal(JSON.parse(a.payload).result, 'get_tempo');
  assert.equal(JSON.parse(b.payload).result, 'list_channel_names');
  assert.equal(originalCalls, 2);
  assert.equal((await bridge.invoke('call', 'set_tempo', {}, 1)).code, 'READ_ONLY_BACKEND');
  assert.equal(dispatches, 2);
  assert.equal((await bridge.invoke('catalog', null, {}, 1)).payload, '[]');
  assert.equal(bridge.acknowledge('document-1'), true);
  mode = 'delay';
  const pending = bridge.invoke('call', 'get_tempo', {}, 1);
  assert.equal((await bridge.invoke('call', 'get_tempo', {}, 1)).code, 'CALL_IN_FLIGHT');
  const expire = [...timers.values()][0];
  timers.clear();
  expire();
  assert.equal((await pending).code, 'EXECUTION_TIMEOUT');
  helper.onRunJson('late');
  assert.equal(bridge.interference, 1);
  assert.equal((await bridge.invoke('call', 'get_tempo', {}, 1)).code, 'SESSION_POISONED');
  assert.equal(bridge.dispose().ok, true);
  assert.equal(helper.onRunJson, original);
  assert.equal(helper.onMCPTools, original);
  state = vm.runInContext(source, context);
  assert.equal(state.poisoned, true);
  assert.equal(state.epoch, 'document-1');
  assert.equal((await window.__dawloopReadonlyBridgeV1.invoke('call', 'get_tempo', {}, 1)).code, 'SESSION_POISONED');
  const oldCallback = helper.onRunJson;
  const freshWindow = {};
  const fresh = vm.createContext({window: freshWindow, crypto: {randomUUID: () => 'document-2'},
    setTimeout: () => 1, clearTimeout: () => {}});
  assert.equal(vm.runInContext(source, fresh).poisoned, false);
  oldCallback('late-old-context');
  assert.equal(freshWindow.__dawloopReadonlyBridgeV1.interference, 0);
  assert.equal(freshWindow.__dawloopReadonlyBridgeV1.epoch, 'document-2');
  assert.equal((await freshWindow.__dawloopReadonlyBridgeV1.invoke('call', 'get_tempo', {}, 1)).code, 'HOST_UNAVAILABLE');
  freshWindow.__dawloopReadonlyBridgeV1.dispose();
  assert.equal(freshWindow.flHelper, undefined);
  const lostWindow = {};
  const lostHost = {};
  const lostContext = vm.createContext({window: lostWindow, script_handler: lostHost,
    crypto: {randomUUID: () => 'document-3'}, setTimeout: () => 1, clearTimeout: () => {}});
  Object.defineProperty(lostHost, 'runJson', {set: () => lostWindow.flHelper.onRunJson('120')});
  vm.runInContext(source, lostContext);
  await lostWindow.__dawloopReadonlyBridgeV1.invoke('call', 'get_tempo', {}, 1);
  lostWindow.__dawloopReadonlyBridgeV1.dispose();
  assert.equal(vm.runInContext(source, lostContext).poisoned, true);
  console.log('桥接时序、锁定、回调恢复测试通过');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
