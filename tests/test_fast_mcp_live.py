import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from uuid import uuid4

from dawloop.adapters.gopher_native.write_backend import CERTIFIED_VERSION
from dawloop.runtime import BackendError
from dawloop.runtime.run_manager import RunContext, RunManager
from research.fast_mcp_live import LiveWiring, ObservationClient
from research.practical_music_slice import TARGET
from test_fast_music import Host, inputs
from test_target_preparation import identity


class Controller:
    def __init__(self):
        self.changes = {}
        self.navigation = 0

    async def read_identity(self):
        await asyncio.sleep(.001)
        value = identity(time.time(), controller_build_id='offline-build', controller_session_id='controller',
                         project_title='offline-fixture')
        value.update(self.changes)
        await asyncio.sleep(.001)
        return value

    async def navigate_once(self, target, binding, operation_id):
        self.navigation += 1
        self.asserted_target = copy.deepcopy(target)


class ConnectedHost(Host):
    def __init__(self):
        super().__init__()
        self.socket = None
        self.host_generation = 'generation'
        self.target_id = 'target'
        self.context_id = 1
        self.release = threading.Event()
        self.catalog_calls = 0
        self.catalog_error = None
        self.bridge_state = dict(epoch='epoch', attached=True, poisoned=False,
                                 unacknowledged=False, write_attempted=False)

    def _evaluate(self, expression):
        return copy.deepcopy(self.bridge_state)

    def connect(self):
        self.socket = object()
        return super().connect()

    def invoke(self, kind):
        self.catalog_calls += 1
        if self.catalog_error:
            raise BackendError(self.catalog_error)
        return super().invoke(kind)

    def invoke_batch(self, *args):
        self.calls += 1
        if not self.release.wait(3):
            raise BackendError('EXECUTION_TIMEOUT', dispatched=True)
        return dict(ok=True, payload={'jsonrpc': '2.0', 'id': '1', 'result': {
            'isError': False, 'content': [{'type': 'text', 'text': 'Script executed without errors'}]}})

    def close(self):
        self.socket = None


class Observer:
    def __init__(self):
        self.ready = True
        self.changes = {}
        self.calls = 0

    def readiness(self):
        return dict(ready=self.ready, request_generation='observer' if self.ready else None)

    async def observe(self, context, stage, target, binding):
        self.calls += 1
        review = dict(region=[1536, 3072], active_region_empty=True, preview_absent=True,
                      human_available=True, preview_closed=True, phrase_visible=True)
        review.update(self.changes)
        return dict(visible=True, confirmed=True, observer='human', pattern_number=1,
            channel_name='808 Kick', window_pid=10, window_hwnd=20, session=binding,
            observed_unix=time.time(), evidence_ref='offline-reviewed-frame', review=review)


class LiveWiringTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings = self.root / 'settings'
        self.settings.mkdir()
        self.config = dict(pid=10, hwnd=20, window_class='offline-window', endpoint='http://127.0.0.1:9222',
            port_name='OFFLINE', fixture=str(self.root / 'fixture.flp'),
            fixture_sha256='a2f9922d6b8cdc7f7627428d0d7072ed7dcab0a4f666fef42145c0c6e91b006f',
            fixture_size=53498, project_title='offline-fixture', controller_session_id='controller',
            project_generation='project', observer_dir=str(self.root / 'observer'), experimental_authorized=True)
        self.controller, self.host, self.observer = Controller(), ConnectedHost(), Observer()
        self.preview = True
        self.target_page = {'id': 'target'}
        self.wiring = LiveWiring(self.config, settings_dir=self.settings, expected_build='offline-build',
            controller=self.controller, transport=self.host, observer=self.observer,
            window_probe=lambda pid, hwnd: {'hwnd': 20} if self.preview and self.host.calls else None,
            targets=lambda: self.target_page)
        self.wiring.fixture_valid = lambda: True
        target, self.plan = inputs()
        target['pattern_name'] = TARGET['expected_pattern_name']
        self.target = target
        self.manager = RunManager(self.root / 'runs', settings_dir=self.settings, expected_build='offline-build',
            runtime_factory=self.wiring.factory, readiness=self.wiring.readiness,
            experimental_authorized=True, allowed_target=target)

    async def asyncTearDown(self):
        self.host.release.set()
        await self.manager.close()
        await self.wiring.close()
        self.temp.cleanup()

    async def waiting(self, run_id, expected):
        async with asyncio.timeout(3):
            while True:
                state = await self.manager.status(run_id)
                if state['state'] == expected:
                    return state
                if state['terminal']:
                    self.fail((self.manager.root / run_id / 'fast_music_result.json').read_text(encoding='utf-8'))
                await asyncio.sleep(.01)

    async def test_actual_factory_runtime_target_preparer_report_claim_and_completion(self):
        from fastmcp import Client
        from dawloop.fast_mcp_server import create_server
        async with Client(create_server(self.manager, cleanup=self.wiring.close)) as client:
            self.assertEqual({tool.name for tool in await client.list_tools()},
                             {'fast_write_music', 'status', 'submit_human_report'})
            handle = (await client.call_tool('fast_write_music', dict(
                operation_id='real-wiring-offline', target=self.target, musical_plan=self.plan))).data
            await self.waiting(handle['run_id'], 'WAITING_FOR_HUMAN_ACCEPT')
            connects = self.host.connects
            for _ in range(3):
                status = (await client.call_tool('status', {'run_id': handle['run_id']})).data
                self.assertEqual(status['preview_window'], {'hwnd': 20})
            self.assertEqual(self.host.connects, connects)
            self.assertEqual(self.host.catalog_calls, 2)
            report = dict(run_id=handle['run_id'], session_id=handle['session_id'], report_id='human-one',
                reported_at=datetime.now(timezone.utc).isoformat(), event_type='ACCEPTED', source='HUMAN',
                evidence_ref='offline-direct-user-report', preview_window={'hwnd': 20}, preview_review_confirmed=True)
            self.assertEqual((await client.call_tool('submit_human_report', {'report': report})).data['delivery'],
                             'PENDING')
            self.preview = False
            self.host.release.set()
            await self.waiting(handle['run_id'], 'COMPLETED_UNVERIFIED')
            state = (await client.call_tool('status', {'run_id': handle['run_id']})).data
            self.assertEqual(state['human_reports'][0]['delivery'], 'REALTIME')
            self.assertEqual(self.controller.navigation, 1)
            self.assertEqual(self.observer.calls, 3)
            self.assertEqual(self.host.calls, 1)
            self.assertEqual(state['run_result']['completion'], 'CONFIRMED')
            self.assertEqual(state['run_result']['exact_set'], 'NOT_VERIFIED')

    async def test_initialized_page_missing_host_object_is_not_ready(self):
        self.host.catalog_error = 'HOST_UNAVAILABLE'
        status = await self.manager.status()
        self.assertEqual(status['runtime'], 'NOT_READY')
        self.assertTrue(status['gopher']['bootstrap_required'])
        self.assertIn('GOPHER_BOOTSTRAP_REQUIRED', status['reasons'])
        self.assertEqual(self.host.calls, 0)

    async def test_gopher_page_not_created_never_connects(self):
        def missing():
            raise BackendError('HOST_NOT_FOUND')
        self.wiring.targets = missing
        status = await self.manager.status()
        self.assertEqual(status['runtime'], 'NOT_READY')
        self.assertIn('GOPHER_BOOTSTRAP_REQUIRED', status['reasons'])
        self.assertEqual(self.host.connects, 0)

    async def test_reviewer_not_ready_blocks_create_with_all_other_components_live(self):
        self.observer.ready = False
        with self.assertRaisesRegex(ValueError, 'OBSERVATION_REVIEW_NOT_READY'):
            await self.manager.create('cannot-write', self.target, self.plan)
        self.assertEqual(self.controller.navigation, 0)
        self.assertEqual(self.host.calls, 0)

    async def test_loaded_build_session_project_and_fixture_mismatch_are_not_ready(self):
        for changes in ({'controller_build_id': 'other'}, {'controller_session_id': 'other'},
                        {'project_generation': 'other'}, {'project_loading': True},
                        {'ppq': 480},
                        {'fl_studio_version': 'unapproved-version'}):
            self.controller.changes = changes
            self.assertEqual((await self.manager.status())['runtime'], 'NOT_READY')
        self.controller.changes = {}
        self.wiring.fixture_valid = lambda: False
        self.assertEqual((await self.manager.status())['runtime'], 'NOT_READY')
        self.assertEqual(self.host.calls, 0)

    async def test_optional_description_title_never_participates_in_identity_binding(self):
        first = await self.manager.components()
        for title, status in (('', 'EMPTY_ACCEPTED'), (None, 'UNKNOWN_ACCEPTED'),
                              ('different-description', 'DESCRIPTION_ONLY')):
            self.wiring.config['project_title'] = title
            LiveWiring(self.wiring.config, settings_dir=self.settings, expected_build='offline-build')
            self.controller.changes = {'project_title': title}
            current = await self.manager.components()
            self.assertEqual(current['runtime'], 'FAST_READY')
            self.assertEqual(current['controller']['project_title'], title)
            self.assertEqual(current['controller']['project_title_status'], status)
            self.assertEqual(self.manager._binding(first), self.manager._binding(current))
        for title in (True, 1, [], {}):
            with self.assertRaisesRegex(ValueError, 'PROJECT_TITLE_TYPE_INVALID'):
                LiveWiring(dict(self.config, project_title=title), settings_dir=self.settings,
                           expected_build='offline-build')
            self.controller.changes = {'project_title': title}
            self.assertEqual((await self.manager.status())['runtime'], 'NOT_READY')
        self.controller.changes = {'project_title': '', 'project_generation': 'different-project'}
        self.assertEqual((await self.manager.status())['runtime'], 'NOT_READY')
        self.controller.changes = {'project_title': ''}
        self.wiring.fixture_valid = lambda: False
        self.assertEqual((await self.manager.status())['runtime'], 'NOT_READY')
        self.assertEqual(self.host.calls, 0)
        self.assertEqual(self.controller.navigation, 0)

    async def test_page_change_poison_and_prior_unknown_are_not_ready(self):
        self.assertEqual((await self.manager.status())['runtime'], 'FAST_READY')
        self.target_page = {'id': 'different'}
        self.assertEqual((await self.manager.status())['runtime'], 'NOT_READY')
        self.target_page = {'id': 'target'}
        self.host.poisoned_epoch = 'epoch'
        self.assertEqual((await self.manager.status())['runtime'], 'NOT_READY')
        self.host.poisoned_epoch = None
        for changes in ({'unacknowledged': True}, {'attached': False}, {'write_attempted': True}):
            before = copy.deepcopy(self.host.bridge_state)
            self.host.bridge_state.update(changes)
            self.assertEqual((await self.manager.status())['runtime'], 'NOT_READY')
            self.host.bridge_state = before
        with self.manager._db() as db:
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,1,NULL)',
                ('prior', 'prior', 'prior', 'prior', 'STOPPED_AFTER_DISPATCH_UNKNOWN'))
        status = await self.manager.status()
        self.assertEqual(status['runtime'], 'NOT_READY')
        self.assertTrue(status['dispatch']['unresolved_prior_dispatch'])
        self.assertIn('UNRESOLVED_PRIOR_DISPATCH', status['reasons'])

    async def test_target_review_cannot_substitute_capture_for_empty_region_confirmation(self):
        self.observer.changes['active_region_empty'] = False
        handle = await self.manager.create('unsafe-region', self.target, self.plan)
        state = await self.waiting(handle['run_id'], 'STOPPED_BEFORE_DISPATCH')
        self.assertEqual(self.controller.navigation, 1)
        self.assertEqual(self.host.calls, 0)
        self.assertNotEqual(state['run_result']['target_preparation'], 'CONFIRMED_OBSERVATIONAL')

    async def test_normal_project_configuration_is_rejected(self):
        for changes in ({'experimental_authorized': False}, {'fixture_sha256': '0' * 64},
                        {'observer_dir': 'relative'}):
            with self.assertRaises(ValueError):
                LiveWiring(dict(self.config, **changes), settings_dir=self.settings, expected_build='offline-build')

    @unittest.skipUnless(shutil.which('node'), '需要已有Node运行时')
    async def test_real_independent_node_capture_file_delivery_and_python_binding(self):
        directory = self.root / 'external-observer'
        worker = Path(__file__).resolve().parent / 'native_fixtures' / 'fast_observer_worker.mjs'
        process = subprocess.Popen([shutil.which('node'), str(worker), str(directory)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8')
        try:
            line = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), 3)
            self.assertEqual(line.strip(), 'READY')
            observer = ObservationClient(directory, window_identity={'pid': 10, 'hwnd': 20},
                process_alive=lambda pid: pid == process.pid and process.poll() is None)
            state = observer.readiness()
            self.assertTrue(state['ready'])
            folder = self.root / 'observation-run'
            folder.mkdir()
            context = RunContext('read-only-offline', uuid4().hex, uuid4().hex, folder,
                folder, self.settings, 'offline-build', {'observation': state})
            receipt = await observer.observe(context, 'TARGET', TARGET, {'native': 'offline'})
            self.assertTrue(receipt['confirmed'])
            self.assertEqual(receipt['channel_name'], '808 Kick')
            self.assertEqual(receipt['window_hwnd'], 20)
            public = json.loads((folder / receipt['evidence_ref']).read_text(encoding='utf-8'))
            self.assertNotIn('artifact', public)
            self.assertLessEqual(public['capture']['capture_started_at']['monotonic_ms'],
                                 public['capture']['capture_completed_at']['monotonic_ms'])
            wrong = dict(TARGET, expected_channel_name='808 Clap')
            with self.assertRaisesRegex(ValueError, 'PIANO_ROLL_TARGET_UNCONFIRMED'):
                await observer.observe(context, 'TARGET', wrong, {'native': 'offline'})
        finally:
            output, error = await asyncio.to_thread(process.communicate, 'STOP\n', timeout=3)
            self.assertEqual(process.returncode, 0, error)
            self.assertEqual(json.loads(output.strip())['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
