import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class TargetIsolationTests(TestCase):
    def load(self):
        spec=importlib.util.spec_from_file_location('target_isolation',ROOT/'scripts/runtime_v2_target_isolation_live.py')
        module=importlib.util.module_from_spec(spec)
        with patch.object(sys,'path',[str(ROOT/'scripts'),*sys.path]):
            spec.loader.exec_module(module)
        return module

    def test_next_session_requires_verified_no_save_recovery(self):
        module=self.load()
        with tempfile.TemporaryDirectory() as temp,patch.object(module,'OUTPUT',Path(temp)):
            old=Path(temp)/'aligned'; old.mkdir()
            recovery=dict(host_closed=True,debug_port_closed=True,
                fixture_hash_before=module.FIXTURE_HASH,fixture_hash_after='changed')
            (old/'recovery.json').write_text(json.dumps(recovery),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'RECOVERY'):
                module.session_gate('channel_mismatch')
            recovery['fixture_hash_after']=module.FIXTURE_HASH
            (old/'recovery.json').write_text(json.dumps(recovery),encoding='utf-8')
            module.session_gate('channel_mismatch')

    def test_dispatch_intent_blocks_repeat_and_finished_stage_blocks_all(self):
        module=self.load()
        with tempfile.TemporaryDirectory() as temp,patch.object(module,'OUTPUT',Path(temp)),patch.object(module,'fixture'):
            directory=Path(temp)/'aligned'; directory.mkdir()
            (directory/'intent.json').touch()
            with self.assertRaisesRegex(ValueError,'BUDGET'):
                module.dispatch_gate('aligned',directory)
            (Path(temp)/'summary.json').touch()
            with self.assertRaises(ValueError):
                module.session_gate('aligned')

    def test_unrepresentable_mismatch_never_passes_dispatch_guard(self):
        module=self.load()
        with tempfile.TemporaryDirectory() as temp,patch.object(module,'OUTPUT',Path(temp)),patch.object(module,'fixture'):
            directory=Path(temp)/'aligned'; directory.mkdir()
            (directory/'preflight.json').write_text(json.dumps(dict(observed_unix=__import__('time').time(),
                state_representable=False)),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'UI_EVIDENCE'):
                module.dispatch_gate('aligned',directory)
