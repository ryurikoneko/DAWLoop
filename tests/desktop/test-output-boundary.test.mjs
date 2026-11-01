import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

test('写入、复制、移动、删除和链接不能越过本次输出根',async()=>{
  const base=await fs.mkdtemp(path.join(os.tmpdir(),'test-output-boundary-'));
  try {
    const owned=path.join(base,'owned'),history=path.join(base,'history');await fs.mkdir(owned);await fs.mkdir(history);
    const sentinel=path.join(history,'original');await fs.writeFile(sentinel,'original');
    const guard=new URL('../../tools/test-output-guard.mjs',import.meta.url).href;
    const code=`const fs=await import('node:fs/promises');const root=${JSON.stringify(owned)},old=${JSON.stringify(sentinel)};await fs.writeFile(root+'/new','new');
      for(const action of [()=>fs.writeFile(old,'changed'),()=>fs.copyFile(root+'/new',old),()=>fs.rename(root+'/new',old),()=>fs.unlink(old),()=>fs.rm(${JSON.stringify(history)},{recursive:true}),()=>fs.writeFile(root+'/../history/new','changed')]) {
        try{await action();throw new Error('ESCAPE_ACCEPTED');}catch(error){if(!String(error).includes('TEST_OUTPUT_OUTSIDE_OWNED_ROOT'))throw error;}
      }
      try{await fs.symlink(${JSON.stringify(history)},root+'/link','junction');throw new Error('LINK_CREATION_ACCEPTED');}catch(error){if(error.code!=='ERR_ACCESS_DENIED')throw error;}`;
    const child=spawnSync(process.execPath,['--permission','--allow-fs-read=*','--allow-fs-write='+owned,'--import='+guard,'--input-type=module','-e',code],
      {encoding:'utf8',env:{...process.env,NODE_OPTIONS:'',DAWLOOP_TEST_OUTPUT_ROOT:owned}});
    assert.equal(child.status,0,child.stderr);
    assert.equal(await fs.readFile(sentinel,'utf8'),'original');assert.deepEqual(await fs.readdir(history),['original']);
  } finally {await fs.rm(base,{recursive:true,force:true});}
});
