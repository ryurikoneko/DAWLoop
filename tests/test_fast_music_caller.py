import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime_v2_navigated_music as caller
import test_target_navigation_contract as support
from test_fast_music import Host
from dawloop.adapters.fl_target_navigation import ControllerTargetNavigator
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from dawloop.runtime import NativeWriteJournal
from dawloop.runtime.fast_music import _plan
from dawloop.runtime.human_reports import HumanReportStore
from research.practical_music_navigation import NavigatedMusicPreparation


class CallerTests(unittest.IsolatedAsyncioTestCase):
    async def test_human_timeout_leaves_late_store_without_resuming(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HumanReportStore.create(directory, run_id='run', session_id='session',
                operation_id=caller.OPERATION)
            store.bind_preview({'hwnd': 20})
            with patch.object(caller.legacy, 'OPERATION_ID', caller.OPERATION):
                interaction = caller.FastHumanInteraction(None, None, report_store=store)
            now = [0.0]
            interaction.clock = lambda: now[0]
            interaction.event_wait_seconds = 1
            interaction.completed_response = lambda: None

            async def advance(seconds):
                now[0] += seconds
            interaction.sleep = advance
            with self.assertRaisesRegex(ValueError, 'HUMAN_EVENT_TIMEOUT'):
                await interaction.event('accept')
            report = dict(run_id='run', session_id='session', report_id='late',
                reported_at='2026-10-05T12:00:00+08:00', event_type='ACCEPTED', source='HUMAN',
                evidence_ref='offline-late', preview_window={'hwnd': 20}, preview_review_confirmed=True)
            self.assertEqual(store.submit(report)['delivery'], 'LATE')
            self.assertIsNone(store.claim_accept())
            self.assertEqual(interaction.events, [])

    async def test_cancellation_closes_report_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HumanReportStore.create(directory, run_id='run', session_id='session',
                operation_id=caller.OPERATION)
            store.bind_preview({'hwnd': 20})
            with patch.object(caller.legacy, 'OPERATION_ID', caller.OPERATION):
                interaction = caller.FastHumanInteraction(None, None, report_store=store)
            interaction.completed_response = lambda: None
            waiting = asyncio.Event()

            async def pause(seconds):
                waiting.set()
                await asyncio.Event().wait()
            interaction.sleep = pause
            task = asyncio.create_task(interaction.event('accept'))
            await asyncio.wait_for(waiting.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(store.snapshot()['phase'], 'ACCEPT_CLOSED')
            self.assertIsNone(store.claim_accept())

    def test_structured_inputs_render_identical_successful_source(self):
        target, plan = caller.fast_inputs()
        _, rendered = _plan(target, plan, caller.OPERATION,
            dict(add_only=True, max_notes=16, retry=0, fallback_after_dispatch=0))
        history = caller.ROOT / 'tests/native_fixtures/practical_16_note'
        self.assertEqual(rendered.source, (history / 'rendered_source.py').read_bytes())
        self.assertEqual(rendered.sha256, json.loads(
            (history / 'summary.json').read_text(encoding='utf-8'))['source_hash'])

    async def test_actual_caller_navigation_and_human_receipt_lifecycle(self):
        harness = support.NavigationTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        harness.pattern, harness.selected = 2, {1}
        harness.module.ui.getVersion = lambda *a: 'Producer Edition v26.1.6 [build 5639]'
        navigator = ControllerTargetNavigator('offline-port', settings_dir=harness.root)
        context = dict(harness.session)
        context.pop('binding_kind', None)
        accepted = threading.Event()

        class Transport(Host):
            def invoke_batch(self, *args):
                if not accepted.wait(2):
                    raise AssertionError('离线人工回执未到达')
                return super().invoke_batch(*args)

        transport = Transport()
        native = transport.connect()
        observed = []

        async def observe(target, binding):
            observed.append(binding)
            # 模拟独立采样边界，避免低分辨率时钟把夹读顺序压成同一时刻。
            await asyncio.sleep(.01)
            result = dict(visible=True, confirmed=True, observer='agent_visual_review',
                evidence_ref='offline-current-frame', pattern_number=1, channel_name='808 Kick',
                window_pid=10, window_hwnd=20, session=binding, observed_unix=time.time())
            await asyncio.sleep(.01)
            return result

        preparation = NavigatedMusicPreparation(navigator, observe, controller_context=context,
            native_guard=lambda s: s == native, window_identity=dict(pid=10, hwnd=20))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            window = dict(hwnd=20)
            reports = HumanReportStore.create(root, run_id='offline-run', session_id='offline-session',
                operation_id=caller.OPERATION)
            for name, receipt in {
                'accept': dict(accepted=True, observer='human', accept_actor='human',
                    preview_review_confirmed=True, window=window),
                'application': dict(observed=True, observer='agent_visual_review',
                    preview_closed=True, phrase_visible=True)
            }.items():
                (root / (name + '.json')).write_text(json.dumps(dict(receipt,
                    operation_id=caller.OPERATION, evidence_ref='offline-' + name)), encoding='utf-8')
            backend = GopherNativeWriteBackend(enabled=True, transport=transport,
                target_preparer=preparation, journal=NativeWriteJournal(root / 'journal'),
                disposable_guard=lambda: True)
            class Human(caller.FastHumanInteraction):
                accepted_seen = False

                def preview_window(self):
                    return None if self.accepted_seen else window

                def read_receipt(self, name):
                    value = super().read_receipt(name)
                    if name == 'preview' and value is not None:
                        reports.submit(dict(run_id='offline-run', session_id='offline-session',
                            report_id='human-accept-1', reported_at='2026-10-05T12:00:00+08:00',
                            event_type='ACCEPTED', source='HUMAN', evidence_ref='offline-human-reply',
                            preview_window=window, preview_review_confirmed=True))
                    return value

                async def event(self, name, *, pending=False):
                    value = await super().event(name, pending=pending)
                    if name == 'accept':
                        self.accepted_seen = True
                        accepted.set()
                    return value

            with patch.object(caller.legacy, 'OUTPUT', root), \
                    patch.object(caller.legacy, 'EVENTS', root), \
                    patch.object(caller.legacy, 'OPERATION_ID', caller.OPERATION), \
                    patch.dict(sys.modules, {'mido': harness.midi,
                        'midi': types.SimpleNamespace(REC_Chan_PianoRoll=7, EE_PR=3)}):
                backend.interaction = Human(backend, preparation, report_store=reports)
                events = []
                result = await caller.execute_music_workflow(backend, on_event=events.append)
            self.assertEqual(result.state, 'COMPLETED_UNVERIFIED', result.to_dict())
            self.assertEqual(result.human_accept, 'REPORTED')
            (root/'fast_music_result.json').write_text(json.dumps(result.to_dict()), encoding='utf-8')
            reports.finalize((root/'fast_music_result.json').read_bytes())
            self.assertEqual(reports.snapshot()['human_reports'][0]['delivery'], 'REALTIME')
            self.assertEqual(result.producer_target_binding, 'NOT_VERIFIED')
            self.assertEqual(result.exact_set, 'NOT_VERIFIED')
            self.assertEqual(transport.calls, 1)
            timing = backend.interaction.timing()['application_delivery']
            self.assertIsNotNone(timing['coordinator_claimed_at'])
            self.assertIsNotNone(timing['application_confirmed_at'])
            self.assertEqual(timing['coordinator_claimed_at']['clock_domain'],
                timing['application_confirmed_at']['clock_domain'])
            self.assertLessEqual(timing['coordinator_claimed_at']['monotonic_ms'],
                timing['application_confirmed_at']['monotonic_ms'])
            self.assertEqual(len(observed), 2)
            self.assertEqual(harness.steps,
                ['select_pattern', 'select_channel_global', 'targeted_open_piano_roll'])
            self.assertEqual(len(events), 1)
            self.assertIsNone(backend.session)

    async def test_caller_calls_public_entrypoint_once_on_unknown(self):
        calls = []

        class Runtime:
            def __init__(self, backend):
                pass

            async def execute_fast_music_plan(self, target, plan, **kwargs):
                calls.append((target, plan, kwargs))
                return types.SimpleNamespace(state='STOPPED_AFTER_DISPATCH_UNKNOWN')

        with patch.object(caller, 'FastMusicRuntime', Runtime):
            result = await caller.execute_music_workflow(object())
        self.assertEqual(result.state, 'STOPPED_AFTER_DISPATCH_UNKNOWN')
        self.assertEqual(len(calls), 1)
        self.assertEqual(set(calls[0][1]), {'ppq_context', 'notes'})

    async def test_application_consumption_does_not_imply_confirmation(self):
        with patch.object(caller.legacy, 'OPERATION_ID', caller.OPERATION):
            interaction = caller.FastHumanInteraction(None, None)
        interaction.accept_receipt = {'accepted': True}
        receipt = dict(operation_id=caller.OPERATION, evidence_ref='offline-invalid',
            observer='agent_visual_review', observed=True, preview_closed=False, phrase_visible=True)
        interaction.read_event = lambda name: receipt
        with self.assertRaisesRegex(ValueError, 'APPLICATION_REVIEW_REQUIRED'):
            await interaction.wait_application(caller.OPERATION)
        self.assertIsNotNone(interaction.application_timing['coordinator_claimed_at'])
        self.assertIsNone(interaction.application_timing['application_confirmed_at'])

    def test_human_adapter_rejects_agent_or_wrong_window(self):
        interaction = caller.FastHumanInteraction(None, None)
        interaction.bound_window = {'hwnd': 1}
        receipt = dict(observer='human', accept_actor='human',
            preview_review_confirmed=True, window={'hwnd': 1})
        for change in ({'accept_actor': 'agent_computer_use'}, {'window': {'hwnd': 2}}):
            with patch.object(caller.legacy.LiveHumanInteraction, 'read_receipt',
                    return_value=dict(receipt, **change)):
                with self.assertRaisesRegex(ValueError, 'HUMAN_ACCEPT_RECEIPT_REQUIRED'):
                    interaction.read_receipt('accept')
