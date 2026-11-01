import test from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { TrustedSessionProvider } from '../../packages/core-session/index.mjs';
import { startTrustedSessionWorker } from '../../packages/core-session/worker.mjs';
import { MixerSnapshotPublisher } from '../../packages/core-snapshot/index.mjs';
import { PublishedMixerAdapter } from '../../packages/core-adapter/published.mjs';
import { rendererMethodAllowed } from '../../apps/desktop/electron/renderer-policy.mjs';

function setup(t) {
  const key=Buffer.alloc(32,7),nonce='a'.repeat(32),expected={workerPid:123,configSha256:'b'.repeat(64),launcherSha256:'c'.repeat(64),targetSha256:'d'.repeat(64)};
  let now=Date.now(),alive=true,seq=0;
  const provider=new TrustedSessionProvider({key,nonce,expected,alive:()=>alive,now:()=>now});
  const publisher=new MixerSnapshotPublisher({source:provider.source,minIntervalMs:0,now:()=>now});
  t.after(()=>{publisher.close();provider.close();});
  const data={binding:{operation_id:'test-operation',controller_build_id:'test-build',session_id:'test-session',project_generation:'test-project',host_generation:'pid:456:module:'+'f'.repeat(32)},observedAt:new Date(now).toISOString(),observationId:'test-observation',targetSha256:expected.targetSha256};
  const packet=(kind,data,override={})=>{const body=JSON.stringify({version:1,kind,nonce,sequence:++seq,processId:123,runId:'test-run',configSha256:expected.configSha256,scope:'LIVE_READONLY',data,...override});return{body,mac:createHmac('sha256',key).update(body).digest('hex')};};
  const hello=()=>provider.accept(packet('hello',{launcherSha256:expected.launcherSha256}));
  return {provider,publisher,adapter:new PublishedMixerAdapter(publisher),data,packet,hello,now:value=>now=value,exit:()=>alive=false};
}
test('认证worker身份发布Session但不发布Mixer或插件；消费和订阅不启动任务',async t=>{
  const x=setup(t);x.hello();x.provider.accept(x.packet('session',x.data));
  const cancels=Array.from({length:16},()=>x.publisher.subscribe(()=>{}));
  const first=await x.publisher.refresh();assert.equal(await x.publisher.refresh(),first);
  const w=x.adapter.accept(first);assert.equal(w.session.sessionId,'test-session');assert.equal(w.presentation,'real-live');
  assert.deepEqual(w.tracks,[]);assert.equal(w.target,null);assert.equal(w.publisher.levels.identity,'not-ready');cancels.forEach(fn=>fn());
});
test('普通JSON、自报passed、错误MAC、来源PID/nonce/config/模拟消息拒绝',t=>{
  for(const override of [{processId:999},{nonce:'e'.repeat(32)},{configSha256:'e'.repeat(64)},{scope:'SIMULATED'}]) {
    const x=setup(t);assert.throws(()=>x.provider.accept(x.packet('hello',{launcherSha256:'c'.repeat(64)},override)));
  }
  const x=setup(t);assert.throws(()=>x.provider.accept({passed:true,body:'{}',mac:'0'.repeat(64)}));assert.throws(()=>x.provider.read());
});
test('Host/Plugin消息不能混淆；未握手、未知类型和重复序列拒绝',t=>{
  const a=setup(t);assert.throws(()=>a.provider.accept(a.packet('session',a.data)));
  const b=setup(t);b.hello();assert.throws(()=>b.provider.accept(b.packet('plugin',b.data)));
  const c=setup(t);c.hello();const frame=c.packet('session',c.data);c.provider.accept(frame);assert.throws(()=>c.provider.accept(frame));
});
test('错目标、身份变化、过期、超时或退出撤销旧信封且不能复活',async t=>{
  for(const mode of ['target','session','stale','timeout','exit']) {
    const x=setup(t);x.hello();x.provider.accept(x.packet('session',x.data));const old=await x.publisher.refresh();
    if(mode==='target'){x.data.targetSha256='e'.repeat(64);assert.throws(()=>x.provider.accept(x.packet('session',x.data)));}
    if(mode==='session'){x.data.binding.session_id='changed';assert.throws(()=>x.provider.accept(x.packet('session',x.data)));}
    if(mode==='stale'){x.now(Date.parse(x.data.observedAt)+15001);assert.throws(()=>x.provider.accept(x.packet('session',x.data)));}
    if(mode==='timeout')x.now(Date.parse(x.data.observedAt)+1501);
    if(mode==='exit')x.exit();
    assert.throws(()=>x.adapter.accept(old));assert.throws(()=>x.provider.read());
  }
});
test('IPC仍不能启动、注册或控制会话；关闭与取消撤销来源',async t=>{
  const x=setup(t);x.hello();x.provider.accept(x.packet('session',x.data));const old=await x.publisher.refresh();
  x.provider.close();assert.throws(()=>x.adapter.accept(old));
  for(const method of ['HOST_SESSION_IDENTITY_READ','TARGET_PLUGIN_IDENTITY_READ','startHost','registerSessionProvider','publishSession']) assert.equal(rendererMethodAllowed(method,false),false);
});
test('未授权现场配置在创建worker前拒绝，不能借已确认fixture启动',async t=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'session-spec-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));
  const configPath=path.join(dir,'config.json'),bytes=Buffer.from(JSON.stringify({mode:'LIVE_READONLY',test_operation:'HOST_SESSION_IDENTITY_READ',session_stream:true,live_authorized:false}));await fs.writeFile(configPath,bytes);
  const {createHash}=await import('node:crypto');const configSha256=createHash('sha256').update(bytes).digest('hex');
  await assert.rejects(startTrustedSessionWorker({configPath,configSha256}),/SESSION_LIVE_AUTHORIZATION_REQUIRED/);
});
test('退出发生在源码校验期间时，创建worker前取消',async t=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'session-cancel-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));
  const {createHash}=await import('node:crypto');const hash=data=>createHash('sha256').update(data).digest('hex');
  const launcherPath=path.join(dir,'launcher.py'),python=path.join(dir,'python.exe');
  await fs.writeFile(launcherPath,'not executable','utf8');await fs.writeFile(python,'not executable','utf8');
  const launcherSha256=hash(await fs.readFile(launcherPath)),pythonSha256=hash(await fs.readFile(python));
  const configPath=path.join(dir,'config.json'),bytes=Buffer.from(JSON.stringify({mode:'LIVE_READONLY',live_authorized:true,
    test_operation:'HOST_SESSION_IDENTITY_READ',session_stream:true,external_sources:{'dawloop_automix_live_session.py':launcherSha256}}));
  await fs.writeFile(configPath,bytes);await assert.rejects(startTrustedSessionWorker({configPath,configSha256:hash(bytes),launcherPath,launcherSha256,python,pythonSha256},{cancelled:()=>true}),/SESSION_START_CANCELLED/);
});
