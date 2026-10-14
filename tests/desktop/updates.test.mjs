// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 ryurikoneko
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {EventEmitter} from 'node:events';
import {DesktopUpdates,RELEASES,GATE,REPOSITORY,compare,gateAllows,selectRelease} from '../../packages/desktop-updates/service.mjs';
import {windowsNotifier} from '../../apps/desktop/electron/update-toast.mjs';

const release=(version='v0.6.0',extra={})=>({id:1,name:'DAWLoop Desktop '+version,tag_name:version,draft:false,prerelease:version.includes('-'),published_at:'2026-10-14T00:00:00Z',html_url:REPOSITORY+'/releases/tag/'+version,body:'Synthetic test release notes',...extra});
const gate=(version='v0.6.0',extra={})=>({schema_version:2,product:'dawloop-desktop',version,release_id:1,channel:version.includes('-')?'preview':'stable',notification_enabled:true,approved_by_owner:true,approved_owner:'ryurikoneko',approval_command:'ENABLE_PUBLIC_UPDATE_NOTIFICATION',active_approval_id:'test-only',approvals:[{approval_id:'test-only',owner:'ryurikoneko',command:'ENABLE_PUBLIC_UPDATE_NOTIFICATION',version,release_id:extra.release_id||1,channel:version.includes('-')?'preview':'stable',content_url:REPOSITORY+'/releases/tag/'+version,approved_at:'2026-10-14T00:00:00Z',expires_at:'2026-10-21T00:00:00Z'}],revocations:[],...extra});
function setup(t,{items=[release()],remoteGate=gate(),version='0.5.6',buildChannel='stable',failure=false}={}) {
  const root=fs.mkdtempSync(path.join(process.env.DAWLOOP_TEST_OUTPUT_ROOT||os.tmpdir(),'updates-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));let clock=Date.parse('2026-10-14T01:00:00Z');const notices=[],requests=[],opened=[];
  const options={file:path.join(root,'state.json'),version,buildChannel,now:()=>clock,notify:payload=>{notices.push(payload);return true;},open:url=>opened.push(url),fetcher:async(url,params)=>{requests.push({url,params});if(failure)throw Error('offline');return new Response(JSON.stringify(url===RELEASES?items:remoteGate));}};
  const service=new DesktopUpdates(options);service.configure({notifications:true});
  return {service,options,notices,requests,opened,advance:()=>{clock+=86400001;},tick:ms=>{clock+=ms;}};
}
test('无更新不通知',async t=>{const f=setup(t,{items:[release('v0.5.6')],localGate:gate('v0.5.6'),remoteGate:gate('v0.5.6')});assert.equal((await f.service.check()).status,'UP_TO_DATE');assert.equal(f.notices.length,0);});
test('批准的新Stable显示一次通知；点击仅打开相应发布页',async t=>{const f=setup(t);const r=await f.service.check();assert.equal(r.status,'UPDATE_AVAILABLE');assert.equal(f.notices.length,1);assert.match(f.notices[0].title,/DAWLoop/);await f.notices[0].onClick();assert.deepEqual(f.opened,[release().html_url]);await f.service.check();assert.equal(f.notices.length,1);assert.equal(f.requests.length,2);});
test('Stable用户不收到Preview；主动选择Preview才能收到',async t=>{const a=setup(t,{items:[release('v0.6.0-beta.1')],localGate:gate('v0.6.0-beta.1'),remoteGate:gate('v0.6.0-beta.1')});await a.service.check();assert.equal(a.notices.length,0);const b=setup(t,{items:[release('v0.6.0-beta.1')],localGate:gate('v0.6.0-beta.1'),remoteGate:gate('v0.6.0-beta.1')});b.service.configure({channel:'preview'});assert.equal((await b.service.check()).status,'UPDATE_AVAILABLE');assert.equal(b.notices.length,1);});
test('Preview通道接受后续正式版',async t=>{const f=setup(t,{version:'0.6.0-beta.1'});f.service.configure({channel:'preview'});assert.equal((await f.service.check()).status,'UPDATE_AVAILABLE');});
test('默认关闭开关：不提示、不暴露未批准候选',async t=>{const g=JSON.parse(fs.readFileSync(new URL('../../release_notification.json',import.meta.url),'utf8'));const f=setup(t,{remoteGate:g});const r=await f.service.check();assert.equal(r.publicPush,'DISABLED');assert.equal(r.release,null);assert.equal(r.status,'UNKNOWN');assert.equal(f.notices.length,0);await assert.rejects(f.service.openRelease());});
test('同一旧客户端可以接收后续独立批准的Release，不固定安装时的版本',async t=>{const f=setup(t);await f.service.check();f.advance();f.service.fetcher=async url=>new Response(JSON.stringify(url===RELEASES?[release('v0.7.0',{id:2})]:gate('v0.7.0',{release_id:2})));assert.equal((await f.service.check()).release.version,'v0.7.0');assert.equal(f.notices.length,2);});
test('任意一个审批条件缺失都拒绝',async t=>{for(const [key,value] of Object.entries({notification_enabled:false,approved_by_owner:false,approved_owner:'other',approval_command:null,release_id:2,version:'v0.7.0',channel:'internal',product:'core'})){const f=setup(t,{remoteGate:gate('v0.6.0',{[key]:value})});assert.equal((await f.service.check()).publicPush,'DISABLED');assert.equal(f.notices.length,0);}});
test('Internal构建不能向用户通知',async t=>{const f=setup(t,{buildChannel:'internal'});assert.equal((await f.service.check()).release,null);assert.equal(f.notices.length,0);});
test('Internal Release与Draft永远被过滤',()=>{assert.equal(selectRelease([release('v0.7.0-internal'),release('v0.8.0',{draft:true})],'preview'),null);});
test('Core Release不冒充Desktop版本',()=>{assert.equal(selectRelease([release('v1.0.0',{name:'DAWLoop Core'})],'preview'),null);});
test('网络失败不声称最新，且24h内不反复请求',async t=>{const f=setup(t,{failure:true});assert.equal((await f.service.check()).status,'CHECK_FAILED');await f.service.check();assert.equal(f.requests.length,1);f.advance();await f.service.check();assert.equal(f.requests.length,2);assert.equal(f.notices.length,0);});
test('关闭检查不发送请求',async t=>{const f=setup(t);f.service.configure({enabled:false});assert.equal((await f.service.check()).status,'CHECK_DISABLED');assert.equal(f.requests.length,0);});
test('关闭Windows通知保留获批应用内更新',async t=>{const f=setup(t);f.service.configure({notifications:false});assert.equal((await f.service.check()).status,'UPDATE_AVAILABLE');assert.equal(f.notices.length,0);});
test('稍后提醒与seen跨重启持久化',async t=>{const f=setup(t);f.service.snooze();await f.service.check();assert.equal(f.notices.length,0);const again=new DesktopUpdates(f.options);await again.check();assert.equal(f.notices.length,0);});
test('关闭通知后重启不再骚扰',async t=>{const f=setup(t);await f.service.check();f.notices[0].onClose();const again=new DesktopUpdates(f.options);await again.check();assert.equal(f.notices.length,1);});
test('升级后的安装重新比较缓存版本，不建议重复更新或降级',async t=>{const f=setup(t);await f.service.check();const upgraded=new DesktopUpdates({...f.options,version:'0.6.0'});assert.equal((await upgraded.check()).status,'UP_TO_DATE');const ahead=new DesktopUpdates({...f.options,version:'0.6.1'});assert.equal((await ahead.check()).status,'UP_TO_DATE');assert.equal(f.notices.length,1);});
test('并发启动只执行一次请求链',async t=>{const f=setup(t);await Promise.all([f.service.check(),f.service.check(),f.service.check()]);assert.equal(f.requests.length,2);assert.equal(f.notices.length,1);});
test('切换频道不绕过24h网络限制',async t=>{const f=setup(t);await f.service.check();f.service.configure({channel:'preview'});await f.service.check();assert.equal(f.requests.length,2);});
test('损坏缓存重新检查，恶意URL不能被打开',async t=>{const f=setup(t);fs.writeFileSync(f.options.file,'{invalid','utf8');const service=new DesktopUpdates({...f.options,fetcher:async()=>new Response(JSON.stringify([release('v0.6.0',{html_url:'https://evil.invalid'})]))});assert.equal((await service.check()).status,'UNKNOWN');await assert.rejects(service.openRelease());});
test('JSON异常/限流/超时仅返回CHECK_FAILED',async t=>{for(const mode of ['json','http','timeout']){const f=setup(t);f.service.fetcher=async()=>{if(mode==='timeout')throw Error('timeout');return new Response(mode==='json'?'invalid':'{}',{status:mode==='http'?429:200});};assert.equal((await f.service.check()).status,'CHECK_FAILED');}});
test('不向服务器传工程、路径、模型或本机版本数据',async t=>{const f=setup(t);await f.service.check();for(const r of f.requests){assert.ok([RELEASES,GATE].includes(r.url));assert.equal(r.params.body,undefined);assert.equal(r.params.credentials,'omit');assert.deepEqual(Object.keys(r.params.headers).sort(),['Accept','User-Agent']);}});
test('Renderer没有开启公共通知的方法或参数',async t=>{const f=setup(t);await assert.rejects(f.service.call('ENABLE_PUBLIC_UPDATE_NOTIFICATION'));assert.throws(()=>f.service.configure({approved_by_owner:true}));});
test('fader/FL/Music文件不属于更新模块',()=>{const source=fs.readFileSync(new URL('../../packages/desktop-updates/service.mjs',import.meta.url),'utf8');for(const token of ['flstudio','MusicIntelligence','execFile','autoUpdater'])assert.equal(source.includes(token),false);});
test('semantic版本不按字符串排序',()=>{assert.equal(compare('0.5.10','0.5.9'),1);assert.equal(compare('0.6.0a1','0.6.0'),-1);assert.equal(compare('0.6.0a4.dev2','0.6.0a3'),1);assert.equal(compare('unknown','0.6.0'),null);});
test('Toast软件名称、官方Icon、单次展示和点击绑定正确',async()=>{
  class Fake extends EventEmitter {static isSupported(){return true;}constructor(options){super();this.options=options;Fake.latest=this;}show(){this.shown=(this.shown||0)+1;}}
  let clicked=0,closed=0;const notify=windowsNotifier(Fake,'official.ico','win32');
  assert.equal(notify({title:'DAWLoop update available',body:'Synthetic notification',onClick:()=>clicked++,onClose:()=>closed++,id:'dawloop-update',groupId:'dawloop-updates'}),true);
  assert.equal(Fake.latest.options.icon,'official.ico');assert.equal(Fake.latest.shown,1);assert.equal(Fake.latest.options.silent,true);
  Fake.latest.emit('click');await new Promise(resolve=>setImmediate(resolve));assert.equal(clicked,1);Fake.latest.emit('close');assert.equal(closed,1);
});
test('不支持系统通知时安全返回',()=>{assert.equal(windowsNotifier({isSupported:()=>false},'official.ico','win32')({}),false);});
test('生产用户默认不启用系统通知',t=>{const f=setup(t);assert.equal(new DesktopUpdates({...f.options,file:f.options.file+'.new'}).get().preferences.notifications,false);});
test('旧缓存默认true不等于用户确认；明确选择跨重启保留',t=>{const f=setup(t);const s=JSON.parse(fs.readFileSync(f.options.file,'utf8'));delete s.notificationConsent;fs.writeFileSync(f.options.file,JSON.stringify(s));assert.equal(new DesktopUpdates(f.options).get().preferences.notifications,false);f.service.configure({notifications:true});assert.equal(new DesktopUpdates(f.options).get().preferences.notifications,true);});
test('布尔开关、旧合同和重复审批均不能授权通知',()=>{
  const r=selectRelease([release()],'stable'),now=Date.parse('2026-10-14T01:00:00Z');
  for(const g of [gate('v0.6.0',{schema_version:1}),gate('v0.6.0',{approvals:[]}),gate('v0.6.0',{approvals:[...gate().approvals,...gate().approvals]})])assert.equal(gateAllows(g,r,now),false);
});
test('撤销与过期审批拒绝且不会批准下一版本',()=>{
  const r=selectRelease([release()],'stable');
  assert.equal(gateAllows(gate('v0.6.0',{revocations:[{approval_id:'test-only',reason:'test rollback'}]}),r,Date.parse('2026-10-14T01:00:00Z')),false);
  assert.equal(gateAllows(gate(),r,Date.parse('2026-10-22T01:00:00Z')),false);
  assert.equal(gateAllows(gate(),selectRelease([release('v0.7.0')],'stable'),Date.parse('2026-10-14T01:00:00Z')),false);
});
test('撤销检查五分钟内失效，离线不复用旧批准',async t=>{
  const f=setup(t);await f.service.check();f.tick(300001);assert.equal(f.service.get().publicPush,'DISABLED');
  f.service.fetcher=async()=>{throw Error('offline');};await f.service.check();assert.equal(f.service.get().publicPush,'DISABLED');assert.equal(f.notices.length,1);
});
