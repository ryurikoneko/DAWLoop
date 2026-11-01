import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { AppCore } from '../../packages/app-core/index.mjs';
import { RealAdapter, unavailable, validateSnapshot } from '../../packages/core-adapter/index.mjs';
import { desktopDevelopment, rendererMethodAllowed } from '../../apps/desktop/electron/renderer-policy.mjs';

const deferred = () => Promise.withResolvers();
async function coreFor(t, options = {}) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'dawloop-hardening-'));
  const core = new AppCore({ roamingRoot:root, localRoot:root, ...options });
  await core.initialize();
  t.after(async () => { await core.close(); await fs.rm(root, { recursive:true, force:true }); });
  return core;
}
test('独立 Renderer 权限拒绝 Core 未来高权限方法及开发方法', () => {
  for (const method of ['plugin.parameter.write','writeMixerParameter','loadProject','applyAutomation','privateRuntimeFunction','toString']) {
    assert.equal(rendererMethodAllowed(method, false), false);
    assert.equal(rendererMethodAllowed(method, true), false);
  }
  assert.equal(rendererMethodAllowed('getConfig'), true);
  for (const method of ['setBackend','setMockScenario']) {
    assert.equal(rendererMethodAllowed(method), false);
    assert.equal(rendererMethodAllowed(method, true), true);
  }
  assert.equal(rendererMethodAllowed(null, true), false);
});
test('正式打包始终拒绝开发标志，未打包也必须显式启用', () => {
  for (const flags of [[], ['--mock'], ['--dev'], ['--dev','--mock']]) assert.equal(desktopDevelopment(true, flags), false);
  assert.equal(desktopDevelopment(false, []), false);
  assert.equal(desktopDevelopment(false, ['--mock']), true);
  assert.equal(desktopDevelopment(false, ['--dev']), true);
});
test('绕过 Renderer 白名单仍不能在普通 Core 启用 Mock', async t => {
  const core = await coreFor(t);
  assert.equal((await core.call('setBackend','mock')).error.code, 'METHOD_UNAVAILABLE');
  assert.equal((await core.call('setMockScenario','connected')).error.code, 'METHOD_UNAVAILABLE');
  assert.equal(core.mode, 'real');
  assert.throws(() => new AppCore({ mode:'mock' }));
});
test('慢观察器不阻塞语言、配置、Profile、日志；并发状态查询共用观察', async t => {
  const entered = deferred(), result = deferred(); let calls = 0;
  const core = await coreFor(t, { realAdapter:{ snapshot(){ calls++; entered.resolve(); return result.promise; }, close(){ result.resolve(unavailable()); } } });
  const status = core.call('getAppStatus'); await entered.promise;
  const host = core.call('getHostStatus');
  try {
    const local = await Promise.race([
      Promise.all([core.call('getConfig'),core.call('updateConfig',{ui:{language:'zh-CN'}}),core.call('createProfile','While observing'),core.call('getRecentLogs')]),
      new Promise((_, reject) => { const timer = setTimeout(()=>reject(new Error('本地服务被观察器阻塞')), 1000); timer.unref(); }),
    ]);
    assert.ok(local.every(x=>x.ok));
    assert.equal(local[1].data.ui.language,'zh-CN');
    assert.equal((await core.call('setActiveProfile',local[2].data.id)).ok,true);
    assert.equal((await core.call('getActiveProfile')).data.id,local[2].data.id);
    assert.equal(calls,1);
  } finally { result.resolve(unavailable()); }
  assert.equal((await status).data.backend,'real'); assert.equal((await host).data.state,'unknown');
});
test('配置修改串行，读取独立；并发更新保留两个字段', async t => {
  const core = await coreFor(t), entered = deferred(), release = deferred();
  const update = core.config.update.bind(core.config); let calls = 0;
  core.config.update = async patch => { calls++; if (calls === 1) { entered.resolve(); await release.promise; } return update(patch); };
  const first = core.call('updateConfig',{general:{logLevel:'Debug'}}); await entered.promise;
  const second = core.call('updateConfig',{features:{experimentalMixerWrite:true}});
  try { assert.equal((await core.call('getConfig')).ok,true); assert.equal(calls,1); }
  finally { release.resolve(); }
  assert.ok((await first).ok && (await second).ok);
  const config = (await core.call('getConfig')).data;
  assert.equal(config.general.logLevel,'Debug'); assert.equal(config.features.experimentalMixerWrite,true);
});
test('Runtime 控制串行且不锁住本地修改', async t => {
  const core = await coreFor(t,{development:true,mode:'mock'}), entered=deferred(), release=deferred();
  const order=[];
  core.mock.control=async action => { order.push(action); if (action==='start') { entered.resolve(); await release.promise; } return {...unavailable().runtime,state:action==='start'?'running':'stopped'}; };
  const start=core.call('startRuntime'); await entered.promise;
  const stop=core.call('stopRuntime');
  try { assert.equal((await core.call('updateConfig',{ui:{language:'en-US'}})).ok,true); assert.deepEqual(order,['start']); }
  finally { release.resolve(); }
  assert.equal((await start).data.state,'running'); assert.equal((await stop).data.state,'stopped'); assert.deepEqual(order,['start','stop']);
});
test('切换后端时旧观察不能被标为新后端；退出等待所属请求并拒绝新请求', async t => {
  const entered=deferred(), release=deferred();
  const core=await coreFor(t,{development:true,realAdapter:{snapshot(){entered.resolve();return release.promise;},close(){release.resolve(unavailable());}}});
  const old=core.call('getAppStatus'); await entered.promise;
  const switched=await core.call('setBackend','mock'); assert.equal(switched.data.backend,'mock');
  await core.close(); assert.equal((await old).data.backend,'real');
  assert.equal((await core.call('getConfig')).error.code,'METHOD_UNAVAILABLE');
});
test('五档 confidence 保留原值；非合同取值拒绝', () => {
  for (const confidence of ['high','medium','low','very-low','unknown','HIGH','very_low','']) {
    const value={apiVersion:1,...unavailable(),capabilities:[{id:'plugin.parameter.read',state:'experimental',confidence,backend:'observer',notes:[]}]};
    if (['HIGH','very_low',''].includes(confidence)) assert.throws(()=>validateSnapshot(value));
    else assert.equal(validateSnapshot(value).capabilities[0].confidence,confidence);
  }
});
test('并发日志按 sequence 持久化，诊断并发导出仍为完整 JSON', async t => {
  const core=await coreFor(t,{development:true,mode:'mock'});
  await Promise.all(Array.from({length:30},(_,i)=>core.logs.emit('Desktop','INFO',`TEST_${i}`)));
  const rows=(await fs.readFile(core.logs.filename,'utf8')).trim().split('\n').map(JSON.parse);
  assert.deepEqual(rows.map(x=>x.sequence),core.logs.recent().map(x=>x.sequence));
  assert.ok(rows.every((x,i)=>i===0 || x.sequence===rows[i-1].sequence+1));
  const reports=await Promise.all([core.call('getDiagnostics'),core.call('getDiagnostics')]);
  const saved=JSON.parse(await fs.readFile(path.join(core.localRoot,'diagnostics','latest.json'),'utf8'));
  assert.ok(reports.some(x=>JSON.stringify(x.data)===JSON.stringify(saved)));
});
test('关闭后延迟读取不能再启动观察进程', async () => {
  let spawned=false;
  const adapter=new RealAdapter({spawnProcess(){spawned=true;throw new Error('不应启动');}});
  adapter.close();
  await assert.rejects(adapter.detectPath({}),e=>e.code==='BACKEND_OFFLINE');
  await assert.rejects(adapter.snapshot({}),e=>e.code==='BACKEND_OFFLINE');
  assert.equal(spawned,false);
});
