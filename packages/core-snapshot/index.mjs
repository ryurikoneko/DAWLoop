import { randomUUID } from 'node:crypto';
import { validateWorld, promotion } from '../core-adapter/world.mjs';
import { validateSnapshot } from '../core-adapter/index.mjs';

export const LEVELS = ['session','structure','identity','layout','values'];
export const MAX_BYTES = 2 * 1024 * 1024;
export const TTL_MS = 15000;
const ids = ['mixer.track.read','plugin.enumerate','plugin.identity.read','plugin.parameter.layout','plugin.parameter.read'];
const bindingKeys = ['session_id','project_generation','host_generation'];
const targetKeys = [...bindingKeys,'operation_id','controller_build_id','mixer_track','effect_slot','raw_plugin_name','api_version'];
const fail = code => { throw Object.assign(new Error(code), { code }); };
const same = (a,b,keys) => !!a && !!b && keys.every(k => a[k] === b[k]);
const id = x => typeof x === 'string' && /^[a-zA-Z0-9._:-]{1,160}$/.test(x);
// 构建标识沿用 Core 的多段来源摘要，不截断或转换成另一套身份。
const buildId = x => typeof x === 'string' && /^[a-zA-Z0-9._:+-]{1,1024}$/.test(x);
const date = x => typeof x === 'string' && Number.isFinite(Date.parse(x));
const clone = x => structuredClone(x);
function freeze(x) { if (x && typeof x === 'object') { Object.values(x).forEach(freeze); Object.freeze(x); } return x; }

