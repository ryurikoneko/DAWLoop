import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {fileDigest} from './model-download.mjs';
import {terminateOwnedProcess} from './owned-process.mjs';
const directory=path.dirname(fileURLToPath(import.meta.url));
export async function installRuntime({home,modelId,job,signal,log}){
  let runtime;try{runtime=JSON.parse(await fs.readFile(path.join(home,'runtime.json'),'utf8'));}catch{throw Error('MI_BASE_PYTHON_REQUIRED');}
  if(!runtime.basePython||!runtime.basePythonSha256||await fileDigest(runtime.basePython)!==runtime.basePythonSha256)throw Error('MI_BASE_PYTHON_REQUIRED');
  const environment=path.join(home,'environments',modelId+'-v1'),temp=path.join(home,'temp'),cache=path.join(home,'pip-cache');
  await fs.mkdir(temp,{recursive:true});await fs.mkdir(cache,{recursive:true});
  const disk=await fs.statfs(home);if(disk.bsize*disk.bavail<8*1024**3)throw Error('MI_DISK_SPACE_REQUIRED');
  const run=(executable,args)=>new Promise((resolve,reject)=>{
    if(signal.aborted)return reject(Error('MI_CANCELLED'));
    const child=spawn(executable,args,{windowsHide:true,shell:false,stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONPATH:'',TEMP:temp,TMP:temp,PIP_CACHE_DIR:cache,PIP_DISABLE_PIP_VERSION_CHECK:'1'}});
    job.child=child;let bytes=0;let timedOut=false;let writing=Promise.resolve();const timer=setTimeout(()=>{timedOut=true;terminateOwnedProcess(child);},15*60*1000);const abort=()=>terminateOwnedProcess(child);signal.addEventListener('abort',abort,{once:true});
    const capture=chunk=>{bytes+=chunk.length;if(bytes>8*1024*1024){child.kill();return;}writing=writing.then(()=>log({stage:'RUNTIME_INSTALL',text:chunk.toString().slice(0,4096).replace(/https?:\/\/\S+/g,'[OFFICIAL_URL]').replaceAll(home,'[MODEL_HOME]')}));};
    child.stdout.on('data',capture);child.stderr.on('data',capture);child.on('error',()=>reject(Error('MI_RUNTIME_INSTALL_START_FAILED')));child.on('close',async code=>{clearTimeout(timer);signal.removeEventListener('abort',abort);await writing;if(signal.aborted)reject(Error('MI_CANCELLED'));else if(timedOut)reject(Error('MI_RUNTIME_INSTALL_TIMEOUT'));else if(code!==0)reject(Error('MI_RUNTIME_INSTALL_FAILED'));else resolve();});
  });
  job.state='PREPARING';await run(runtime.basePython,['-I','-m','venv',environment]);
  const executable=path.join(environment,'Scripts','python.exe');job.state='INSTALLING';
  await run(executable,['-I','-m','pip','install','--isolated','--cache-dir',cache,'--require-hashes','--no-deps','--only-binary=:all:','--index-url','https://pypi.org/simple',...(modelId==='basic'?[]:['--extra-index-url','https://download.pytorch.org/whl/cpu']),'-r',path.join(directory,modelId==='basic'?'basic-requirements.lock':'omar-requirements.lock')]);
  await run(executable,['-I','-c',modelId==='basic'?'import librosa,soundfile,mido;print(librosa.__version__)':'import omar_rq,torch,torchaudio;print(torch.__version__)']);
  if(signal.aborted)throw Error('MI_CANCELLED');const key=modelId==='basic'?'python':'omarPython';runtime[key]=executable;runtime[key+'Sha256']=await fileDigest(executable);
  const pending=path.join(home,'runtime.json.new');await fs.writeFile(pending,JSON.stringify(runtime),{flag:'wx'});await fs.rename(pending,path.join(home,'runtime.json'));
  return {modelId,executable,runtimeVerified:true};
}
