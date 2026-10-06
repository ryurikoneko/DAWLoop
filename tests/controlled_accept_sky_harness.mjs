import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { acceptReviewedOnce, validateReviewedCoordinates } from '../scripts/controlled_accept_sky.mjs';

const control = { template_hash: 'e340115a21ca6bde8cdf6b9ce2cbd04f74137414f5a27e2bcbdc9e2a95df97f4',
  role: 'ACCEPT', identity_method: 'NATIVE_TITLE_AND_CLASS_WITH_EXACT_REVIEWED_BUTTON_BAR',
  native_title:'DAWLoop Native Add', window_class:'TScriptDialog',
  click_point_relative: [451,136], dpi: 120, window_rectangle: [778,470,1271,635],
  control_id: 'reviewed-accept:e340115a21ca6bde8cdf6b9ce2cbd04f74137414f5a27e2bcbdc9e2a95df97f4', };
const request = { control, context: { operation_id: 'fixed' }, main_origin: [0,0],
  sky_window_id: 10, pending: true };
const observation = { window: { id: 10, app: 'returned-app' },
  screenshots: [{ id: 'current', originX: 0, originY: 0, width: 2048, height: 1152 }] };
assert.deepEqual(validateReviewedCoordinates(request, observation), { screenshotId:'current', x:1229, y:606 });
for (const changed of [ { ...request, pending:false }, { ...request, sky_window_id:11 },
  { ...request, control:{...control, click_point_relative:[10,10]} },
  { ...request, control:{...control, dpi:120.5} } ]) {
  assert.throws(() => validateReviewedCoordinates(changed, observation));
}
for (const control of [{...request.control,native_title:'Other'},
    {...request.control,window_class:'Other'}, {...request.control,native_title:undefined}]) {
  assert.throws(() => validateReviewedCoordinates({...request,control},observation));
}
assert.throws(() => validateReviewedCoordinates(request, {...observation, screenshots:[]}));
assert.throws(() => validateReviewedCoordinates(request, {...observation, screenshots:observation.screenshots.concat(observation.screenshots)}));
for (const mode of ['success','fresh_reject','generation_reject','unknown']) {
  const directory = await mkdtemp(join(tmpdir(), 'dawloop-sky-'));
  let clicks = 0;
  const sky = { click: async input => { clicks++; assert.equal(input.click_count,1);
    if (mode === 'unknown') throw new Error('点击结果未知'); }, get_window_state: async () => observation };
  await writeFile(join(directory,'action_request.json'), JSON.stringify(request));
  const revalidate = async (_, __, generation) => ({...request,
    generation:mode === 'generation_reject' ? 'old' : generation, pending:mode !== 'fresh_reject'});
  try {
    if (mode === 'success') {
      const result = await acceptReviewedOnce({sky,observation,directory,revalidate});
      assert.equal(result.outcome.acknowledged,true);
      assert.equal(result.outcome.commit_status,'UNKNOWN');
    } else {
      await assert.rejects(acceptReviewedOnce({sky,observation,directory,revalidate}));
    }
    assert.equal(clicks, ['fresh_reject','generation_reject'].includes(mode) ? 0 : 1);
    await assert.rejects(acceptReviewedOnce({sky,observation,directory,revalidate}));
    assert.equal(clicks, ['fresh_reject','generation_reject'].includes(mode) ? 0 : 1);
    if(mode === 'unknown') assert.equal(JSON.parse(await readFile(join(directory,'action_answer.json'),'utf8')).acknowledged,false);
  } finally { await rm(directory,{recursive:true,force:true}); }
}
console.log('受支持动作适配拒绝与一次预算测试通过');
