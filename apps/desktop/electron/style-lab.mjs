import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {managedRuntime} from '../../../packages/music-intelligence/managed-runtime.mjs';
import {terminateOwnedProcess} from '../../../packages/music-intelligence/owned-process.mjs';

export class StyleLabBridge {
  constructor(music){this.music=music;this.root=null;this.workers=new Set();}
  async open(root){
    const resolved=await fs.realpath(root);await fs.access(path.join(resolved,'library.sqlite'));
    this.root=resolved;
    try{return await this.call('list',{});}catch(e){this.root=null;throw e;}
  }
  async call(method,params){
    const keys={list:[],search:['query','scope'],feedback:['query','candidate','liked'],profile:['name','segments'],clip:['id']}[method];
    if(!this.root||!keys||!params||Object.keys(params).sort().join()!==[...keys].sort().join())throw Error('IPC_REJECTED');
    const runtime=await managedRuntime(this.music.home);
    if(runtime.state!=='VERIFIED')throw Error('MI_PYTHON_NOT_CONFIGURED');
    const script=fileURLToPath(new URL('../../../packages/music-intelligence/style-bridge.py',import.meta.url));
    return new Promise((resolve,reject)=>{
      const child=spawn(runtime.python,[script,this.root,this.music.home],{windowsHide:true,env:{...process.env,HF_HUB_OFFLINE:'1',TRANSFORMERS_OFFLINE:'1',PYTHONUTF8:'1'},stdio:['pipe','pipe','pipe']});this.workers.add(child);
      let stdout='';const timer=setTimeout(()=>terminateOwnedProcess(child),20000);
      child.stdout.on('data',data=>{stdout+=data;if(Buffer.byteLength(stdout)>1024*1024)terminateOwnedProcess(child);});
      child.stderr.resume();child.on('error',reject);
      child.on('close',code=>{clearTimeout(timer);this.workers.delete(child);if(code!==0)return reject(Error('STYLE_LAB_TASK_FAILED'));try{resolve(JSON.parse(stdout));}catch{reject(Error('STYLE_LAB_RESULT_INVALID'));}});
      child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify({method,params}));
    });
  }
  async preview(id){
    const file=await this.call('clip',{id});
    const real=await fs.realpath(file);const relative=path.relative(path.join(this.root,'audition'),real);
    if(relative.startsWith('..')||path.isAbsolute(relative)||path.extname(real)!=='.wav')throw Error('IPC_REJECTED');
    const asset=await this.music.importAudio(real);
    return {assetId:asset.id,url:await this.music.preview(asset.id)};
  }
  close(){for(const worker of this.workers)terminateOwnedProcess(worker);}
}
