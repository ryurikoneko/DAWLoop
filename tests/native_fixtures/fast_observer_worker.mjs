import { readFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { FastObservationPeer } from '../../research/fast_observation_peer.mjs';

const directory = process.argv[2];
const jpeg = await readFile(new URL('./capture_return_2x3.jpg', import.meta.url));
const window = { id: 20, app: 'OFFLINE' };
const sky = { async get_window_state() {
  return { window, screenshots: [{ id: 'offline-frame', width: 2, height: 3,
    url: 'data:image/jpeg;base64,' + jpeg.toString('base64') }] };
} };
const peer = new FastObservationPeer(sky, window, { directory, runtimePid: process.pid,
  artifactDirectory: directory + '/private', review: async (request, packet) => ({
    request_id: request.request_id, observer_generation: request.observer_generation,
    image_hash: packet.result.image_hash, observer: 'human', confirmed: true, visible: true,
    pattern_number: 1, channel_name: '808 Kick', window_pid: 10, window_hwnd: 20,
    region: [1536, 3072], active_region_empty: true, preview_absent: true, human_available: true,
    preview_closed: true, phrase_visible: true }) });
await peer.start();
process.stdout.write('READY\n');
for await (const line of createInterface({ input: process.stdin })) {
  if (line === 'STOP') break;
}
const result = await peer.stop();
process.stdout.write(JSON.stringify(result) + '\n');
