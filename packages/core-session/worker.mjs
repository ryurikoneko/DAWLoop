import fs from 'node:fs/promises';
import { createHash, randomBytes } from 'node:crypto';
import { spawn } from 'node:child_process';
import { TrustedSessionProvider } from './index.mjs';
import { verifyFrozenSessionSource } from './frozen-spec.mjs';

const hash = data => createHash('sha256').update(data).digest('hex');
const require = (condition,code) => {if(!condition)throw Object.assign(new Error(code),{code});};

export async function startTrustedSessionWorker(spec,{cancelled=()=>false}={}) {
  const configBytes=await fs.readFile(spec.configPath);
  require(hash(configBytes)===spec.configSha256,'SESSION_CONFIG_CHANGED');
  const config=JSON.parse(configBytes.toString('utf8'));
  require(config.mode==='LIVE_READONLY' && config.live_authorized===true && config.test_operation==='HOST_SESSION_IDENTITY_READ' && config.session_stream===true,'SESSION_LIVE_AUTHORIZATION_REQUIRED');
  require(hash(await fs.readFile(spec.launcherPath))===spec.launcherSha256,'SESSION_LAUNCHER_CHANGED');
  require(hash(await fs.readFile(spec.python))===spec.pythonSha256,'SESSION_PYTHON_CHANGED');
  require(config.external_sources['dawloop_automix_live_session.py']===spec.launcherSha256,'SESSION_SOURCE_REJECTED');
  await verifyFrozenSessionSource(spec,config);
  require(!cancelled(),'SESSION_START_CANCELLED');
  const key=randomBytes(32),nonce=randomBytes(16).toString('hex');
  // 只启动现有统一入口的同一个 worker；没有 FL、Scanner 或通用 RPC 调用。
  const child=spawn(spec.python,['-B',spec.launcherPath,'--worker','--config',spec.configPath,'--output',spec.output,
    '--config-sha256',spec.configSha256,'--launcher-sha256',spec.launcherSha256],{windowsHide:true,stdio:['pipe','pipe','pipe'],env:{...process.env,PYTHONPATH:''}});
  let alive=true,buffer='',provider;
  const exited=new Promise(resolve=>{child.once('exit',()=>{alive=false;provider?.close();resolve();});child.once('error',()=>{alive=false;provider?.close();resolve();});});
  provider=new TrustedSessionProvider({key,nonce,expected:{workerPid:child.pid,configSha256:spec.configSha256,launcherSha256:spec.launcherSha256,targetSha256:config.identity_authorization.target_sha256},alive:()=>alive});
  child.stdin.on('error',()=>provider.close());
  child.stdout.setEncoding('utf8');child.stdout.on('data',chunk=>{
    buffer+=chunk;
    if(Buffer.byteLength(buffer)>131072){provider.close('SESSION_STREAM_TOO_LARGE');buffer='';child.stdin.end();return;}
    let index;
    while((index=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,index).trimEnd();buffer=buffer.slice(index+1);
      if(line.startsWith('DAWLOOP_SESSION ')) {try{provider.accept(JSON.parse(line.slice(16)));}catch{child.stdin.end();}}
    }
  });
  // stderr 被消费但不作为状态来源，也不把任意宿主消息写入 Renderer 日志。
  child.stderr.resume();
  child.stdin.write(JSON.stringify({key:key.toString('hex'),nonce})+'\n');key.fill(0);
  return {source:provider.source,close:async()=>{provider.close();child.stdin.end();await exited;}};
}
