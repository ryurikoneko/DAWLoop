"""只存内存的观测事件；诊断失败不能改变派发结果。"""

import time
from contextlib import contextmanager


class DiagnosticTrace:
    def __init__(self, trace_id, operation_id):
        self.trace_id = trace_id
        self.operation_id = operation_id
        self.host_generation = None
        self.events = []

    def emit(self, event, layer='runtime', **metadata):
        self.events.append(dict(trace_id=self.trace_id, operation_id=self.operation_id,
            host_generation=self.host_generation, layer=layer, event=event,
            clock_domain='python_perf_counter', timestamp=time.perf_counter_ns(),
            timestamp_unit='ns', metadata=metadata))


def observe(trace, event, layer='runtime', **metadata):
    if trace is not None:
        try:
            trace.emit(event, layer, **metadata)
        except Exception:
            pass


@contextmanager
def diagnostic_span(trace, event, layer='runtime'):
    observe(trace, event + '_begin', layer)
    try:
        yield
    finally:
        observe(trace, event + '_complete', layer)


def duration_ms(first, last):
    if (first is None or last is None or first['trace_id'] != last['trace_id']
            or first['clock_domain'] != last['clock_domain']
            or (first['host_generation'] is not None and last['host_generation'] is not None
                and first['host_generation'] != last['host_generation'])
            or first['timestamp_unit'] != last['timestamp_unit']):
        return None
    difference = last['timestamp'] - first['timestamp']
    if difference < 0:
        return None
    return difference / 1000000 if first['timestamp_unit'] == 'ns' else difference
