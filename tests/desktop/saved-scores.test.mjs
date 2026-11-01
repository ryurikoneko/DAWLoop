import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {MusicIntelligenceService} from '../../packages/music-intelligence/service.mjs';
import {saveUserScore,savedUserScores} from '../../packages/music-intelligence/saved-scores.mjs';
const score={schemaVersion:1,source:'BASIC_PITCH',tempo:120,meter:[4,4],tempoMap:[{start:0,bpm:120}],notes:[{id:'owned-note-1',pitch:60,start:1/3,duration:.5,velocity:90,part:0}],edits:[],pitchBends:[{start:.5,value:100,part:0}]};
test('明确保存的编辑乐谱可跨重启恢复，保留稳定ID和精度且不改原始候选或音频可见性',async()=>{
 const home=await fs.mkdtemp(path.join(os.tmpdir(),'mi-score-save-'));let one,two;
 try {one=new MusicIntelligenceService({home});await one.initialize();assert.deepEqual(await one.call('savedScores',{}),[]);const original=JSON.stringify(score),raw=path.join(home,'scores','owned-original.json');await fs.writeFile(raw,original,'utf8');const saved=await one.call('saveScore',{score,name:'Owned edited score'});assert.equal(saved.score.source,'USER_EDITED');assert.equal(JSON.stringify(score),original);assert.equal(await fs.readFile(raw,'utf8'),original);await one.close();two=new MusicIntelligenceService({home});await two.initialize();const rows=await two.call('savedScores',{});assert.equal(rows.length,1);assert.equal(rows[0].score.notes[0].id,'owned-note-1');assert.equal(rows[0].score.notes[0].start,1/3);assert.deepEqual(rows[0].score.pitchBends,score.pitchBends);assert.deepEqual((await two.call('status',{})).assets,[]);
  await assert.rejects(two.call('saveScore',{score:{...score,notes:[{...score.notes[0],velocity:128}]},name:'Invalid'}),/MI_SCORE_EDITOR_REJECTED/);await assert.rejects(two.call('saveScore',{score,name:'Bad',path:'outside'}),/IPC_REJECTED/);await assert.rejects(two.call('saveScore',{score:{...score,provenance:{assetId:'a'.repeat(32),sourceSha256:'b'.repeat(64)}},name:'False binding'}),/MI_SCORE_SOURCE_REJECTED/);
  const file=path.join(home,'user-scores',saved.id+'.json'),envelope=JSON.parse(await fs.readFile(file,'utf8'));envelope.record.score.notes[0].pitch=66;await fs.writeFile(file,JSON.stringify(envelope),'utf8');await assert.rejects(two.call('savedScores',{}),/MI_SCORE_INTEGRITY_REJECTED/);
 } finally {await one?.close();await two?.close();await fs.rm(home,{recursive:true,force:true});}
});
test('并发保存共享同一限额，失败后队列仍可使用且不会写出第101份记录',async()=>{
 const home=await fs.mkdtemp(path.join(os.tmpdir(),'mi-score-limit-'));
 try{const outcomes=await Promise.allSettled(Array.from({length:101},(_,i)=>saveUserScore(home,{score,name:'Owned '+i})));assert.equal(outcomes.filter(o=>o.status==='fulfilled').length,100);assert.equal(outcomes.filter(o=>o.status==='rejected'&&o.reason.message==='MI_SCORE_SAVE_LIMIT').length,1);assert.equal((await savedUserScores(home)).length,100);assert.equal((await fs.readdir(path.join(home,'user-scores'))).some(n=>n.endsWith('.tmp')),false);await assert.rejects(saveUserScore(home,{score,name:'Overflow'}),/MI_SCORE_SAVE_LIMIT/);
 }finally{await fs.rm(home,{recursive:true,force:true});}
});
