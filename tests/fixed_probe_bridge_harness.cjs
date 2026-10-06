const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[2], 'utf8');
const probe = fs.readFileSync(process.argv[3], 'utf8');
const hash = require('crypto').createHash('sha256').update(probe).digest('hex');
const helper = {};
const window = {flHelper: helper};
const host = {};
let dispatches = [];
Object.defineProperty(host, 'runJson', {set(value) {
  dispatches.push(JSON.parse(value));
  helper.onRunJson(JSON.stringify({result: 'ACK_ONLY'}));
}});
const context = vm.createContext({window, script_handler: host,
  crypto: {randomUUID: () => 'probe-context'}, setTimeout: () => 1, clearTimeout: () => {}});
(async () => {
  vm.runInContext(source, context);
  const bridge = window.__dawloopReadonlyBridgeV1;
  assert.equal((await bridge.invoke('call', 'run_piano_roll_script', {source: probe}, 1000)).code, 'READ_ONLY_BACKEND');
  for (const args of [['wrong', hash, probe], ['piano_roll_count_return_v1', '0'.repeat(64), probe],
                      ['piano_roll_count_return_v1', hash, probe + '\n']]) {
    assert.equal((await bridge.invokeFixedCountProbe(...args, 1000)).code, 'FIXED_PROBE_MISMATCH');
  }
  assert.equal(dispatches.length, 0);
  const response = await bridge.invokeFixedCountProbe('piano_roll_count_return_v1', hash, probe, 1000);
  assert.equal(response.ok, true);
  assert.equal(dispatches.length, 1);
  assert.equal(dispatches[0].params.name, 'run_piano_roll_script');
  assert.equal(dispatches[0].params.arguments.source, probe);
  assert.equal(bridge.acknowledge('probe-context'), true);
  assert.equal(bridge.dispose().ok, true);
  console.log('固定研究探针与普通拒绝路径通过');
})().catch(error => {console.error(error); process.exitCode = 1;});
