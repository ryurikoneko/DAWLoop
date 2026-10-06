import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { CaptureIntervalObserver, extractImage } from '../research/capture_interval_observer.mjs';

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==','base64');
const jpeg = await readFile(new URL('./native_fixtures/capture_return_2x3.jpg',import.meta.url));
const window = {id:10,app:'OFFLINE'};
const make = payload => new CaptureIntervalObserver({async get_window_state(){return {
  window,screenshots:[{id:'frame',url:payload,width:2,height:3}]};}});
let passed=0;
for (const [mime,bytes,dimensions] of [['image/png',png,{width:1,height:1}],
  ['image/jpeg',jpeg,{height:3,width:2}]]) {
  const observer=make(`data:${mime};base64,${bytes.toString('base64')}`);
  const request=observer.request('op',{session:'s'});
  let raw;
  const packet=await observer.capture(request,window,{onRawResponse:async value=>{raw=value;}});
  assert.equal(raw.raw_response_type.structure.screenshots.items[0].structure.url.declared_mime,mime);
  assert.equal(raw.request_id,request.request_id);
  assert.equal(raw.raw_response_hash,packet.result.raw_response_hash);
  assert.equal(raw.capture_started_at.monotonic_ms,packet.result.capture_started_at.monotonic_ms);
  assert.deepEqual(packet.bytes,bytes);
  assert.deepEqual(packet.result.image_dimensions,dimensions);
  assert.equal(observer.accept(request,packet).accepted,true);
  assert.equal((await observer.teardown(request)).status,'PASS');passed++;
}
for (const [input,error] of [[123,'PAYLOAD_MISSING'],[undefined,'PAYLOAD_MISSING'],
  ['data:image/png;base64,','PAYLOAD_EMPTY'],['data:image/unknown;base64,AA==','FORMAT_UNSUPPORTED']]) {
  assert.throws(()=>extractImage({url:input}),new RegExp(error));passed++;
}
for (const fault of ['payload_changed','same_metadata_different_bytes','request_mismatch',
  'generation_mismatch','reversed_interval']) {
  const observer=make(`data:image/jpeg;base64,${jpeg.toString('base64')}`);
  const request=observer.request('op',{session:'s'});
  const packet=await observer.capture(request,window);
  if(fault==='payload_changed')packet.bytes=png;
  if(fault==='same_metadata_different_bytes') {
    packet.bytes=Buffer.from(packet.bytes);packet.bytes[packet.bytes.length-1]^=1;
  }
  if(fault==='reversed_interval')packet.result.capture_started_at.monotonic_ms=packet.result.capture_completed_at.monotonic_ms+1;
  const supplied=fault==='request_mismatch'?{...request,request_id:'old'}:
    fault==='generation_mismatch'?{...request,observer_generation:'old'}:request;
  assert.throws(()=>observer.accept(supplied,packet),/BINDING_FAILED|GENERATION_MISMATCH|TIMESTAMP_UNAVAILABLE/);passed++;
}
const unsupported=make('data:image/unknown;base64,AA==');
const request=unsupported.request('op',{session:'s'});
let preserved;
await assert.rejects(unsupported.capture(request,window,{onRawResponse:async value=>{preserved=value;}}),/FORMAT_UNSUPPORTED/);
assert.ok(preserved.raw_response_hash);
assert.ok(preserved.capture_completed_at.monotonic_ms>=preserved.capture_started_at.monotonic_ms);
assert.equal(unsupported.tasks.size,0);passed++;
console.log(JSON.stringify({scope:'OFFLINE_SIMULATION',cases_passed:passed,
  supported_encodings:['PNG','JPEG'],live_format_known:false,capture_calls_live:0}));
