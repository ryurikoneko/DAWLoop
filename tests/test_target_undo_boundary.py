import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from test_controller_runtime import load_live_controller
from dawloop.runtime import ScriptInvocationState, ScriptCompletionStatus


class TargetUndoBoundaryTests(TestCase):
    def test_observed_effect_can_coexist_with_unknown_completion(self):
        state = ScriptInvocationState(True, True, ScriptCompletionStatus.UNKNOWN)
        self.assertTrue(state.application_observed)
        self.assertEqual(state.completion.value, 'COMPLETION_UNKNOWN')
        with self.assertRaises(ValueError):
            ScriptInvocationState(False, True)

    def controller(self, root):
        module = load_live_controller(root)
        module._SESSION_ID = 'session'
        module._PROJECT_GENERATION = 'project'
        self.state = dict(position=2, count=2, last=1, hint='2/2', changed_flag=1)
        self.calls = []
        def undo():
            self.calls.append('undo')
            self.state['position'] -= 1
            return 1
        module.general = SimpleNamespace(
            getUndoHistoryPos=lambda: self.state['position'], getUndoHistoryCount=lambda: self.state['count'],
            getUndoHistoryLast=lambda: self.state['last'], getUndoLevelHint=lambda: self.state['hint'],
            getChangedFlag=lambda: self.state['changed_flag'], safeToEdit=lambda: 1, undoUp=undo)
        return module

    def params(self):
        return dict(trial='aligned', source_hash='bbf82b82bc172858d09ac9a3fd95818e3069d30a10ce152c1db1591ba6753570',
            controller_session='session', project_generation='project',
            before=dict(position=1,count=1,last=0,hint='1/1',changed_flag=0), after=dict(self.state))

    def test_disabled_research_never_undoes(self):
        with tempfile.TemporaryDirectory() as directory:
            module = self.controller(Path(directory))
            self.assertEqual(module._undo_state(), self.state)
            with self.assertRaisesRegex(ValueError, 'DISABLED'):
                module._research_undo_once(self.params())
            self.assertEqual(self.calls, [])

    def test_new_level_undo_once_and_replay_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            module = self.controller(Path(directory))
            module.UNDO_RESEARCH_ENABLED = True
            params = self.params()
            result = module._research_undo_once(params)
            self.assertEqual(result['undo_after_call']['position'], 1)
            with self.assertRaisesRegex(ValueError, 'BUDGET'):
                module._research_undo_once(params)
            self.assertEqual(self.calls, ['undo'])

    def test_stale_changed_or_unproven_history_never_undoes(self):
        with tempfile.TemporaryDirectory() as directory:
            module = self.controller(Path(directory))
            module.UNDO_RESEARCH_ENABLED = True
            for field, value in (('source_hash','wrong'),('controller_session','old'),('project_generation','old')):
                params=self.params(); params[field]=value
                with self.assertRaises(ValueError):
                    module._research_undo_once(params)
            params=self.params(); params['after']['position']=3
            with self.assertRaises(ValueError):
                module._research_undo_once(params)
            params=self.params(); params['before']=dict(self.state)
            with self.assertRaisesRegex(ValueError, 'UNPROVEN'):
                module._research_undo_once(params)
            self.assertEqual(self.calls, [])
