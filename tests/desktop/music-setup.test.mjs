import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {capabilityMatrix,saveSetup} from '../../packages/music-intelligence/setup.mjs';
import {MusicIntelligenceService} from '../../packages/music-intelligence/service.mjs';
test('Hardware policy independently evaluates planning and full audio, preserves uncertainty',()=>{
 const rows=capabilityMatrix({platform:'win32',ramBytes:32*1024**3,gpu:{memoryMiB:8188}},40*1024**3);
 assert.equal(rows.find(r=>r.id==='basic-pitch').qualification,'RECOMMENDED');assert.equal(rows.find(r=>r.id==='yue2-plan').qualification,'UNKNOWN');assert.equal(rows.find(r=>r.id==='yue2-audio').qualification,'UNSUPPORTED');assert.equal(capabilityMatrix({platform:'win32',ramBytes:0,gpu:null},0).find(r=>r.id==='yue2-audio').qualification,'UNKNOWN');assert.ok(rows.every(r=>r.freeBytes===40*1024**3));
});
test('Setup rejects duplicate/unknown providers and unconfirmed code licenses before launching installers',async()=>{
 const home=await fs.mkdtemp(path.join(os.tmpdir(),'mi-setup-'));const mi=new MusicIntelligenceService({home});try{await mi.initialize();for(const models of [[],[{id:'exec',license:'x'}],[{id:'omar-rq',license:'CC-BY-NC-SA-4.0'}],[{id:'basic-pitch',license:'Apache-2.0'},{id:'basic-pitch',license:'Apache-2.0'}]])await assert.rejects(mi.setupInstall({models}));assert.equal(mi.jobs.size,0);assert.equal(mi.children.size,0);await assert.rejects(mi.call('exec',{}),/IPC_REJECTED/);await assert.rejects(mi.reviewOffsets('..',{}),/MI_ASSET_UNKNOWN/);await saveSetup(home,true);assert.equal(JSON.parse(await fs.readFile(path.join(home,'ai-setup.json'),'utf8')).skipped,true);}finally{await mi.close();await fs.rm(home,{recursive:true,force:true});}
});
test('Online experience uses one fixed user-triggered URL and never accepts arbitrary URLs or uploads',async()=>{
 const main=await fs.readFile(new URL('../../apps/desktop/electron/main.mjs',import.meta.url),'utf8');assert.match(main,/shell.openExternal\('https:\/\/yue.noizai.net\/'\)/);assert.doesNotMatch(main,/shell.openExternal\(params/);assert.equal(main.match(/new BrowserWindow/g).length,1);
 const installer=await fs.readFile(new URL('../../packages/music-intelligence/pitch-install.mjs',import.meta.url),'utf8');assert.doesNotMatch(installer,/runtime.basePython/);assert.match(installer,/pip-bootstrap.py/);assert.match(installer,/--require-hashes/);assert.match(installer,/--cache-dir/);
});
test('Setup preserves another provider after a failure and cancels only its active child',async()=>{
 const home=await fs.mkdtemp(path.join(os.tmpdir(),'mi-setup-'));const mi=new MusicIntelligenceService({home});let release;const statfs=fs.statfs;
 // 此测试只验证编排与取消，磁盘资格由独立策略测试覆盖。
 fs.statfs=async file=>path.resolve(file)===home?{bsize:4096,bavail:20*1024**3/4096}:statfs(file);
 try{await mi.initialize();const seen=[];mi.install=async id=>{seen.push(id);if(id==='sheetsage2')throw Error('TEST_PROVIDER_FAILURE');return mi.job('install',async()=>({testOnly:true}));};mi.modelOperation=async(id,op)=>op==='unload'?true:mi.job(op,async()=>({testOnly:true}));mi.modelsStatus=async()=>[{id:'basic-pitch',status:'VERIFIED'}];
  const id=await mi.setupInstall({models:[{id:'sheetsage2',license:'CC-BY-NC-4.0'},{id:'basic-pitch',license:'Apache-2.0'}]});while(mi.jobs.get(id).state==='RUNNING')await new Promise(r=>setTimeout(r,25));assert.deepEqual(seen,['sheetsage2','basic-pitch']);assert.deepEqual(mi.jobs.get(id).result.models.map(r=>r.state),['FAILED','HEALTHY']);
  mi.install=async()=>mi.job('install',()=>new Promise(r=>{release=r;}));const cancelled=await mi.setupInstall({models:[{id:'basic-pitch',license:'Apache-2.0'}]});while(!mi.jobs.get(cancelled).activeJobId)await new Promise(r=>setTimeout(r,10));const child=mi.jobs.get(cancelled).activeJobId;mi.cancel(cancelled);assert.equal(mi.jobs.get(child).state,'CANCELLED');release({testOnly:true});
 }finally{fs.statfs=statfs;release?.({testOnly:true});await mi.close();await new Promise(r=>setTimeout(r,150));await fs.rm(home,{recursive:true,force:true});}
});
