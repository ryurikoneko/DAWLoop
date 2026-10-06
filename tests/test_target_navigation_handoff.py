"""重放已取得目录，演练实际协调、准备契约与证据交接。"""

import asyncio
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import unittest

from dawloop.adapters.gopher_native.backend import GopherNativeBackend
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.target_navigation_handoff import NavigationHandoff


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT/'tests/native_fixtures/catalog/live_catalog.json').read_text(encoding='utf-8'))
SESSION = dict(session='epoch', bridge_epoch='epoch', host_generation='generation', target_id='page')
TARGETS = dict(A=dict(expected_pattern_index=1, expected_pattern_name='样式 1',
                      expected_channel_index=0, expected_channel_name='808 Kick'),
               B=dict(expected_pattern_index=2, expected_pattern_name='样式 2',
                      expected_channel_index=1, expected_channel_name='808 Clap'))
STEPS = dict(A_TO_B=('select_pattern', 'select_channel', 'open_piano_roll'),
             B_TO_A=('select_pattern', 'select_channel', 'open_piano_roll'))
REPORTS = {}


class SimulatedInputs:
    def __init__(self, fault=None):
        self.fault = fault
        self.now = 1000.0
        self.session = dict(SESSION)
        self.target = dict(TARGETS['A'])
        self.visible_channel = '808 Kick'
        self.reads = self.observations = 0
        self.primitive_calls = []
        self.note_dispatches = self.script_calls = 0
        self.callbacks_restored = None
        self.poisoned_epoch = None

    def tick(self):
        self.now = round(self.now + .01, 2)
        return self.now

    def connect(self):
        return copy.deepcopy(self.session)

    def invoke(self, kind, *args):
        if kind != 'catalog':
            self.note_dispatches += 1
            self.script_calls += 1
            raise AssertionError('禁止进入任何宿主工具派发')
        if self.fault == 'catalog_field':
            return dict(ok=True, value=CATALOG['tools'])
        if self.fault == 'catalog_format':
            return dict(ok=True, payload='{')
        if self.fault == 'catalog_decoder':
            return dict(ok=True, payload=json.dumps(dict(tools=[dict(name=1)])))
        if self.fault == 'catalog_transport':
            raise RuntimeError('目录读取失败')
        # 与已实现桥接的目录回调信封一致，内容重放48项真实目录而非自造简化工具。
        return dict(ok=True, payload=json.dumps(CATALOG['tools']), interference=0)

    def close(self):
        self.callbacks_restored = True

    async def read_session(self):
        return copy.deepcopy(self.session)

    async def read_identity(self):
        self.reads += 1
        target = self.target
        row = dict(source='fl_studio_midi_scripting', controller_session='controller',
                   project_generation='project', project_loading=False,
                   pattern_number=target['expected_pattern_index'], pattern_name=target['expected_pattern_name'],
                   channel_index=target['expected_channel_index'], channel_name=target['expected_channel_name'],
                   selected_channels=[target['expected_channel_index']], channel_index_type='global', ppq=96,
                   fl_studio_version='Producer Edition v26.1.6 [build 5639]',
                   observed_at=datetime.fromtimestamp(self.tick(), timezone.utc).isoformat())
        if self.fault == 'initial_a' and self.reads == 1:
            row['pattern_number'] = 2
        if self.reads == 5:
            if self.fault == 'wrong_channel':
                row.update(channel_index=0, channel_name='808 Kick', selected_channels=[0])
            if self.fault == 'wrong_pattern':
                row.update(pattern_number=1, pattern_name='样式 1')
            if self.fault == 'multiselect':
                row['selected_channels'] = [0, 1]
            if self.fault in ('project_generation', 'controller_session'):
                row[self.fault] = 'changed'
        if self.fault == 'identity_2' and self.reads == 6:
            row['pattern_number'] = 1
        return row

    async def primitive(self, name, target, session):
        self.tick()
        self.primitive_calls.append(dict(primitive=name, target=copy.deepcopy(target)))
        if len(self.primitive_calls) == 2 and self.fault == 'primitive_failure':
            raise RuntimeError('输入中途失败')
        if len(self.primitive_calls) == 2 and self.fault == 'transaction_unknown':
            return 'UNKNOWN'
        if len(self.primitive_calls) == 5 and self.fault == 'return_failure':
            return 'FAILED'
        if name == 'select_pattern':
            for key in ('expected_pattern_index', 'expected_pattern_name'):
                self.target[key] = target[key]
        if name == 'select_channel':
            for key in ('expected_channel_index', 'expected_channel_name'):
                self.target[key] = target[key]
        if name == 'open_piano_roll':
            self.visible_channel = target['expected_channel_name']
        return 'SUCCESS'

    async def ui(self, target, session):
        self.observations += 1
        started = self.tick()
        observed = self.tick()
        completed = self.tick()
        row = dict(visible=True, confirmed=True, observer='agent_visual_review',
                   evidence_ref=f'模拟界面观察-{self.observations}',
                   pattern_number=self.target['expected_pattern_index'], channel_name=self.visible_channel,
                   window_pid=10, window_hwnd=20, session=copy.deepcopy(session),
                   capture_started_unix=started, observed_unix=observed, capture_completed_unix=completed)
        if self.observations == 2:
            if self.fault == 'wrong_ui':
                row['channel_name'] = '808 Kick'
            if self.fault == 'stale_ui':
                row['observed_unix'] = 1
            if self.fault == 'unbracketed_ui':
                row['capture_started_unix'] = 999
            if self.fault == 'window_changed':
                row['window_hwnd'] = 21
            if self.fault in ('host_generation', 'bridge_epoch', 'target_id'):
                self.session[self.fault] = 'changed'
        return row

    async def recover(self):
        return dict(no_save_exit=True, baseline_unchanged=True, host_closed=True,
                    debug_port_closed=self.fault != 'recovery_failure', scope='OFFLINE_SIMULATION')

    def handoff(self, steps=STEPS):
        return NavigationHandoff(GopherNativeBackend(transport=self), self, self.read_session,
                                  self.primitive, self.ui, self.recover, targets=TARGETS, steps=steps,
                                  window_identity=dict(pid=10, hwnd=20),
                                  expected_catalog_hash=CATALOG['catalog_hash'], scope='OFFLINE_SIMULATION',
                                  clock=lambda:self.now)


