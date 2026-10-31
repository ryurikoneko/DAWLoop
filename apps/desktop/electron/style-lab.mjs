import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {managedRuntime} from '../../../packages/music-intelligence/managed-runtime.mjs';
import {terminateOwnedProcess} from '../../../packages/music-intelligence/owned-process.mjs';
import {fileDigest} from '../../../packages/music-intelligence/model-download.mjs';

export class StyleLabBridge {
  constructor(music){this.music=music;this.root=null;this.workers=new Set();this.semanticWorker=null;}
  async open(root){
    if(this.semanticWorker)throw Error('STYLE_SEMANTIC_BUSY');
    const resolved=await fs.realpath(root);await fs.access(path.join(resolved,'library.sqlite'));
    this.root=resolved;
    try{return await this.call('list',{});}catch(e){this.root=null;throw e;}
  }
  async semantic(method,params){
    if(!this.root||!params||Object.keys(params).length||!['styleSemanticStart','styleSemanticStatus','styleSemanticCancel'].includes(method))throw Error('IPC_REJECTED');
    const root=this.root,folder=path.join(root,'phase6');
    const read=async()=>{
      let status={state:'NOT_INSTALLED',completed:0,total:0},songs=[];
      try{status=JSON.parse(await fs.readFile(path.join(folder,'status.json'),'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
      if(['PROCESSING','LOADING'].includes(status.state)&&!this.semanticWorker)status={...status,state:'EXTERNAL_OR_INTERRUPTED'};
      if(status.state==='READY'){
        songs=JSON.parse(await fs.readFile(path.join(folder,'results.json'),'utf8'));
        // 源文件变更后不把旧描述显示为当前分析。
        for(const song of songs){const structure=JSON.parse(await fs.readFile(path.join(root,'structure',song.asset+'.json'),'utf8'));if(song.sourceSha256!==structure.sourceSha256)throw Error('SEMANTIC_SOURCE_MISMATCH');}
      }
      const profiles={};
      for(const [key,file] of Object.entries({collection:'collection-profile.json',personal:'personal-profile.json',experiment:'suno-experiment.json'}))try{profiles[key]=JSON.parse(await fs.readFile(path.join(folder,file),'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
      return {status,songs,profiles};
    };
    if(method==='styleSemanticStatus')return read();
    if(method==='styleSemanticCancel'){if(!this.semanticWorker)throw Error('SEMANTIC_WORKER_NOT_OWNED');await fs.writeFile(path.join(folder,'cancel.request'),'cancel','utf8');return true;}
    if(this.semanticWorker)throw Error('STYLE_SEMANTIC_BUSY');
    const runtime=await managedRuntime(this.music.home);if(runtime.state!=='VERIFIED')throw Error('MI_PYTHON_NOT_CONFIGURED');
    const config=JSON.parse(await fs.readFile(path.join(runtime.manifestRoot,'runtime.json'),'utf8'));
    if(!path.isAbsolute(config.omarPython??'')||await fileDigest(config.omarPython)!==config.omarPythonSha256)throw Error('SEMANTIC_PYTHON_UNVERIFIED');
    await fs.access(path.join(folder,'provider.json'));
    await fs.rm(path.join(folder,'cancel.request'),{force:true});
    const script=fileURLToPath(new URL('../../../packages/music-intelligence/style_semantics.py',import.meta.url));
    const child=spawn(config.omarPython,[script,root,path.dirname(path.dirname(path.dirname(config.omarPython)))],{windowsHide:true,env:{...process.env,HF_HUB_OFFLINE:'1',TRANSFORMERS_OFFLINE:'1',PYTHONUTF8:'1'},stdio:['ignore','ignore','pipe']});
    this.semanticWorker=child;this.workers.add(child);child.stderr.on('data',b=>{void fs.appendFile(path.join(folder,'worker.log'),b).catch(()=>{});});
    const timer=setTimeout(()=>terminateOwnedProcess(child),15*60*1000);
    child.once('error',()=>{});
    child.once('close',async()=>{clearTimeout(timer);this.workers.delete(child);this.semanticWorker=null;try{const {status}=await read();if(status.state==='EXTERNAL_OR_INTERRUPTED'){await fs.writeFile(path.join(folder,'status.json'),JSON.stringify({...status,state:'INTERRUPTED',error:'SEMANTIC_WORKER_EXITED'}),'utf8');}}catch{} });
    return true;
  }
  async call(method,params){
    const keys={auditionDisposition:['pair','status','reason'],auditionLeaveBlind:[],auditionSummary:[],auditionList:[],auditionReveal:['pair'],auditionRate:['pair','ratings'],auditionPreview:params&&'mode' in params?['pair','side','mode']:['pair','side'],list:[],search:['query','scope'],feedback:['query','candidate','liked'],profile:['name','segments'],clip:['id'],song:['asset'],sectionEdit:['asset','index','start','end','label'],fullPrompt:['assets'],fullPromptSave:['assets','text'],rangeClip:['asset','start','end'],rangeSearch:['asset','start','end','scope']}[method];
    if(!this.root||!keys||!params||Object.keys(params).sort().join()!==[...keys].sort().join())throw Error('IPC_REJECTED');
    const runtime=await managedRuntime(this.music.home);
    if(runtime.state!=='VERIFIED')throw Error('MI_PYTHON_NOT_CONFIGURED');
    const script=fileURLToPath(new URL('../../../packages/music-intelligence/style-bridge.py',import.meta.url));
    return new Promise((resolve,reject)=>{
      const child=spawn(runtime.python,[script,this.root,this.music.home],{windowsHide:true,env:{...process.env,HF_HUB_OFFLINE:'1',TRANSFORMERS_OFFLINE:'1',PYTHONUTF8:'1'},stdio:['pipe','pipe','pipe']});this.workers.add(child);
      let stdout='';const timer=setTimeout(()=>terminateOwnedProcess(child),60000);
      child.stdout.on('data',data=>{stdout+=data;if(Buffer.byteLength(stdout)>1024*1024)terminateOwnedProcess(child);});
      child.stderr.resume();child.on('error',reject);
      child.on('close',code=>{clearTimeout(timer);this.workers.delete(child);if(code!==0)return reject(Error('STYLE_LAB_TASK_FAILED'));try{resolve(JSON.parse(stdout));}catch{reject(Error('STYLE_LAB_RESULT_INVALID'));}});
      child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify({method,params}));
    });
  }
  async preview(id,range,audition){
    const file=audition?await this.call('auditionPreview',audition):range?await this.call('rangeClip',range):await this.call('clip',{id});
    const real=await fs.realpath(file);const relative=path.relative(path.join(this.root,'audition'),real);
    if(relative.startsWith('..')||path.isAbsolute(relative)||path.extname(real)!=='.wav')throw Error('IPC_REJECTED');
    const asset=await this.music.importAudio(real);
    return {assetId:asset.id,url:await this.music.preview(asset.id)};
  }
  close(){for(const worker of this.workers)terminateOwnedProcess(worker);}
}
