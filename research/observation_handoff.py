"""导航前置交接：请求隔离、采样绑定、协作取消和分域时间诊断。"""

import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
import queue
import threading
import time
import uuid


def stamp(domain):
    return dict(clock_domain=domain, monotonic=time.perf_counter(), wall=time.time())


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


class Cancelled(Exception):
    pass


class CooperativeObserver:
    def __init__(self, capture, publish):
        self.capture, self.publish = capture, publish
        self.cancel = threading.Event()
        self.requests = queue.Queue(maxsize=1)
        self.phase = 'WAITING_FOR_REQUEST'
        self.domain = 'observer-' + uuid.uuid4().hex
        self.observer_attached = False
        self.thread = threading.Thread(target=self.run, name=self.domain, daemon=False)

    def check(self):
        if self.cancel.is_set():
            raise Cancelled()

    def wait(self, seconds):
        if self.cancel.wait(seconds):
            raise Cancelled()

    def put(self, destination, value):
        while True:
            self.check()
            try:
                destination.put(value, timeout=.01)
                return
            except queue.Full:
                continue

    def run(self):
        try:
            while not self.cancel.is_set():
                try:
                    request = self.requests.get(timeout=.01)
                except queue.Empty:
                    continue
                self.check()
                trace = {'T2': stamp(self.domain)}
                self.phase = 'CAPTURE'
                self.observer_attached = True
                # 采样器必须在真实采样边界打点，外层调用起止不是截图时间。
                evidence, capture_trace = self.capture(self, request)
                self.check()
                trace.update(capture_trace)
                self.phase = 'PUBLISH'
                trace['T5'] = stamp(self.domain)
                evidence['published_at'] = trace['T5']
                self.check()
                self.publish(self, dict(request=request, evidence=evidence,
                                  evidence_hash=content_hash(evidence), trace=trace))
                self.phase = 'WAITING_FOR_REQUEST'
                self.observer_attached = False
        except Cancelled:
            self.phase = 'CANCELLED'
        finally:
            self.observer_attached = False

    def start(self):
        self.thread.start()

    def close(self, timeout=.25):
        self.cancel.set()
        self.thread.join(timeout=timeout)
        alive = self.thread.is_alive()
        return dict(status='THREAD_TEARDOWN_FAILED' if alive else 'PASS',
                    cancellation_signaled=True, worker_alive=alive,
                    thread_name=self.thread.name, last_phase=self.phase,
                    observer_remaining=self.observer_attached)


