import { readFile, writeFile } from 'node:fs/promises';
import { setTimeout } from 'node:timers/promises';
import { acceptReviewedOnce } from '../scripts/controlled_accept_sky.mjs';

const [directory, mode] = process.argv.slice(2);
let clicks = 0;
await writeFile(`${directory}/offline_peer_ready.json`, '{}', { encoding: 'utf8', flag: 'wx' });
const deadline = performance.now() + 5000;
async function readWhenReady(name) {
  while (performance.now() < deadline) {
    try { return JSON.parse(await readFile(`${directory}/${name}`, 'utf8')); }
    catch (error) {
      if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
      await setTimeout(2);
    }
  }
  throw new Error('离线交接等待超时');
}
await readWhenReady('action_request.json');
const observation = { window: { id: 10, app: 'offline-simulation' },
  screenshots: [{ id: 'offline-only', originX: 0, originY: 0, width: 2048, height: 1152 }] };
// 模拟输入只计数，禁止导入任何真实电脑操控模块。
const sky = { click: async () => {
  clicks++;
  if (mode === 'unknown_action') throw new Error('模拟动作结果未知');
}, get_window_state: async () => observation };
let error = null;
try {
  await acceptReviewedOnce({sky, observation, directory,
    revalidate: async (context, control, generation) => {
      await writeFile(`${directory}/fresh_check_request.json`, JSON.stringify({context,control,generation}),
        {encoding:'utf8',flag:'wx'});
      return readWhenReady('fresh_check_answer.json');
    }});
} catch (caught) { error = caught.message; }
await writeFile(`${directory}/offline_peer_result.json`, JSON.stringify({clicks,error}),
  {encoding:'utf8',flag:'wx'});
