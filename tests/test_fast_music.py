import asyncio
import copy
import json
import tempfile
import time
import unittest

from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from dawloop.runtime import BackendError, NativeWriteJournal
from dawloop.runtime.fast_music import FastMusicRuntime
from research.practical_music_slice import TARGET, operation_plan
from test_native_write_runtime import Transport, Target


def inputs():
    old = operation_plan()
    return dict(pattern_index=TARGET['expected_pattern_index'], pattern_name='甲',
        channel_global_index=0, expected_channel_name='808 Kick'), dict(
        ppq_context=dict(ppq=96, time_unit='ticks', velocity_unit='normalized_0_1'),
        notes=[dict(pitch=n['number'], start=n['time'], length=n['length'], velocity=n['velocity'])
               for n in old.parameters['notes']])


class Host(Transport):
    def __init__(self, error=None, payload=None):
        super().__init__(error)
        self.payload = payload
        self.connects = 0

    def connect(self):
        self.connects += 1
        return super().connect()

    def invoke_batch(self, *args):
        super().invoke_batch(*args)
        return dict(ok=True, payload=self.payload if self.payload is not None else {
            'jsonrpc': '2.0', 'id': '1', 'result': {'isError': False,
                'content': [{'type': 'text', 'text': 'Script executed without errors'}]}})


class Human:
    def __init__(self, fail=None, actor='human'):
        self.fail = fail
        self.actor = actor

    async def wait_preview(self, operation_id):
        await asyncio.sleep(0)
        return dict(operation_id=operation_id, observed=True, host_preview_present=True,
                    evidence_ref='offline-preview')

    async def wait_accept(self, operation_id):
        if self.fail:
            raise ValueError(self.fail)
        return dict(operation_id=operation_id, accepted=True, accept_actor=self.actor,
                    evidence_ref='offline-human-report')

    async def wait_application(self, operation_id):
        return dict(operation_id=operation_id, observed=True, evidence_ref='offline-application')


class FastMusicTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.host = Host()
        self.human = Human()
        self.target = Target()
        self.backend = GopherNativeWriteBackend(enabled=True, transport=self.host,
            target_preparer=self.target, interaction=self.human,
            journal=NativeWriteJournal(self.directory.name), disposable_guard=lambda: True)
        self.runtime = FastMusicRuntime(self.backend)

    async def execute(self, **kwargs):
        return await self.runtime.execute_fast_music_plan(*inputs(), operation_id='music-1',
            experimental_authorized=True, **kwargs)

    async def test_actual_backend_renderer_journal_decoder_and_public_result(self):
        events = []
        result = await self.execute(on_event=events.append)
        self.assertEqual(result.state, 'COMPLETED_UNVERIFIED')
        self.assertEqual((result.human_accept, result.application, result.completion),
                         ('REPORTED', 'OBSERVED', 'CONFIRMED'))
        self.assertEqual(result.target_preparation, 'CONFIRMED_OBSERVATIONAL')
        self.assertEqual(result.producer_target_binding, 'NOT_VERIFIED')
        self.assertEqual(result.exact_set, 'NOT_VERIFIED')
        self.assertEqual([e['state'] for e in events], ['READY_FOR_HUMAN_ACCEPT'])
        self.assertEqual(self.host.calls, 1)
        self.assertIs(self.backend.interaction, self.human)
        self.assertIsNone(self.backend.session)
        json.dumps(result.to_dict())

    async def test_invalid_input_rejected_before_discovery_or_navigation(self):
        target, plan = inputs()
        variants = [(dict(target, channel_global_index=True), plan),
            (dict(target, source='arbitrary'), plan),
            (target, dict(plan, notes=plan['notes'] * 2)),
            (target, dict(plan, notes=plan['notes'][:15])),
            (target, dict(plan, ppq_context=dict(ppq=192, time_unit='ticks', velocity_unit='normalized_0_1'))),
            (target, dict(plan, ppq_context=dict(ppq=96, time_unit='beats', velocity_unit='normalized_0_1')))]
        bad = copy.deepcopy(plan)
        bad['notes'][0]['velocity'] = float('nan')
        variants.append((target, bad))
        bad = copy.deepcopy(plan)
        bad['notes'][0]['start'] = 3072
        variants.append((target, bad))
        for target_value, plan_value in variants:
            with self.subTest(target=target_value):
                result = await self.runtime.execute_fast_music_plan(target_value, plan_value,
                    operation_id='invalid', experimental_authorized=True)
                self.assertEqual(result.state, 'STOPPED_BEFORE_DISPATCH')
        self.assertEqual(self.host.connects, 0)
        self.assertEqual(self.host.calls, 0)

    async def test_default_authorization_and_auto_accept_rejected(self):
        result = await self.runtime.execute_fast_music_plan(*inputs(), operation_id='no-auth')
        self.assertEqual(result.error_code, 'EXPERIMENTAL_AUTHORIZATION_REQUIRED')
        result = await self.execute(acceptance_mode='auto')
        self.assertEqual(result.error_code, 'HUMAN_ACCEPT_ONLY')
        self.assertEqual(self.host.connects, 0)

    async def test_policy_retry_fallback_and_four_note_detector_rejected(self):
        for field in ('retry', 'fallback_after_dispatch', 'max_notes'):
            policy = dict(add_only=True, max_notes=16, retry=0, fallback_after_dispatch=0)
            policy[field] = 1
            result = await self.execute(policy=policy)
            self.assertEqual(result.error_code, 'CERTIFIED_FAST_POLICY_REQUIRED')
        self.human.local_preview = True
        result = await self.execute()
        self.assertEqual(result.error_code, 'HUMAN_PREVIEW_INTERACTION_REQUIRED')
        self.assertEqual(self.host.connects, 0)

    async def test_target_mismatch_stops_before_dispatch(self):
        self.target.changed = True
        result = await self.execute()
        self.assertEqual(result.state, 'STOPPED_BEFORE_DISPATCH')
        self.assertEqual(self.host.calls, 0)

    async def test_timeout_consumes_single_dispatch_and_duplicate_does_not_navigate(self):
        self.host.error = 'EXECUTION_TIMEOUT'
        result = await self.execute()
        self.assertEqual(result.state, 'STOPPED_AFTER_DISPATCH_UNKNOWN')
        self.assertEqual(result.completion, 'UNKNOWN')
        self.assertEqual(result.dispatch, 'DISPATCHED')
        duplicate = await self.execute()
        self.assertEqual(duplicate.error_code, 'OPERATION_ALREADY_ATTEMPTED')
        self.assertEqual(duplicate.dispatch, 'NOT_DISPATCHED')
        self.assertEqual(self.host.calls, 1)
        self.assertEqual(self.host.connects, 1)

    async def test_host_completion_does_not_hide_human_event_timeout(self):
        self.human.fail = 'HUMAN_EVENT_TIMEOUT'
        result = await self.execute()
        self.assertEqual(result.human_accept, 'TIMEOUT')
        self.assertEqual(result.completion, 'CONFIRMED')
        self.assertEqual(result.application, 'NOT_OBSERVED')
        self.assertEqual(result.state, 'STOPPED_AFTER_DISPATCH_UNKNOWN')
        self.assertEqual(result.error_code, 'HUMAN_EVENT_TIMEOUT')

    async def test_agent_click_cannot_become_human_report(self):
        self.human.actor = 'agent_computer_use'
        result = await self.execute()
        self.assertEqual(result.human_accept, 'REJECTED')
        self.assertNotEqual(result.state, 'COMPLETED_UNVERIFIED')

    async def test_empty_completion_payload_cannot_become_complete(self):
        self.host.payload = {'result': {'isError': False, 'content': []}}
        result = await self.execute()
        self.assertEqual(result.completion, 'UNKNOWN')
        self.assertEqual(result.state, 'STOPPED_AFTER_DISPATCH_UNKNOWN')

    async def test_notification_failure_does_not_repeat_dispatch(self):
        def fail(event):
            raise RuntimeError('offline-notifier')
        result = await self.execute(on_event=fail)
        self.assertEqual(result.evidence['notification_error'], 'RuntimeError')
        self.assertEqual(self.host.calls, 1)
        self.assertEqual(result.state, 'COMPLETED_UNVERIFIED')

    async def test_actual_controller_preparer_identity_ui_bracket(self):
        from dawloop.adapters.fl_target_preparation import ControllerTargetPreparer
        from test_target_preparation import identity
        counts = dict(navigation=0, observation=0)
        captured_clock = time.time() - 1

        class Reader:
            calls = 0

            async def read_identity(self):
                self.calls += 1
                value = identity(captured_clock + self.calls * 0.01)
                value['pattern_name'] = '甲'
                return value

        reader = Reader()

        async def navigate(target, session):
            counts['navigation'] += 1

        async def observe(target, session):
            counts['observation'] += 1
            return dict(visible=True, confirmed=True, observer='agent_visual_review',
                evidence_ref='offline-current-frame', pattern_number=1, channel_name='808 Kick',
                window_pid=10, window_hwnd=20, session=dict(session),
                observed_unix=captured_clock + reader.calls * 0.01 + 0.005)

        self.backend.target_preparer = ControllerTargetPreparer(reader, navigate, observe,
            window_identity=dict(pid=10, hwnd=20))
        result = await self.execute()
        self.assertEqual(result.state, 'COMPLETED_UNVERIFIED', result.evidence)
        self.assertEqual(counts, dict(navigation=1, observation=2))
        self.assertEqual(self.host.calls, 1)