export function validateMixerSnapshot(raw, now = Date.now()) {
  let size;
  try { size = Buffer.byteLength(JSON.stringify(raw),'utf8'); } catch { fail('SNAPSHOT_INVALID'); }
  if (size > MAX_BYTES) fail('SNAPSHOT_TOO_LARGE');
  if (!raw || raw.schemaVersion !== 1) fail('SNAPSHOT_SCHEMA_MISMATCH');
  if (!['local-observer','validated-core'].includes(raw.sourceBackend)) fail('SNAPSHOT_SOURCE_REJECTED');
  if (!id(raw.snapshotId) || !id(raw.observationId) || !Number.isSafeInteger(raw.sequence) || raw.sequence < 1 || !date(raw.observedAt) || !date(raw.publishedAt)) fail('SNAPSHOT_INVALID');
  if (Date.parse(raw.publishedAt) < Date.parse(raw.observedAt) || Date.parse(raw.publishedAt) > now || now - Date.parse(raw.observedAt) < 0) fail('SNAPSHOT_TIME_INVALID');
  if (!raw.freshness || raw.freshness.maxAgeMs !== TTL_MS || !LEVELS.every(k => ['available','partial','not-ready','unknown'].includes(raw.levels?.[k]))) fail('SNAPSHOT_INVALID');
  if (!Array.isArray(raw.reasonCodes) || raw.reasonCodes.length > 32 || !raw.reasonCodes.every(id) || !Array.isArray(raw.errors) || raw.errors.length > 32 || !raw.errors.every(id)) fail('SNAPSHOT_INVALID');
  if (!Array.isArray(raw.tracks) || !Array.isArray(raw.capabilityEvidence)) fail('SNAPSHOT_INVALID');
  const s = raw.sessionBinding;
  if (s !== null && (!bindingKeys.every(k => id(s?.[k])) || raw.sessionId !== s.session_id)) fail('SESSION_BINDING_INVALID');
  if (s === null && raw.sessionId !== null) fail('SESSION_BINDING_INVALID');
  if (raw.levels.session === 'available' && !s) fail('SESSION_BINDING_INVALID');
  const t = raw.targetBinding;
  if (t !== null && (!same(t,s,bindingKeys) || !id(t.operation_id) || !buildId(t.controller_build_id) || typeof t.raw_plugin_name !== 'string' || t.raw_plugin_name.length>160 || /[\x00-\x1f]/.test(t.raw_plugin_name) || !Number.isSafeInteger(t.mixer_track) || t.mixer_track < 1 || t.mixer_track>65535 || !Number.isSafeInteger(t.effect_slot) || t.effect_slot < 0 || t.effect_slot>65535 || !Number.isSafeInteger(t.api_version) || t.api_version < 26)) fail('TARGET_BINDING_INVALID');
  if (raw.sourceBackend === 'local-observer' && (s !== null || t !== null || raw.world !== null || raw.tracks.length || raw.capabilityEvidence.length || raw.levels.session === 'available' || LEVELS.slice(1).some(k=>raw.levels[k] === 'available'))) fail('SNAPSHOT_SOURCE_REJECTED');
  let world = null;
  if (raw.world !== null) {
    world = validateWorld(raw.world,now);
    if (!s || !same({session_id:world.session.sessionId,project_generation:world.session.projectGeneration,host_generation:world.session.hostId},s,bindingKeys) || world.observedAt !== raw.observedAt) fail('SESSION_BINDING_INVALID');
    if (t && (world.target?.trackIndex !== t.mixer_track || world.target?.slotIndex !== t.effect_slot || world.tracks.find(v=>v.index===t.mixer_track)?.slots.find(v=>v.index===t.effect_slot)?.plugin?.name !== t.raw_plugin_name)) fail('TARGET_BINDING_INVALID');
    if (JSON.stringify(raw.tracks) !== JSON.stringify(world.tracks) || JSON.stringify(raw.capabilityEvidence) !== JSON.stringify(world.capabilities)) fail('SNAPSHOT_INVALID');
  } else if (raw.tracks.length || raw.capabilityEvidence.length) fail('SNAPSHOT_INVALID');
  for (let i=1;i<LEVELS.length;i++) if (raw.levels[LEVELS[i]] === 'available' && (raw.levels[LEVELS[i-1]] !== 'available' || !world || (i>=2 && !t))) fail('SNAPSHOT_LEVEL_INVALID');
  const evidenceTime=Date.parse(raw.observedAt);
  const evidenceWorld=world ? {...world,state:'current'} : null;
  if (raw.levels.structure === 'available' && (!promotion(evidenceWorld,ids[0],null,evidenceTime).enabled || !promotion(evidenceWorld,ids[1],null,evidenceTime).enabled)) fail('SNAPSHOT_EVIDENCE_INVALID');
  for (let i=2;i<5;i++) if (raw.levels[LEVELS[i]] === 'available' && !promotion(evidenceWorld,ids[i],world.target,evidenceTime).enabled) fail('SNAPSHOT_EVIDENCE_INVALID');
  if (world && raw.levels.layout === 'available') for (const track of world.tracks) for (const slot of track.slots) {
    if (!slot.plugin) continue;
    const p=slot.plugin;
    if (track.index!==t.mixer_track || slot.index!==t.effect_slot) continue;
    if (p.parameterCount === null || p.parameters.length !== p.parameterCount || p.parameters.some((v,i)=>v.index!==i)) fail('SNAPSHOT_LAYOUT_INCOMPLETE');
    if (raw.levels.values === 'available' && p.parameters.some(v=>v.readState!=='available' || v.value===null || v.value<0 || v.value>1)) fail('SNAPSHOT_VALUES_INCOMPLETE');
  }
  if (raw.pluginIdentity !== null && (!t || raw.pluginIdentity.rawPluginName !== t.raw_plugin_name || raw.pluginIdentity.instanceId !== world?.target?.instanceId)) fail('PLUGIN_INSTANCE_CHANGED');
  if (raw.pluginIdentity !== null && (!raw.pluginIdentity || !['verified','unknown'].includes(raw.pluginIdentity.continuity) || !(raw.pluginIdentity.instanceId===null || id(raw.pluginIdentity.instanceId)) || !(raw.pluginIdentity.format===null || (typeof raw.pluginIdentity.format==='string' && raw.pluginIdentity.format.length<=80 && !/[\x00-\x1f]/.test(raw.pluginIdentity.format))))) fail('PLUGIN_INSTANCE_UNKNOWN');
  if (raw.levels.identity === 'available' && (!raw.pluginIdentity || raw.pluginIdentity.continuity!=='verified')) fail('PLUGIN_INSTANCE_UNKNOWN');
  const status=now-Date.parse(raw.observedAt)<=TTL_MS ? 'current' : 'stale';
  let connection=null;
  if (raw.connection!==null) {
    const c=validateSnapshot({...raw.connection,apiVersion:1,capabilities:[]});
    connection={runtime:c.runtime,host:c.host,bridges:c.bridges};
  }
  return clone({...raw,world,connection,freshness:{maxAgeMs:TTL_MS,state:status}});
}

