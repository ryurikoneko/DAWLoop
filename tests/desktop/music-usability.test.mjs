import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {MusicIntelligenceService} from '../../packages/music-intelligence/service.mjs';
import {managedRuntime} from '../../packages/music-intelligence/managed-runtime.mjs';
import {workerErrorDetail} from '../../packages/music-intelligence/sanitize.mjs';

test('Worker diagnostics redact Windows and repr paths without dropping the failure explanation',()=>{
 const home='D:\\managed\\music';for(const root of [home,home.replaceAll('\\','\\\\'),home.replaceAll('\\','/')]){const result=workerErrorDetail("LibsndfileError: Error opening '"+root+"/audio-library/owned.wav': Format not recognised",home);assert.ok(result.includes('[MUSIC_HOME]'));assert.ok(result.includes('Format not recognised'));assert.ok(!result.includes('D:'));}
});

async function fixture(run){const home=await fs.mkdtemp(path.join(os.tmpdir(),'mi-ux02-')),source=path.join(home,'owned.wav'),services=[];const open=async()=>{const s=new MusicIntelligenceService({home});await s.initialize();services.push(s);return s;};try{await fs.writeFile(source,'OWNED_TEST_FIXTURE');await run({home,source,open});}finally{for(const s of services)await s.close();await fs.rm(home,{recursive:true,force:true});}}
async function settled(s,id){const until=Date.now()+3000;while(!s.jobs.get(id)?.finishedAt){assert.ok(Date.now()<until);await new Promise(r=>setTimeout(r,5));}return s.jobs.get(id);}
test('Session imports disappear after restart without deleting library or immutable artifacts',()=>fixture(async({home,source,open})=>{
 const one=await open(),a=await one.importAudio(source),library=await fs.readFile(path.join(home,'library.json'));
 assert.equal((await one.status()).assets[0].visibility,'SESSION_IMPORT');await one.close();const two=await open();assert.deepEqual((await two.status()).assets,[]);assert.ok(two.assets.has(a.id));assert.deepEqual(await fs.readFile(path.join(home,'library.json')),library);assert.equal(await fs.readFile(source,'utf8'),'OWNED_TEST_FIXTURE');
 await two.importAudio(source);assert.equal((await two.status()).assets.length,1);
}));
test('Explicit audio projects survive restarts; removing a reference preserves both audio copies and library bytes',()=>fixture(async({home,source,open})=>{
 const one=await open(),a=await one.importAudio(source);await one.saveAsset({assetId:a.id,kind:'USER_SAVED_PROJECT'});const bytes=await fs.readFile(path.join(home,'library.json'));await one.close();const two=await open();assert.equal((await two.status()).assets[0].visibility,'USER_SAVED_PROJECT');await two.removeAsset(a.id);assert.deepEqual((await two.status()).assets,[]);assert.deepEqual(await fs.readFile(path.join(home,'library.json')),bytes);assert.ok(await fs.stat(two.assetPath(a.id)));assert.ok(await fs.stat(source));await two.close();const three=await open();assert.deepEqual((await three.status()).assets,[]);
}));
test('Missing managed runtime rejects exposed analysis before creating any task',()=>fixture(async({source,open})=>{
 const s=await open(),a=await s.importAudio(source);assert.equal((await s.basicReadiness()).state,'NOT_READY');await assert.rejects(s.call('analyze',{assetId:a.id}),/MI_PYTHON_NOT_CONFIGURED/);assert.equal(s.jobs.size,0);await assert.rejects(s.saveAsset({assetId:a.id,kind:'USER_SAVED_ANALYSIS'}));await assert.rejects(s.saveAsset({assetId:a.id,kind:'FORGED'}));
}));
test('Finished tasks can be independently dismissed without deleting diagnostic files or an active task',()=>fixture(async({home,open})=>{
 const s=await open(),failed=s.job('ownedFailure',async()=>{throw Error('OWNED_FAILURE');}),good=s.job('ownedSuccess',async()=>({ok:true}));await settled(s,failed);await settled(s,good);const log=await fs.readFile(path.join(home,'jobs',failed+'.json'));let release;const active=s.job('ownedPending',()=>new Promise(r=>{release=r;}));assert.throws(()=>s.dismiss(active),/MI_JOB_STILL_RUNNING/);s.dismiss(failed);assert.ok(s.jobs.has(good)&&s.jobs.has(active));assert.deepEqual(await fs.readFile(path.join(home,'jobs',failed+'.json')),log);release(true);await settled(s,active);s.dismiss(good);assert.ok(s.jobs.has(active));
}));
test('Cancelled task cannot be dismissed before cleanup finishes; failure does not prevent a later task',()=>fixture(async({open})=>{
 const s=await open();let release;const id=s.job('ownedCancelable',()=>new Promise(r=>{release=r;}));assert.equal(s.cancel(id),true);assert.throws(()=>s.dismiss(id),/MI_JOB_STILL_RUNNING/);release(true);await settled(s,id);assert.equal(s.jobs.get(id).state,'CANCELLED');s.dismiss(id);const next=s.job('ownedSuccess',async()=>true);assert.equal((await settled(s,next)).state,'COMPLETED');
}));
test('Managed runtime uses only explicit manifests and rejects drift and relative Python paths',()=>fixture(async({home})=>{
 const file=path.join(home,'python-test-fixture.bin');await fs.writeFile(file,'OWNED_NOT_EXECUTABLE');const digest=createHash('sha256').update('OWNED_NOT_EXECUTABLE').digest('hex'),manifest=path.join(home,'runtime.json');await fs.writeFile(manifest,JSON.stringify({schemaVersion:1,python:file,pythonSha256:digest}));assert.equal((await managedRuntime(home)).state,'VERIFIED');await fs.writeFile(file,'changed');assert.equal((await managedRuntime(home)).reasonCode,'MI_PYTHON_UNVERIFIED');await fs.writeFile(manifest,JSON.stringify({schemaVersion:1,python:'python',pythonSha256:digest}));assert.equal((await managedRuntime(home)).reasonCode,'MI_RUNTIME_MANIFEST_REJECTED');
}));
