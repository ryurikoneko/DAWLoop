import asyncio
import json
from pathlib import Path
import sys
import time
import types
import tempfile
import unittest
from unittest.mock import patch

from research.practical_music_navigation import NavigatedMusicPreparation
from research.practical_music_slice import TARGET, operation_plan, validate_slice
from dawloop.adapters.fl_target_navigation import ControllerTargetNavigator
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend

sys.path.insert(0, str(Path(__file__).parent))
import test_target_navigation_contract as harness_support


class IntegratedMusicTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_accept_after_thirty_seconds_requires_live_completion_path(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
        import runtime_v2_navigated_music as live
        async def check():
            return True
        interaction = live.Interaction(None,None)
        interaction.verify_target = check
        interaction.clock = lambda: 46
        interaction.bound_window = {'hwnd':1}
        interaction.preview = {}
        task = asyncio.create_task(asyncio.sleep(10))
        interaction.bind_dispatch_task(task)
        interaction.started = 0
        receipt = dict(operation_id=interaction.operation_id,evidence_ref='current-click',
            observer='agent_visual_review',accepted=True,accepted_within_window=False,
            accept_actor='agent_computer_use',preview_review_confirmed=True,
            click_completed=True,window={'hwnd':1})
        try:
            with patch.object(live.legacy.LiveHumanInteraction,'read_receipt',return_value=receipt):
                await interaction.wait_accept(interaction.operation_id)
            self.assertTrue(interaction.timing()['agent_accept_reported'])
            self.assertIsNone(interaction.timing()['accept_window_seconds'])
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        async def failed():
            return None,ValueError('timeout'),0,0
        task = asyncio.create_task(failed())
        await task
        interaction.bind_dispatch_task(task)
        with patch.object(live.legacy.LiveHumanInteraction,'read_receipt',return_value=receipt):
            with self.assertRaisesRegex(ValueError,'CALL_COMPLETION_UNKNOWN'):
                await interaction.wait_accept(interaction.operation_id)

    async def test_dispatched_restart_allows_recovery_but_not_another_prepare(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
        import runtime_v2_navigated_music as live
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'dispatch_intents').mkdir()
            journal = root/'dispatch_intents/operation.json'
            journal.write_bytes(b'{"dispatched":true}')
            (root/'restart_1').mkdir()
            (root/'restart_1/recovery.json').write_text(
                '{"host_closed":true,"debug_port_closed":true}',encoding='utf-8')
            (root/'restart_2').mkdir()
            fixture = root/'fixture.flp'
            fixture.write_bytes(b'unchanged fixture')
            argv = ['runtime_v2_navigated_music.py','recover','--restart-after-reboot',
                '--attempt','2','--settings-dir',str(root),'--expected-build','offline']
            with patch.object(live,'LEDGER_ROOT',root),patch.object(live,'OUTPUT',root),\
                    patch.object(live.legacy,'OUTPUT',root),patch.object(live.legacy,'EVENTS',root),\
                    patch.object(live.legacy,'baseline',return_value=fixture),\
                    patch.object(live.legacy,'process_state',return_value=dict(host_closed=True,debug_port_closed=True)),\
                    patch.object(sys,'argv',argv),patch.object(sys,'executable',str(live.ROOT/'.venv/Scripts/python.exe')):
                live.main()
                argv[1] = 'prepare'
                with self.assertRaisesRegex(ValueError,'OLD_DISPATCH_MAY_HAVE_OCCURRED'):
                    live.main()
            self.assertTrue(json.loads((root/'restart_2/recovery.json').read_text(encoding='utf-8'))['host_closed'])
            self.assertEqual(journal.read_bytes(),b'{"dispatched":true}')

    async def test_setup_calls_do_not_collide_with_runtime_identity_evidence(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
        import runtime_v2_navigated_music as live
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            setup_bytes = b'{"stage":"setup"}'
            (output/'call_1.json').write_bytes(setup_bytes)
            (output/'launch.json').write_text('{"pid":123}',encoding='utf-8')
            (output/'human_report_context.json').write_text(json.dumps(dict(run_id='offline-run',
                session_id='offline-session', operation_id=live.OPERATION)), encoding='utf-8')
            class Navigator:
                def __init__(self, *args, output, **kwargs):
                    self.output = output
                async def read_identity(self):
                    (self.output/'call_1.json').write_bytes(b'{"stage":"runtime"}')
                    raise ValueError('OFFLINE_STOP_BEFORE_NAVIGATION')
            args = types.SimpleNamespace(pid=123,settings_dir=output,expected_build='offline')
            with patch.object(live,'OUTPUT',output),patch.object(live.legacy,'OUTPUT',output),\
                    patch.object(live.legacy,'guard'),patch.object(live,'RecordedNavigator',Navigator):
                with self.assertRaisesRegex(ValueError,'OFFLINE_STOP_BEFORE_NAVIGATION'):
                    await live.run(args)
            self.assertEqual((output/'call_1.json').read_bytes(),setup_bytes)
            self.assertEqual((output/'runtime_controller_calls/call_1.json').read_bytes(),
                b'{"stage":"runtime"}')

    async def test_agent_click_receipt_is_not_human_acceptance(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
        import runtime_v2_navigated_music as live
        async def completed():
            return {'result':{'isError':False}},None,1,1
        async def check():
            return True
        interaction = live.Interaction(None,None)
        interaction.verify_target = check
        interaction.bound_window = {'hwnd':1}
        interaction.preview = {}
        task = asyncio.create_task(completed())
        await task
        interaction.bind_dispatch_task(task)
        receipt = dict(operation_id=interaction.operation_id,evidence_ref='current-click',
            observer='agent_visual_review',accepted=True,accepted_within_window=True,
            accept_actor='agent_computer_use',preview_review_confirmed=True,
            click_completed=True,window={'hwnd':1})
        with patch.object(live.legacy.LiveHumanInteraction,'read_receipt',return_value=receipt):
            await interaction.wait_accept(interaction.operation_id)
        self.assertTrue(interaction.timing()['agent_accept_reported'])
        self.assertFalse(interaction.timing()['human_accept_reported'])
        self.assertIsNone(interaction.timing()['human_accept_timestamp'])

    async def test_unreviewed_or_wrong_window_click_receipt_rejected(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
        import runtime_v2_navigated_music as live
        interaction = live.Interaction(None,None)
        interaction.bound_window = {'hwnd':1}
        receipt = dict(accept_actor='agent_computer_use',preview_review_confirmed=True,
            click_completed=True,window={'hwnd':1})
        for change in ({'accept_actor':'human'},{'preview_review_confirmed':False},
                {'click_completed':False},{'window':{'hwnd':2}}):
            with patch.object(live.legacy.LiveHumanInteraction,'read_receipt',
                    return_value=dict(receipt,**change)):
                with self.assertRaisesRegex(ValueError,'AGENT_ACCEPT_RECEIPT_REQUIRED'):
                    interaction.read_receipt('accept')
            self.assertFalse(interaction.timing()['agent_accept_reported'])

    async def test_actual_navigator_preparer_and_write_target_contract(self):
        harness = harness_support.NavigationTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        harness.pattern = 2
        harness.selected = {1}
        harness.module.ui.getVersion = lambda *args: 'Producer Edition v26.1.6 [build 5639]'
        navigator = ControllerTargetNavigator('offline-port', settings_dir=harness.root)
        context = dict(harness.session)
        context.pop('binding_kind', None)
        native = dict(session='native-session', bridge_epoch='epoch', host_generation='host', target_id='page')
        observed = []

        async def observe(target, binding):
            observed.append(dict(binding))
            # 合成观察必须与夹读分开采样，不能依赖宿主wall clock的亚毫秒分辨率。
            await asyncio.sleep(0.01)
            result = dict(visible=True, confirmed=True, observer='agent_visual_review',
                evidence_ref='offline/current-image', pattern_number=1, channel_name='808 Kick',
                window_pid=10, window_hwnd=20, session=binding, observed_unix=time.time())
            await asyncio.sleep(0.01)
            return result

        prep = NavigatedMusicPreparation(navigator, observe, controller_context=context,
            native_guard=lambda value: value == native, window_identity=dict(pid=10, hwnd=20))
        backend = GopherNativeWriteBackend(enabled=True, target_preparer=prep)
        backend.session = native
        plan = operation_plan('practical-kick-16-auto-navigation-session-1')
        with patch.dict(sys.modules, {'mido':harness.midi,
                'midi':types.SimpleNamespace(REC_Chan_PianoRoll=7,EE_PR=3)}):
            await backend.resolve_target(plan)
            evidence = await prep.confirm(TARGET, native)
            backend.check_target(plan, evidence)
            with self.assertRaisesRegex(RuntimeError, 'BUDGET_EXHAUSTED'):
                await prep.prepare(TARGET, native)
        self.assertEqual(harness.steps, ['select_pattern','select_channel_global','targeted_open_piano_roll'])
        self.assertEqual(evidence['session'], native)
        self.assertEqual(observed[0]['controller_build_id'], context['controller_build_id'])
        self.assertEqual(observed[0]['host_generation'], native['host_generation'])
        self.assertFalse(evidence['binding']['producer_target_verified'])
        self.assertEqual(validate_slice(plan, plan.metadata['operation_id']).note_count, 16)
        self.assertEqual(sum(x['action']=='dawloop.navigateTargetOnce' for x in harness.commands),1)
        self.assertFalse(any(x['action']=='run_piano_roll_script' for x in harness.commands))

    async def test_generation_changes_reject_before_navigation(self):
        class ForbiddenNavigator:
            async def read_identity(self):
                raise AssertionError('不可读取或导航')
        context = dict(controller_build_id='build',controller_session_id='controller',project_generation='project')
        native = dict(session='native',bridge_epoch='epoch',host_generation='host',target_id='page')
        for guard, session, target in [(lambda _:False,native,TARGET),
                (lambda _:True,dict(native,controller_build_id='wrong'),TARGET),
                (lambda _:True,native,dict(TARGET,expected_channel_index=1))]:
            prep = NavigatedMusicPreparation(ForbiddenNavigator(),None,controller_context=context,
                native_guard=guard,window_identity=dict(pid=10,hwnd=20))
            with self.assertRaises(ValueError):
                await prep.prepare(target,session)