export function localObservation(status, now = Date.now()) {
  return { schemaVersion:1,sourceBackend:'local-observer',observationId:randomUUID(), observedAt:status?.backend==='real' ? status.observedAt : new Date(now).toISOString(),
    sessionBinding:null,targetBinding:null,pluginIdentity:null,world:null,
    levels:{session:status?.backend==='real' ? 'partial':'unknown',structure:'not-ready',identity:'not-ready',layout:'not-ready',values:'not-ready'},
    reasonCodes:['SESSION_BINDING_UNAVAILABLE','MIXER_PUBLISHER_NOT_CONNECTED'],errors:[],
    connection:status?.backend==='real' ? {runtime:status.runtime,host:status.host,bridges:status.bridges}:null };
}

export class MixerSnapshotPublisher {
  #source; #unsubscribe; #issued=new WeakMap(); #epoch=0; #sequence=0; #latest=null; #pending=null; #closed=false; #subscribers=new Set(); #queued=false; #history=[]; #now; #lastAttempt=-Infinity; #lastObservedAt=-Infinity; #input=null; #seen=new Map();
  constructor({source,now=Date.now,timeoutMs=1000,minIntervalMs=1000}={}) {
    if (!source || !['local-observer','validated-core'].includes(source.sourceBackend) || typeof source.read !== 'function' || typeof source.verify !== 'function' || typeof source.currentBinding !== 'function') fail('SNAPSHOT_SOURCE_REJECTED');
    this.#source=Object.freeze({...source}); this.#now=now; this.timeoutMs=timeoutMs; this.minIntervalMs=minIntervalMs;
    this.#unsubscribe=source.onInvalidation?.(reason=>this.invalidate(reason));
  }
  get history() { return clone(this.#history); }
  invalidate(reason='CORE_DISCONNECTED') {
    if (!/^[A-Z0-9_]{1,120}$/.test(reason)) reason='SNAPSHOT_SOURCE_REJECTED';
    this.#epoch++; this.#latest=null; this.#pending?.controller.abort();
    this.#history.push({reason,at:new Date(this.#now()).toISOString(),sequence:this.#sequence});
    this.#history=this.#history.slice(-16); this.#notify();
  }
  #notify() {
    if (this.#queued) return; this.#queued=true;
    queueMicrotask(()=>{this.#queued=false; for (const fn of this.#subscribers) { try { fn(this.#latest); } catch {} }});
  }
  subscribe(fn) {
    if (this.#closed || typeof fn!=='function' || this.#subscribers.size>=16) fail('SNAPSHOT_SUBSCRIPTION_REJECTED');
    this.#subscribers.add(fn); return ()=>this.#subscribers.delete(fn);
  }
  verify(envelope) {
    const record=this.#issued.get(envelope);
    if (this.#closed || !record || record.epoch!==this.#epoch || envelope!==this.#latest) fail('SNAPSHOT_SOURCE_REJECTED');
    const current=this.#source.currentBinding();
    if (!current?.connected) { this.invalidate('CORE_DISCONNECTED'); fail('CORE_DISCONNECTED'); }
    const s=envelope.snapshot;
    if (s.sessionBinding && !same(current.sessionBinding,s.sessionBinding,bindingKeys)) { this.invalidate('SESSION_CHANGED'); fail('SESSION_CHANGED'); }
    if (s.targetBinding && !same(current.targetBinding,s.targetBinding,targetKeys)) { this.invalidate('TARGET_CHANGED'); fail('TARGET_CHANGED'); }
    if (s.pluginIdentity && current.instanceId!==s.pluginIdentity.instanceId) { this.invalidate('PLUGIN_INSTANCE_CHANGED'); fail('PLUGIN_INSTANCE_CHANGED'); }
    if (s.pluginIdentity?.instanceId===null && s.levels.identity==='available' && current.continuityVerified!==true) { this.invalidate('PLUGIN_INSTANCE_UNKNOWN'); fail('PLUGIN_INSTANCE_UNKNOWN'); }
    return validateMixerSnapshot(s,this.#now());
  }
  async refresh() {
    if (this.#closed) fail('CORE_DISCONNECTED');
    if (this.#pending) return this.#pending.result;
    if (this.#now()-this.#lastAttempt<this.minIntervalMs) {
      if (this.#latest) return this.#latest;
      fail('SNAPSHOT_RATE_LIMITED');
    }
    this.#lastAttempt=this.#now(); const epoch=this.#epoch,controller=new AbortController();
    const pending={controller}; this.#pending=pending;
    let timer;
    const work=Promise.resolve().then(()=>this.#source.read(controller.signal)).then(async input=>{
      const serialized=JSON.stringify(input);
      if (typeof serialized!=='string' || Buffer.byteLength(serialized,'utf8')>MAX_BYTES) fail('SNAPSHOT_TOO_LARGE');
      if (input.schemaVersion!==1) fail('SNAPSHOT_SCHEMA_MISMATCH');
      if (input.sourceBackend!==this.#source.sourceBackend) fail('SNAPSHOT_SOURCE_REJECTED');
      const observation=freeze(clone(input));
      if (controller.signal.aborted || this.#closed || epoch!==this.#epoch) fail('OBSERVATION_CANCELLED');
      // 来源验证器必须验证当前宿主回执；JSON 内的 passed 和摘要不授予信任。
      if (await this.#source.verify(observation,controller.signal)!==true) fail('SNAPSHOT_SOURCE_REJECTED');
      if (controller.signal.aborted || this.#closed || epoch!==this.#epoch) fail('OBSERVATION_CANCELLED');
      if (Date.parse(observation.observedAt)<this.#lastObservedAt) fail('SNAPSHOT_SEQUENCE_ROLLBACK');
      if (this.#latest) {
        const previous=this.#latest.snapshot;
        if (observation.observationId===previous.observationId) {
          if (serialized!==this.#input) fail('SNAPSHOT_DUPLICATE_CONFLICT');
          this.verify(this.#latest); return this.#latest;
        }
      }
      if (this.#seen.has(observation.observationId)) fail('SNAPSHOT_DUPLICATE_CONFLICT');
      const snapshot=validateMixerSnapshot({observationId:observation.observationId,observedAt:observation.observedAt,sessionBinding:observation.sessionBinding,targetBinding:observation.targetBinding,
        pluginIdentity:observation.pluginIdentity,world:observation.world,levels:observation.levels,reasonCodes:observation.reasonCodes,errors:observation.errors,
        connection:this.#source.sourceBackend==='local-observer' ? observation.connection : null,
        schemaVersion:1,snapshotId:randomUUID(),sessionId:observation.sessionBinding?.session_id??null,
        sequence:++this.#sequence,publishedAt:new Date(this.#now()).toISOString(),sourceBackend:this.#source.sourceBackend,
        freshness:{maxAgeMs:TTL_MS,state:'current'},tracks:observation.world?.tracks??[],capabilityEvidence:observation.world?.capabilities??[]},this.#now());
      const envelope=freeze({snapshot}); this.#issued.set(envelope,{epoch}); this.#latest=envelope;
      try { this.verify(envelope); } catch (error) { this.#latest=null; throw error; }
      this.#input=serialized; this.#lastObservedAt=Date.parse(snapshot.observedAt); this.#seen.set(observation.observationId,true);
      if (this.#seen.size>64) this.#seen.delete(this.#seen.keys().next().value);
      this.#notify(); return envelope;
    });
    // 超时后仍占用观察槽，直到来源真正退出；取消失效不允许重叠观察。
    void work.then(()=>{if(this.#pending===pending)this.#pending=null;},()=>{if(this.#pending===pending)this.#pending=null;});
    pending.result=Promise.race([work,new Promise((_,reject)=>{timer=setTimeout(()=>{this.invalidate('CORE_TIMEOUT');reject(Object.assign(new Error('CORE_TIMEOUT'),{code:'CORE_TIMEOUT'}));},this.timeoutMs);})])
      .catch(error=>{if(epoch===this.#epoch)this.invalidate(error.code??'SNAPSHOT_SOURCE_REJECTED');throw error;}).finally(()=>clearTimeout(timer));
    return pending.result;
  }
  close() { this.#closed=true; this.#unsubscribe?.(); this.invalidate('CORE_DISCONNECTED'); this.#subscribers.clear(); }
}
