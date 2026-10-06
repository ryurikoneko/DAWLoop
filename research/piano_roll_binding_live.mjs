import { readFile, writeFile } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomUUID } from 'node:crypto';
import { CaptureIntervalObserver } from './capture_interval_observer.mjs';

export async function observePianoRoll(sky, window, context) {
  const observer = new CaptureIntervalObserver(sky);
  const execute = promisify(execFile);
  const save = (name, value) => writeFile(join(context.output, name),
    JSON.stringify(value, null, 2), {flag:'wx'});
  const identity = async () => {
    const started_at = observer.stamp();
    const {stdout} = await execute(context.python,
      [join(context.repository,'scripts/runtime_v2_capture_identity.py'),
       'identity','--settings-dir',context.settings_dir], {cwd:context.repository,timeout:10000});
    const completed_at = observer.stamp();
    const value = JSON.parse(stdout.trim());
    if (value.controller_build_id !== context.expected_build ||
        value.controller_session_id !== context.controller_session_id ||
        value.project_generation !== context.project_generation ||
        value.project_loading !== false || value.pattern_number !== (context.target?.expected_pattern_index ?? 1) ||
        (context.target && value.pattern_name !== context.target.expected_pattern_name) ||
        value.channel_index_type !== 'global' || value.channel_index !== (context.target?.expected_channel_index ?? 1) ||
        value.channel_name !== (context.target?.expected_channel_name ?? '808 Clap') ||
        JSON.stringify(value.selected_channels) !== JSON.stringify([context.target?.expected_channel_index ?? 1]) ||
        value.ppq !== 96)
      throw Error('TARGET_CONTEXT_CHANGED');
    return {value,started_at,completed_at};
  };
  let request;
  try {
    const first = await identity();
    await save('identity_1.json',first);
    request = observer.request(randomUUID(),{
      controller_build_id:first.value.controller_build_id,
      controller_session:first.value.controller_session_id,
      project_generation:first.value.project_generation,
      host_pid:context.pid, window_id:window.id,
      native_bridge_attached:false, bridge_epoch:null, page_target_id:null,
    });
    await save('request.json',request);
    const packet = await observer.capture(request,window,
      {onRawResponse:raw=>save('raw_response_metadata.json',raw)});
    const receipt = observer.accept(request,packet);
    const second = await identity();
    await save('identity_2.json',second);
    await save('observation.json',receipt);
    const comparable = value => Object.fromEntries(Object.entries(value).filter(([key])=>key!=='observed_at'));
    if (JSON.stringify(comparable(first.value)) !== JSON.stringify(comparable(second.value)))
      throw Error('IDENTITY_DISAGREEMENT');
    const a = first.completed_at.monotonic_ms;
    const b = packet.result.capture_started_at.monotonic_ms;
    const c = packet.result.capture_completed_at.monotonic_ms;
    const d = second.started_at.monotonic_ms;
    const end = second.completed_at.monotonic_ms;
    if (!(a < b && b <= c && c < d) || !receipt.accepted)
      throw Error('STRICT_UI_BRACKET_FAILED');
    if (end-b > 60000) throw Error('TARGET_EVIDENCE_STALE');
    // 私人图像仅保留于临时目录，公开证据保存精确图像摘要与调用区间。
    await observer.persist(packet,join(tmpdir(),'DAWLoop_PianoRollBinding_'+request.request_id+
      (packet.result.image_mime === 'image/jpeg' ? '.jpg' : '.png')));
    const teardown = await observer.teardown(request,1000);
    if (teardown.status !== 'PASS') throw Error('OBSERVER_TEARDOWN_FAILED');
    const result = {status:'BRACKET_PASSED_PENDING_VISUAL_REVIEW',
      identity_equal:true, identity_bracket:true,
      image_hash:packet.result.image_hash,image_dimensions:packet.result.image_dimensions,
      request_id:request.request_id, observer_generation:observer.generation,
      window_id:window.id,host_pid:context.pid,
      timing:{identity_1_ms:first.completed_at.monotonic_ms-first.started_at.monotonic_ms,
        capture_ms:receipt.capture_duration_ms,
        identity_2_ms:second.completed_at.monotonic_ms-second.started_at.monotonic_ms,
        capture_age_interval_ms:[end-c,end-b],
        delivery_age_interval_ms:receipt.delivery_age_interval_ms,
        handoff_ms:receipt.received_at.monotonic_ms-request.created_at.monotonic_ms},
      deadlines:{handoff_seconds:55,state_age_seconds:60},
      teardown, observer_tasks_remaining:observer.tasks.size,
      producer_target_verified:false,exact_target_binding:false};
    await save('bracket_result.json',result);
    return result;
  } catch(error) {
    let teardown = null;
    if (request && observer.records.has(request.request_id)) {
      observer.cancel(request);
      teardown = await observer.teardown(request,1000);
    }
    const result = {status:'FAIL',error_code:error.message.split('\n')[0],teardown};
    await save('failure.json',result);
    return result;
  }
}
