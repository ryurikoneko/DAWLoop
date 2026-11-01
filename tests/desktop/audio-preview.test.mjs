import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {MusicIntelligenceService} from '../../packages/music-intelligence/service.mjs';
import {byteRange} from '../../packages/music-intelligence/audio-preview.mjs';
test('Audio range validates suffix, open-end, oversized and malformed requests',()=>{
  assert.deepEqual(byteRange('bytes=2-4',10),{start:2,end:4,status:206});assert.equal(byteRange('bytes=-3',10).start,7);assert.equal(byteRange('bytes=5-',10).end,9);
  for(const h of ['bytes=10-','bytes=8-2','bytes=-0','bytes=0-1,3-4','bytes=a-b'])assert.throws(()=>byteRange(h,10));
});
test('Audio grants stream exact bytes, reject arbitrary paths and revoke on removal/switch/close',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'mi-audio-'));const mi=new MusicIntelligenceService({home:root});
  try{await mi.initialize();const file=path.join(root,'owned.wav');await fs.writeFile(file,Buffer.from('0123456789'));const asset=await mi.importAudio(file);const url=await mi.preview(asset.id);assert.ok(url.startsWith('dawloop-audio:'));assert.ok(url.length<120);
    let response=await mi.audioPreview.response(new Request(url,{headers:{Range:'bytes=2-4'}}));assert.equal(response.status,206);assert.equal(await response.text(),'234');assert.equal(response.headers.get('content-range'),'bytes 2-4/10');
    assert.equal((await mi.audioPreview.response(new Request(url,{headers:{Range:'bytes=100-'}}))).status,416);
    assert.equal((await mi.audioPreview.response(new Request('dawloop-audio://preview/windows/system32'))).status,403);
    const newer=await mi.preview(asset.id);assert.equal((await mi.audioPreview.response(new Request(url))).status,410);await mi.removeAsset(asset.id);assert.equal((await mi.audioPreview.response(new Request(newer))).status,410);assert.equal(mi.audioPreview.grants.size,0);
  }finally{await mi.close();await fs.rm(root,{recursive:true,force:true});}
});
test('Audio source changes invalidate grants rather than serving substituted bytes',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'mi-audio-'));const mi=new MusicIntelligenceService({home:root});try{await mi.initialize();const file=path.join(root,'test.flac');await fs.writeFile(file,'abc');const asset=await mi.importAudio(file);const url=await mi.preview(asset.id);await fs.writeFile(mi.assetPath(asset.id),'changed');assert.equal((await mi.audioPreview.response(new Request(url))).status,410);}finally{await mi.close();await fs.rm(root,{recursive:true,force:true});}
});
test('Paused consumers keep stream read-ahead bounded instead of buffering the full file',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'mi-audio-'));const mi=new MusicIntelligenceService({home:root});try{await mi.initialize();const file=path.join(root,'test.wav');await fs.writeFile(file,Buffer.alloc(4*1024**2,1));const asset=await mi.importAudio(file);const url=await mi.preview(asset.id);const response=await mi.audioPreview.response(new Request(url));const reader=response.body.getReader();await reader.read();await new Promise(r=>setTimeout(r,150));const stream=[...mi.audioPreview.streams.values()][0].values().next().value;assert.ok(stream.bytesRead<=512*1024,`read-ahead ${stream.bytesRead}`);await reader.cancel();}finally{await mi.close();await fs.rm(root,{recursive:true,force:true});}
});
