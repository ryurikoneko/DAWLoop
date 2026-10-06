"""只分析已保存证据，区分显示事件接收、内容就绪与绘制。"""

from collections import Counter
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def select_candidate(events, before, after, dispatch_ns, pid, trace_id):
    old = {w['hwnd'] for w in before['windows']}
    visible = {w['hwnd'] for w in after['windows'] if w.get('fixed_probe_title_match')
        and w.get('class_name') == 'TScriptDialog' and w.get('visible') is True}
    candidates = []
    for event in events:
        details = event.get('details', {})
        if (event.get('event') == 'SHOW' and event.get('idObject') == 0 and event.get('idChild') == 0
                and event.get('clock_domain') == 'python_perf_counter' and event.get('timestamp_unit') == 'ns'
                and event.get('trace_id') == trace_id and event.get('callback_enter', 0) >= dispatch_ns
                and event.get('hwnd') not in old and event.get('hwnd') in visible
                and details.get('process_id') == pid and details.get('fixed_probe_title_match') is True
                and details.get('class_name') == 'TScriptDialog' and details.get('parent_hwnd') in old):
            candidates.append(event)
    return candidates[0] if len(candidates) == 1 else None


def stable_windows(snapshot):
    return {w['hwnd']: {k: w.get(k) for k in ('name', 'class_name', 'visible', 'enabled',
        'bounding_rectangle', 'parent_hwnd')} for w in snapshot['windows']}


def analyze_trial(directory):
    before, after = read(directory / 'native_before.json'), read(directory / 'native_at_preview.json')
    installed = read(directory / 'native_after_install.json')
    events = read(directory / 'winevents.json')
    trace = [e for e in read(directory / 'trace.json') if e['clock_domain'] == 'python_perf_counter']
    dispatch = next(e for e in trace if e['event'] == 'native_dispatch_begin')
    notification = next(e for e in trace if e['event'] == 'runtime_preview_notification')
    candidate = select_candidate(events['events'], before, after, dispatch['timestamp'],
        events['pid'], dispatch['trace_id'])
    valid = candidate is not None and events['dropped'] == 0 and events['unhooked'] is True
    return dict(trial=directory.name, host_generation=read(directory / 'session.json')['host_generation'],
        candidate_correlated=valid, candidate_hwnd=candidate['hwnd'] if candidate else None,
        class_name='TScriptDialog' if candidate else None,
        native_dispatch_ns=dispatch['timestamp'],
        preview_native_event_ns=candidate['callback_enter'] if valid else None,
        runtime_preview_notification_ns=notification['timestamp'],
        dispatch_to_native_show_receipt_ms=(candidate['callback_enter']-dispatch['timestamp'])/1000000 if valid else None,
        native_show_receipt_to_runtime_notification_ms=(notification['timestamp']-candidate['callback_enter'])/1000000 if valid else None,
        callback_resolution_lag_ms=(candidate['details']['resolution_perf_counter_ns']-candidate['callback_enter'])/1000000 if valid else None,
        callback_semantics='ASYNCHRONOUS_SHOW_RECEIPT', preview_content_ready_ns=None,
        pixel_first_visible_ns=None, counts=dict(Counter(e['event'] for e in events['events'])),
        dropped=events['dropped'], reentrant_events=sum(e['reentrant'] for e in events['events']),
        unhooked=events['unhooked'], callback_max_duration_ns=max(
            (e['callback_exit']-e['callback_enter'] for e in events['events']), default=None),
        install_native_state_unchanged=stable_windows(before) == stable_windows(installed),
        install_foreground_unchanged=(before.get('foreground_hwnd') == installed.get('foreground_hwnd'))
            if 'foreground_hwnd' in before and 'foreground_hwnd' in installed else None,
        observer_nonintrusion_proven=False,
        completion=read(directory / 'result.json')['value']['completion_status'])


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1] / 'evidence/runtime_v2/native_preview_onset'
    rows = [analyze_trial(root / name) for name in ('discovery', 'repeat1', 'repeat2')]
    with (root / 'timing.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(clock_domain='python_perf_counter', trials=rows,
            notification_difference_semantics='INCLUDES_MANUAL_SCREENSHOT_TOOL_DELIVERY_AND_MARKER_WAIT'),
            stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(rows, ensure_ascii=False))
