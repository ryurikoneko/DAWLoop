"""本地真实线程与离线时间故障；不启动宿主、不执行导航。"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
import queue
import statistics
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.observation_handoff import (ObservationExchange, CooperativeObserver,
                                         FileMailbox, content_hash, stamp)

BINDING = dict(controller_session='controller', project_generation='project',
               host_generation='host', bridge_epoch='epoch')
REPORTS = []


class HandoffFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifact = Path(self.directory.name)/'synthetic_capture.bin'
        self.artifact.write_bytes(b'OFFLINE_SYNTHETIC_CAPTURE')

    def result(self, exchange, request, domain='synthetic-observer'):
        trace = {k:stamp(domain) for k in ('T2','T3','T4','T5')}
        evidence = dict(captured_at=trace['T4'], published_at=trace['T5'],
                        capture_completed_unix=trace['T4']['wall'],
                        capture_artifact=str(self.artifact),
                        capture_sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest())
        return dict(request=request, evidence=evidence, evidence_hash=content_hash(evidence), trace=trace)

    def begin(self, **kwargs):
        exchange = ObservationExchange(**kwargs)
        request = exchange.begin(BINDING, stamp(exchange.domain))
        return exchange, request

    def test_synthetic_failures_are_quarantined_without_dispatch(self):
        for fault in ('evidence_stale_before_capture','fresh_capture_late_delivery',
                      'old_generation','duplicate_result','capture_binding','artifact_binding'):
            with self.subTest(fault=fault):
                exchange, request = self.begin(delivery_timeout=.02)
                result = self.result(exchange, request)
                if fault == 'evidence_stale_before_capture':
                    result['trace']['T4']['wall'] -= 61
                    result['evidence']['capture_completed_unix'] -= 61
                    result['evidence_hash'] = content_hash(result['evidence'])
                if fault == 'fresh_capture_late_delivery':
                    time.sleep(.03)
                if fault == 'old_generation':
                    result['request']['operation_id'] = 'old'
                if fault == 'capture_binding':
                    result['evidence']['capture_completed_unix'] -= 1
                    result['evidence_hash'] = content_hash(result['evidence'])
                if fault == 'artifact_binding':
                    self.artifact.write_bytes(b'changed')
                if fault == 'duplicate_result':
                    self.assertIsInstance(exchange.receive(result), dict)
                    self.assertFalse(exchange.receive(result))
                else:
                    with self.assertRaises((ValueError, TimeoutError)):
                        exchange.receive(result)
                    self.assertFalse(exchange.receive(result))
                self.assertTrue(exchange.diagnostics)
                REPORTS.append(dict(scope='OFFLINE_SIMULATION', case=fault,
                    navigation_transactions=0, navigation_primitives=0,
                    note_dispatches=0, script_dispatches=0, passed=True))

    def test_local_worker_normal_slow_and_cancellation(self):
        for case in ('normal_fast','slow_valid','cancel_wait','cancel_capture',
                     'timeout_before_finish','worker_returns_after_timeout','publish_after_cancel'):
            with self.subTest(case=case):
                exchange, request = self.begin(delivery_timeout=.15)
                results = queue.Queue()
                entered = threading.Event()

                def capture(worker, request):
                    entered.set()
                    t3 = stamp(worker.domain)
                    worker.wait(.025 if case == 'slow_valid' else .005)
                    if case in ('cancel_capture','timeout_before_finish',
                                'worker_returns_after_timeout','publish_after_cancel'):
                        worker.wait(.025 if case == 'worker_returns_after_timeout' else .3)
                    evidence = dict(captured_at=None, capture_artifact=str(self.artifact),
                        capture_sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest())
                    t4 = stamp(worker.domain)
                    evidence.update(captured_at=t4, capture_completed_unix=t4['wall'])
                    return evidence, dict(T3=t3, T4=t4)

                worker = CooperativeObserver(capture, lambda worker,value:worker.put(results,value))
                worker.start()
                if case != 'cancel_wait':
                    worker.requests.put(request, timeout=.1)
                    self.assertTrue(entered.wait(.1))
                if case in ('normal_fast','slow_valid'):
                    result = results.get(timeout=.2)
                    received = exchange.receive(result)
                    self.assertEqual(received['captured_at'], result['trace']['T4'])
                    exchange.confirm_started()
                    exchange.confirm_complete()
                    self.assertIsNone(exchange.durations()['delivery_age_ms'])
                    self.assertIsNone(exchange.durations()['state_age_ms'])
                else:
                    exchange.terminate('TIMED_OUT' if 'timeout' in case else 'ABORT')
                    if case == 'worker_returns_after_timeout':
                        late = results.get(timeout=.2)
                        self.assertFalse(exchange.receive(late))
                        self.assertNotIn('T7',exchange.trace)
                teardown = worker.close()
                self.assertEqual(teardown['status'], 'PASS')
                self.assertFalse(teardown['worker_alive'])
                self.assertFalse(teardown['observer_remaining'])
                if case not in ('normal_fast','slow_valid'):
                    self.assertTrue(results.empty())
                    self.assertFalse(exchange.receive(self.result(exchange, request)))
                    self.assertEqual(exchange.diagnostics[-1]['event'], 'LATE_RESULT')
                REPORTS.append(dict(scope='LOCAL_REHEARSAL_SYNTHETIC_CAPTURE', case=case,
                    timing=exchange.durations(), trace=exchange.trace, teardown=teardown,
                    navigation_transactions=0, navigation_primitives=0,
                    note_dispatches=0, script_dispatches=0))

    def test_bounded_teardown_failure_does_not_skip_other_cleanup(self):
        release, entered = threading.Event(), threading.Event()
        def broken(worker, request):
            entered.set()
            release.wait(.5)
            worker.check()
        worker = CooperativeObserver(broken, lambda worker,result:None)
        worker.start()
        worker.requests.put({})
        self.assertTrue(entered.wait(.1))
        try:
            teardown = worker.close(timeout=.01)
            self.assertEqual(teardown['status'], 'THREAD_TEARDOWN_FAILED')
            cleanup = []
            for name in ('callback_restore','observer_remove','port_check','baseline_check'):
                cleanup.append(name)
            self.assertEqual(len(cleanup), 4)
        finally:
            release.set()
            self.assertEqual(worker.close()['status'], 'PASS')
        REPORTS.append(dict(scope='LOCAL_REHEARSAL', case='thread_fails_to_exit',
            teardown=teardown, other_cleanup_attempted=cleanup,
            navigation_transactions=0, navigation_primitives=0, note_dispatches=0, script_dispatches=0))

    def test_local_mailbox_timeout_cancel_and_late_result(self):
        async def trial():
            exchange, request = self.begin(delivery_timeout=.02)
            mailbox = FileMailbox(self.directory.name, exchange)
            with self.assertRaises(TimeoutError):
                await mailbox.request(dict(request=request))
            self.assertTrue((Path(self.directory.name)/(request['request_id']+'.cancel.json')).is_file())
            result = self.result(exchange, request)
            mailbox.write(request['request_id']+'.result.json', result)
            self.assertFalse(exchange.receive(result))
            mailbox.quarantine()
            self.assertEqual(exchange.diagnostics[-1]['event'], 'LATE_OR_DUPLICATE_RESULT')
            self.assertFalse(any(t.name.startswith('asyncio_') for t in threading.enumerate()))
        asyncio.run(trial())

    def test_actual_preparer_local_capture_bracket(self):
        from dawloop.adapters.fl_target_preparation import ControllerTargetPreparer
        async def trial():
            exchange = ObservationExchange()
            mailbox = FileMailbox(self.directory.name, exchange)
            session = dict(session='session', bridge_epoch='epoch', host_generation='host', target_id='page')
            target = dict(expected_pattern_index=1, expected_pattern_name='样式 1',
                          expected_channel_index=0, expected_channel_name='808 Kick')
            reads = []
            latest = None
            class Identity:
                async def read_identity(inner):
                    nonlocal latest
                    if reads:
                        exchange.confirm_started()
                    value = dict(source='fl_studio_midi_scripting', controller_session='controller',
                        project_generation='project', project_loading=False, pattern_number=1,
                        pattern_name='样式 1', channel_index=0, channel_name='808 Kick',
                        selected_channels=[0], channel_index_type='global', ppq=96,
                        fl_studio_version='OFFLINE', observed_at=datetime.now(timezone.utc).isoformat())
                    latest = stamp(exchange.domain)
                    reads.append(value)
                    if len(reads) == 2:
                        exchange.confirm_complete()
                    return value
            def capture(worker, request):
                t3 = stamp(worker.domain)
                worker.wait(.002)
                t4 = stamp(worker.domain)
                evidence = dict(visible=True, confirmed=True, observer='agent_visual_review',
                    evidence_ref='OFFLINE_SYNTHETIC_CAPTURE', pattern_number=1, channel_name='808 Kick',
                    window_pid=10, window_hwnd=20, session=session,
                    capture_started_unix=t3['wall'], observed_unix=t4['wall'],
                    capture_completed_unix=t4['wall'], captured_at=t4,
                    capture_artifact=str(self.artifact),
                    capture_sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest())
                return evidence, dict(T3=t3,T4=t4)
            def publish(worker, result):
                worker.check()
                mailbox.write(result['request']['request_id']+'.result.json', result)
            worker = CooperativeObserver(capture, publish)
            worker.start()
            async def ui(target, session):
                request = exchange.begin(BINDING, latest)
                worker.requests.put(request, timeout=.01)
                result = await mailbox.request(dict(request=request))
                return exchange.receive(result)
            async def forbidden(*args):
                raise AssertionError('禁止导航')
            preparer = ControllerTargetPreparer(Identity(), forbidden, ui,
                                                window_identity=dict(pid=10,hwnd=20))
            try:
                evidence = await preparer.observe(target,session,('controller','project'))
                self.assertEqual(evidence['binding']['level'],'OBSERVATIONAL')
                self.assertFalse(evidence['binding']['producer_target_verified'])
                self.assertEqual(set(exchange.trace), {'T'+str(i) for i in range(9)})
            finally:
                exchange.terminate('STOPPED')
                teardown = worker.close()
            self.assertEqual(teardown['status'],'PASS')
            REPORTS.append(dict(scope='LOCAL_REHEARSAL_SYNTHETIC_CAPTURE',
                case='actual_preparer_capture_bracket', trace=exchange.trace,
                timing=exchange.durations(), teardown=teardown,
                navigation_transactions=0,navigation_primitives=0,note_dispatches=0,script_dispatches=0))
        asyncio.run(trial())

    def test_recovery_attempted_when_callback_restore_fails(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_target_navigation_handoff import SimulatedInputs
        inputs = SimulatedInputs('initial_a')
        recovered = []
        def failed_close():
            raise RuntimeError('CALLBACK_RESTORE_FAILED')
        original = inputs.recover
        async def recovery():
            recovered.append(True)
            return await original()
        inputs.close = failed_close
        inputs.recover = recovery
        result = asyncio.run(inputs.handoff().run())
        self.assertEqual(recovered,[True])
        self.assertFalse(result['callbacks_restored'])
        self.assertEqual(result['navigation_transactions'],0)
        self.assertEqual(result['navigation_primitives'],0)

    def test_local_timing_distribution(self):
        for role, delay in (('fast',.001),('slow',.015)):
            samples = []
            for _ in range(20):
                exchange, request = self.begin()
                results = queue.Queue()
                def capture(worker, request):
                    t3 = stamp(worker.domain)
                    worker.wait(delay)
                    t4 = stamp(worker.domain)
                    return dict(captured_at=t4,capture_completed_unix=t4['wall'],
                        capture_artifact=str(self.artifact),
                        capture_sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest()), dict(T3=t3,T4=t4)
                worker = CooperativeObserver(capture,lambda worker,value:worker.put(results,value))
                worker.start()
                try:
                    worker.requests.put(request,timeout=.1)
                    exchange.receive(results.get(timeout=.2))
                    exchange.confirm_started()
                    exchange.confirm_complete()
                    samples.append(exchange.durations())
                finally:
                    self.assertEqual(worker.close()['status'],'PASS')
            distribution = {}
            for field in samples[0]:
                values = sorted(row[field] for row in samples if row[field] is not None)
                distribution[field] = (dict(min=min(values),median=statistics.median(values),
                    p95=values[int(.95*(len(values)-1))],max=max(values)) if values else None)
            REPORTS.append(dict(scope='LOCAL_REHEARSAL_SYNTHETIC_CAPTURE',case='distribution_'+role,
                sample_count=20, distribution=distribution, navigation_transactions=0,
                navigation_primitives=0,note_dispatches=0,script_dispatches=0))

    def test_cancellation_during_blocked_publish(self):
        exchange,request = self.begin()
        full = queue.Queue(maxsize=1)
        full.put('occupied')
        publishing = threading.Event()
        def capture(worker,request):
            result = self.result(exchange,request,worker.domain)
            return result['evidence'], {k:result['trace'][k] for k in ('T3','T4')}
        def publish(worker,value):
            publishing.set()
            worker.put(full,value)
        worker = CooperativeObserver(capture,publish)
        worker.start()
        worker.requests.put(request,timeout=.1)
        self.assertTrue(publishing.wait(.1))
        exchange.terminate('ABORT')
        self.assertEqual(worker.close()['status'],'PASS')
        self.assertEqual(full.get(),'occupied')
        self.assertTrue(full.empty())


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HandoffFreshnessTests))
    if '--evidence' in sys.argv and result.wasSuccessful():
        path = Path(__file__).resolve().parents[1]/'evidence/runtime_v2/target_preparation/handoff_rehearsal.json'
        path.write_text(json.dumps(dict(cases=REPORTS, scope='OFFLINE_AND_LOCAL_ONLY',
            host_started=False, handoff_freshness_ready='LOCAL_ONLY', teardown='PASS',
            live_navigation_validation='NOT_REACHED'), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
