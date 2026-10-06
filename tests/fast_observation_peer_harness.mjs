import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';
import { randomUUID } from 'node:crypto';
import { AgentVisualReview, FastObservationPeer } from '../research/fast_observation_peer.mjs';

const root = await mkdtemp(join(tmpdir(), 'dawloop-observer-offline-'));
const jpeg = await readFile(new URL('./native_fixtures/capture_return_2x3.jpg', import.meta.url));
const window = { id: 20, app: 'OFFLINE' };
let captures = 0;
const sky = { async get_window_state() {
  captures++;
  return { window, screenshots: [{ id: 'offline-frame', width: 2, height: 3,
    url: 'data:image/jpeg;base64,' + jpeg.toString('base64') }] };
} };
let passed = 0;
try {
  for (const runtimePid of [undefined, null, 0, -1, 1.5, '1']) {
    assert.throws(() => new FastObservationPeer(sky, window, {
      directory: root, artifactDirectory: root, runtimePid }), /OBSERVER_RUNTIME_PID_REQUIRED/);
  }
  const unavailable = new FastObservationPeer(sky, window, {
    directory: join(root, 'missing-review'), artifactDirectory: join(root, 'private'), runtimePid: process.pid });
  await unavailable.start();
  const manifest = JSON.parse(await readFile(join(root, 'missing-review', 'observer.json'), 'utf8'));
  assert.equal(manifest.ready, false);
  assert.equal(manifest.review_ready, false);
  assert.equal(captures, 0);
  assert.equal((await unavailable.stop()).status, 'PASS');
  passed++;

  const reviewer = new AgentVisualReview();
  const directory = join(root, 'agent-review');
  const peer = new FastObservationPeer(sky, window, { directory,
    artifactDirectory: join(directory, 'private'), review: reviewer.attach(), runtimePid: process.pid });
  await peer.start();
  const request = { request_id: randomUUID().replaceAll('-', ''), run_id: randomUUID().replaceAll('-', ''),
    session_id: randomUUID().replaceAll('-', ''), operation_id: 'offline-agent-review',
    observer_generation: peer.observer.generation, stage: 'TARGET', target: { channel_name: '808 Clap' } };
  const prefix = join(directory, 'mailbox', request.request_id);
  await writeFile(prefix + '.request.json', JSON.stringify({ request }), { flag: 'wx', encoding: 'utf8' });
  const deadline = Date.now() + 3000;
  while (!reviewer.current() && Date.now() < deadline) await delay(10);
  const frame = reviewer.current();
  assert.deepEqual(frame.bytes, jpeg);
  frame.bytes.fill(0);
  assert.deepEqual(reviewer.current().bytes, jpeg);
  const review = { observer: 'agent_visual_review', request_id: request.request_id,
    observer_generation: request.observer_generation, image_hash: frame.result.image_hash,
    visible: true, confirmed: true, pattern_number: 1, channel_name: '808 Kick', window_pid: 10, window_hwnd: 20 };
  assert.throws(() => reviewer.confirm(null), /IMAGE_REVIEW_BINDING_FAILED/);
  assert.throws(() => reviewer.confirm({ ...review, request_id: 'old' }), /IMAGE_REVIEW_BINDING_FAILED/);
  reviewer.confirm(review);
  while (!peer.completed.size && Date.now() < deadline) await delay(10);
  const returned = JSON.parse(await readFile(prefix + '.result.json', 'utf8'));
  // 预期Clap不能覆盖实际审阅Kick；最终目标比较由既有Python观察合同拒绝。
  assert.equal(returned.review.channel_name, '808 Kick');
  assert.equal(reviewer.current(), null);
  reviewer.detach();
  await peer.manifest(true);
  assert.equal(JSON.parse(await readFile(join(directory, 'observer.json'), 'utf8')).ready, false);
  assert.equal((await peer.stop()).status, 'PASS');
  passed++;

  const cancelledReviewer = new AgentVisualReview();
  const callback = cancelledReviewer.attach();
  const cancellation = new AbortController();
  const pending = callback(request, { result: frame.result, bytes: jpeg }, { signal: cancellation.signal });
  cancellation.abort();
  await assert.rejects(pending, /REQUEST_CANCELLED/);
  assert.equal(cancelledReviewer.current(), null);
  assert.throws(() => cancelledReviewer.confirm(review), /IMAGE_REVIEW_BINDING_FAILED/);
  cancelledReviewer.detach();
  passed++;

  for (const fault of ['cancel', 'changed-image-hash', 'old-generation']) {
    const directory = join(root, fault);
    let reviewing = false;
    const peer = new FastObservationPeer(sky, window, { directory, artifactDirectory: join(directory, 'private'),
      runtimePid: process.pid,
      review: async (request, packet, { signal }) => {
        reviewing = true;
        if (fault === 'cancel') {
          await new Promise(resolve => signal.addEventListener('abort', resolve, { once: true }));
        }
        return { request_id: request.request_id,
          observer_generation: fault === 'old-generation' ? 'old' : request.observer_generation,
          image_hash: fault === 'changed-image-hash' ? '0'.repeat(64) : packet.result.image_hash };
      } });
    await peer.start();
    const request = { request_id: randomUUID().replaceAll('-', ''), run_id: randomUUID().replaceAll('-', ''),
      session_id: randomUUID().replaceAll('-', ''), operation_id: 'offline-only',
      observer_generation: peer.observer.generation, stage: 'TARGET' };
    const prefix = join(directory, 'mailbox', request.request_id);
    await writeFile(prefix + '.request.json', JSON.stringify({ request }), { flag: 'wx', encoding: 'utf8' });
    const deadline = Date.now() + 3000;
    while (!reviewing && Date.now() < deadline) await delay(10);
    assert.equal(reviewing, true);
    if (fault === 'cancel') await writeFile(prefix + '.cancel.json', '{}', { flag: 'wx', encoding: 'utf8' });
    while (!peer.failure && Date.now() < deadline) await delay(10);
    assert.match(peer.failure, /REQUEST_CANCELLED|IMAGE_REVIEW_BINDING_FAILED/);
    await assert.rejects(readFile(prefix + '.result.json'), /ENOENT/);
    const teardown = await peer.stop();
    assert.equal(teardown.status, 'PASS');
    assert.equal(teardown.tasks_remaining, 0);
    assert.equal(teardown.review_tasks_remaining, 0);
    assert.equal(JSON.parse(await readFile(join(directory, 'observer.json'), 'utf8')).ready, false);
    passed++;
  }
  console.log(JSON.stringify({ scope: 'OFFLINE_SIMULATION', cases_passed: passed, live_captures: 0 }));
} finally {
  assert.equal(dirname(resolve(root)), resolve(tmpdir()));
  assert.ok(basename(root).startsWith('dawloop-observer-offline-'));
  await rm(root, { recursive: true, force: true });
}
