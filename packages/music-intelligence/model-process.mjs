import {spawn} from 'node:child_process';
import path from 'node:path';
export class ModelProcess {
  constructor(python,script,onExit,log,home){
    this.pending=null;this.log=log;this.buffer='';this.bytes=0;
    this.child=spawn(python,['-I','-B',script],{windowsHide:true,shell:false,stdio:['pipe','pipe','pipe'],env:{...process.env,PYTHONPATH:'',HF_HOME:path.join(home,'hf-cache'),HF_MODULES_CACHE:path.join(home,'hf-modules'),TORCH_HOME:path.join(home,'torch-cache'),TEMP:path.join(home,'temp'),TMP:path.join(home,'temp'),OMP_NUM_THREADS:'2',HF_HUB_OFFLINE:'1',TORCH_FORCE_WEIGHTS_ONLY_LOAD:'1'}});
    this.child.stdout.setEncoding('utf8');this.child.stdout.on('data',chunk=>{this.bytes+=Buffer.byteLength(chunk);if(this.bytes>8*1024*1024)return this.fail('MI_OUTPUT_TOO_LARGE');this.buffer+=chunk;let i;
      while((i=this.buffer.indexOf('\n'))>=0){const line=this.buffer.slice(0,i);this.buffer=this.buffer.slice(i+1);try{const v=JSON.parse(line);if(v.schemaVersion!==1||!this.pending)throw Error();if(v.kind==='result'){const p=this.pending;this.pending=null;clearTimeout(p.timer);p.resolve(v.data);}else if(v.kind==='error'){void this.log(v);this.fail(v.code,v.detail);}else throw Error();}catch{this.fail('MI_PROTOCOL_REJECTED');}}
    });
    this.child.stderr.on('data',chunk=>{void this.log({kind:'stderr',detail:chunk.toString().slice(0,2000).replace(/https?:\/\/\S+/g,'[URL]')});});
    this.child.stdin.on('error',()=>{});this.child.on('error',()=>this.fail('MI_MODEL_PYTHON_UNAVAILABLE'));
    this.child.on('close',()=>{this.fail('MI_MODEL_WORKER_EXITED');onExit();});
  }
  request(method,params){if(this.pending)throw Error('MI_RESOURCE_BUSY');if((this.child.exitCode!==null||this.child.signalCode!==null))throw Error('MI_MODEL_WORKER_EXITED');this.bytes=0;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>this.fail('MI_MODEL_TIMEOUT'),180000);this.pending={resolve,reject,timer};this.child.stdin.write(JSON.stringify({schemaVersion:1,method,params})+'\n');});}
  fail(code,detail){if(this.pending){const p=this.pending;this.pending=null;clearTimeout(p.timer);p.reject(Object.assign(Error(/^[A-Z0-9_]+$/.test(code)?code:'MI_MODEL_RUNTIME_FAILED'),{detail}));}this.child.kill();}
  async close(){if((this.child.exitCode!==null||this.child.signalCode!==null))return;this.child.stdin.end();await new Promise((resolve,reject)=>{let finalTimer;const t=setTimeout(()=>{this.child.kill();finalTimer=setTimeout(()=>reject(Error('MI_WORKER_CLEANUP_FAILED')),1000);},3000);this.child.once('close',()=>{clearTimeout(t);clearTimeout(finalTimer);resolve();});});}
}
