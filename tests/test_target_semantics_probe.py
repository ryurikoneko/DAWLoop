import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('target_probe', ROOT / 'scripts/runtime_v2_target_probe_live.py')
probe = importlib.util.module_from_spec(spec)
with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
    spec.loader.exec_module(probe)


class TargetProbeTests(unittest.TestCase):
    def test_locked_bytes_and_hash(self):
        self.assertEqual(probe.prepare_source(), probe.SOURCE)
        with patch.object(probe, 'SOURCE_HASH', '0'*64), self.assertRaises(ValueError):
            probe.prepare_source()

    def test_intent_is_persistent_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'OUTPUT', Path(directory)):
            with self.assertRaises(ValueError):
                probe.reserve('mismatch', {})
            probe.reserve('simple', {'status': 'UNKNOWN'})
            with self.assertRaises(FileExistsError):
                probe.reserve('simple', {})

    def test_second_requires_confirmed_first_and_undo(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'OUTPUT', Path(directory)):
            root = Path(directory)
            (root / 'ui.png').touch()
            observation = dict(observed_unix=time.time(), fixture_confirmed=True, marker_absent=True,
                               piano_roll_channel_a_visible=True, no_other_calls=True,
                               selected_channel=1, pattern_number=1, screenshot='ui.png')
            (root / 'mismatch_preflight.json').write_text(json.dumps(observation), encoding='utf-8')
            (root / 'simple_target.json').write_text('{"status":"MATCHED_SIMPLE_TARGET"}', encoding='utf-8')
            (root / 'undo.json').write_text('{"baseline_restored":false}', encoding='utf-8')
            with self.assertRaises(ValueError):
                probe.check_observation('mismatch')
            (root / 'undo.json').write_text('{"baseline_restored":true}', encoding='utf-8')
            self.assertEqual(probe.check_observation('mismatch'), observation)

    def test_closed_experiment_refuses_before_connection(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'OUTPUT', Path(directory)):
            (Path(directory) / 'summary.json').write_text('{"experiment_closed":true}', encoding='utf-8')
            for phase in ('simple', 'mismatch'):
                with self.subTest(phase=phase), patch.object(sys, 'argv', ['probe', '--phase', phase]), \
                        patch.object(probe, 'CDPTransport') as transport, self.assertRaises(ValueError):
                    probe.main()
                transport.assert_not_called()

    def test_stale_or_incomplete_ui_observation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'OUTPUT', Path(directory)):
            root = Path(directory)
            (root / 'ui.png').touch()
            valid = dict(observed_unix=time.time(), fixture_confirmed=True, marker_absent=True,
                         piano_roll_channel_a_visible=True, no_other_calls=True,
                         selected_channel=0, pattern_number=1, screenshot='ui.png')
            for change in ({'observed_unix': time.time()-61}, {'marker_absent': False}, {'selected_channel': 1}):
                (root / 'simple_preflight.json').write_text(json.dumps(dict(valid, **change)), encoding='utf-8')
                with self.subTest(change=change), self.assertRaises(ValueError):
                    probe.check_observation('simple')

    @unittest.skipUnless(shutil.which('node'), '需要脚本引擎验证实际桥接')
    def test_bridge_fixed_write_budget_and_generic_block(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/target_probe_bridge_harness.cjs'),
                                 str(ROOT / 'src/dawloop/adapters/gopher_native/bridge.js'),
                                 str(ROOT / 'research/piano_roll_probe/target_semantics_v1.pyscript')],
                                capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
