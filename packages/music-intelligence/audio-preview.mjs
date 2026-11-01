import fs from 'node:fs/promises';
import {createHash,randomBytes} from 'node:crypto';
import {Readable} from 'node:stream';
import path from 'node:path';

export function byteRange(header,size){
  if(!header)return {start:0,end:size-1,status:200};
  const m=/^bytes=(\d*)-(\d*)$/.exec(header);
  if(!m||(!m[1]&&!m[2]))throw Error('MI_RANGE_REJECTED');
  const start=m[1]?Number(m[1]):Math.max(0,size-Number(m[2]));
  const end=m[1]?(m[2]?Math.min(Number(m[2]),size-1):size-1):size-1;
  if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||start>=size||end<start||(!m[1]&&Number(m[2])===0))throw Error('MI_RANGE_REJECTED');
  return {start,end,status:206};
}

export class AudioPreview {
  constructor(service){this.service=service;this.grants=new Map();this.streams=new Map();}
  revoke(token){this.grants.delete(token);for(const stream of this.streams.get(token)??[])stream.destroy();this.streams.delete(token);return true;}
  release(id,url){if(typeof url!=='string')return;const token=url.split('/').at(-1);if(this.grants.get(token)?.id===id)this.revoke(token);}
  revokeAsset(id){for(const [token,g] of this.grants)if(g.id===id)this.revoke(token);}
  close(){this.generation=(this.generation??0)+1;for(const token of this.grants.keys())this.revoke(token);}
  async open(id){
    this.close();const generation=this.generation;
    const file=this.service.assetPath(id),asset=this.service.assets.get(id);
    const real=await fs.realpath(file),root=await fs.realpath(path.join(this.service.home,'audio-library'));
    if(path.dirname(real)!==root||real!==file)throw Error('MI_AUDIO_SOURCE_REJECTED');
    const handle=await fs.open(real,'r');let stat;
    try{stat=await handle.stat();if(!stat.isFile()||stat.size===0)throw Error('MI_AUDIO_REJECTED');const hash=createHash('sha256');for await(const chunk of handle.createReadStream({autoClose:false}))hash.update(chunk);if(hash.digest('hex')!==asset.sha256)throw Error('MI_ASSET_CHANGED');}finally{await handle.close();}
    // 单个主窗口只有一个有效试听凭据，旧请求不能继续读取已切换资源。
    if(this.service.closed||!this.service.assets.has(id)||generation!==this.generation)throw Error('MI_PREVIEW_REVOKED');
    const token=randomBytes(32).toString('hex');this.grants.set(token,{id,file,stat,extension:asset.extension});
    return `dawloop-audio://preview/${token}`;
  }
  async response(request){
    let handle;
    try{
      const url=new URL(request.url);if(url.protocol!=='dawloop-audio:'||url.hostname!=='preview'||url.search||url.hash||!/^\/[a-f0-9]{64}$/.test(url.pathname)||!['GET','HEAD'].includes(request.method))return new Response(null,{status:403});
      const token=url.pathname.slice(1),g=this.grants.get(token);if(!g||!this.service.assets.has(g.id))return new Response(null,{status:410});
      if(await fs.realpath(g.file)!==g.file)return new Response(null,{status:403});
      handle=await fs.open(g.file,'r');const stat=await handle.stat();if(stat.size!==g.stat.size||stat.mtimeMs!==g.stat.mtimeMs||stat.ino!==g.stat.ino){await handle.close();handle=null;this.revoke(token);return new Response(null,{status:410});}
      let range;try{range=byteRange(request.headers.get('range'),stat.size);}catch{await handle.close();handle=null;return new Response(null,{status:416,headers:{'Content-Range':`bytes */${stat.size}`}});}
      const headers={'Content-Type':{'.wav':'audio/wav','.mp3':'audio/mpeg','.flac':'audio/flac'}[g.extension],'Content-Length':String(range.end-range.start+1),'Accept-Ranges':'bytes','Cache-Control':'no-store','Access-Control-Allow-Origin':'*','X-Content-Type-Options':'nosniff'};
      if(range.status===206)headers['Content-Range']=`bytes ${range.start}-${range.end}/${stat.size}`;
      if(request.method==='HEAD'){await handle.close();handle=null;return new Response(null,{status:range.status,headers});}
      const stream=handle.createReadStream({start:range.start,end:range.end,highWaterMark:64*1024});handle=null;
      const active=this.streams.get(token)??new Set();this.streams.set(token,active);active.add(stream);stream.on('close',()=>{active.delete(stream);if(!active.size)this.streams.delete(token);});
      request.signal?.addEventListener('abort',()=>stream.destroy(),{once:true});
      // WebStream 默认按块计数；按字节限队列才能在暂停消费时保持背压。
      return new Response(Readable.toWeb(stream,{strategy:{highWaterMark:64*1024,size:chunk=>chunk.byteLength}}),{status:range.status,headers});
    }catch{await handle?.close().catch(()=>{});return new Response(null,{status:404});}
  }
}
