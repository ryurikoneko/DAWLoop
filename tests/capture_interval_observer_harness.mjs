import assert from 'node:assert/strict';
import { CaptureIntervalObserver } from '../research/capture_interval_observer.mjs';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==','base64');
const window = { id: 10, app: 'OFFLINE' };
const sky = { async get_window_state() { return { window, screenshots: [
  { id: 'offline-frame', url: 'data:image/png;base64,'+png.toString('base64') }] }; } };
const faults = ['image_swap','hash_change','different_image_duplicate','old_generation',
                'missing_boundary','reversed_interval'];
for (const fault of faults) {
  const observer = new CaptureIntervalObserver(sky);
  const request = observer.request('operation', { session: 'test' });
  const packet = await observer.capture(request,window);
  if (fault === 'image_swap') packet.bytes = Buffer.from('other-image');
  if (fault === 'hash_change') packet.result.image_hash = 'changed';
  if (fault === 'different_image_duplicate') {
    assert.equal(observer.accept(request,packet).accepted,true);
    packet.bytes = Buffer.from('other-image');
  }
  if (fault === 'missing_boundary') delete packet.result.capture_started_at;
  if (fault === 'reversed_interval') packet.result.capture_started_at.monotonic_ms += 1000;
  if (fault === 'old_generation') {
    assert.throws(()=>observer.accept({...request,observer_generation:'old'},packet),/GENERATION_MISMATCH/);
  } else assert.throws(()=>observer.accept(request,packet),/BINDING_FAILED|TIMESTAMP_UNAVAILABLE/);
}
const observer = new CaptureIntervalObserver(sky);
const request = observer.request('operation', { session:'test' });
const packet = await observer.capture(request,window,{ beforeDelivery:async()=>observer.cancel(request) });
assert.equal(packet.cancelled,true);
assert.equal(observer.accept(request,packet).accepted,false);
assert.equal((await observer.teardown(request)).status,'PASS');
assert.equal(observer.tasks.size,0);
const directory = await mkdtemp(join(tmpdir(), 'dawloop-application-'));
try {
  const producer = new CaptureIntervalObserver(sky);
  const current = producer.request('operation', { run_id:'run', session_id:'session' });
  const captured = await producer.capture(current, window);
  const observation = producer.accept(current, captured);
  const review = { image_hash:observation.result.image_hash, observed:true,
    preview_closed:true, phrase_visible:true, visible_pattern:1, channel_name:'offline' };
  const paths = { evidencePath:join(directory,'application_observation.json'),
    receiptPath:join(directory,'application.json'), timingPath:join(directory,'timing.json') };
  await assert.rejects(producer.submitApplication(current, observation,
    { ...review, image_hash:'wrong' }, paths), /IMAGE_REVIEW_BINDING_FAILED/);
  const submitted = await producer.submitApplication(current, observation, review, paths);
  assert.deepEqual(JSON.parse(await readFile(paths.receiptPath,'utf8')), submitted.receipt);
  const stages = ['capture_completed_at','review_completed_at','submit_started_at','receipt_persisted_at'];
  assert.equal(new Set(stages.map(k=>submitted.timing[k].clock_domain)).size,1);
  for (let i=1;i<stages.length;i++)
    assert.ok(submitted.timing[stages[i]].monotonic_ms >= submitted.timing[stages[i-1]].monotonic_ms);
  assert.equal('coordinator_claimed_at' in submitted.timing,false);
  await assert.rejects(producer.submitApplication(current, observation, review, paths),
    /IMAGE_REVIEW_BINDING_FAILED/);
  assert.equal((await producer.teardown(current)).status,'PASS');
} finally {
  await rm(directory,{ recursive:true });
}
console.log(JSON.stringify({scope:'OFFLINE_SIMULATION',rejection_cases:6,cancellation:'PASS',
  application_submission:'PASS',
  navigation_transactions:0,navigation_primitives:0,note_dispatches:0,script_dispatches:0}));