class HandoffTests(unittest.IsolatedAsyncioTestCase):
    async def trial(self, fault=None):
        simulated = SimulatedInputs(fault)
        handoff = simulated.handoff()
        result = await handoff.run()
        REPORTS[fault or 'success'] = result
        self.assertEqual(simulated.note_dispatches, 0)
        self.assertEqual(simulated.script_calls, 0)
        self.assertEqual(result['repair_retries'], 0)
        self.assertEqual(result['fallback_navigation'], 0)
        self.assertFalse(result['live_certified'])
        self.assertFalse(result['producer_target_verified'])
        self.assertEqual(result, json.loads(json.dumps(result, ensure_ascii=False)))
        if fault != 'recovery_failure':
            self.assertTrue(result['recovery']['debug_port_closed'])
        self.assertTrue(result['callbacks_restored'])
        return simulated, handoff, result

    async def test_complete_roundtrip_with_real_contracts(self):
        simulated, handoff, result = await self.trial()
        self.assertEqual(result['status'], 'HANDOFF_PASSED')
        self.assertEqual(result['navigation_transactions'], 2)
        self.assertEqual(result['navigation_primitives'], 6)
        self.assertEqual(set(result['evidence']), {'A_CONFIRMED','B_CONFIRMED','A_RECONFIRMED'})
        for direction in STEPS:
            self.assertEqual(result['directions'][direction]['navigation_transactions'], 1)
            self.assertEqual(result['directions'][direction]['navigation_primitives'], 3)
        events = [row['event'] for row in result['events']]
        self.assertEqual(events.count('NO_MORE_NAVIGATION'), 2)
        self.assertEqual(events.count('UI_OBSERVATION'), 3)
        self.assertLess(events.index('B_CONFIRMED'), events.index('A_RECONFIRMED'))
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            await handoff.run()
        self.assertEqual(len(simulated.primitive_calls), 6)

    async def test_failures_stop_without_extra_navigation(self):
        faults = ('catalog_field','catalog_format','catalog_decoder','catalog_transport','initial_a',
                  'primitive_failure','transaction_unknown','wrong_ui','identity_2',
                  'wrong_channel','wrong_pattern','multiselect','stale_ui','unbracketed_ui',
                  'project_generation','controller_session','host_generation','bridge_epoch',
                  'target_id','window_changed','return_failure','recovery_failure')
        for fault in faults:
            with self.subTest(fault=fault):
                simulated, handoff, result = await self.trial(fault)
                self.assertEqual(result['status'], 'STOPPED')
                expected = 0 if fault.startswith('catalog_') or fault=='initial_a' else (
                    2 if fault in ('primitive_failure','transaction_unknown') else (
                    5 if fault=='return_failure' else (6 if fault=='recovery_failure' else 3)))
                self.assertEqual(result['navigation_primitives'], expected)
                self.assertEqual(len(simulated.primitive_calls), expected)
                if fault not in ('recovery_failure', 'return_failure') and expected == 3:
                    self.assertEqual(result['failed_phase'], 'A_TO_B_CONFIRM')
                    self.assertEqual(result['failure_category'], 'TARGET_CONFIRMATION_FAILED')
                if expected < 5:
                    self.assertNotIn('B_TO_A', result['directions'])
                with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
                    await handoff.run()
                self.assertEqual(len(simulated.primitive_calls), expected)
                with self.assertRaisesRegex(ValueError, 'TRANSACTION_FORBIDDEN'):
                    await handoff.navigate(TARGETS['B'], SESSION)
                self.assertEqual(len(simulated.primitive_calls), expected)

    async def test_steps_frozen_before_transaction(self):
        simulated = SimulatedInputs()
        handoff = simulated.handoff()
        steps = {key:list(values) for key,values in STEPS.items()}
        handoff = NavigationHandoff(GopherNativeBackend(transport=simulated), simulated,
            simulated.read_session, simulated.primitive, simulated.ui, simulated.recover,
            targets=TARGETS, steps=steps, window_identity=dict(pid=10, hwnd=20),
            expected_catalog_hash=CATALOG['catalog_hash'], scope='OFFLINE_SIMULATION', clock=lambda:simulated.now)
        steps['A_TO_B'].append('focus_channel_rack')
        self.assertEqual(handoff.steps['A_TO_B'], STEPS['A_TO_B'])
        with self.assertRaises(TypeError):
            handoff.steps['A_TO_B'] = ('focus_channel_rack',)
        self.assertEqual((await handoff.run())['navigation_primitives'], 6)

    async def test_primitive_count_comes_from_frozen_plan(self):
        simulated = SimulatedInputs()
        handoff = simulated.handoff(dict(STEPS, A_TO_B=('focus_channel_rack',) + STEPS['A_TO_B']))
        result = await handoff.run()
        self.assertEqual(result['status'], 'HANDOFF_PASSED')
        self.assertEqual(result['navigation_primitives'], 7)
        self.assertEqual(result['directions']['A_TO_B']['navigation_primitives'], 4)


if __name__ == '__main__':
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HandoffTests))
    if '--evidence' in sys.argv and result.wasSuccessful():
        output = ROOT/'evidence/runtime_v2/target_preparation/offline_handoff.json'
        output.write_text(json.dumps(dict(scope='OFFLINE_SIMULATION', cases=REPORTS,
            elapsed_seconds=time.perf_counter()-started, tests_run=result.testsRun,
            live_navigation_validation='NOT_REACHED', harness_protocol_error='FIXED_OFFLINE',
            auto_target_navigation='NOT_YET_LIVE_CERTIFIED'), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
