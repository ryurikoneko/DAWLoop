import fs from 'node:fs/promises';
import path from 'node:path';
import {basicComponentSource,verifyBasicEnvironment,installBasicComponent} from './basic-component.mjs';
export const PITCH_COMPONENT=JSON.parse(await fs.readFile(new URL('./pitch-component.lock',import.meta.url),'utf8'));
export const pitchComponentSource=root=>basicComponentSource(root,PITCH_COMPONENT);
export async function currentPitchEnvironment(home){
  const environment=path.join(home,'environments',PITCH_COMPONENT.componentId+'-'+PITCH_COMPONENT.version);
  await fs.access(environment);
  let manifest;try{manifest=await verifyBasicEnvironment(environment,PITCH_COMPONENT);}catch(error){if(error.code==='ENOENT')throw Error('MI_COMPONENT_HASH_REJECTED');throw error;}
  return {version:manifest.providerVersion,python:path.join(environment,'python.exe'),bytes:manifest.installedBytes,componentVersion:manifest.version};
}
export async function installPitchComponent(options){
  const result=await installBasicComponent({...options,component:PITCH_COMPONENT,healthScript:'pitch-component-health.py'});
  return {...await currentPitchEnvironment(options.home),reused:result.reused};
}
