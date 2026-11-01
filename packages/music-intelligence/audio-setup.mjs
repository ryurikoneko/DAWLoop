import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {managedRuntime} from './managed-runtime.mjs';
import {fileDigest} from './model-download.mjs';

// 只发现产品安装根中的现有环境，不搜索 PATH，也不把安装记录当成健康检查。
export async function localAudioResources(root) {
  if(!root)return [];
  const realRoot=await fs.realpath(root).catch(()=>null);if(!realRoot||realRoot!==path.resolve(root))return [];
  const entries=await fs.readdir(root,{withFileTypes:true});const results=[];
  for(const entry of entries.filter(e=>e.isDirectory()&&!e.isSymbolicLink()).slice(0,32)) {
    const home=path.join(realRoot,entry.name);
    try {
      if(await fs.realpath(home)!==home)continue;
      const bytes=await fs.readFile(path.join(home,'runtime.json'));
      const manifest=JSON.parse(bytes.toString('utf8'));
      if(typeof manifest.python!=='string'||!path.isAbsolute(manifest.python))continue;
      const python=path.resolve(manifest.python);
      if(!python.startsWith(home+path.sep)||await fs.realpath(python)!==python)continue;
      if(manifest.basePython&&(!path.isAbsolute(manifest.basePython)||!/^[a-f0-9]{64}$/.test(manifest.basePythonSha256)||await fileDigest(manifest.basePython)!==manifest.basePythonSha256))continue;
      const runtime=await managedRuntime(home);if(!runtime.python||runtime.manifestRoot!==home)continue;
      results.push({id:createHash('sha256').update(home).update(bytes).digest('hex'),home,license:'PSF/ISC/BSD',additionalBytes:0,kind:'EXISTING_MANAGED_ENVIRONMENT'});
    } catch {}
  }
  return results;
}
