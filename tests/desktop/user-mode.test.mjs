import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {ConfigService,defaults,validateConfig} from '../../packages/config/index.mjs';

test('普通模式默认、旧配置兼容、即时持久化与非法模式拒绝',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-user-mode-'));
  try{
    assert.equal(defaults().ui.mode,'USER_MODE');const store=new ConfigService(root);
    const initial=await store.get();const old={...initial,ui:{language:'zh-CN'}};validateConfig(old);
    await fs.writeFile(store.filename,JSON.stringify(old),'utf8');assert.equal((await store.get()).ui.mode,undefined);
    await store.update({ui:{mode:'DEVELOPER_MODE'}});assert.equal((await new ConfigService(root).get()).ui.mode,'DEVELOPER_MODE');
    assert.equal((await store.get()).ui.language,'zh-CN');await store.update({ui:{mode:'USER_MODE'}});
    assert.equal((await new ConfigService(root).get()).ui.mode,'USER_MODE');
    await assert.rejects(store.update({ui:{mode:'ADMIN'}}),/INVALID_CONFIG/);
    assert.equal((await store.get()).features.experimentalMixerWrite,false);
  }finally{await fs.rm(root,{recursive:true,force:true});}
});
