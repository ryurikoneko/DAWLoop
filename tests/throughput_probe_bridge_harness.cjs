const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const bridgeSource = fs.readFileSync(process.argv[2], 'utf8');
const directory = process.argv[3];
const manifest = JSON.parse(fs.readFileSync(directory + '/probe_hashes.json', 'utf8'));
(async () => {
  for (const count of [1, 4, 32, 64, 128]) {
    const source = fs.readFileSync(directory + '/probe_' + String(count).padStart(3, '0') + '.py', 'utf8');
    const window = {flHelper: {}};
    let writes = 0;
    const host = {};
    Object.defineProperty(host, 'runJson', {set(value) {
      writes++;
      assert.equal(JSON.parse(value).params.arguments.source, source);
      window.flHelper.onRunJson('ACK');
    }});
    const context = vm.createContext({window, script_handler: host, crypto: {randomUUID: () => 'batch'},
      setTimeout: () => 1, clearTimeout() {}});
    vm.runInContext(bridgeSource, context);
    const bridge = window.__dawloopReadonlyBridgeV1;
    assert.equal((await bridge.invoke('call', 'run_piano_roll_script', {source}, 1000)).code, 'READ_ONLY_BACKEND');
    assert.equal((await bridge.invokeFixedThroughputProbe(count, manifest[count].sha256, source + '\n', 1000)).code, 'FIXED_PROBE_MISMATCH');
    assert.equal((await bridge.invokeFixedThroughputProbe(256, manifest[count].sha256, source, 1000)).code, 'FIXED_PROBE_MISMATCH');
    assert.equal((await bridge.invokeFixedThroughputProbe(count, manifest[count].sha256, source, 0)).code, 'INVALID_PROBE_TIMEOUT');
    assert.equal(writes, 0);
    assert.equal((await bridge.invokeFixedThroughputProbe(count, manifest[count].sha256, source, 1000)).ok, true);
    bridge.acknowledge('batch');
    bridge.dispose();
    vm.runInContext(bridgeSource, context);
    assert.equal((await window.__dawloopReadonlyBridgeV1.invokeFixedThroughputProbe(count, manifest[count].sha256, source, 1000)).code, 'PROBE_BUDGET_EXHAUSTED');
    assert.equal(writes, 1);
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
