const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(process.argv[2], 'utf8');
const probe = fs.readFileSync(process.argv[3], 'utf8');
const hash = require('crypto').createHash('sha256').update(probe).digest('hex');
const window = {flHelper:{}};
let dispatches = 0;
const host = {};
Object.defineProperty(host,'runJson',{set(value) {
  dispatches++;
  assert.equal(JSON.parse(value).params.arguments.source,probe);
  window.flHelper.onRunJson('ACK_ONLY');
}});
const context=vm.createContext({window,script_handler:host,crypto:{randomUUID:()=> 'executor'},setTimeout:()=>1,clearTimeout(){}});
(async()=>{
  vm.runInContext(source,context);
  const bridge=window.__dawloopReadonlyBridgeV1;
  assert.equal((await bridge.invoke('call','run_piano_roll_script',{source:probe},1000)).code,'READ_ONLY_BACKEND');
  assert.equal((await bridge.invokeFixedExecutorProbe('executor_canonical_v1',hash,probe+'\n',1000)).code,'FIXED_PROBE_MISMATCH');
  assert.equal(dispatches,0);
  assert.equal((await bridge.invokeFixedExecutorProbe('executor_canonical_v1',hash,probe,1000)).ok,true);
  bridge.acknowledge('executor');
  bridge.dispose();
  vm.runInContext(source,context);
  assert.equal((await window.__dawloopReadonlyBridgeV1.invokeFixedExecutorProbe('executor_canonical_v1',hash,probe,1000)).code,'PROBE_BUDGET_EXHAUSTED');
  assert.equal(dispatches,1);
  console.log('规范固定源码、单次预算及通用拒绝通过');
})().catch(e=>{console.error(e);process.exitCode=1;});
