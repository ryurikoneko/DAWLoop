import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend, controller_snapshot, compose_controller_native
from dawloop.runtime import guard_identity


class CompositeIdentityTests(unittest.TestCase):
    def target(self):
        return {'source':'fl_studio_midi_scripting','controller_session':'controller-1','project_generation':'project-1',
                'project_loading':False,'observed_at':datetime.now(timezone.utc).isoformat(),'project_title':'',
                'pattern_number':1,'pattern_name':'片段一','channel_index':4,'channel_name':'合成器',
                'channel_index_type':'global','selected_channels':[4],'ppq':96,'fl_studio_version':'26.1.6',
                'visible_channels':[{'visual_index':1,'global_index':4,'name':'合成器','plugin_name':'FLEX'}]}

    def combine(self,target,rows=None):
        return compose_controller_native(target,{'channels':rows or [{'visual_index':1,'display_name':'合成器 [FLEX]'}]},
            host_generation='native-1',binding_evidence='single-host-inspected',native_observed_at=datetime.now(timezone.utc))

    def test_partial_identity_and_global_visual_mapping(self):
        target=self.target()
        actual=self.combine(target)
        self.assertIsNone(actual.snapshot.project)
        self.assertIsNone(actual.snapshot.project_title)
        self.assertEqual(actual.field_status['native_channel_mapping'],'AVAILABLE')
        token=guard_identity(actual.snapshot,actual,now=datetime.now(timezone.utc))
        self.assertEqual((token.pattern_index,token.channel_index,token.ppq),(1,4,96))
        self.assertEqual(actual.snapshot.pattern_index.method,'patterns.patternNumber')
        self.assertEqual(actual.snapshot.fl_version.value,'26.1.6')
        self.assertEqual(actual.field_status['fl_version'],'AVAILABLE')

    def test_ambiguity_staleness_and_target_changes_block(self):
        target=self.target()
        expected=self.combine(target).snapshot
        for changed in (dict(target,pattern_number=2),dict(target,selected_channels=[4,5]),
                        dict(target,project_generation='project-2'),
                        dict(target,observed_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())):
            actual=self.combine(changed)
            with self.assertRaises(ValueError):
                guard_identity(expected,actual,now=datetime.now(timezone.utc))
        actual=self.combine(target,[{'visual_index':1,'display_name':'相同编号但不同通道'}])
        self.assertEqual(actual.field_status['native_channel_mapping'],'AMBIGUOUS')
        with self.assertRaises(ValueError):
            compose_controller_native(target,{},host_generation='',binding_evidence='',native_observed_at=datetime.now(timezone.utc))

    def test_missing_runtime_blocks_before_midi_import_or_request_write(self):
        with tempfile.TemporaryDirectory() as directory:
            b=ControllerIdentityBackend('explicit-port',settings_dir=Path(directory))
            with self.assertRaisesRegex(RuntimeError,'CONTROLLER_BUILD_ID_MISSING'):
                asyncio.run(b.read_identity())
            self.assertFalse((Path(directory)/'Hardware').exists())

    def test_host_loading_and_invalid_fields_are_not_available(self):
        target=self.target()
        with self.assertRaises(ValueError):
            controller_snapshot(dict(target,project_loading=True))
        snapshot,status=controller_snapshot(dict(target,ppq='96',pattern_name='\ufffd'))
        self.assertEqual(status['ppq'],'ERROR')
        self.assertEqual(status['pattern_name'],'ERROR')
        self.assertIsNone(snapshot.ppq)