class ObservationExchange:
    def __init__(self, *, delivery_timeout=55, state_max_age=60):
        if not 0 < delivery_timeout <= 55 or not 0 < state_max_age <= 60:
            raise ValueError('HANDOFF_BUDGET_INVALID')
        self.operation_id = uuid.uuid4().hex
        self.domain = 'coordinator-' + uuid.uuid4().hex
        self.delivery_timeout, self.state_max_age = delivery_timeout, state_max_age
        self.active = None
        self.closed = False
        self.trace = {}
        self.diagnostics = []
        self._created = None

    def begin(self, binding, identity_complete):
        if self.closed or self.active is not None:
            raise ValueError('OPERATION_NOT_AVAILABLE')
        required = ('controller_session', 'project_generation', 'host_generation', 'bridge_epoch')
        if any(not isinstance(binding.get(k), str) or not binding[k] for k in required):
            raise ValueError('REQUEST_BINDING_REQUIRED')
        if identity_complete['clock_domain'] != self.domain:
            raise ValueError('IDENTITY_CLOCK_DOMAIN_MISMATCH')
        self.trace = {'T0': copy.deepcopy(identity_complete), 'T1': stamp(self.domain)}
        self._created = self.trace['T1']['monotonic']
        self.active = dict(operation_id=self.operation_id, request_id=uuid.uuid4().hex,
                           **copy.deepcopy(binding))
        return copy.deepcopy(self.active)

    def terminate(self, reason):
        self.closed = True
        self.active = None
        self.diagnostics.append(dict(event=reason, timestamp=stamp(self.domain)))

    def receive(self, result):
        try:
            return self._receive(result)
        except Exception:
            self.terminate('STOPPED')
            raise

    def _receive(self, result):
        received = stamp(self.domain)
        if self.closed or self.active is None:
            self.diagnostics.append(dict(event='LATE_RESULT', result=copy.deepcopy(result)))
            return False
        if result.get('request') != self.active:
            self.terminate('OLD_GENERATION_RESULT')
            raise ValueError('REQUEST_GENERATION_MISMATCH')
        if received['monotonic'] - self._created > self.delivery_timeout:
            self.terminate('TIMED_OUT')
            self.diagnostics.append(dict(event='LATE_RESULT', result=copy.deepcopy(result)))
            raise TimeoutError('HANDOFF_DELIVERY_TIMEOUT')
        evidence, trace = result.get('evidence'), result.get('trace', {})
        if not isinstance(evidence, dict) or result.get('evidence_hash') != content_hash(evidence):
            self.terminate('STOPPED')
            raise ValueError('CAPTURE_CONTENT_BINDING_INVALID')
        artifact = evidence.get('capture_artifact')
        if (not isinstance(artifact, str) or not Path(artifact).is_file() or
                hashlib.sha256(Path(artifact).read_bytes()).hexdigest() != evidence.get('capture_sha256')):
            raise ValueError('CAPTURE_ARTIFACT_BINDING_INVALID')
        if set(trace) != {'T2', 'T3', 'T4', 'T5'}:
            raise ValueError('CAPTURE_TIMING_MISSING')
        domains = {row['clock_domain'] for row in trace.values()}
        points = [trace[k]['monotonic'] for k in ('T2', 'T3', 'T4', 'T5')]
        if (len(domains) != 1 or points != sorted(points) or
                any(type(row.get(k)) not in (int, float) or not math.isfinite(row[k])
                    for row in trace.values() for k in ('monotonic', 'wall'))):
            raise ValueError('OBSERVER_CLOCK_INVALID')
        if (evidence.get('captured_at') != trace['T4'] or
                evidence.get('published_at') != trace['T5'] or
                evidence.get('capture_completed_unix') != trace['T4']['wall']):
            raise ValueError('CAPTURE_TIMESTAMP_UNBOUND')
        # 跨域单调值不能相减；沿用既有墙钟年龄守卫，墙钟差不作为性能值。
        age = received['wall'] - trace['T4']['wall']
        if not 0 <= age <= self.state_max_age:
            raise ValueError('TARGET_EVIDENCE_STALE')
        self.trace.update(copy.deepcopy(trace), T6=received)
        value = copy.deepcopy(evidence)
        value['received_at'] = received
        self.active = None
        return value

    def confirm_started(self):
        self.trace['T7'] = stamp(self.domain)

    def confirm_complete(self):
        self.trace['T8'] = stamp(self.domain)
        age = self.trace['T8']['wall'] - self.trace['T4']['wall']
        if not 0 <= age <= self.state_max_age:
            self.terminate('STOPPED')
            raise ValueError('TARGET_EVIDENCE_STALE')

    def durations(self):
        pairs = dict(identity_to_request=('T0', 'T1'), worker_queue=('T2', 'T3'),
                     capture=('T3', 'T4'), capture_to_publish=('T4', 'T5'),
                     handoff=('T1', 'T6'), received_to_confirm=('T6', 'T7'),
                     confirm=('T7', 'T8'), delivery_age=('T4', 'T6'), state_age=('T4', 'T8'))
        output = {}
        for name, (a, b) in pairs.items():
            first, last = self.trace.get(a), self.trace.get(b)
            output[name + '_ms'] = ((last['monotonic']-first['monotonic'])*1000
                if first and last and first['clock_domain'] == last['clock_domain'] else None)
        return output


class FileMailbox:
    """取消文件通知外部观察者；本协调器没有阻塞输入线程。"""
    def __init__(self, directory, exchange):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.exchange = exchange

    def write(self, filename, value):
        target = self.directory / filename
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        temporary.replace(target)

    async def request(self, payload):
        token = payload['request']['request_id']
        self.write(token + '.request.json', payload)
        reply = self.directory / (token + '.result.json')
        try:
            async with asyncio.timeout(self.exchange.delivery_timeout):
                while not reply.exists():
                    await asyncio.sleep(.01)
                return json.loads(reply.read_text(encoding='utf-8'))
        except BaseException:
            self.exchange.terminate('TIMED_OUT_OR_ABORTED')
            self.write(token + '.cancel.json', dict(request=payload['request'], cancel=True))
            raise

    def quarantine(self):
        for path in self.directory.glob('*.result.json'):
            self.exchange.diagnostics.append(dict(event='LATE_OR_DUPLICATE_RESULT', filename=path.name))
