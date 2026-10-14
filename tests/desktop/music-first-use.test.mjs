import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {localAudioResources} from '../../packages/music-intelligence/audio-setup.mjs';
import {MusicIntelligenceService} from '../../packages/music-intelligence/service.mjs';
const sha=raw=>createHash('sha256').update(raw).digest('hex');
test('本地资源发现限定安装根；连接拒绝任意路径、来源变化和额外参数',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'mi-ux03-'));let service;
 try {
  const sources=path.join(root,'resources'),home=path.join(sources,'existing'),python=path.join(home,'python.exe');await fs.mkdir(home,{recursive:true});await fs.writeFile(python,'OWNED_NOT_EXECUTABLE');await fs.writeFile(path.join(home,'runtime.json'),JSON.stringify({schemaVersion:1,python,pythonSha256:sha('OWNED_NOT_EXECUTABLE')}));
  service=new MusicIntelligenceService({home:path.join(root,'user'),localRuntimeRoot:sources});await service.initialize();const status=await service.audioSetupStatus();assert.equal(status.state,'NOT_READY');assert.equal(status.offlineInstallAvailable,false);assert.equal(status.resources.length,1);assert.ok(!JSON.stringify(status).includes(root));assert.equal(service.jobs.size,0);
  await assert.rejects(service.connectLocalAudioRuntime({resourceId:status.resources[0].id,path:home}),/IPC_REJECTED/);await assert.rejects(service.connectLocalAudioRuntime({resourceId:home}),/IPC_REJECTED/);
  await fs.writeFile(python,'DRIFT');await assert.rejects(service.connectLocalAudioRuntime({resourceId:status.resources[0].id}),/MI_LOCAL_RUNTIME_CHANGED/);assert.equal(service.python,undefined);assert.equal(service.jobs.size,0);
  const outside=path.join(root,'outside.exe');await fs.writeFile(outside,'EXTERNAL');await fs.writeFile(path.join(home,'runtime.json'),JSON.stringify({schemaVersion:1,python:outside,pythonSha256:sha('EXTERNAL')}));assert.deepEqual(await localAudioResources(sources),[]);assert.deepEqual(await localAudioResources(path.join(root,'absent')),[]);
 }finally{await service?.close();await fs.rm(root,{recursive:true,force:true});}
});
