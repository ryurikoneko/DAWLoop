import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {MusicIntelligenceService} from '../../packages/music-intelligence/service.mjs';

test('公开候选不借用旧 Python 安装链，许可不能改变安全门',async t=>{
  const home=await fs.mkdtemp(path.join(os.tmpdir(),'alpha-install-gate-'));
  t.after(()=>fs.rm(home,{recursive:true,force:true}));
  let downloads=0;
  const service=new MusicIntelligenceService({home,allowLegacyPitchInstall:false,fetcher:async()=>{downloads++;throw Error('UNEXPECTED_DOWNLOAD');}});
  await assert.rejects(service.install('basic-pitch','Apache-2.0'),/MI_COMPONENT_PACKAGE_MISSING/);
  assert.equal(downloads,0);assert.equal(service.jobs.size,0);
});
test('公开发行不会签发更新通知批准',async()=>{
  const gate=JSON.parse(await fs.readFile(new URL('../../release_notification.json',import.meta.url),'utf8'));
  assert.equal(gate.schema_version,2);assert.equal(gate.notification_enabled,false);
  assert.equal(gate.approved_by_owner,false);assert.equal(gate.active_approval_id,null);
  assert.deepEqual(gate.approvals,[]);
});
