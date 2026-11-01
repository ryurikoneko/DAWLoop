import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {basicComponentSource,verifyBasicEnvironment,installBasicComponent} from './basic-component.mjs';
export const PITCH_COMPONENT=JSON.parse(await fs.readFile(new URL('./pitch-component.lock',import.meta.url),'utf8'));
export const pitchComponentSource=root=>basicComponentSource(root,PITCH_COMPONENT);
export async function pitchInstallationInfo(home){
  const environment=path.join(home,'environments',PITCH_COMPONENT.componentId+'-'+PITCH_COMPONENT.version);
  try{
    const bytes=await fs.readFile(path.join(environment,'component.json'));
    if(createHash('sha256').update(bytes).digest('hex')!==PITCH_COMPONENT.manifestSha256)throw Error('MI_COMPONENT_HASH_REJECTED');
    const manifest=JSON.parse(bytes);
    return {version:manifest.providerVersion,bytes:manifest.installedBytes,componentVersion:manifest.version};
  }catch(error){if(error.code!=='ENOENT')throw error;}
  return JSON.parse(await fs.readFile(path.join(home,'models/basic-pitch/0.4.0-r2/manifest.json'),'utf8'));
}
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
