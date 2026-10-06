import { readFile, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';

const 模板摘要 = 'e340115a21ca6bde8cdf6b9ce2cbd04f74137414f5a27e2bcbdc9e2a95df97f4';

function 坐标请求(request, observation) {
  const control = request.control;
  if (control?.template_hash !== 模板摘要 || control?.control_id !== 'reviewed-accept:' + 模板摘要
      || control?.role !== 'ACCEPT'
      || control?.identity_method !== 'NATIVE_TITLE_AND_CLASS_WITH_EXACT_REVIEWED_BUTTON_BAR'
      || control?.native_title !== 'DAWLoop Native Add' || control?.window_class !== 'TScriptDialog'
      || JSON.stringify(control.click_point_relative) !== '[451,136]'
      || control.dpi !== 120 || request.pending !== true) {
    throw new Error('SKY_ACCEPT_REQUEST_UNPROVEN');
  }
  const rectangle = control.window_rectangle;
  const origin = request.main_origin;
  if (!Array.isArray(rectangle) || rectangle.length !== 4
      || !rectangle.every(Number.isSafeInteger)
      || rectangle[2] - rectangle[0] !== 493 || rectangle[3] - rectangle[1] !== 165
      || !Array.isArray(origin) || origin.length !== 2 || !origin.every(Number.isSafeInteger)) {
    throw new Error('SKY_ACCEPT_COORDINATES_UNPROVEN');
  }
  const point = [rectangle[0] + 451, rectangle[1] + 136];
  const screenshots = observation.screenshots?.filter(s =>
    Number.isFinite(s.originX) && Number.isFinite(s.originY)
    && Number.isFinite(s.width) && Number.isFinite(s.height)
    && s.originX <= rectangle[0] && s.originY <= rectangle[1]
    && s.originX + s.width >= rectangle[2] && s.originY + s.height >= rectangle[3]) || [];
  if (screenshots.length !== 1 || observation.window?.id !== request.sky_window_id
      || origin[0] !== screenshots[0].originX || origin[1] !== screenshots[0].originY) {
    throw new Error('SKY_ACCEPT_SCREENSHOT_MAPPING_UNPROVEN');
  }
  return { screenshotId: screenshots[0].id, x: point[0] - origin[0], y: point[1] - origin[1] };
}

// 观察必须先由调用方展示并审核；此函数只执行一次动作及立即刷新。
export async function acceptReviewedOnce({ sky, observation, directory, revalidate }) {
  const request = JSON.parse(await readFile(`${directory}/action_request.json`, 'utf8'));
  const coordinates = 坐标请求(request, observation);
  await writeFile(`${directory}/sky_action_intent.json`, JSON.stringify({
    context: request.context, control_id: request.control.control_id,
    action_status: 'RESERVED', exact_set_verified: false,
  }), { encoding: 'utf8', flag: 'wx' });
  const generation = randomUUID();
  const started = performance.now();
  const latest = await revalidate(request.context, request.control, generation);
  if (performance.now() - started > 500 || latest?.generation !== generation
      || latest?.pending !== true || JSON.stringify(latest.control) !== JSON.stringify(request.control)
      || JSON.stringify(latest.main_origin) !== JSON.stringify(request.main_origin)
      || latest.sky_window_id !== request.sky_window_id) {
    throw new Error('SKY_ACCEPT_FRESH_CHECK_REJECTED');
  }
  let outcome = { context: request.context, control_id: request.control.control_id,
    acknowledged: false, action_status: 'UNKNOWN', commit_status: 'UNKNOWN' };
  try {
    await sky.click({ window: observation.window, ...coordinates, click_count: 1 });
    outcome = { ...outcome, acknowledged: true, action_status: 'ACTION_CONFIRMED' };
  } finally {
    await writeFile(`${directory}/action_answer.json`, JSON.stringify(outcome),
      { encoding: 'utf8', flag: 'wx' });
  }
  return { outcome, state: await sky.get_window_state({ window: observation.window,
    include_screenshot: true, include_text: false }) };
}

export { 坐标请求 as validateReviewedCoordinates };
