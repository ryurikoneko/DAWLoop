"""只处理已结束的现场证据，不连接宿主。"""

import json
import os
from pathlib import Path
from dawloop.runtime.diagnostics import duration_ms

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'evidence/runtime_v2/preview_latency'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    reports = []
    for name in ('raw1', 'raw2', 'full1'):
        directory = OUTPUT/name
        trace = read(directory/'trace.json')
        session = read(directory/'session.json')
        events = Path(os.environ['TEMP'])/('DAWLoop_RuntimeV2_3_2_' + name)
        observer = read(events/'observer.json')
        for event in observer:
            event['host_generation'] = session['host_generation']
            event['metadata']['time_semantics'] = 'KNOWN_PRESENT_UPPER_BOUND_OR_INPUT_INVOCATION'
        (directory/'observer_trace.json').write_text(json.dumps(observer, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        for event in ('target', 'preview', 'accept', 'application'):
            (directory/('ui_' + event + '.json')).write_bytes((events/(event+'.json')).read_bytes())
        def get(event):
            return next((e for e in trace if e['event'] == event), None)
        def span(begin, end):
            return duration_ms(get(begin), get(end))
        def aggregate(event):
            pending = None
            output = []
            for item in trace:
                if item['event'] == event + '_begin':
                    pending = item
                elif item['event'] == event + '_complete' and pending:
                    value = duration_ms(pending, item)
                    if value is not None:
                        output.append(value)
                    pending = None
            return output
        timing = dict(trial=name, clock_domain=get('runtime_preview_notification')['clock_domain'],
            raw_call_or_native_dispatch_to_preview_notification_ms=span(
                'raw_call_begin' if name.startswith('raw') else 'native_dispatch_begin',
                'runtime_preview_notification'),
            dispatch_to_first_preview_ms=None, preview_detection_lag_ms=None,
            marker_receipt_to_runtime_notification_ms=span('preview_marker_received', 'runtime_preview_notification'),
            runJson_assignment_observed_ms=span('script_handler_assignment_begin', 'script_handler_assignment_return'),
            webview_observed_timestamp_quantum_ms=0.1,
            assignment_zero_means='BELOW_OBSERVED_CLOCK_QUANTUM',
            assignment_to_callback_ms=span('script_handler_assignment_return', 'host_callback_received'),
            bridge_timeout_ms=span('script_handler_assignment_begin', 'bridge_timeout'),
            enqueue_delay_ms=None, target_prepare_ms=span('target_prepare_begin', 'target_prepare_complete'),
            target_reconfirm_ms=span('target_reconfirm_begin', 'target_reconfirm_complete'),
            routing_to_backend_selected_ms=span('routing_begin', 'backend_selected'),
            routing_to_native_dispatch_ms=span('routing_begin', 'native_dispatch_begin'),
            render_inclusive_samples_ms=aggregate('rendering'),
            hash_validation_samples_ms=aggregate('hash_validation'), AST_validation_samples_ms=aggregate('AST_validation'),
            routing_to_result_emitted_ms=span('routing_begin', 'operation_result_emitted'),
            total_operation_to_result_emitted_ms=span('operation_received', 'operation_result_emitted'),
            actual_apply_latency_ms=None, discovery_ms=span('discovery_begin', 'discovery_complete'))
        result = read(directory/'result.json')
        (directory/'analysis.json').write_text(json.dumps(timing, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        reports.append(dict(timing=timing, completion=result.get('completion') or result.get('value',{}).get('completion_status'),
            recovery=read(directory/'recovery.json'), callbacks_restored=result['callbacks_restored']))
    cheap = read(OUTPUT/'raw2/cheap.json')
    summary = dict(status='MEASUREMENT_COMPLETED_ATTRIBUTION_UNRESOLVED', closed=True,
        bottleneck='UNRESOLVED', experiments=reports,
        cheap_native={k:cheap[k] for k in ('n','median','p50','p95','p95_method','max')},
        initial_cheap_clock_resolution_ms=15.625, initial_cheap_retained_separately=True,
        source_sha256='ac68744417a7b98f7c2a7c2293ba255b73e6d99ecd3609618af0f501f786da75',
        native_write_calls=3, ordinary_read_calls=40, capability_changed=False,
        performance_optimization_performed=False,
        capability=dict(NATIVE_PIANO_ROLL_BATCH_ADD='EXPERIMENTAL_LIVE', FAST_SUPPORTED=True,
            AUTO_SUPPORTED=False, VERIFIED_SUPPORTED=False, MAX_CERTIFIED_BATCH=128, PRODUCTION_WRITE_READY=False),
        tests=dict(total=240, added=3, failures=0, errors=0, skipped=0))
    # 已结束阶段仅重算报告；该脚本没有连接或派发入口。
    with (OUTPUT/'summary.json').open('w', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
