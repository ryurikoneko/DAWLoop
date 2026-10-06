import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dawloop.runtime.snapshot_output import OUTPUT_PROBE, OUTPUT_PROBE_SHA256, OutputProbeClient


OBSERVED = {'dispatch_count': 1, 'dispatch_observed': True, 'invocation_completed': True}


class OutputProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'DAWLoop_RuntimeV2_OutputSnapshot'

    def produce(self):
        with patch.dict('os.environ', {'TEMP': str(self.root.parent)}):
            exec(compile(OUTPUT_PROBE.read_bytes(), '<固定输出探针>', 'exec'), {})
        return dict(OBSERVED)

    async def run_probe(self, client=None, trigger=None, idle=True):
        return await (client or OutputProbeClient(self.root, timeout=.04)).run(
            installed_probe=OUTPUT_PROBE, confirm_idle=lambda: idle, trigger=trigger or self.produce)

    def test_fixed_probe_has_no_input_score_or_mutation_path(self):
        self.assertEqual(hashlib.sha256(OUTPUT_PROBE.read_bytes()).hexdigest(), OUTPUT_PROBE_SHA256)
        tree = ast.parse(OUTPUT_PROBE.read_text(encoding='utf-8'))
        modules = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertEqual(modules, {'json', 'os', 'uuid'})
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'open':
                self.assertEqual(node.args[1].value, 'w')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, {'read', 'load', 'mkdir', 'open', 'replace', 'unlink', 'getNote', 'addNote'})

    def test_five_runs_use_distinct_ids_and_preserve_old_artifacts(self):
        async def check():
            ids = []
            for _ in range(5):
                result = await self.run_probe()
                self.assertEqual(result.freshness, 'FRESH_FOR_TRANSACTION')
                self.assertFalse(result.target_bound)
                ids.append(result.snapshot['snapshot_id'])
            self.assertEqual(len(set(ids)), 5)
            self.assertEqual(len(list((self.root / 'archive').glob('*.json'))), 4)
        asyncio.run(check())

    def test_timeout_blocks_recreated_client_without_archiving_late_artifact(self):
        async def check():
            result = await self.run_probe(trigger=lambda: dict(OBSERVED))
            self.assertEqual(result.freshness, 'TIMEOUT')
            self.produce()
            original = (self.root / 'snapshot.json').read_bytes()
            blocked = await self.run_probe(trigger=lambda: self.fail('未决执行不能再次派发'))
            self.assertEqual(blocked.error_code, 'PRIOR_INVOCATION_PENDING_OR_UNKNOWN')
            self.assertEqual((self.root / 'snapshot.json').read_bytes(), original)
            self.assertFalse((self.root / 'archive').exists())
        asyncio.run(check())

    def test_unknown_idle_or_unknown_existing_artifact_never_triggers(self):
        async def check():
            result = await self.run_probe(idle=False, trigger=lambda: self.fail('空闲未证实不能触发'))
            self.assertEqual(result.error_code, 'NO_PENDING_INVOCATION_UNPROVEN')
            (self.root / 'snapshot.json').write_text('已有未知产物', encoding='utf-8')
            blocked = await self.run_probe(trigger=lambda: self.fail('未知旧调用不能触发'))
            self.assertEqual(blocked.error_code, 'PRIOR_INVOCATION_UNKNOWN')
            self.assertEqual((self.root / 'snapshot.json').read_text(encoding='utf-8'), '已有未知产物')
        asyncio.run(check())

    def test_reused_producer_id_is_not_fresh(self):
        async def check():
            with patch('uuid.uuid4', return_value=SimpleNamespace(hex='a'*32)):
                first = await self.run_probe()
                second = await self.run_probe()
            self.assertEqual(first.freshness, 'FRESH_FOR_TRANSACTION')
            self.assertEqual(second.error_code, 'SNAPSHOT_ID_REUSED')
            self.assertIsNone(second.snapshot)
        asyncio.run(check())

    def test_arbitrary_or_changed_source_is_rejected_before_cleanup(self):
        async def check():
            source = Path(self.temporary.name) / 'changed.pyscript'
            source.write_text('print(1)', encoding='utf-8')
            result = await OutputProbeClient(self.root).run(installed_probe=source, confirm_idle=lambda: True,
                                                          trigger=lambda: self.fail('非固定源码不能派发'))
            self.assertEqual(result.error_code, 'FIXED_PROBE_HASH_MISMATCH')
            self.assertFalse(self.root.exists())
        asyncio.run(check())

    def test_incomplete_output_is_not_accepted(self):
        async def check():
            def trigger():
                (self.root / 'snapshot.json').write_text('{', encoding='utf-8')
                return dict(OBSERVED)
            result = await self.run_probe(trigger=trigger)
            self.assertEqual(result.freshness, 'INVALID')
            self.assertEqual(result.error_code, 'OUTPUT_PAYLOAD_INCOMPLETE')
            self.assertIsNone(result.snapshot)
        asyncio.run(check())

    def test_multiple_dispatch_or_unobserved_completion_is_unknown(self):
        async def check():
            def trigger():
                self.produce()
                return dict(OBSERVED, dispatch_count=2)
            result = await self.run_probe(trigger=trigger)
            self.assertEqual(result.error_code, 'SINGLE_DISPATCH_UNPROVEN')
            self.assertIsNone(result.snapshot)
        asyncio.run(check())

    def test_output_file_error_stops_without_cache_success(self):
        async def check():
            def trigger():
                return dict(OBSERVED, host_error='HOST_FILE_OUTPUT_NOT_VIABLE')
            result = await self.run_probe(trigger=trigger)
            self.assertEqual(result.error_code, 'HOST_FILE_OUTPUT_NOT_VIABLE')
            self.assertIsNone(result.snapshot)
            self.assertIsNone(result.latency['parse_ms'])
        asyncio.run(check())

    def test_closed_file_route_refuses_all_live_entry_points(self):
        repository = Path(__file__).resolve().parents[1]
        for name in ('runtime_v2_fresh_export_live.py', 'runtime_v2_completion_export_live.py',
                     'runtime_v2_output_probe_live.py'):
            with self.subTest(entry=name):
                process = subprocess.run([sys.executable, str(repository / 'scripts' / name), '--install'],
                                         cwd=repository, capture_output=True, text=True, encoding='utf-8',
                                         env=dict(os.environ, PYTHONIOENCODING='utf-8'), timeout=10)
                self.assertNotEqual(process.returncode, 0)
                self.assertIn('钢琴卷帘文件快照路线已关闭', process.stderr)
