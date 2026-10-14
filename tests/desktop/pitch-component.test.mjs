import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {PITCH_COMPONENT,pitchComponentSource,currentPitchEnvironment} from '../../packages/music-intelligence/pitch-component.mjs';
import {MusicIntelligenceService} from '../../packages/music-intelligence/service.mjs';
import {pitchManifest} from '../../packages/music-intelligence/pitch-install.mjs';

test('新转录组件缺失或损坏拒绝安装，不启动旧Python下载',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'pitch-component-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 let downloads=0;const service=new MusicIntelligenceService({home:path.join(root,'user'),componentRoot:root,allowLegacyPitchInstall:false,fetcher:async()=>{downloads++;throw Error('NETWORK_UNEXPECTED');}});await service.initialize();t.after(()=>service.close());
 await assert.rejects(service.install('basic-pitch','Apache-2.0'),/MI_COMPONENT_PACKAGE_MISSING/);
 await fs.writeFile(path.join(root,PITCH_COMPONENT.fileName),'corrupted');
 assert.equal((await pitchComponentSource(root)).reasonCode,'MI_COMPONENT_HASH_REJECTED');
 await assert.rejects(service.install('basic-pitch','Apache-2.0'),/MI_COMPONENT_HASH_REJECTED/);
 assert.equal(downloads,0);assert.equal(service.jobs.size,0);assert.equal(service.python,undefined);
});
test('新运行环境存在但不完整时拒绝，不回退到历史环境',async t=>{
 const home=await fs.mkdtemp(path.join(os.tmpdir(),'pitch-partial-'));t.after(()=>fs.rm(home,{recursive:true,force:true}));
 const environment=path.join(home,'environments',PITCH_COMPONENT.componentId+'-'+PITCH_COMPONENT.version);await fs.mkdir(environment,{recursive:true});
 await assert.rejects(currentPitchEnvironment(home),/MI_COMPONENT_HASH_REJECTED/);await assert.rejects(pitchManifest(home),/MI_COMPONENT_HASH_REJECTED/);
});
test('转录组件与基础分析组件版本独立，公开分发仍需独立审查',async()=>{
 assert.equal(PITCH_COMPONENT.componentId,'basic-pitch');assert.equal(PITCH_COMPONENT.publicRedistributionReview,'NATIVE_NOTICE_SOURCE_AND_REDIST_REVIEWED');assert.ok(PITCH_COMPONENT.archiveBytes<160*1024**2);assert.equal(PITCH_COMPONENT.downloadUrl,null);
 const review=JSON.parse(await fs.readFile(new URL('../../LICENSES/basic-pitch/NATIVE_INVENTORY.json',import.meta.url),'utf8'));assert.equal(review.reviewStatus,'NOTICE_SOURCE_AND_REDIST_OBLIGATIONS_REVIEWED');assert.equal(review.authorizationScope,'PRE_RELEASE_DRAFT_ONLY_PENDING_MAINTAINER_FINAL_PUBLICATION');assert.equal(review.newNativeFiles.length,3);
 const recipe=JSON.parse(await fs.readFile(new URL('../../packages/music-intelligence/pitch-component-sources.lock',import.meta.url),'utf8'));assert.equal(recipe.length,9);assert.ok(recipe.every(r=>r.url.startsWith('https://files.pythonhosted.org/')&&/^[a-f0-9]{64}$/.test(r.sha256)));assert.equal(recipe.some(r=>/tensorflow|setuptools|torch/.test(r.name)),false);
});
test('模型已载入或其他任务执行时拒绝并发安装',async()=>{
 const service=new MusicIntelligenceService({home:os.tmpdir(),allowLegacyPitchInstall:false});service.pitchProcess={};
 await assert.rejects(service.install('basic-pitch','Apache-2.0'),/MI_RESOURCE_BUSY/);service.pitchProcess=null;
 service.jobs.set('other',{id:'other',method:'analyze',state:'RUNNING'});await assert.rejects(service.install('basic-pitch','Apache-2.0'),/MI_RESOURCE_BUSY/);assert.equal(service.jobs.size,1);
});
