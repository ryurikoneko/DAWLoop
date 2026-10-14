import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {randomUUID,createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {fileDigest} from './model-download.mjs';
import {terminateOwnedProcess} from './owned-process.mjs';
import {extractComponent} from './component-extract.mjs';

const directory=path.dirname(fileURLToPath(import.meta.url));
export const BASIC_COMPONENT=JSON.parse(await fs.readFile(path.join(directory,'basic-component.lock'),'utf8'));
const cache=new Map();
export async function basicComponentSource(root){
  if(process.platform!==BASIC_COMPONENT.platform||process.arch!==BASIC_COMPONENT.arch)return {available:false,reasonCode:'MI_COMPONENT_PLATFORM_UNSUPPORTED'};
  if(!root)return {available:false,reasonCode:'MI_COMPONENT_PACKAGE_MISSING'};
  const file=path.resolve(root,BASIC_COMPONENT.fileName);
  try {
    if(await fs.realpath(root)!==path.resolve(root)||await fs.realpath(file)!==file)throw Error('MI_COMPONENT_SOURCE_REJECTED');
    const stat=await fs.stat(file);if(!stat.isFile()||stat.size!==BASIC_COMPONENT.archiveBytes)throw Error('MI_COMPONENT_HASH_REJECTED');
    const key=[file,stat.size,stat.mtimeMs,stat.ctimeMs].join(':');
    if(!cache.has(key)){if(await fileDigest(file)!==BASIC_COMPONENT.sha256)throw Error('MI_COMPONENT_HASH_REJECTED');cache.clear();cache.set(key,true);}
    return {available:true,file,reasonCode:null};
  }catch(error){return {available:false,reasonCode:error.code==='ENOENT'?'MI_COMPONENT_PACKAGE_MISSING':/^[A-Z0-9_]+$/.test(error.message)?error.message:'MI_COMPONENT_SOURCE_REJECTED'};}
}
export async function verifyBasicEnvironment(root){
  const bytes=await fs.readFile(path.join(root,'component.json'));
  if(createHash('sha256').update(bytes).digest('hex')!==BASIC_COMPONENT.manifestSha256)throw Error('MI_COMPONENT_HASH_REJECTED');
  const manifest=JSON.parse(bytes);
  if(manifest.componentId!==BASIC_COMPONENT.componentId||manifest.version!==BASIC_COMPONENT.version||manifest.files.length!==BASIC_COMPONENT.fileCount)throw Error('MI_COMPONENT_HASH_REJECTED');
  if(await fs.realpath(root)!==path.resolve(root))throw Error('MI_COMPONENT_SOURCE_REJECTED');
  const allowed=new Set([...manifest.files.map(row=>row.path),'component.json','runtime.json']);
  async function inventory(folder){for(const entry of await fs.readdir(folder,{withFileTypes:true})){const file=path.join(folder,entry.name);if(entry.isSymbolicLink()||await fs.realpath(file)!==file)throw Error('MI_COMPONENT_SOURCE_REJECTED');if(entry.isDirectory())await inventory(file);else if(!entry.isFile()||!allowed.has(path.relative(root,file).replaceAll('\\','/')))throw Error('MI_COMPONENT_HASH_REJECTED');}}
  // 额外的 .pth、sitecustomize 或字节码也可能执行；不能只验证清单内文件。
  await inventory(root);
  for(const row of manifest.files){const file=path.resolve(root,row.path);if(!file.startsWith(root+path.sep)||await fs.realpath(file)!==file||(await fs.stat(file)).size!==row.bytes||await fileDigest(file)!==row.sha256)throw Error('MI_COMPONENT_HASH_REJECTED');}
  return manifest;
}
function run(executable,args,{job,signal,log,home}){
  return new Promise((resolve,reject)=>{
    if(signal.aborted)return reject(Error('MI_CANCELLED'));
    const temp=path.join(home,'temp');
    const child=spawn(executable,args,{windowsHide:true,shell:false,stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONPATH:'',PYTHONHOME:'',PYTHONNOUSERSITE:'1',TEMP:temp,TMP:temp,NUMBA_CACHE_DIR:temp,OMP_NUM_THREADS:'2',NUMBA_NUM_THREADS:'2'}});
    job.child=child;let bytes=0,errorCode=null,writing=Promise.resolve();
    const kill=code=>{errorCode=code;terminateOwnedProcess(child);};
    const timer=setTimeout(()=>kill('MI_COMPONENT_TIMEOUT'),180000);const abort=()=>kill('MI_CANCELLED');signal.addEventListener('abort',abort,{once:true});
    const capture=chunk=>{bytes+=chunk.length;if(bytes>8*1024*1024)kill('MI_OUTPUT_TOO_LARGE');writing=writing.then(()=>log({event:'COMPONENT_OUTPUT',detail:chunk.toString().slice(0,4096)}));void writing.catch(()=>kill('MI_COMPONENT_AUDIT_FAILED'));};
    child.stdout.on('data',capture);child.stderr.on('data',capture);
    const cleanup=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);job.child=null;};
    child.once('error',()=>{cleanup();reject(Error('MI_COMPONENT_WORKER_START_FAILED'));});
    child.once('close',async code=>{cleanup();try{await writing;if(errorCode||signal.aborted)throw Error(errorCode??'MI_CANCELLED');if(code!==0)throw Error('MI_COMPONENT_INSTALL_FAILED');resolve();}catch(error){reject(error);}});
  });
}
export async function installBasicComponent({home,componentRoot,job,signal,log}){
  const source=await basicComponentSource(componentRoot);if(!source.available)throw Error(source.reasonCode);
  if(await fs.realpath(home)!==path.resolve(home))throw Error('MI_COMPONENT_SOURCE_REJECTED');
  const environments=path.join(home,'environments');await fs.mkdir(environments,{recursive:true});
  if(await fs.realpath(environments)!==environments)throw Error('MI_COMPONENT_SOURCE_REJECTED');
  const target=path.join(environments,'basic-audio-'+BASIC_COMPONENT.version);
  try{await fs.access(target);await verifyBasicEnvironment(target);return {environment:target,reused:true};}catch(error){if(error.code!=='ENOENT')throw error;}
  const disk=await fs.statfs(home);if(disk.bavail*disk.bsize<BASIC_COMPONENT.minimumFreeBytes)throw Error('MI_DISK_SPACE_REQUIRED');
  // 嵌入式依赖的深层模块可能受Windows路径上限影响，暂存名保持短且唯一。
  const owner=path.join(environments,'.b-'+randomUUID());await fs.mkdir(owner);
  const archive=path.join(owner,'component.zip'),staging=path.join(owner,'e');
  try {
    job.state='PREPARING';await fs.copyFile(source.file,archive,constants.COPYFILE_EXCL);
    // 只执行本次拥有的字节副本，避免来源在检查后被其他任务修改。
    if(signal.aborted)throw Error('MI_CANCELLED');if(await fileDigest(archive)!==BASIC_COMPONENT.sha256)throw Error('MI_COMPONENT_HASH_REJECTED');
    job.state='INSTALLING';job.totalBytes=BASIC_COMPONENT.installedBytes;job.progress=0;
    await extractComponent({archive,target:staging,signal,job,maxBytes:BASIC_COMPONENT.installedBytes+4*1024*1024,fileCount:BASIC_COMPONENT.fileCount+1});
    job.state='VERIFYING';await verifyBasicEnvironment(staging);if(signal.aborted)throw Error('MI_CANCELLED');
    await run(path.join(staging,'python.exe'),['-I','-B',path.join(directory,'component-health.py')],{job,signal,log,home});
    if(signal.aborted)throw Error('MI_CANCELLED');
    const python=path.join(target,'python.exe');
    await fs.writeFile(path.join(staging,'runtime.json'),JSON.stringify({schemaVersion:1,python,pythonSha256:await fileDigest(path.join(staging,'python.exe')),componentId:BASIC_COMPONENT.componentId,componentVersion:BASIC_COMPONENT.version}),{encoding:'utf8',flag:'wx'});
    await fs.rename(staging,target);await log({event:'COMPONENT_VERIFIED',version:BASIC_COMPONENT.version,sha256:BASIC_COMPONENT.sha256});
    return {environment:target,reused:false};
  } finally {
    if(path.dirname(owner)!==environments||await fs.realpath(owner)!==owner)throw Error('MI_COMPONENT_CLEANUP_REJECTED');
    await fs.rm(owner,{recursive:true,force:true});
  }
}
