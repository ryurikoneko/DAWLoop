"""按原时钟域整理已有预览证据，不访问宿主或合并异域时间。"""

import math


def elapsed(start, end, domain, unit):
    result = dict(value_ms=None, clock_domain=domain, status='UNKNOWN')
    if domain not in ('python_perf_counter', 'webview_performance') or unit not in ('ns', 'ms'):
        return dict(result, status='UNSUPPORTED_CLOCK')
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) for value in (start, end)):
        return dict(result, status='MISSING_TIMESTAMP')
    if end < start:
        return dict(result, status='INVALID_TIME_ORDER')
    return dict(result, status='MEASURED', value_ms=(end-start)/(1e6 if unit == 'ns' else 1))


def build_report(result, local, full, trace):
    value = result.get('value') or {}
    observation = local.get('observation') or {}
    context = {key: value.get(key) for key in ('operation_id', 'host_generation')}
    context_valid = all(context.values()) and all(observation.get(k) == v for k, v in context.items())

    def pair(first, last, domain='python_perf_counter', unit='ns'):
        rows = [[row for row in trace if row.get('event') == name] for name in (first, last)]
        if not context_valid or any(any(row.get(k) != v for k, v in context.items())
                                    for group in rows for row in group):
            return dict(value_ms=None, status='CONTEXT_MISMATCH', clock_domain=domain)
        if any(len(group) != 1 for group in rows):
            return dict(value_ms=None, status='MISSING_OR_AMBIGUOUS_EVENT', clock_domain=domain)
        if any(row.get('clock_domain') != domain or row.get('timestamp_unit') != unit
               for group in rows for row in group):
            return dict(value_ms=None, status='CLOCK_MISMATCH', clock_domain=domain)
        return elapsed(rows[0][0].get('timestamp'), rows[1][0].get('timestamp'), domain, unit)

    domain = observation.get('clock_domain')
    metrics = dict(
        full_screen_preparation=elapsed(full.get('started_at_ns'), full.get('ready_at_ns'),
                                        full.get('clock_domain'), 'ns'),
        local_preparation=elapsed(local.get('prepare_started_at'), local.get('prepare_ready_at'), domain, 'ns'),
        dispatch_to_first_positive=elapsed(observation.get('dispatch_at'),
                                          observation.get('preview_detected_at'), domain, 'ns'),
        positive_to_confirmation=elapsed(observation.get('preview_detected_at'),
                                        observation.get('confirmation_at'), domain, 'ns'),
        confirmation_to_runtime=elapsed(observation.get('confirmation_at'), local.get('runtime_ready_at'), domain, 'ns'),
        runtime_ready_to_accept_notice=pair('runtime_preview_notification', 'runtime_accept_notification'),
        accept_notice_to_application_notice=pair('runtime_accept_notification', 'application_marker_received'),
        routing_to_completion=pair('routing_begin', 'dispatch_task_joined'),
        assignment_to_callback=pair('script_handler_assignment_return', 'host_callback_received',
                                    'webview_performance', 'ms'),
    )
    if not context_valid:
        for key, metric in metrics.items():
            if key != 'full_screen_preparation':
                metric.update(value_ms=None, status='CONTEXT_MISMATCH')
    interval = None
    lower = elapsed(observation.get('dispatch_at'), observation.get('last_absent_capture_started_at'), domain, 'ns')
    upper = metrics['dispatch_to_first_positive']
    if context_valid and lower['status'] == upper['status'] == 'MEASURED' and lower['value_ms'] <= upper['value_ms']:
        interval = [lower['value_ms'], upper['value_ms']]
    return dict(scope='POSTPROCESS_EXISTING_LIVE_EVIDENCE', context=context,
        execution_status=result.get('execution_status'), metrics=metrics,
        preview_onset_interval_ms=interval, exact_set_verified=False,
        producer_apply_latency_ms=None, manual_accept_exact_time=None,
        semantics=dict(
            dispatch_reference='LOCAL_PRE_HOST_DISPATCH_HOOK',
            onset='SAMPLING_BOUND_NOT_EXACT_RENDER_TIME',
            notices='RUNTIME_RECEIPT_INCLUDES_HUMAN_AND_COMPUTER_USE_WAIT',
            assignment_to_callback='INCLUDES_PREVIEW_AND_ACCEPT_WAIT_NOT_PRODUCER_SPEED',
            routing_to_completion='EXCLUDES_EARLIER_FULL_SCREEN_PREPARATION',
            phase_addition='OVERLAPPING_PHASES_NOT_SUMMED'),
    )
