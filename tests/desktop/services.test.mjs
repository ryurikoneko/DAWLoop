import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { ConfigService, defaults, atomicWrite } from '../../packages/config/index.mjs';
import { ProfileService, profileDefaults } from '../../packages/profiles/index.mjs';
import { AppCore } from '../../packages/app-core/index.mjs';
import { MockAdapter, RealAdapter, unavailable, validateSnapshot } from '../../packages/core-adapter/index.mjs';
import { redact, diagnosticReport } from '../../packages/diagnostics/index.mjs';
import { LogService } from '../../packages/logging/index.mjs';

async function temporary(t) { const root = await fs.mkdtemp(path.join(os.tmpdir(), 'dawloop-desktop-')); t.after(() => fs.rm(root, { recursive: true, force: true })); return root; }
test('配置保存、重读和嵌套未知字段保留', async t => {
  const config = new ConfigService(await temporary(t));
  await config.update({ future: { x: 4 }, general: { futureOption: 'keep' } });
  await config.update({ general: { logLevel: 'Debug' } });
  const restored = await new ConfigService(path.dirname(path.dirname(config.filename))).get();
  assert.equal(restored.future.x, 4); assert.equal(restored.general.futureOption, 'keep'); assert.equal(restored.general.logLevel, 'Debug');
});
test('无效配置不会覆盖原文件', async t => {
  const config = new ConfigService(await temporary(t)); await config.get();
  for (const data of ['{broken', '[]', JSON.stringify({ ...defaults(), schemaVersion: 99 }), JSON.stringify({ ...defaults(), general: {} })]) {
    await fs.writeFile(config.filename, data, 'utf8'); await assert.rejects(config.get()); assert.equal(await fs.readFile(config.filename, 'utf8'), data);
  }
});
test('v0升级保留原字节、未知字段，拒绝原型注入', async t => {
  const config = new ConfigService(await temporary(t)); const original = '{"schemaVersion":0,"future":{"data":5}}';
  await fs.mkdir(path.dirname(config.filename), { recursive: true }); await fs.writeFile(config.filename, original, 'utf8');
  const result = await config.get(); assert.equal(result.schemaVersion, 1); assert.equal(result.future.data, 5);
  const backup = (await fs.readdir(path.dirname(config.filename))).find(x => x.endsWith('.bak')); assert.equal(await fs.readFile(path.join(path.dirname(config.filename), backup), 'utf8'), original);
  await assert.rejects(config.update(JSON.parse('{"__proto__":{"polluted":1}}'))); assert.equal({}.polluted, undefined);
});
test('Profile 创建、载入、未知字段合并、切换与重启恢复', async t => {
  const root = await temporary(t); const core = new AppCore({ roamingRoot: root, localRoot: root, development:true, mode:'mock' }); await core.initialize(); t.after(() => core.close());
  const created = (await core.call('createProfile', 'Production')).data; assert.ok(created.id);
  await core.call('updateProfile', { ...created, agent: { futurePreference: 1 } });
  await core.call('updateProfile', { ...created, agent: { model: 'custom' } });
  assert.equal((await core.call('setActiveProfile', created.id)).ok, true);
  assert.equal((await core.call('getActiveProfile')).data.agent.futurePreference, 1);
  const service = new ConfigService(root); assert.equal((await service.get()).activeProfileId, created.id);
  const before = await service.get(); assert.equal((await core.call('setActiveProfile', '../bad')).ok, false); assert.deepEqual(await service.get(), before);
  assert.equal((await core.call('updateConfig', { activeProfileId: 'missing' })).ok, false);
});
test('Profile 无效版本、路径、名称及迁移', async t => {
  const profiles = new ProfileService(await temporary(t)); await profiles.get('default');
  await assert.rejects(profiles.create('')); await assert.rejects(profiles.get('../x')); await assert.rejects(profiles.get('missing'));
  await atomicWrite(profiles.filename('default'), { schemaVersion: 0, id:'default', name:'旧版', future:8 });
  assert.equal((await profiles.get('default')).future, 8);
  await atomicWrite(profiles.filename('default'), { ...profileDefaults(), schemaVersion: 88 }); await assert.rejects(profiles.get('default'));
  await atomicWrite(profiles.filename('default'), { ...profileDefaults('other'), schemaVersion: 0 });
  await assert.rejects(profiles.get('default')); assert.equal(JSON.parse(await fs.readFile(profiles.filename('default'),'utf8')).schemaVersion, 0);
});
test('Mock 场景、部分能力、Runtime 启停和故障', async () => {
  const mock = new MockAdapter('connected'); assert.equal((await mock.snapshot()).host.state,'connected');
  assert.equal((await mock.control('start')).state,'running'); assert.equal((await mock.control('stop')).state,'stopped');
  mock.setScenario('degraded'); assert.equal((await mock.snapshot()).bridges.find(x => x.id==='mcp').state,'degraded'); assert.ok((await mock.snapshot()).capabilities.some(x=>x.state==='partial'));
  mock.setScenario('faulted'); assert.equal((await mock.snapshot()).runtime.state,'faulted'); await assert.rejects(mock.control('start'));
  for (const scenario of ['offline','timeout','backend-error']) { mock.setScenario(scenario); await assert.rejects(mock.snapshot()); }
});
function fakeChild() { const child = new EventEmitter(); child.stdin = new PassThrough(); child.stdout = new PassThrough(); child.stderr = new PassThrough(); child.kill = () => { child.killed = true; }; return child; }
test('真实 Adapter 成功、超时、离线及畸形响应，不返回异常路径', async () => {
  for (const kind of ['success','timeout','offline','malformed']) {
    let child; const real = new RealAdapter({ cwd:'.', timeoutMs: 15, spawnProcess: () => {
      child = fakeChild(); setTimeout(() => {
        if (kind === 'offline') child.emit('error', new Error('private path password=secret'));
        else if (kind !== 'timeout') { child.stdout.write(kind==='success' ? JSON.stringify({ apiVersion:1,ok:true,data:{ apiVersion:1,...unavailable() } }) : '{'); child.emit('close',0); }
      }, 1); return child;
    } });
    if (kind === 'success') assert.equal((await real.snapshot(defaults())).runtime.state,'unknown');
    else await assert.rejects(real.snapshot(defaults()), error => !error.message.includes('secret'));
    if (kind === 'timeout') assert.equal(child.killed,true); real.close();
  }
});
test('后端故障将所有状态降为unknown；真实启停拒绝', async t => {
  const root = await temporary(t); const core = new AppCore({ roamingRoot:root, localRoot:root, development:true, mode:'mock', scenario:'connected' }); await core.initialize(); t.after(()=>core.close());
  await core.call('setMockScenario','timeout'); const status = (await core.call('getAppStatus')).data;
  assert.equal(status.host.state,'unknown'); assert.equal(status.runtime.state,'unknown'); assert.equal(status.errors[0].code,'BACKEND_TIMEOUT');
  await core.call('setBackend','real'); assert.equal((await core.call('startRuntime')).error.code,'RUNTIME_CONTROL_UNAVAILABLE');
  assert.equal((await core.call('privateRuntimeFunction')).error.code,'METHOD_UNAVAILABLE');
});
test('诊断脱敏、白名单与磁盘保存', async t => {
  const secret = { username:'someone', apiKey:'sensitive', nested:{ projectPath:'C:\\Users\\someone\\private.flp', message:'Bearer abcxyz token=topsecret' } };
  const serialized = JSON.stringify(redact(secret)); for (const value of ['someone','sensitive','private.flp','abcxyz','topsecret']) assert.ok(!serialized.includes(value));
  const root = await temporary(t); const core = new AppCore({ roamingRoot:root, localRoot:root, development:true, mode:'mock' }); await core.initialize(); t.after(()=>core.close());
  await core.call('updateConfig', { privateProject:'private', host:{ executablePath:'C:\\Users\\someone\\FL64.exe' } });
  const report = (await core.call('getDiagnostics')).data; assert.ok(!JSON.stringify(report).includes('someone')); assert.ok(!JSON.stringify(report).includes('privateProject'));
  assert.deepEqual(JSON.parse(await fs.readFile(path.join(root,'diagnostics','latest.json'),'utf8')),report);
  assert.equal(diagnosticReport((await core.call('getAppStatus')).data,defaults()).configuration.experimentalWritesEnabled,false);
});
test('日志持久化与过滤字段；视图不拥有删除接口', async t => {
  const logs = new LogService(await temporary(t)); await logs.initialize();
  for (const level of ['INFO','WARN','ERROR','DEBUG']) await logs.emit('Runtime',level,`token=secret ${level}`);
  const next = new LogService(path.dirname(path.dirname(logs.filename))); await next.initialize();
  assert.equal(next.recent().length,4); assert.ok(next.recent().every(x=>!x.message.includes('secret')));
});
test('串行配置更新不丢字段；实验开关不授予真实写权限', async t => {
  const root = await temporary(t); const core = new AppCore({ roamingRoot:root, localRoot:root, mode:'real' }); await core.initialize(); t.after(()=>core.close());
  await Promise.all([core.call('updateConfig',{ general:{ logLevel:'Debug' } }),core.call('updateConfig',{ features:{ experimentalMixerWrite:true } })]);
  const config = (await core.call('getConfig')).data; assert.equal(config.general.logLevel,'Debug'); assert.equal(config.features.experimentalMixerWrite,true);
  assert.equal((await core.call('plugin.parameter.write', { value: 1 })).ok,false);
});
test('损坏配置仍可诊断，原件保留且不观察真实后端', async t => {
  const root = await temporary(t); let observed = false;
  const core = new AppCore({roamingRoot:root,localRoot:root,realAdapter:{snapshot(){observed=true;return unavailable();},close(){}}}); await core.initialize(); t.after(()=>core.close());
  await core.config.get(); await fs.writeFile(core.config.filename,'{broken','utf8');
  const report = await core.call('getDiagnostics'); assert.equal(report.ok,true); assert.equal(report.data.configuration.state,'invalid'); assert.equal(report.data.errors[0].code,'INVALID_JSON'); assert.equal(observed,false);
  assert.equal(await fs.readFile(core.config.filename,'utf8'),'{broken');
});
test('后端仅导出协议白名单，不能伪装模式或带原始对象', () => {
  const snapshot = validateSnapshot({apiVersion:1,...unavailable(),backend:'mock',rawException:{password:'secret'}});
  assert.equal(snapshot.backend,undefined); assert.equal(snapshot.rawException,undefined);
  assert.throws(()=>validateSnapshot({apiVersion:1,...unavailable(),host:{...unavailable().host,reason:'C:\\Users\\private'}}));
});
test('路径测试不保存草稿配置', async t => {
  const root = await temporary(t); const core = new AppCore({roamingRoot:root,localRoot:root,development:true, mode:'mock'}); await core.initialize(); t.after(()=>core.close());
  const before = await core.config.get(); assert.equal((await core.call('testHostPath','not-an-executable')).data.valid,false); assert.deepEqual(await core.config.get(),before);
});
