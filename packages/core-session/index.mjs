import { createHmac, timingSafeEqual } from 'node:crypto';
import { TTL_MS } from '../core-snapshot/index.mjs';

const fail = code => { throw Object.assign(new Error(code), {code}); };
const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
const id = value => typeof value==='string' && /^[a-zA-Z0-9._:-]{1,160}$/.test(value);
const fields = ['operation_id','controller_build_id','session_id','project_generation','host_generation'];

export class TrustedSessionProvider {
  #key; #nonce; #expected; #alive; #now; #sequence=0; #run=null; #latest=null; #binding=null; #received=0; #closed=false; #listeners=new Set(); #timer; #serialized=null;
  constructor({key,nonce,expected,alive,now=Date.now}) {
    if (!Buffer.isBuffer(key) || key.length!==32 || !/^[a-f0-9]{32}$/.test(nonce) || typeof alive!=='function') fail('SESSION_SOURCE_REJECTED');
    this.#key=Buffer.from(key); this.#nonce=nonce; this.#expected=Object.freeze({...expected}); this.#alive=alive; this.#now=now;
    this.source={sourceBackend:'validated-core', read:()=>this.read(), verify:observation=>this.verify(observation),
      currentBinding:()=>this.currentBinding(), onInvalidation:listener=>{this.#listeners.add(listener);return()=>this.#listeners.delete(listener);}};
    // 一个来源共用一只失效定时器，Renderer 订阅不会启动观察或宿主。
    this.#timer=setInterval(()=>this.currentBinding(),250); this.#timer.unref?.();
  }
  invalidate(reason='CORE_DISCONNECTED') {
    this.#latest=null; this.#serialized=null; this.#binding=null;
    for (const listener of this.#listeners) listener(reason);
  }
  accept(packet) {
    try {
      if(this.#closed || !this.#alive() || !packet || typeof packet.body!=='string' || Buffer.byteLength(packet.body)>65536 || !/^[a-f0-9]{64}$/.test(packet.mac)) fail('SESSION_SOURCE_REJECTED');
      const actual=createHmac('sha256',this.#key).update(packet.body,'utf8').digest();
      if(!timingSafeEqual(actual,Buffer.from(packet.mac,'hex'))) fail('SESSION_SOURCE_REJECTED');
      const frame=JSON.parse(packet.body);
      if(frame.version!==1 || frame.nonce!==this.#nonce || frame.processId!==this.#expected.workerPid || frame.configSha256!==this.#expected.configSha256 || frame.scope!=='LIVE_READONLY' || !Number.isSafeInteger(frame.sequence) || frame.sequence!==this.#sequence+1 || !id(frame.runId)) fail('SESSION_SOURCE_REJECTED');
      if(this.#run && frame.runId!==this.#run) fail('SESSION_RUN_CHANGED');
      this.#sequence=frame.sequence;
      if(frame.kind==='hello') {
        if(this.#run || frame.sequence!==1 || frame.data.launcherSha256!==this.#expected.launcherSha256) fail('SESSION_SOURCE_REJECTED');
        this.#run=frame.runId;return;
      }
      if(!this.#run) fail('SESSION_SOURCE_REJECTED');
      if(frame.kind==='invalidate') { this.close(/^[A-Z0-9_]{1,120}$/.test(frame.data.reason)?frame.data.reason:'SESSION_SOURCE_REJECTED');return; }
      if(frame.kind!=='session') fail('SESSION_SOURCE_REJECTED');
      const d=frame.data,b=d.binding,age=this.#now()-Date.parse(d.observedAt);
      if(Object.keys(d).sort().join()!==['binding','observedAt','observationId','targetSha256'].sort().join()) fail('SESSION_SOURCE_REJECTED');
      if(!b || Object.keys(b).sort().join()!==[...fields].sort().join() || !['operation_id','session_id','project_generation','host_generation'].every(k=>id(b[k])) || typeof b.controller_build_id!=='string' || !/^[a-zA-Z0-9._:+-]{1,1024}$/.test(b.controller_build_id) || !id(d.observationId) || d.targetSha256!==this.#expected.targetSha256 || !Number.isFinite(age) || age<0 || age>TTL_MS) fail('SESSION_BINDING_INVALID');
      if(this.#binding && !same(this.#binding,b)) fail('SESSION_CHANGED');
      const sessionBinding={session_id:b.session_id,project_generation:b.project_generation,host_generation:b.host_generation};
      const observation={schemaVersion:1,sourceBackend:'validated-core',observationId:d.observationId,observedAt:d.observedAt,
        sessionBinding,targetBinding:null,pluginIdentity:null,world:null,connection:null,
        levels:{session:'available',structure:'not-ready',identity:'not-ready',layout:'not-ready',values:'not-ready'},
        reasonCodes:['HOST_SESSION_IDENTITY_VERIFIED','MIXER_STRUCTURE_NOT_READY'],errors:[]};
      const serialized=JSON.stringify(observation);
      if(this.#latest && serialized!==this.#serialized) fail('SESSION_OBSERVATION_CHANGED');
      this.#binding=structuredClone(b);this.#latest=observation;this.#serialized=serialized;this.#received=this.#now();
    } catch(error) { this.close(error.code??'SESSION_SOURCE_REJECTED');throw error; }
  }
  currentBinding() {
    if(this.#latest && (!this.#alive() || this.#now()-this.#received>1500 || this.#now()-Date.parse(this.#latest.observedAt)>TTL_MS)) this.close('SESSION_SOURCE_EXPIRED');
    return {connected:!this.#closed && !!this.#latest,sessionBinding:structuredClone(this.#latest?.sessionBinding??null),targetBinding:null,instanceId:null,continuityVerified:false};
  }
  read() { if(!this.currentBinding().connected) fail('SESSION_SOURCE_UNAVAILABLE');return structuredClone(this.#latest); }
  verify(observation) { return this.currentBinding().connected && JSON.stringify(observation)===this.#serialized; }
  close(reason='CORE_DISCONNECTED') { if(this.#closed)return;this.#closed=true;clearInterval(this.#timer);this.invalidate(reason);this.#key.fill(0); }
}
