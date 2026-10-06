import asyncio
import sys
import types
from unittest.mock import patch

from test_channel_selection_contract import SelectionTests
from dawloop.adapters.fl_target_navigation import ControllerTargetNavigator


class NavigationTests(SelectionTests):
    def setUp(self):
        super().setUp()
        self.pattern = 1
        self.steps = []
        def jump(index):
            self.steps.append('select_pattern')
            self.pattern = index
        self.module.patterns = types.SimpleNamespace(patternNumber=lambda:self.pattern,
            getPatternName=lambda i:'样式 '+str(i), patternMax=lambda:2,
            isPatternDefault=lambda i:False, jumpToPattern=jump)
        select = self.module.channels.selectOneChannel
        def select_record(index, global_index):
            self.steps.append('select_channel_global')
            select(index, global_index)
        self.module.channels.selectOneChannel = select_record
        self.module.ui.openEventEditor = lambda event, mode:self.steps.append('targeted_open_piano_roll')
        self.module.channels.getRecEventId = lambda index, global_index: 1000 + index if global_index is True else None
        self.target = dict(expected_pattern_index=2,expected_pattern_name='样式 2',
            expected_channel_index=1,expected_channel_name='808 Clap')
        self.session = dict(controller_build_id='offline-build',
            controller_session_id=self.module._SESSION_ID,project_generation=self.module._PROJECT_GENERATION)

    def test_complete_frozen_transaction_actual_controller_and_reader(self):
        navigator=ControllerTargetNavigator('offline-port',settings_dir=self.root)
        with patch.dict(sys.modules,{'mido':self.midi,'midi':types.SimpleNamespace(REC_Chan_PianoRoll=7,EE_PR=3)}):
            result=asyncio.run(navigator.navigate_once(self.target,self.session,'transaction'))
            with self.assertRaisesRegex(RuntimeError,'BUDGET_EXHAUSTED'):
                asyncio.run(navigator.navigate_once(self.target,self.session,'another-id'))
            after=asyncio.run(navigator.read_identity())
        self.assertEqual(self.steps,['select_pattern','select_channel_global','targeted_open_piano_roll'])
        self.assertEqual(result['navigation_transactions'],1)
        self.assertEqual(len(result['primitives']),3)
        self.assertEqual(after['pattern_number'],2)
        self.assertEqual(after['selected_channels'],[1])
        self.assertEqual(len(after['existing_patterns']),2)

    def test_missing_pattern_and_unknown_never_continue_or_retry(self):
        params=dict(self.params(),pattern_index=2,pattern_name='样式 2')
        with patch.dict(sys.modules,{'midi':types.SimpleNamespace(REC_Chan_PianoRoll=7,EE_PR=3)}):
            with self.assertRaisesRegex(ValueError,'EXISTING_PATTERN'):
                self.module._navigate_target_once(dict(params,pattern_index=3))
            self.assertEqual(self.steps,[])
            with patch.object(self.module.channels,'selectOneChannel',side_effect=RuntimeError('unknown')):
                with self.assertRaises(RuntimeError):
                    self.module._navigate_target_once(params)
            with self.assertRaisesRegex(ValueError,'BUDGET_EXHAUSTED'):
                self.module._navigate_target_once(params)
        record=self.module._TARGET_NAVIGATION_OPERATIONS['operation']
        self.assertEqual([x['primitive'] for x in record['primitives']],
            ['select_pattern','select_channel_global'])
        self.assertEqual(record['primitives'][-1]['status'],'UNKNOWN')
        self.assertNotIn('targeted_open_piano_roll',self.steps)
