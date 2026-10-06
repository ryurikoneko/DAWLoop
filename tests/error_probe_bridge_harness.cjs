const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const crypto = require('crypto');
const source = fs.readFileSync(process.argv[2], 'utf8');
const probe = fs.readFileSync(process.argv[3], 'utf8');
const hash = crypto.createHash('sha256').update(probe).digest('hex');
const helper = {};
const window = {flHelper: helper};
let dispatches = 0;
const host = {};
const raw = JSON.stringify({jsonrpc:'2.0', id:1, error:{code:-32000,message:'Exception: DAWLOOP_ERROR_V1|COUNT=3'}});
Object.defineProperty(host, 'runJson', {set(value) {
  assert.equal(JSON.parse(value).params.arguments.source, probe);
  dispatches++;
  helper.onRunJson(raw);
}});
const context = vm.createContext({window, script_handler:host,
  crypto:{randomUUID:()=> 'error-epoch'}, setTimeout:()=>1, clearTimeout:()=>{}});
(async()=>{
  vm.runInContext(source,context);
  const bridge=window.__dawloopReadonlyBridgeV1;
  assert.equal((await bridge.invoke('call','run_piano_roll_script',{source:probe},1000)).code,'READ_ONLY_BACKEND');
  assert.equal((await bridge.invokeFixedErrorProbe('ERROR_RETURN_PROBE_V1',hash,probe+'\n',1000)).code,'FIXED_PROBE_MISMATCH');
  assert.equal(dispatches,0);
  const result=await bridge.invokeFixedErrorProbe('ERROR_RETURN_PROBE_V1',hash,probe,1000);
  assert.equal(result.payload,raw);
  assert.equal(dispatches,1);
  assert.equal(bridge.acknowledge('error-epoch'),true);
  assert.equal((await bridge.invokeFixedErrorProbe('ERROR_RETURN_PROBE_V1',hash,probe,1000)).code,'PROBE_BUDGET_EXHAUSTED');
  assert.equal(dispatches,1);
  assert.equal(bridge.dispose().ok,true);
  console.log('error bridge guard/raw passthrough/single dispatch PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
