import fs from 'node:fs/promises';
import {createReadStream,createWriteStream} from 'node:fs';
import path from 'node:path';
import {createInflateRaw} from 'node:zlib';
import {pipeline} from 'node:stream/promises';

const invalidPart=/^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i;
export function componentEntryPath(root,name){
  const parts=name.split('/');
  if(!name||parts.some(p=>!p||p==='.'||p==='..'||/[\\:\x00-\x1f]|[. ]$/.test(p)||invalidPart.test(p)))throw Error('MI_ARCHIVE_PATH_REJECTED');
  const file=path.resolve(root,...parts);if(!file.startsWith(path.resolve(root)+path.sep))throw Error('MI_ARCHIVE_PATH_REJECTED');return file;
}
export async function extractComponent({archive,target,signal,job,maxBytes,fileCount}){
  const handle=await fs.open(archive,'r');let size;
  try {
    size=(await handle.stat()).size;const tail=Buffer.alloc(Math.min(size,65557));await handle.read(tail,0,tail.length,size-tail.length);
    let end=-1;for(let i=tail.length-22;i>=0;i--){if(tail.readUInt32LE(i)===0x06054b50&&i+22+tail.readUInt16LE(i+20)===tail.length){end=i;break;}}
    if(end<0||tail.readUInt16LE(end+4)||tail.readUInt16LE(end+6)||tail.readUInt16LE(end+8)!==fileCount||tail.readUInt16LE(end+10)!==fileCount)throw Error('MI_COMPONENT_ARCHIVE_REJECTED');
    const length=tail.readUInt32LE(end+12),offset=tail.readUInt32LE(end+16);
    if(length>4*1024*1024||offset+length>size-tail.length+end)throw Error('MI_COMPONENT_ARCHIVE_REJECTED');
    const central=Buffer.alloc(length);await handle.read(central,0,length,offset);const entries=[],names=new Set();let cursor=0,expectedBytes=0;
    for(let n=0;n<fileCount;n++){
      if(cursor+46>length||central.readUInt32LE(cursor)!==0x02014b50)throw Error('MI_COMPONENT_ARCHIVE_REJECTED');
      const flags=central.readUInt16LE(cursor+8),method=central.readUInt16LE(cursor+10),compressed=central.readUInt32LE(cursor+20),bytes=central.readUInt32LE(cursor+24),nameLength=central.readUInt16LE(cursor+28),extra=central.readUInt16LE(cursor+30),comment=central.readUInt16LE(cursor+32),attributes=central.readUInt32LE(cursor+38),local=central.readUInt32LE(cursor+42);
      if(cursor+46+nameLength+extra+comment>length||flags&1||![0,8].includes(method)||(attributes>>>16&0xf000)===0xa000)throw Error('MI_COMPONENT_ARCHIVE_REJECTED');
      const name=central.subarray(cursor+46,cursor+46+nameLength).toString('utf8'),file=componentEntryPath(target,name),key=file.toLowerCase();
      if(names.has(key))throw Error('MI_ARCHIVE_PATH_REJECTED');names.add(key);expectedBytes+=bytes;
      if(expectedBytes>maxBytes||bytes>maxBytes||local+30+compressed>offset)throw Error('MI_COMPONENT_SIZE_REJECTED');
      entries.push({name,file,method,compressed,bytes,local});cursor+=46+nameLength+extra+comment;
    }
    if(cursor!==length)throw Error('MI_COMPONENT_ARCHIVE_REJECTED');
    job.totalBytes=expectedBytes;await fs.mkdir(target);let written=0;
    for(const entry of entries){
      if(signal.aborted)throw Error('MI_CANCELLED');
      const localHeader=Buffer.alloc(30);await handle.read(localHeader,0,30,entry.local);
      if(localHeader.readUInt32LE(0)!==0x04034b50||localHeader.readUInt16LE(8)!==entry.method)throw Error('MI_COMPONENT_ARCHIVE_REJECTED');
      const nameLength=localHeader.readUInt16LE(26),extra=localHeader.readUInt16LE(28),name=Buffer.alloc(nameLength);await handle.read(name,0,nameLength,entry.local+30);
      if(name.toString('utf8')!==entry.name)throw Error('MI_COMPONENT_ARCHIVE_REJECTED');const start=entry.local+30+nameLength+extra;
      if(start+entry.compressed>offset)throw Error('MI_COMPONENT_ARCHIVE_REJECTED');await fs.mkdir(path.dirname(entry.file),{recursive:true});
      if(await fs.realpath(path.dirname(entry.file))!==path.dirname(entry.file))throw Error('MI_ARCHIVE_PATH_REJECTED');
      if(entry.compressed===0){if(entry.bytes!==0)throw Error('MI_COMPONENT_SIZE_REJECTED');await fs.writeFile(entry.file,'',{flag:'wx'});continue;}
      const input=createReadStream(archive,{start,end:start+entry.compressed-1}),output=createWriteStream(entry.file,{flags:'wx'});
      let bytes=0;const decoded=entry.method===8?createInflateRaw():input;
      decoded.on('data',chunk=>{bytes+=chunk.length;if(bytes>entry.bytes)decoded.destroy(Error('MI_COMPONENT_SIZE_REJECTED'));});
      if(entry.method===8)await pipeline(input,decoded,output,{signal});else await pipeline(input,output,{signal});
      if(bytes!==entry.bytes)throw Error('MI_COMPONENT_SIZE_REJECTED');written+=bytes;job.installedBytes=written;job.progress=Math.min(.99,written/expectedBytes);
    }
  }finally{await handle.close();}
}
