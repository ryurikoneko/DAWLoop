import test from 'node:test';
import assert from 'node:assert/strict';
import { MixerSnapshotPublisher, validateMixerSnapshot, localObservation } from '../../packages/core-snapshot/index.mjs';
import { PublishedMixerAdapter } from '../../packages/core-adapter/published.mjs';
import { fixture } from './world-fixture.mjs';
import { AppCore } from '../../packages/app-core/index.mjs';
import { unavailable } from '../../packages/core-adapter/index.mjs';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

function setup() {
  let now=Date.now(), n=0;
  const sessionBinding={session_id:'test-session',project_generation:'test-generation',host_generation:'test-host'};
  const world=fixture(now);
  Object.assign(sessionBinding,{session_id:world.session.sessionId,project_generation:world.session.projectGeneration,host_generation:world.session.hostId});
  const targetBinding={...sessionBinding,operation_id:'offline-operation',controller_build_id:'offline-build',mixer_track:1,effect_slot:0,raw_plugin_name:'Synthetic plugin',api_version:26};
  let observation={schemaVersion:1,sourceBackend:'validated-core',observationId:'offline-observation',observedAt:world.observedAt,sessionBinding,targetBinding,pluginIdentity:{instanceId:world.target.instanceId,rawPluginName:'Synthetic plugin',format:null,continuity:'verified'},
    world,connection:null,levels:{session:'available',structure:'available',identity:'available',layout:'available',values:'available'},errors:[],reasonCodes:['OFFLINE_TEST_ONLY']};
  let current={connected:true,sessionBinding:structuredClone(sessionBinding),targetBinding:structuredClone(targetBinding),instanceId:world.target.instanceId};
  const source={sourceBackend:'validated-core',read:()=>{n++;return observation;},verify:()=>true,currentBinding:()=>current};
  const publisher=new MixerSnapshotPublisher({source,now:()=>now,minIntervalMs:0,timeoutMs:50});
  const adapter=new PublishedMixerAdapter(publisher);
  return {publisher,adapter,source,get observation(){return observation;},set observation(v){observation=v;},current,setNow:v=>now=v,reads:()=>n};
}
test('合法内部发布、显式验证器、相同快照幂等；复制凭据不受信',async()=>{
  const x=setup(); const a=await x.publisher.refresh(), b=await x.publisher.refresh();
  assert.equal(a,b); assert.equal(a.snapshot.sequence,1); assert.ok(Object.isFrozen(a.snapshot.world));
  const world=x.adapter.accept(a);assert.equal(world.presentation,'real-live');assert.equal(world.tracks[0].slots[0].plugin.parameters[0].value,0.5);
  assert.equal(world.tracks[0].slots[0].plugin.writeEnabled,false);
  assert.throws(()=>x.adapter.accept(structuredClone(a)),/SOURCE_REJECTED/);
  const other=setup(); assert.throws(()=>other.adapter.accept(a),/SOURCE_REJECTED/);x.publisher.close();other.publisher.close();
});
test('不匹配schema、缺字段、非法来源和超大合同拒绝',async()=>{
  const x=setup(), raw=structuredClone((await x.publisher.refresh()).snapshot);
  for(const mutate of [s=>s.schemaVersion=2,s=>delete s.observationId,s=>delete s.levels,s=>s.sourceBackend='mock',s=>s.tracks.push(s.tracks[0]),s=>s.sequence=-1,s=>s.errors='bad',s=>s.connection={},s=>s.pluginIdentity.format=4]) {
    const s=structuredClone(raw);mutate(s);assert.throws(()=>validateMixerSnapshot(s));
  }
  assert.throws(()=>validateMixerSnapshot({...raw,extra:'x'.repeat(2*1024*1024)}),/TOO_LARGE/);x.publisher.close();
});
test('保留真实来源格式的完整构建标识，拒绝截断匹配和非法标识',async()=>{
  const x=setup();
  const build='git:'+'a'.repeat(40)+'+controller:'+'b'.repeat(16)+'+readonly:'+'c'.repeat(16)+'+backend:'+'d'.repeat(16)+'+lifecycle:'+'e'.repeat(16)+'+profile:plugin-identity-discovery-v1+target-code:'+'f'.repeat(16)+'+target:'+'0'.repeat(16);
  assert.ok(build.length>160);
  x.observation.targetBinding.controller_build_id=build;
  x.current.targetBinding.controller_build_id=build;
  const envelope=await x.publisher.refresh();
  assert.equal(envelope.snapshot.targetBinding.controller_build_id,build);
  for(const invalid of ['',build+'\n','x'.repeat(1025),build+' /']) {
    const raw=structuredClone(envelope.snapshot);raw.targetBinding.controller_build_id=invalid;
    assert.throws(()=>validateMixerSnapshot(raw),/TARGET_BINDING_INVALID/);
  }
  x.current.targetBinding.controller_build_id=build.slice(0,160);
  assert.throws(()=>x.adapter.accept(envelope),/TARGET_CHANGED/);
  x.publisher.close();
});
test('来源输入版本、Mock标签、不完整布局和非归一化值在发布前拒绝',async()=>{
  for(const mutate of [o=>o.schemaVersion=2,o=>o.sourceBackend='mock',o=>o.world.tracks[0].slots[0].plugin.parameters=[],o=>o.world.tracks[0].slots[0].plugin.parameters[0].value=2,o=>delete o.sessionBinding,o=>o.pluginIdentity.continuity='unknown']) {
    const x=setup();mutate(x.observation);await assert.rejects(x.publisher.refresh());x.publisher.close();
  }
});
test('会话、工程、Slot、轨道、实例及连接变化撤销旧发布凭据',async()=>{
  for (const change of [c=>c.sessionBinding.session_id='new-session',c=>c.sessionBinding.project_generation='new-project',c=>c.targetBinding.effect_slot=1,c=>c.targetBinding.mixer_track=2,c=>c.instanceId='replacement',c=>c.connected=false]) {
    const x=setup(), old=await x.publisher.refresh();change(x.current);assert.throws(()=>x.adapter.accept(old));assert.ok(x.publisher.history.length);
    assert.throws(()=>x.adapter.accept(old));x.publisher.close();
  }
});
test('过期保留诊断元数据但GUI不得继续显示绑定、轨道或参数',async()=>{
  const x=setup(), e=await x.publisher.refresh();x.setNow(Date.parse(e.snapshot.observedAt)+15001);
  const world=x.adapter.accept(e);assert.equal(world.presentation,'real-cached');assert.equal(world.state,'stale');assert.deepEqual(world.tracks,[]);assert.equal(world.session,null);assert.equal(world.target,null);assert.ok(world.publisher.snapshotId);x.publisher.close();
});
test('乱序观察与同ID不同内容拒绝；旧凭据不能重放',async()=>{
  for(const mutate of [o=>{o.observationId='older';o.observedAt=new Date(Date.parse(o.observedAt)-1).toISOString();},o=>o.world.tracks[0].name='changed']) {
    const x=setup(), e=await x.publisher.refresh();mutate(x.observation);await assert.rejects(x.publisher.refresh());assert.throws(()=>x.adapter.accept(e));x.publisher.close();
  }
  const x=setup();await x.publisher.refresh();x.publisher.invalidate('SOURCE_RECONNECTING');
  x.observation.observationId='older-after-reconnect';x.observation.observedAt=new Date(Date.parse(x.observation.observedAt)-1).toISOString();
  await assert.rejects(x.publisher.refresh(),/SEQUENCE_ROLLBACK/);x.publisher.close();
});
test('Core退出及来源校验失败不能使用passed自报声明',async()=>{
  const x=setup();x.source.verify=()=>false;
  const p=new MixerSnapshotPublisher({source:x.source});await assert.rejects(p.refresh(),/SOURCE_REJECTED/);p.close();x.publisher.close();
  const y=setup(), e=await y.publisher.refresh();y.publisher.close();assert.throws(()=>y.adapter.accept(e),/SOURCE_REJECTED/);await assert.rejects(y.publisher.refresh(),/DISCONNECTED/);
});
test('Mock不能注册真实发布器；本地观察无会话身份且不能晋级Mixer',async()=>{
  const source={sourceBackend:'mock',read:()=>{},verify:()=>true,currentBinding:()=>({connected:true})};assert.throws(()=>new MixerSnapshotPublisher({source}),/SOURCE_REJECTED/);
  const observation=localObservation(null);const p=new MixerSnapshotPublisher({source:{...source,sourceBackend:'local-observer',read:()=>observation}});
  const w=await new PublishedMixerAdapter(p).world();assert.equal(w.presentation,'unavailable');assert.deepEqual(w.tracks,[]);assert.equal(w.publisher.levels.session,'unknown');p.close();
});
test('每级独立关闭，后级不能越过前级；未晋级参数在Adapter内消失',async()=>{
  for (const level of ['identity','layout','values']) {
    const x=setup(), keys=['identity','layout','values'];for(const key of keys.slice(keys.indexOf(level)))x.observation.levels[key]='not-ready';
    const w=await x.adapter.world(), p=w.tracks[0].slots[0].plugin;
    if(level==='identity')assert.equal(p,null);else if(level==='layout'){assert.deepEqual(p.parameters,[]);assert.equal(p.parameterCount,null);}else assert.equal(p.parameters[0].value,null);
    assert.equal(w.capabilities.find(c=>c.id==='plugin.parameter.read').promotion.enabled,false);x.publisher.close();
  }
  const x=setup();x.observation.levels.structure='partial';assert.equal((await x.adapter.world()).presentation,'unavailable');x.publisher.close();
});
test('实例ID不可获得时保留null；缺少连续性验证不允许晋级',async()=>{
  const x=setup();x.observation.world.target.instanceId=null;x.observation.world.tracks[0].slots[0].plugin.instanceId=null;
  x.observation.world.capabilities.forEach(c=>{if(c.evidence[0].binding.instanceId!==null)c.evidence[0].binding.instanceId=null;});
  x.observation.pluginIdentity.instanceId=null;x.current.instanceId=null;
  assert.equal((await x.adapter.world()).presentation,'unavailable');x.current.continuityVerified=true;
  const w=await x.adapter.world();assert.equal(w.tracks[0].slots[0].plugin.instanceId,null);x.publisher.close();
});
test('timeout取消后仍等待原观察退出，不重叠发起；退出后晚到结果不得发布',async()=>{
  let resolve, reads=0, signal;
  const source={sourceBackend:'local-observer',read:s=>{signal=s;reads++;return new Promise(r=>resolve=r);},verify:()=>true,currentBinding:()=>({connected:true})};
  const p=new MixerSnapshotPublisher({source,timeoutMs:10,minIntervalMs:0});const adapter=new PublishedMixerAdapter(p);
  assert.equal((await adapter.world()).reason,'CORE_TIMEOUT');assert.equal(signal.aborted,true);
  assert.equal((await adapter.world()).reason,'CORE_TIMEOUT');assert.equal(reads,1);
  p.close();resolve(localObservation(null));await new Promise(r=>setTimeout(r,0));assert.equal(reads,1);
});
test('订阅取消、数量上限及失效通知；慢订阅不建立新观察任务',async()=>{
  const x=setup(), events=[];const unsub=x.publisher.subscribe(e=>events.push(e));await x.publisher.refresh();await Promise.resolve();assert.equal(events.length,1);
  unsub();x.publisher.invalidate('TEST_INVALIDATION');await Promise.resolve();assert.equal(events.length,1);
  const cancels=Array.from({length:16},()=>x.publisher.subscribe(()=>{}));assert.throws(()=>x.publisher.subscribe(()=>{}));cancels.forEach(fn=>fn());x.publisher.close();
});
test('已验证来源经AppCore强类型方法消费；getWorld不触发Python观察或扫描',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-publisher-'));
  const x=setup();let spawned=0;
  const core=new AppCore({roamingRoot:root,localRoot:root,trustedReadSource:x.source,realAdapter:{snapshot:()=>{spawned++;throw Error();},close:()=>{}}});
  await core.initialize();t.after(async()=>{await core.close();x.publisher.close();await fs.rm(root,{recursive:true,force:true});});
  const w=(await core.call('getWorldSnapshot')).data;assert.equal(w.presentation,'real-live');assert.equal(w.tracks[0].slots[0].plugin.parameters[0].value,0.5);assert.equal(spawned,0);
  assert.equal((await core.call('publishMixerSnapshot',fixture())).ok,false);
  x.current.connected=false;assert.equal((await core.call('getWorldSnapshot')).data.presentation,'unavailable');assert.equal(spawned,0);
});
test('失败来源同样受频率限制；并发消费只发起一次观察',async()=>{
  let reads=0;
  const source={sourceBackend:'local-observer',read:()=>{reads++;throw Error('exit');},verify:()=>true,currentBinding:()=>({connected:true})};
  const p=new MixerSnapshotPublisher({source});await Promise.allSettled([p.refresh(),p.refresh(),p.refresh()]);assert.equal(reads,1);
  await assert.rejects(p.refresh(),/RATE_LIMITED/);assert.equal(reads,1);p.close();
});
test('默认来源复用已观察时间且只发布Partial会话，getWorld不重复启动观察',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-local-source-'));let reads=0;
  const core=new AppCore({roamingRoot:root,localRoot:root,realAdapter:{snapshot:async()=>{reads++;return unavailable();},close:()=>{}}});
  await core.initialize();t.after(async()=>{await core.close();await fs.rm(root,{recursive:true,force:true});});
  const status=(await core.call('getAppStatus')).data;
  const w=(await core.call('getWorldSnapshot')).data;assert.equal(w.observedAt,status.observedAt);assert.equal(w.publisher.levels.session,'partial');assert.deepEqual(w.tracks,[]);assert.equal(w.session,null);assert.equal(w.presentation,'unavailable');
  await core.call('getWorldSnapshot');assert.equal(reads,1);
});
