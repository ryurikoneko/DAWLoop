import fs from 'node:fs/promises';
import { AppError } from '../config/index.mjs';

export const unknownWorld = () => ({ apiVersion:1, source:'core', state:'unknown', reason:'WORLD_SNAPSHOT_UNAVAILABLE', observedAt:null, session:null, target:null, tracks:[], capabilities:[] });
const identifier = x => typeof x === 'string' && /^[a-zA-Z0-9._:-]{1,160}$/.test(x);
const text = x => typeof x === 'string' && x.length <= 160 && !/[\x00-\x1f]/.test(x);
const index = x => Number.isSafeInteger(x) && x >= 0 && x <= 65535;
const hash = x => typeof x === 'string' && /^[a-f0-9]{64}$/.test(x);
const confidences = ['high','medium','low','very-low','unknown'];
export function validateWorld(raw, now = Date.now()) {
  const invalid = () => { throw new AppError('INVALID_WORLD_SNAPSHOT','backend'); };
  if (!raw || raw.apiVersion !== 1 || raw.source !== 'core' || !Number.isFinite(Date.parse(raw.observedAt))) invalid();
  const s = raw.session;
  if (!s || !['hostId','sessionId','projectGeneration'].every(k=>identifier(s[k])) || !(s.projectName===null || text(s.projectName))) invalid();
  if (!Array.isArray(raw.tracks) || raw.tracks.length > 512 || !Array.isArray(raw.capabilities) || raw.capabilities.length > 128) invalid();
  const tracks = raw.tracks.map(t => {
    if (!index(t.index) || !text(t.name) || !Array.isArray(t.slots) || t.slots.length > 64) invalid();
    const slots = t.slots.map(slot => {
      if (!index(slot.index) || !['empty','occupied','unknown'].includes(slot.state)) invalid();
      const p = slot.plugin;
      if (slot.state !== 'occupied') { if (p !== null) invalid(); return {index:slot.index,state:slot.state,plugin:null}; }
      if (!p || !(p.instanceId===null || identifier(p.instanceId)) || !text(p.name) || !(p.parameterCount===null || index(p.parameterCount)) || !Array.isArray(p.parameters) || p.parameters.length>65536) invalid();
      const parameters=p.parameters.map(v=>{
        if (!index(v.index) || !text(v.name) || !(v.value===null || (typeof v.value==='number' && Number.isFinite(v.value))) || !['available','unknown','unavailable'].includes(v.readState)) invalid();
        return {index:v.index,name:v.name,value:v.value,readState:v.readState};
      });
      if (new Set(parameters.map(v=>v.index)).size!==parameters.length || (p.parameterCount!==null && parameters.some(v=>v.index>=p.parameterCount))) invalid();
      return {index:slot.index,state:slot.state,plugin:{instanceId:p.instanceId,name:p.name,parameterCount:p.parameterCount,parameters}};
    });
    if (new Set(slots.map(v=>v.index)).size!==slots.length) invalid();
    return {index:t.index,name:t.name,slots};
  });
  if (new Set(tracks.map(v=>v.index)).size!==tracks.length) invalid();
  let target=null;
  if (raw.target!==null) {
    const t=raw.target;
    if (!t || !index(t.trackIndex) || !index(t.slotIndex) || !(t.instanceId===null || identifier(t.instanceId)) || !tracks.some(v=>v.index===t.trackIndex && v.slots.some(slot=>slot.index===t.slotIndex && slot.plugin && slot.plugin.instanceId===t.instanceId))) invalid();
    target={trackIndex:t.trackIndex,slotIndex:t.slotIndex,instanceId:t.instanceId};
  }
  const capabilities=raw.capabilities.map(c=>{
    if (!identifier(c.id) || !['available','partial','experimental','unavailable','unknown'].includes(c.state) || !confidences.includes(c.confidence) || !Array.isArray(c.evidence) || c.evidence.length>16) invalid();
    const evidence=c.evidence.map(e=>{
      if (!identifier(e.id) || !hash(e.sha256) || !['passed','failed','unknown'].includes(e.outcome) || !Number.isFinite(Date.parse(e.observedAt)) || !e.binding || !['hostId','sessionId','projectGeneration'].every(k=>identifier(e.binding[k]))) invalid();
      if (e.binding.trackIndex!==null && !index(e.binding.trackIndex)) invalid();
      if (e.binding.slotIndex!==null && !index(e.binding.slotIndex)) invalid();
      if (e.binding.instanceId!==null && !identifier(e.binding.instanceId)) invalid();
      return {id:e.id,sha256:e.sha256,outcome:e.outcome,observedAt:e.observedAt,binding:Object.fromEntries(['hostId','sessionId','projectGeneration','trackIndex','slotIndex','instanceId'].map(k=>[k,e.binding[k]]))};
    });
    return {id:c.id,state:c.state,confidence:c.confidence,contractVersion:c.contractVersion===1?1:null,evidence};
  });
  if (new Set(capabilities.map(v=>v.id)).size!==capabilities.length) invalid();
  const age=now-Date.parse(raw.observedAt);
  return {apiVersion:1,source:'core',state:age>=0 && age<=15000?'current':'stale',reason:age>=0 && age<=15000?'CORE_WORLD_OBSERVED':'WORLD_SNAPSHOT_STALE',observedAt:raw.observedAt,
    session:{hostId:s.hostId,sessionId:s.sessionId,projectGeneration:s.projectGeneration,projectName:s.projectName},target,tracks,capabilities};
}
// 本函数只校验证据范围；发布端另外校验来源归属及宿主验证器，文件声明不能授予信任。
export function promotion(world, id, selected = null, now = Date.now()) {
  const c=world.capabilities.find(v=>v.id===id);
  const exposed=['mixer.track.read','plugin.enumerate','plugin.identity.read','plugin.parameter.layout','plugin.parameter.read'];
  const stages={coreExists:!!c,liveEvidence:false,contractStable:c?.contractVersion===1,adapterExposed:exposed.includes(id),rendererAllowed:exposed.includes(id)};
  stages.liveEvidence=world.state==='current' && now-Date.parse(world.observedAt)>=0 && now-Date.parse(world.observedAt)<=15000 && !!world.session && !!c?.evidence.some(e=>e.outcome==='passed' && now-Date.parse(e.observedAt)>=0 && now-Date.parse(e.observedAt)<=15000 && ['hostId','sessionId','projectGeneration'].every(k=>e.binding[k]===world.session[k]) && (selected ? e.binding.trackIndex===selected.trackIndex && e.binding.slotIndex===selected.slotIndex && e.binding.instanceId===selected.instanceId : ['trackIndex','slotIndex','instanceId'].every(k=>e.binding[k]===null)));
  return {...stages,enabled:!id.includes('write') && c?.state==='available' && Object.values(stages).every(Boolean)};
}
export async function readWorld(filename) {
  if (!filename) return unknownWorld();
  if (!(await fs.stat(filename)).isFile()) throw new AppError('INVALID_WORLD_SNAPSHOT','backend');
  const handle=await fs.open(filename,'r');
  try {
    const stat=await handle.stat();
    if (!stat.isFile() || stat.size>2*1024*1024) throw new AppError('WORLD_SNAPSHOT_TOO_LARGE','backend');
    const buffer=Buffer.alloc(2*1024*1024+1); let size=0;
    while (size<buffer.length) { const read=await handle.read(buffer,size,buffer.length-size,size); if (!read.bytesRead) break; size+=read.bytesRead; }
    if (size>2*1024*1024) throw new AppError('WORLD_SNAPSHOT_TOO_LARGE','backend');
    return validateWorld(JSON.parse(buffer.subarray(0,size).toString('utf8')));
  } finally { await handle.close(); }
}
