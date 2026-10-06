from datetime import datetime, timezone
import tempfile
import unittest

from dawloop.adapters.fl_target_preparation import ControllerTargetPreparer
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend, CERTIFIED_VERSION
from dawloop.runtime import BackendRouter, ExecutionStatus, NativeWriteJournal
from research.practical_music_slice import TARGET, operation_plan
from test_native_write_runtime import Transport, Interaction


SESSION = dict(session='epoch', bridge_epoch='epoch', host_generation='generation', target_id='target')


def identity(timestamp=100, **changes):
    return dict(source='fl_studio_midi_scripting', controller_session='controller',
        project_generation='project', project_loading=False, pattern_number=1, pattern_name='样式 1',
        channel_index=0, channel_name='808 Kick', selected_channels=[0], channel_index_type='global',
        ppq=96, fl_studio_version=CERTIFIED_VERSION,
        observed_at=datetime.fromtimestamp(timestamp, timezone.utc).isoformat(), **changes)


class Reader:
    def __init__(self):
        self.calls = 0
        self.changes = {}

    async def read_identity(self):
        self.calls += 1
        result = identity(100+self.calls)
        result.update(self.changes.get(self.calls, {}))
        return result


class PreparationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.reader = Reader()
        self.navigation_calls = 0
        self.ui_changes = {}
        self.navigation_error = None
        self.observations = 0

    async def navigate(self, target, session):
        self.navigation_calls += 1
        if self.navigation_error:
            raise self.navigation_error

    async def ui(self, target, session):
        self.observations += 1
        result = dict(visible=True, confirmed=True, observer='agent_visual_review',
            evidence_ref='本次完整卷帘截图', pattern_number=1, channel_name='808 Kick',
            window_pid=10, window_hwnd=20, session=dict(session),
            observed_unix=100+self.reader.calls+0.5)
        result.update(self.ui_changes)
        return result

    def preparer(self):
        return ControllerTargetPreparer(self.reader, self.navigate, self.ui,
            window_identity=dict(pid=10, hwnd=20), clock=lambda:110)

    async def test_prepare_then_confirm_never_navigates_twice(self):
        preparer = self.preparer()
        evidence = await preparer.prepare(TARGET, SESSION)
        await preparer.confirm(TARGET, SESSION)
        self.assertEqual(self.navigation_calls, 1)
        self.assertEqual(self.reader.calls, 5)
        self.assertEqual(self.observations, 2)
        self.assertEqual(evidence['binding']['level'], 'OBSERVATIONAL')
        self.assertFalse(evidence['binding']['producer_target_verified'])
        self.assertFalse(evidence['binding']['automation_live_certified'])

    async def test_navigation_can_change_selection_but_not_project(self):
        self.reader.changes[1] = dict(channel_index=1, channel_name='808 Clap', selected_channels=[1])
        await self.preparer().prepare(TARGET, SESSION)
        self.assertEqual(self.navigation_calls, 1)

    async def test_invalid_request_rejected_before_navigation(self):
        for target in (dict(TARGET, expected_pattern_index=True),
                       dict(TARGET, expected_channel_index=0.0),
                       dict(TARGET, expected_channel_name='')):
            with self.subTest(target=target), self.assertRaises(ValueError):
                await self.preparer().prepare(target, SESSION)
        self.assertEqual(self.navigation_calls, 0)
        self.assertEqual(self.reader.calls, 0)

    async def test_missing_host_binding_rejected(self):
        with self.assertRaisesRegex(ValueError, 'HOST_BINDING'):
            await self.preparer().prepare(TARGET, dict(SESSION, host_generation=''))
        self.assertEqual(self.navigation_calls, 0)

    async def test_navigation_failure_never_retries(self):
        self.navigation_error = RuntimeError('导航结果未知')
        preparer = self.preparer()
        with self.assertRaises(RuntimeError):
            await preparer.prepare(TARGET, SESSION)
        self.assertEqual(self.navigation_calls, 1)
        self.assertEqual(self.observations, 0)
        with self.assertRaisesRegex(ValueError, 'PREPARATION_REQUIRED'):
            await preparer.confirm(TARGET, SESSION)

    async def test_ambiguous_selection_rejected(self):
        self.reader.changes[2] = dict(selected_channels=[0, 1])
        with self.assertRaisesRegex(ValueError, 'AMBIGUOUS'):
            await self.preparer().prepare(TARGET, SESSION)

    async def test_target_change_during_observation_rejected(self):
        self.reader.changes[3] = dict(channel_index=1, channel_name='808 Clap', selected_channels=[1])
        with self.assertRaisesRegex(ValueError, 'MISMATCH'):
            await self.preparer().prepare(TARGET, SESSION)

    async def test_context_change_during_navigation_rejected(self):
        for field in ('controller_session', 'project_generation'):
            self.reader = Reader()
            self.reader.changes[2] = {field:'new'}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'CONTEXT_CHANGED'):
                await self.preparer().prepare(TARGET, SESSION)

    async def test_mismatched_visible_roll_window_and_session_rejected(self):
        for mutation in ({'channel_name':'808 Clap'}, {'window_pid':11}, {'window_hwnd':21},
                         {'session':dict(SESSION, bridge_epoch='new')}, {'confirmed':False}):
            self.reader = Reader()
            self.ui_changes = mutation
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'UNCONFIRMED'):
                await self.preparer().prepare(TARGET, SESSION)

    async def test_cached_ui_and_stale_identity_rejected(self):
        self.ui_changes = {'observed_unix':101.5}
        with self.assertRaisesRegex(ValueError, 'ORDER_UNPROVEN'):
            await self.preparer().prepare(TARGET, SESSION)
        self.reader = Reader()
        self.ui_changes = {}
        self.reader.changes[1] = {'observed_at':datetime.fromtimestamp(0, timezone.utc).isoformat()}
        with self.assertRaisesRegex(ValueError, 'STALE'):
            await self.preparer().prepare(TARGET, SESSION)

    async def test_confirm_failure_invalidates_preparation(self):
        preparer = self.preparer()
        await preparer.prepare(TARGET, SESSION)
        with self.assertRaisesRegex(ValueError, 'PREPARATION_REQUIRED'):
            await preparer.confirm(TARGET, dict(SESSION, host_generation='new'))
        with self.assertRaisesRegex(ValueError, 'PREPARATION_REQUIRED'):
            await preparer.confirm(TARGET, SESSION)
        self.assertEqual(self.navigation_calls, 1)

    async def test_returned_evidence_cannot_change_bound_target(self):
        preparer = self.preparer()
        evidence = await preparer.prepare(TARGET, SESSION)
        evidence['session']['host_generation'] = 'changed'
        evidence['identity']['pattern_number'] = 2
        self.assertEqual((await preparer.confirm(TARGET, SESSION))['identity']['pattern_number'], 1)

    async def test_runtime_reconfirm_failure_reaches_no_native_write(self):
        self.reader.changes[5] = dict(channel_index=1, channel_name='808 Clap', selected_channels=[1])
        transport = Transport()
        with tempfile.TemporaryDirectory() as directory:
            backend = GopherNativeWriteBackend(enabled=True, transport=transport,
                target_preparer=self.preparer(), interaction=Interaction(),
                journal=NativeWriteJournal(directory), disposable_guard=lambda:True)
            router = BackendRouter([backend])
            await router.discover()
            result = await router.execute(operation_plan())
            self.assertEqual(result.execution_status, ExecutionStatus.NOT_DISPATCHED)
            self.assertEqual(transport.calls, 0)
            self.assertEqual(self.navigation_calls, 1)
