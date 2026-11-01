import fs from 'node:fs/promises';
import path from 'node:path';
import {fileDigest} from './model-download.mjs';
import {verifyBasicEnvironment,BASIC_COMPONENT} from './basic-component.mjs';

export async function managedRuntime(home) {
  try {
    let root=path.resolve(home);
    try {
      const reference=JSON.parse(await fs.readFile(path.join(root,'audio-runtime-reference.json'),'utf8'));
      if(reference.schemaVersion!==1||typeof reference.home!=='string'||!path.isAbsolute(reference.home))throw Error('MI_RUNTIME_REFERENCE_REJECTED');
      root=reference.home;
    } catch(e) { if(e.code!=='ENOENT')throw e; }
    const runtime=JSON.parse(await fs.readFile(path.join(root,'runtime.json'),'utf8'));
    if(runtime.schemaVersion!==1||typeof runtime.python!=='string'||!path.isAbsolute(runtime.python)||!/^[a-f0-9]{64}$/.test(runtime.pythonSha256))throw Error('MI_RUNTIME_MANIFEST_REJECTED');
    if(runtime.componentId!==undefined){if(runtime.componentId!==BASIC_COMPONENT.componentId||runtime.componentVersion!==BASIC_COMPONENT.version||runtime.python!==path.join(root,'python.exe'))throw Error('MI_RUNTIME_MANIFEST_REJECTED');await verifyBasicEnvironment(root);}
    if(await fileDigest(runtime.python)!==runtime.pythonSha256)throw Error('MI_PYTHON_UNVERIFIED');
    return {state:'VERIFIED',reasonCode:null,python:runtime.python,sha256:runtime.pythonSha256,manifestRoot:root};
  } catch(e) {
    return {state:'NOT_READY',reasonCode:e.code==='ENOENT'?'MI_PYTHON_NOT_CONFIGURED':/^[A-Z0-9_]+$/.test(e.message)?e.message:'MI_RUNTIME_MANIFEST_REJECTED',python:null};
  }
}
