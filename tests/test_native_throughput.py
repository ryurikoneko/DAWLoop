import ast
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class NativeThroughputTests(TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location('throughput', ROOT / 'scripts/runtime_v2_throughput_live.py')
        module = importlib.util.module_from_spec(spec)
        with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
            spec.loader.exec_module(module)
        module.OUTPUT = ROOT/'tests/native_fixtures/throughput'
        return module

    def test_fixed_sources_and_grid_preserve_original_region(self):
        module = self.load()
        for count in module.COUNTS:
            source, _ = module.checked_source(count)
            tree = ast.parse(source)
            calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
            self.assertEqual(calls, {'flp.ScriptDialog', 'range', 'flp.Note', 'flp.score.addNote'})
            points = [(84+i//16, 32*96+(i%16)*48) for i in range(count)]
            self.assertEqual(len(set(points)), count)
            self.assertTrue(all(time >= 3072 for _, time in points))
        with self.assertRaises(ValueError):
            module.source_for(256)

    def test_no_progress_after_partial_effect_or_open_host(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'OUTPUT', Path(temp)), patch.object(module, 'baseline'):
            old = Path(temp) / 'n001'
            module.write(old / 'recovery.json', dict(host_closed=True, debug_port_closed=True,
                sha256_after=module.BASELINE_HASH, size_after=module.BASELINE_SIZE))
            module.write(old / 'observation.json', dict(visible_batch_effect=False, stop_condition=True))
            with self.assertRaisesRegex(ValueError, 'NOT_PASSED'):
                module.gate(4)

    def test_intent_blocks_repeat_before_connect(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'intent.json').touch()
            with self.assertRaisesRegex(ValueError, 'BUDGET'):
                module.dispatch(1, path)

    def test_actual_bridge_fixed_allowlist_and_budget(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        subprocess.run([node, str(ROOT / 'tests/throughput_probe_bridge_harness.cjs'),
            str(ROOT / 'src/dawloop/adapters/gopher_native/bridge.js'), str(self.load().OUTPUT)],
            check=True, timeout=10, capture_output=True)
