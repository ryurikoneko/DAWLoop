// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 ryurikoneko
import fs from 'node:fs';
import path from 'node:path';

export const REPOSITORY='https://github.com/ryurikoneko/DAWLoop';
export const RELEASES='https://api.github.com/repos/ryurikoneko/DAWLoop/releases?per_page=100';
export const GATE='https://raw.githubusercontent.com/ryurikoneko/DAWLoop/main/release_notification.json';
const DAY=86400000;
const GATE_TTL=300000;
export function versionKey(value) {
  if(typeof value!=='string')return null;
  const m=/^v?(\d+)\.(\d+)\.(\d+)(?:[-.]?(alpha|beta|rc|a|b)[.-]?(\d*))?(?:\.dev(\d+))?$/.exec(value);
  if(!m)return null;
  return [+m[1],+m[2],+m[3],m[4]?{alpha:0,a:0,beta:1,b:1,rc:2}[m[4]]:m[6]!==undefined?-1:3,+(m[5]||0),m[6]===undefined?1:0,+(m[6]||0)];
}
export function compare(a,b) { const x=versionKey(a),y=versionKey(b);if(!x||!y)return null;for(let i=0;i<x.length;i++)if(x[i]!==y[i])return Math.sign(x[i]-y[i]);return 0; }
export function releaseUrl(url) { return typeof url==='string'&&/^https:\/\/github\.com\/ryurikoneko\/DAWLoop\/releases\/tag\/[A-Za-z0-9._-]+$/.test(url); }
export function selectRelease(items,channel) {
  if(!Array.isArray(items))throw Error('INVALID_RELEASE_JSON');
  const candidates=items.filter(r=>r&&r.draft===false&&Number.isSafeInteger(r.id)&&r.id>0&&
    typeof r.name==='string'&&(r.name.startsWith('DAWLoop Desktop ')||r.body?.includes('<!-- dawloop-product: desktop -->'))&&
    typeof r.tag_name==='string'&&!/internal/i.test(r.tag_name)&&versionKey(r.tag_name)&&releaseUrl(r.html_url)&&r.html_url===REPOSITORY+'/releases/tag/'+r.tag_name&&
    Number.isFinite(Date.parse(r.published_at))&&(channel==='preview'||r.prerelease===false&&versionKey(r.tag_name)[3]===3));
  const r=candidates.sort((a,b)=>compare(b.tag_name,a.tag_name))[0];
  return r?{id:r.id,version:r.tag_name,url:r.html_url,publishedAt:r.published_at,notes:String(r.body||'').replace(/<!--.*?-->/gs,'').replace(/[\x00-\x08\x0b-\x1f]/g,'').slice(0,1500),channel:r.prerelease||versionKey(r.tag_name)[3]!==3?'preview':'stable'}:null;
}
export function gateAllows(gate,release,now=Date.now()) {
  if(!(gate&&release&&gate.schema_version===2&&gate.product==='dawloop-desktop'&&
    gate.notification_enabled===true&&gate.approved_by_owner===true&&gate.approved_owner==='ryurikoneko'&&
    gate.approval_command==='ENABLE_PUBLIC_UPDATE_NOTIFICATION'&&gate.version===release.version&&
    gate.release_id===release.id&&gate.channel===release.channel&&gate.channel!=='internal'))return false;
  if(!Array.isArray(gate.approvals)||!Array.isArray(gate.revocations))return false;
  const entries=gate.approvals.filter(a=>a?.approval_id===gate.active_approval_id);
  if(entries.length!==1||gate.revocations.some(r=>r?.approval_id===gate.active_approval_id))return false;
  const a=entries[0],issued=Date.parse(a.approved_at),expires=Date.parse(a.expires_at);
  return typeof a.approval_id==='string'&&/^[A-Za-z0-9._-]{1,100}$/.test(a.approval_id)&&
    a.owner==='ryurikoneko'&&a.command==='ENABLE_PUBLIC_UPDATE_NOTIFICATION'&&
    a.version===release.version&&a.release_id===release.id&&a.channel===release.channel&&
    a.content_url===release.url&&Number.isFinite(issued)&&issued<=now&&
    Number.isFinite(expires)&&expires>now&&expires-issued<=30*DAY;
}
function readState(file) {
  try {if(fs.statSync(file).size>65536)return null;const v=JSON.parse(fs.readFileSync(file,'utf8'));return v?.schema===1?v:null;}catch{return null;}
}
export async function fetchJson(url,fetcher) {
  const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),3000);
  try {
    const response=await fetcher(url,{signal:abort.signal,redirect:'error',credentials:'omit',headers:{Accept:'application/json','User-Agent':'DAWLoop-Desktop'}});
    if(!response.ok)throw Error('UPDATE_HTTP_FAILED');
    const reader=response.body.getReader();let size=0;const chunks=[];
    try {while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>1024*1024)throw Error('UPDATE_RESPONSE_TOO_LARGE');chunks.push(Buffer.from(value));}}
    finally {await reader.cancel().catch(()=>{});}
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } finally {clearTimeout(timer);}
}

