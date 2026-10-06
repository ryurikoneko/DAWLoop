import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class PreviewObserverTests(unittest.TestCase):
    def load_entry(self):
        with patch.object(sys, 'path', [str(ROOT / 'scripts')] + sys.path):
            spec = importlib.util.spec_from_file_location('preview_onset_entry',
                ROOT / 'scripts/runtime_v2_preview_onset_live.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

    def test_observer_detection_limits_and_disposal(self):
        result = subprocess.run(['node', 'tests/preview_onset_observer_harness.cjs'],
            cwd=ROOT, capture_output=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_closed_stage_rejects_before_host_access(self):
        module = self.load_entry()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / 'summary.json').write_text('{}', encoding='utf-8')
            for action in ('launch', 'run', 'recover'):
                with patch.object(module, 'OUTPUT', output), patch.object(sys, 'argv', ['probe', action]), \
                        patch.object(module, 'process_state', side_effect=AssertionError('不应访问宿主')):
                    with self.assertRaisesRegex(ValueError, 'STAGE_CLOSED'):
                        module.main()

    def test_run_requires_owned_launch(self):
        module = self.load_entry()
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(module, 'OUTPUT', Path(temporary)), \
                    patch.object(sys, 'argv', ['probe', 'run']), \
                    patch.object(module, 'run', side_effect=AssertionError('不应派发')):
                with self.assertRaisesRegex(ValueError, 'EXPERIMENT_NOT_LAUNCHED'):
                    module.main()
