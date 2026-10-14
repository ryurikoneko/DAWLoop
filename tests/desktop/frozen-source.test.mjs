import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { verifyFrozenSessionSource } from '../../packages/core-session/frozen-spec.mjs';

const hash = raw => createHash('sha256').update(raw).digest('hex');
async function fixture(t) {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'dawloop-frozen-parent-'));
  const draft = path.join(temp, 'draft'); await fs.mkdir(draft);
  const files = [
    ['runtime/python.exe','python','EXECUTION_DEPENDENCY'],
    ['private/dawloop_automix_live_session.py','launcher','EXECUTION_DEPENDENCY'],
    ['private/dawloop_automix_live_driver.py','driver','EXECUTION_DEPENDENCY'],
    ['contracts/frozen-execution-v1.json','contract','CONTRACT_DOCUMENT'],
    ['evidence/ROADMAP.md','progress','EVIDENCE_DOCUMENT']
  ];
  for (const [relative,raw] of files) { const file=path.join(draft,relative);await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,raw); }
  const manifest={schema_version:2,allowed_operations:['HOST_SESSION_IDENTITY_READ'],source_sha256s:files.map(([snapshot,raw,category])=>({snapshot,sha256:hash(raw),category}))};
  const raw=JSON.stringify(manifest),digest=hash(raw),root=path.join(temp,`sha256-${digest}`);
  await fs.writeFile(path.join(draft,'source_manifest.json'),raw);await fs.rename(draft,root);
  const seal=async()=>{for(const [relative] of files)await fs.chmod(path.join(root,relative),0o444);await fs.chmod(path.join(root,'source_manifest.json'),0o444);};
  await seal();
  t.after(async()=>{for(const [relative]of files)await fs.chmod(path.join(root,relative),0o666);await fs.chmod(path.join(root,'source_manifest.json'),0o666);await fs.rm(temp,{recursive:true,force:true});});
  const config={test_operation:'HOST_SESSION_IDENTITY_READ',source:{checkpoint_repository:root,repository_root:path.join(root,'public'),package_root:path.join(root,'public','src'),private_root:path.join(root,'private'),frozen_execution:{schema_version:1,manifest_sha256:digest}}};
  const spec={python:path.join(root,'runtime','python.exe'),launcherPath:path.join(root,'private','dawloop_automix_live_session.py')};
  return{root,spec,config,seal};
}

test('父进程在解释器启动前验证整个封存来源，进度文字漂移仅记录',async t=>{
  const x=await fixture(t);assert.equal((await verifyFrozenSessionSource(x.spec,x.config)).bundleId,path.basename(x.root));
  const p=path.join(x.root,'evidence/ROADMAP.md');await fs.chmod(p,0o666);await fs.writeFile(p,'updated');
  assert.equal((await verifyFrozenSessionSource(x.spec,x.config)).evidence[0].matches,false);
});
test('未封存执行文件和变化依赖均在 spawn 前拒绝',async t=>{
  const x=await fixture(t),p=path.join(x.root,'private/dawloop_automix_live_driver.py');await fs.chmod(p,0o666);
  await assert.rejects(()=>verifyFrozenSessionSource(x.spec,x.config),{code:'FROZEN_SOURCE_NOT_SEALED'});
  await fs.writeFile(p,'changed');await x.seal();
  await assert.rejects(()=>verifyFrozenSessionSource(x.spec,x.config),{code:'FROZEN_DEPENDENCY_CHANGED'});
});
test('父进程拒绝非固定根、错误内容地址及越权操作',async t=>{
  const x=await fixture(t);
  await assert.rejects(()=>verifyFrozenSessionSource(x.spec,{...x.config,source:{...x.config.source,private_root:path.dirname(x.root)}}),{code:'FROZEN_ROOT_REJECTED'});
  await assert.rejects(()=>verifyFrozenSessionSource(x.spec,{...x.config,source:{...x.config.source,frozen_execution:{schema_version:1,manifest_sha256:'0'.repeat(64)}}}),{code:'FROZEN_MANIFEST_REJECTED'});
  await assert.rejects(()=>verifyFrozenSessionSource(x.spec,{...x.config,test_operation:'TARGET_PLUGIN_IDENTITY_READ'}),{code:'FROZEN_OPERATION_REJECTED'});
});
