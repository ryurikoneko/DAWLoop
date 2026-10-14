import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { verifyPortable } from '../../tools/verify-portable.mjs';

test('非法清单拒绝目录逃逸、schema和冲突路径',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'portable-manifest-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  for(const manifest of [{schemaVersion:2,files:[]},{schemaVersion:1,files:[{path:'../outside',sha256:'a'.repeat(64)}]},
    {schemaVersion:1,files:[{path:'portable-manifest.json',sha256:'a'.repeat(64)}]}]) {
    await fs.writeFile(path.join(root,'portable-manifest.json'),JSON.stringify(manifest),'utf8');
    await assert.rejects(verifyPortable(root),/PORTABLE_(SCHEMA|ENTRY)_REJECTED/);
  }
});
test('来源字节变化、缺必需资源与额外文件拒绝',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'portable-manifest-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const manifest={schemaVersion:1,files:[]};
  await fs.writeFile(path.join(root,'portable-manifest.json'),JSON.stringify(manifest));
  await assert.rejects(verifyPortable(root),/PORTABLE_REQUIRED_FILE_MISSING/);
  await fs.writeFile(path.join(root,'unexpected.py'),'not-allowed');
  await assert.rejects(verifyPortable(root),/PORTABLE_EXTRA_FILE_REJECTED/);
  await fs.writeFile(path.join(root,'portable-manifest.json'),JSON.stringify({schemaVersion:1,files:[{path:'unexpected.py',sha256:'a'.repeat(64)}]}));
  await assert.rejects(verifyPortable(root),/PORTABLE_BYTES_CHANGED/);
});
