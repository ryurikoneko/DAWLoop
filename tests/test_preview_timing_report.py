"""缺失、异域和歧义时间不能形成性能结论。"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
from preview_timing_report import build_report, elapsed


@pytest.mark.parametrize('start,end,domain,unit,status', [
    (None, 1, 'python_perf_counter', 'ns', 'MISSING_TIMESTAMP'),
    (True, 1, 'python_perf_counter', 'ns', 'MISSING_TIMESTAMP'),
    (0, float('nan'), 'python_perf_counter', 'ns', 'MISSING_TIMESTAMP'),
    (2, 1, 'python_perf_counter', 'ns', 'INVALID_TIME_ORDER'),
    (0, 1, 'unix', 's', 'UNSUPPORTED_CLOCK'),
])
def test_unknown_or_invalid_timestamp_stays_null(start, end, domain, unit, status):
    metric = elapsed(start, end, domain, unit)
    assert metric['status'] == status and metric['value_ms'] is None


def evidence():
    context = dict(operation_id='one', host_generation='host')
    result = dict(value=context, execution_status='SUCCESS')
    local = dict(observation=dict(context, clock_domain='python_perf_counter', dispatch_at=0,
        last_absent_capture_started_at=0, preview_detected_at=20_000_000, confirmation_at=40_000_000),
        prepare_started_at=0, prepare_ready_at=10_000_000, runtime_ready_at=41_000_000)
    trace = [dict(context, event=event, timestamp=timestamp, timestamp_unit='ns',
        clock_domain='python_perf_counter') for event, timestamp in (
            ('routing_begin', 0), ('dispatch_task_joined', 100_000_000))]
    return result, local, {}, trace


def test_same_clock_duration_preserves_unknown_producer_and_manual_times():
    report = build_report(*evidence())
    assert report['metrics']['routing_to_completion']['value_ms'] == 100
    assert report['preview_onset_interval_ms'] == [0, 20]
    assert report['producer_apply_latency_ms'] is None
    assert report['manual_accept_exact_time'] is None
    assert report['exact_set_verified'] is False


@pytest.mark.parametrize('fault', ['clock', 'unit', 'context', 'duplicate', 'missing'])
def test_trace_pair_refuses_cross_clock_cross_request_and_ambiguous_events(fault):
    result, local, full, trace = evidence()
    if fault == 'clock':
        trace[1]['clock_domain'] = 'webview_performance'
    elif fault == 'unit':
        trace[1]['timestamp_unit'] = 'ms'
    elif fault == 'context':
        trace[1]['operation_id'] = 'another'
    elif fault == 'duplicate':
        trace.append(copy.deepcopy(trace[1]))
    else:
        trace.pop()
    assert build_report(result, local, full, trace)['metrics']['routing_to_completion']['value_ms'] is None


def test_observation_from_another_host_cannot_be_reused():
    result, local, full, trace = evidence()
    local['observation']['host_generation'] = 'another'
    report = build_report(result, local, full, trace)
    assert report['preview_onset_interval_ms'] is None
    assert report['metrics']['dispatch_to_first_positive']['value_ms'] is None
