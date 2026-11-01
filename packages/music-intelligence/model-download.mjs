import fs from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
export const OMAR_REVISION='9df2cecc1345c333c0688b8952b21c4789ab0fd7';
export const OMAR_MODEL='mtg-upf/omar-rq-multifeature-25hz-fsq';
export const OMAR_WEIGHT_SHA='2bf2a7e0ff047a60de8d68e8caa77941ae31e71df5034402e007b34a485e726b';
export async function fileDigest(file,algorithm='sha256'){
  const hash=createHash(algorithm);for await(const chunk of createReadStream(file))hash.update(chunk);return hash.digest('hex');
}
export function validateMetadata(meta){
  if(meta.sha!==OMAR_REVISION||meta.gated||meta.cardData?.license!=='cc-by-nc-sa-4.0')throw Error('MI_MODEL_SOURCE_REJECTED');
  const rows=['config.gin','LICENSE','model.ckpt'].map(name=>meta.siblings?.find(r=>r.rfilename===name));
  if(rows.some(r=>!r||!Number.isSafeInteger(r.size)||r.size<1)||rows[2].lfs?.sha256!==OMAR_WEIGHT_SHA||rows[0].blobId!=='5a60fd2716b2866fc7f3def74d0e6ba6ae92ff0a'||rows[1].blobId!=='cbe5ad1670406e4402217edfb82d2c56af7e8631')throw Error('MI_MODEL_MANIFEST_REJECTED');
  if(rows.some(r=>r.lfs?!/^[a-f0-9]{64}$/.test(r.lfs.sha256):!/^[a-f0-9]{40}$/.test(r.blobId)))throw Error('MI_MODEL_MANIFEST_REJECTED');
  return rows;
}
export async function verifyFile(file,row){
  try{
    if((await fs.lstat(file)).isSymbolicLink()||(await fs.stat(file)).size!==row.size)return false;
    if(row.lfs)return await fileDigest(file)===row.lfs.sha256;
    const raw=await fs.readFile(file);return createHash('sha1').update(`blob ${raw.length}\0`).update(raw).digest('hex')===row.blobId;
  }catch{return false;}
}
export async function officialMetadata(fetcher,signal){
  const url=`https://huggingface.co/api/models/${OMAR_MODEL}/revision/${OMAR_REVISION}?blobs=true`;
  let response;try{response=await fetcher(url,{signal});}catch(e){throw Object.assign(Error(signal?.aborted?'MI_DOWNLOAD_CANCELLED':'MI_METADATA_NETWORK_FAILED'),{detail:e?.message,stage:'METADATA',url});}
  if(!response.ok)throw Object.assign(Error('MI_MODEL_SOURCE_UNAVAILABLE'),{httpStatus:response.status,stage:'METADATA',url});
  const text=await response.text();if(Buffer.byteLength(text)>1024*1024)throw Error('MI_METADATA_TOO_LARGE');
  const meta=JSON.parse(text);validateMetadata(meta);return meta;
}
export async function downloadOmar({home,fetcher,job,signal,log}){
  const meta=await officialMetadata(fetcher,signal),rows=validateMetadata(meta);
  const bytes=rows.reduce((n,r)=>n+r.size,0);if(bytes>30*1024**3)throw Error('MI_MODEL_BUDGET_REJECTED');
  const disk=await fs.statfs(home);if(disk.bavail*disk.bsize<bytes*2)throw Error('MI_DISK_SPACE_REQUIRED');
  const dir=path.join(home,'models','omar-rq',OMAR_REVISION);await fs.mkdir(dir,{recursive:true});
  const manifestFile=path.join(dir,'manifest.json');
  try{const previous=JSON.parse(await fs.readFile(manifestFile,'utf8'));if(JSON.stringify(validateMetadata(previous))!==JSON.stringify(rows))throw Error('MI_MODEL_MANIFEST_CONFLICT');}catch(e){if(e.code!=='ENOENT')throw e;await fs.writeFile(manifestFile,JSON.stringify(meta),{flag:'wx'});}
  let complete=0;job.totalBytes=bytes;job.state='DOWNLOADING';
  for(const row of rows){
    if(signal.aborted)throw Error('MI_DOWNLOAD_CANCELLED');
    const file=path.join(dir,row.rfilename);if(await verifyFile(file,row)){complete+=row.size;job.downloadedBytes=complete;await log('CACHE_VERIFIED',{file:row.rfilename,bytes:row.size});continue;}
    // 不覆盖未通过验证的既有文件；保留冲突字节，要求用户诊断。
    try{await fs.stat(file);throw Error('MI_MODEL_CACHE_CONFLICT');}catch(e){if(e.code!=='ENOENT')throw e;}
    const partial=file+'.partial';let offset=0;try{if((await fs.lstat(partial)).isSymbolicLink())throw Error('MI_MODEL_PARTIAL_CONFLICT');offset=(await fs.stat(partial)).size;}catch(e){if(e.code!=='ENOENT')throw e;}
    if(offset>row.size)throw Error('MI_MODEL_PARTIAL_CONFLICT');
    const url=`https://huggingface.co/${OMAR_MODEL}/resolve/${OMAR_REVISION}/${row.rfilename}`;
    if(offset<row.size){
      let r;try{r=await fetcher(url,{signal,headers:offset?{Range:`bytes=${offset}-`}:undefined});}catch(e){throw Object.assign(Error('MI_WEIGHT_NETWORK_FAILED'),{detail:e.message,stage:'TRANSFER',url});}
      if(offset&&r.status!==206)throw Error('MI_RESUME_NOT_SUPPORTED');if(!offset&&r.status!==200)throw Object.assign(Error('MI_DOWNLOAD_HTTP_FAILED'),{httpStatus:r.status,url,stage:'TRANSFER'});
      if(offset){const expected=`bytes ${offset}-`;if(!r.headers.get('content-range')?.startsWith(expected)||!r.headers.get('content-range')?.endsWith('/'+row.size))throw Error('MI_CONTENT_RANGE_REJECTED');}
      const redirected=new URL(r.url||url);if(redirected.protocol!=='https:'||!['huggingface.co','hf.co'].includes(redirected.hostname)&&!redirected.hostname.endsWith('.hf.co')&&!redirected.hostname.endsWith('.huggingface.co'))throw Error('MI_DOWNLOAD_REDIRECT_REJECTED');
      await log(offset?'DOWNLOAD_RESUME':'DOWNLOAD_START',{url,redirectHost:redirected.hostname,file:row.rfilename,offset,bytes:row.size});
      const handle=await fs.open(partial,offset?'a':'wx');
      try{for await(const chunk of r.body){if(signal.aborted)throw Error('MI_DOWNLOAD_CANCELLED');offset+=chunk.length;if(offset>row.size)throw Error('MI_MODEL_SIZE_REJECTED');await handle.write(chunk);job.downloadedBytes=complete+offset;job.progress=job.downloadedBytes/bytes;}}finally{await handle.close();}
    }
    if(signal.aborted)throw Error('MI_DOWNLOAD_CANCELLED');if(!await verifyFile(partial,row))throw Error('MI_MODEL_HASH_REJECTED');
    await fs.rename(partial,file);complete+=row.size;await log('DOWNLOAD_VERIFIED',{file:row.rfilename,bytes:row.size,sha256:await fileDigest(file)});
  }
  return {revision:meta.sha,bytes,files:Object.fromEntries(await Promise.all(rows.map(async r=>[r.rfilename,await fileDigest(path.join(dir,r.rfilename))])))};
}
