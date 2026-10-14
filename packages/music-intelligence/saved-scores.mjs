import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {canonicalJson,safeJson,validId} from './analysis-contract.mjs';
const digest=v=>createHash('sha256').update(canonicalJson(v)).digest('hex');
const saveQueues=new Map();
export function validateSavedScore(score){
 safeJson(score,1024*1024);if(!score||score.schemaVersion!==1||!Number.isFinite(score.tempo)||score.tempo<20||score.tempo>300||!Array.isArray(score.notes)||score.notes.length>20000||!Array.isArray(score.meter)||score.meter.length!==2||!Number.isInteger(score.meter[0])||score.meter[0]<1||score.meter[0]>32||![1,2,4,8,16,32].includes(score.meter[1])||!Array.isArray(score.tempoMap)||score.tempoMap.length>10000||!Array.isArray(score.edits)||score.edits.length>200)throw Error('MI_SCORE_EDITOR_REJECTED');
 const ids=new Set();for(const n of score.notes){if(!n||!Number.isInteger(n.pitch)||n.pitch<0||n.pitch>127||!Number.isFinite(n.start)||n.start<0||n.start>86400||!Number.isFinite(n.duration)||n.duration<=0||n.duration>3600||!Number.isInteger(n.velocity)||n.velocity<1||n.velocity>127||!Number.isInteger(n.part)||n.part<0||n.part>15||typeof n.id!=='string'||!/^[a-zA-Z0-9-]{1,100}$/.test(n.id)||ids.has(n.id))throw Error('MI_SCORE_EDITOR_REJECTED');ids.add(n.id);}
 for(const p of score.tempoMap)if(!Number.isFinite(p.start)||p.start<0||!Number.isFinite(p.bpm)||p.bpm<20||p.bpm>300)throw Error('MI_SCORE_EDITOR_REJECTED');
 if(score.pitchBends!==undefined&&(!Array.isArray(score.pitchBends)||score.pitchBends.length>50000||score.pitchBends.some(b=>!Number.isFinite(b.start)||b.start<0||!Number.isInteger(b.value)||b.value< -8192||b.value>8191||!Number.isInteger(b.part)||b.part<0||b.part>15)))throw Error('MI_SCORE_EDITOR_REJECTED');return score;
}
async function directory(home,create){const root=await fs.realpath(home),folder=path.join(root,'user-scores');if(create)await fs.mkdir(folder,{recursive:true});const s=await fs.lstat(folder);if(!s.isDirectory()||s.isSymbolicLink()||await fs.realpath(folder)!==folder)throw Error('MI_SCORE_PATH_REJECTED');return folder;}
export async function saveUserScore(home,p){
 const key=await fs.realpath(home),previous=saveQueues.get(key)??Promise.resolve();
 const operation=previous.then(()=>saveScoreRecord(key,p)),settled=operation.then(()=>{},()=>{});saveQueues.set(key,settled);
 try{return await operation;}finally{if(saveQueues.get(key)===settled)saveQueues.delete(key);}
}
async function saveScoreRecord(home,p){
 if(!p||Object.keys(p).some(k=>!['score','name'].includes(k))||typeof p.name!=='string'||!p.name.trim()||p.name.length>120)throw Error('IPC_REJECTED');validateSavedScore(p.score);
 const folder=await directory(home,true),entries=await fs.readdir(folder);if(entries.filter(n=>n.endsWith('.json')).length>=100)throw Error('MI_SCORE_SAVE_LIMIT');
 const id=randomUUID(),record={schemaVersion:1,id,name:p.name.trim(),savedAt:new Date().toISOString(),category:'USER_EDITED',score:{...JSON.parse(safeJson(p.score)),source:'USER_EDITED'}},file=path.join(folder,id+'.json'),temporary=path.join(folder,'.'+randomUUID()+'.tmp');
 try{const handle=await fs.open(temporary,'wx');try{await handle.writeFile(JSON.stringify({record,sha256:digest(record)}),'utf8');await handle.sync();}finally{await handle.close();}await fs.link(temporary,file);}finally{await fs.unlink(temporary).catch(e=>{if(e.code!=='ENOENT')throw e;});}return record;
}
export async function savedUserScores(home){
 let folder;try{folder=await directory(home,false);}catch(e){if(e.code==='ENOENT')return [];throw e;}
 const names=await fs.readdir(folder);if(names.length>200)throw Error('MI_SCORE_SAVE_LIMIT');const records=[];
 for(const name of names.filter(n=>n.endsWith('.json'))){validId(name.slice(0,-5));const file=path.join(folder,name),stat=await fs.lstat(file);if(!stat.isFile()||stat.isSymbolicLink()||stat.size>1100*1024)throw Error('MI_SCORE_PATH_REJECTED');const envelope=JSON.parse(await fs.readFile(file,'utf8')),record=envelope.record;if(!record||record.schemaVersion!==1||typeof record.name!=='string'||!record.name.trim()||record.name.length>120||typeof record.savedAt!=='string'||!Number.isFinite(Date.parse(record.savedAt))||envelope.sha256!==digest(record)||record.id!==name.slice(0,-5)||record.category!=='USER_EDITED'||record.score?.source!=='USER_EDITED')throw Error('MI_SCORE_INTEGRITY_REJECTED');validateSavedScore(record.score);records.push(record);}
 return records.sort((a,b)=>b.savedAt.localeCompare(a.savedAt));
}