export class DesktopUpdates {
  constructor({file,version,buildChannel='internal',fetcher=fetch,notify=()=>false,open=()=>{},now=Date.now,language=()=> 'en-US'}) {
    this.file=file;this.version=version;this.buildChannel=buildChannel;this.fetcher=fetcher;this.notify=notify;this.open=open;this.now=now;this.language=language;
    this.manualObservation=null;
    const state=readState(file);
    this.state={schema:1,preferences:{enabled:true,channel:'stable',notifications:false},checkedAt:null,gateCheckedAt:null,checkStatus:'UNKNOWN',release:null,remoteGate:null,seen:[],snoozeUntil:0};
    if(state) {
      if(typeof state.preferences?.enabled==='boolean')this.state.preferences.enabled=state.preferences.enabled;
      if(state.notificationConsent==='USER_OPT_IN'&&state.preferences?.notifications===true){this.state.preferences.notifications=true;this.state.notificationConsent='USER_OPT_IN';}
      if(['stable','preview'].includes(state.preferences?.channel))this.state.preferences.channel=state.preferences.channel;
      if(Number.isFinite(state.checkedAt)&&state.checkedAt>=0&&state.checkedAt<=now()&&['UPDATE_AVAILABLE','UP_TO_DATE','CHECK_FAILED','UNKNOWN'].includes(state.checkStatus)) {
        // 缓存由同一发布解析器重新校验，避免损坏缓存放行链接或跨渠道候选。
        const r=state.release;
        try {this.state.release=r?selectRelease([{id:r.id,name:'DAWLoop Desktop cache',draft:false,prerelease:r.channel==='preview',tag_name:r.version,html_url:r.url,published_at:r.publishedAt,body:r.notes}],this.state.preferences.channel):null;}catch{}
        if(!r||this.state.release){
          this.state.checkedAt=state.checkedAt;this.state.remoteGate=state.remoteGate;
          if(Number.isFinite(state.gateCheckedAt)&&state.gateCheckedAt<=now())this.state.gateCheckedAt=state.gateCheckedAt;
          const comparison=this.state.release?compare(this.version,this.state.release.version):null;
          this.state.checkStatus=state.checkStatus==='CHECK_FAILED'?'CHECK_FAILED':comparison===null?'UNKNOWN':comparison<0?'UPDATE_AVAILABLE':'UP_TO_DATE';
        }
      }
      this.state.seen=Array.isArray(state.seen)?state.seen.filter(x=>typeof x==='string'&&x.length<100).slice(-100):[];
      this.state.snoozeUntil=Number.isFinite(state.snoozeUntil)?state.snoozeUntil:0;
    }
  }
  persist() {
    fs.mkdirSync(path.dirname(this.file),{recursive:true});
    const temporary=this.file+'.tmp';fs.writeFileSync(temporary,JSON.stringify(this.state),{encoding:'utf8',mode:0o600});fs.renameSync(temporary,this.file);
  }
  allowed() {
    const r=this.state.release;
    return ['stable','preview'].includes(this.buildChannel)&&gateAllows(this.state.remoteGate,r,this.now())&&
      this.state.gateCheckedAt!==null&&this.now()-this.state.gateCheckedAt<GATE_TTL&&
      this.state.preferences.enabled&&(r?.channel==='stable'||this.state.preferences.channel==='preview')&&
      this.state.checkStatus==='UPDATE_AVAILABLE'&&this.state.checkedAt!==null&&this.now()-this.state.checkedAt<DAY;
  }
  get() {
    const allowed=this.allowed(),enabled=this.state.preferences.enabled;
    return {version:this.version,preferences:{...this.state.preferences},checkedAt:this.state.checkedAt,
      status:!enabled?'CHECK_DISABLED':this.state.checkStatus==='UPDATE_AVAILABLE'&&!allowed?'UNKNOWN':this.state.checkStatus,
      release:allowed?this.state.release:null,publicPush:allowed?'APPROVED':'DISABLED',snoozeUntil:this.state.snoozeUntil};
  }
  configure(options) {
    if(!options||Object.keys(options).some(k=>!['enabled','channel','notifications'].includes(k))||
      options.enabled!==undefined&&typeof options.enabled!=='boolean'||options.notifications!==undefined&&typeof options.notifications!=='boolean'||
      options.channel!==undefined&&!['stable','preview'].includes(options.channel))throw Error('UPDATE_PREFERENCES_INVALID');
    if(options.channel&&options.channel!==this.state.preferences.channel){this.state.release=null;this.state.checkStatus='UNKNOWN';this.state.remoteGate=null;this.manualObservation=null;}
    if(options.notifications!==undefined)this.state.notificationConsent=options.notifications?'USER_OPT_IN':null;
    Object.assign(this.state.preferences,options);this.persist();return this.get();
  }
  async check() {
    if(!this.state.preferences.enabled)return this.get();
    if(this.pending)return this.pending;
    this.pending=this.checkOnce().finally(()=>{this.pending=null;});return this.pending;
  }
  async checkManual() {
    if(this.manualPending)return this.manualPending;
    this.manualObservation=null;
    this.manualPending=(async()=>{
      try {
        const channel=this.state.preferences.channel;
        const release=selectRelease(await fetchJson(RELEASES,this.fetcher),channel);
        if(channel!==this.state.preferences.channel)throw Error('UPDATE_CHANNEL_CHANGED');
        const checkedAt=this.now(),comparison=release?compare(this.version,release.version):null;
        this.manualObservation={release,checkedAt,channel};
        // 手动查询结果不进入自动提醒缓存，也不授予通知资格。
        return {...this.get(),checkedAt,release,publicPush:'DISABLED',status:comparison===null?'UNKNOWN':comparison<0?'UPDATE_AVAILABLE':'UP_TO_DATE'};
      }catch{return {...this.get(),checkedAt:this.now(),release:null,publicPush:'DISABLED',status:'CHECK_FAILED'};}
    })().finally(()=>{this.manualPending=null;});
    return this.manualPending;
  }
  async checkOnce() {
    if(this.state.checkedAt!==null&&this.now()-this.state.checkedAt<DAY){
      if(this.state.release&&this.state.checkStatus==='UPDATE_AVAILABLE'&&(this.state.gateCheckedAt===null||this.now()-this.state.gateCheckedAt>=GATE_TTL))await this.refreshGate();
      await this.maybeNotify();return this.get();
    }
    try {
      const r=selectRelease(await fetchJson(RELEASES,this.fetcher),this.state.preferences.channel),comparison=r?compare(this.version,r.version):null;
      this.state.release=r;
      this.state.checkStatus=comparison===null?'UNKNOWN':comparison<0?'UPDATE_AVAILABLE':'UP_TO_DATE';
      this.state.remoteGate=comparison!==null&&comparison<0?await fetchJson(GATE,this.fetcher):null;
      this.state.gateCheckedAt=this.now();
    } catch {this.state.release=null;this.state.remoteGate=null;this.state.checkStatus='CHECK_FAILED';}
    this.state.checkedAt=this.now();
    try {this.persist();}catch{this.state.checkStatus='CHECK_FAILED';return this.get();}
    await this.maybeNotify();return this.get();
  }
  async refreshGate() {
    try {this.state.remoteGate=await fetchJson(GATE,this.fetcher);}catch {this.state.remoteGate=null;}
    this.state.gateCheckedAt=this.now();
    try{this.persist();}catch{this.state.remoteGate=null;}
  }
  async maybeNotify() {
    const r=this.state.release,key=r?`${r.id}:${r.version}`:null;
    if(!this.allowed()||!this.state.preferences.notifications||this.state.seen.includes(key)||this.now()<this.state.snoozeUntil)return false;
    // 先落盘再展示；即使关闭事件未送达或程序崩溃，下次启动也不会重复弹窗。
    this.state.seen.push(key);this.state.seen=this.state.seen.slice(-100);try{this.persist();}catch{return false;}
    const chinese=this.language()==='zh-CN';
    try{return await this.notify({title:chinese?'DAWLoop 有新版本':'A new DAWLoop version is available',body:`DAWLoop ${r.version}${r.channel==='preview'?' · Alpha / Preview':''}\n${chinese?'有空时来看看新变化。点击查看更新与下载。':'Explore what is new when you have time. Click to view the update and download.'}`,
      onClick:()=>this.openRelease(),onClose:()=>{},id:'dawloop-update',groupId:'dawloop-updates'});}catch{return false;}
  }
  snooze() {this.state.snoozeUntil=this.now()+7*DAY;this.persist();return this.get();}
  async openRelease() {if(!this.allowed()||!releaseUrl(this.state.release?.url))throw Error('PUBLIC_UPDATE_NOT_APPROVED');await this.open(this.state.release.url);return true;}
  async openManualRelease() {
    const observation=this.manualObservation;
    if(!observation||observation.channel!==this.state.preferences.channel||this.now()-observation.checkedAt>=DAY||!releaseUrl(observation.release?.url))throw Error('PUBLIC_RELEASE_NOT_VERIFIED');
    await this.open(observation.release.url);return true;
  }
  async call(method,params) {
    if(method==='get'&&params===undefined)return this.get();
    if(method==='check'&&params===undefined)return this.check();
    if(method==='check'&&params&&Object.keys(params).length===1&&params.manual===true)return this.checkManual();
    if(method==='configure')return this.configure(params);
    if(method==='snooze'&&params===undefined)return this.snooze();
    if(method==='open'&&params===undefined)return this.openRelease();
    if(method==='open'&&params&&Object.keys(params).length===1&&params.manual===true)return this.openManualRelease();
    throw Error('UPDATE_METHOD_REJECTED');
  }
}
