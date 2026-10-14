import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { validateWorld, promotion, readWorld } from '../../packages/core-adapter/world.mjs';
import { AppCore } from '../../packages/app-core/index.mjs';

import { fixture } from './world-fixture.mjs';
test('只读晋级要求全部阶段；写入永不晋级',()=>{
  const now=Date.now(), world=validateWorld(fixture(now),now);
  assert.equal(promotion(world,'mixer.track.read',null,now).enabled,true);
  assert.equal(promotion(world,'plugin.parameter.read',world.target,now).enabled,true);
  assert.equal(promotion(world,'plugin.parameter.write',world.target,now).enabled,false);
  for (const change of [w=>w.capabilities[4].evidence=[],w=>w.capabilities[4].contractVersion=null,w=>w.capabilities[4].state='experimental',w=>w.capabilities[4].evidence[0].binding.projectGeneration='other',w=>w.capabilities[4].evidence[0].binding.slotIndex=1,w=>w.capabilities[4].evidence[0].binding.instanceId='other']) {
    const w=validateWorld(fixture(now),now);change(w);assert.equal(promotion(w,'plugin.parameter.read',w.target,now).enabled,false);
  }
  assert.equal(promotion(world,'plugin.parameter.read',world.target,now+16000).enabled,false);
});
test('严格世界合同拒绝错误target、重复索引、越界参数与伪造来源',()=>{
  for (const change of [w=>w.target.instanceId='wrong',w=>w.tracks.push(w.tracks[0]),w=>w.tracks[0].slots[0].plugin.parameters[0].index=1,w=>w.source='mock',w=>w.capabilities[0].evidence[0].sha256='not-a-hash']) {
    const raw=fixture();change(raw);assert.throws(()=>validateWorld(raw));
  }
  const raw=fixture(Date.now()-20000);assert.equal(validateWorld(raw).state,'stale');
  raw.observedAt=new Date(Date.now()+60000).toISOString();assert.equal(validateWorld(raw).state,'stale');
});
test('没有发布端时未知；未晋级的数据不能通过IPC泄露为可读参数',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-world-'));
  const worldFile=path.join(root,'world.json');
  const core=new AppCore({roamingRoot:root,localRoot:root,worldFile,development:true}); await core.initialize();
  t.after(async()=>{await core.close();await fs.rm(root,{recursive:true,force:true});});
  assert.equal((await core.call('getWorldSnapshot')).data.state,'unknown');
  let raw=fixture();await fs.writeFile(worldFile,JSON.stringify(raw),'utf8');
  const normal=new AppCore({roamingRoot:root,localRoot:root,worldFile});
  assert.deepEqual((await normal.call('getWorldSnapshot')).data.tracks,[]);await normal.close();
  let world=(await core.call('getWorldSnapshot')).data;
  assert.equal(world.tracks[0].slots[0].plugin.parameters[0].value,0.5);
  assert.equal(world.tracks[0].slots[0].plugin.writeEnabled,false);
  raw.capabilities[4].evidence[0].binding.sessionId='other';await fs.writeFile(worldFile,JSON.stringify(raw),'utf8');
  world=(await core.call('getWorldSnapshot')).data;
  assert.equal(world.tracks[0].slots[0].plugin.parameters[0].value,null);
  raw.capabilities[0].state='experimental';await fs.writeFile(worldFile,JSON.stringify(raw),'utf8');
  assert.deepEqual((await core.call('getWorldSnapshot')).data.tracks,[]);
  await fs.writeFile(worldFile,'{broken','utf8');assert.equal((await core.call('getWorldSnapshot')).data.reason,'WORLD_SNAPSHOT_REJECTED');
  await fs.writeFile(worldFile,'x'.repeat(2*1024*1024+1),'utf8');await assert.rejects(readWorld(worldFile));
});
