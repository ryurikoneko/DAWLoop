import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('probe_audit', ROOT / 'scripts/runtime_v2_piano_roll_probe_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PianoRollResearchProbeTests(unittest.TestCase):
    def test_evidence_redaction_preserves_public_origin_and_catalog_words(self):
        live_spec = importlib.util.spec_from_file_location('fixed_probe_live', ROOT / 'scripts/runtime_v2_fixed_probe_live.py')
        live = importlib.util.module_from_spec(live_spec)
        with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
            live_spec.loader.exec_module(live)
        with patch.dict('os.environ', {'USERNAME': 'TESTUSER'}):
            self.assertEqual(live.redact('https://gopher-fls.image-line.com/?token=secret'),
                             'https://gopher-fls.image-line.com/')
            self.assertEqual(live.redact('program testuser'), 'program <用户已脱敏>')
            self.assertEqual(live.redact(r'C:\Users\TESTUSER\fixture.flp'), '<本机路径已脱敏>')

    @unittest.skipUnless(shutil.which('node'), '需要本地脚本引擎验证实际桥接拒绝边界')
    def test_fixed_probe_bridge_keeps_general_scripts_blocked(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/fixed_probe_bridge_harness.cjs'),
                                 str(ROOT / 'src/dawloop/adapters/gopher_native/bridge.js'),
                                 str(ROOT / 'research/piano_roll_probe/count_return_v1.pyscript')],
                                capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_locked_artifact_has_only_static_certification(self):
        source, result = audit.prepare_count_probe()
        self.assertEqual(source, audit.EXPECTED_SOURCE)
        self.assertEqual(result['source_safety'], 'PASS_STATIC_ONLY')
        self.assertFalse(result['host_dispatch_enabled'])
        self.assertEqual(result['host_behavior'], 'UNPROVEN')

    def test_source_id_and_bytes_must_match_even_for_harmless_changes(self):
        for probe_id, source in [(audit.PROBE_ID, audit.EXPECTED_SOURCE + b'\n'),
                                 ('other', audit.EXPECTED_SOURCE),
                                 (audit.PROBE_ID, audit.EXPECTED_SOURCE.replace(b'noteCount', b'clearNotes()')),
                                 (audit.PROBE_ID, audit.EXPECTED_SOURCE + b'import os\n')]:
            with self.subTest(probe_id=probe_id), self.assertRaises(ValueError):
                audit.audit_fixed_source(probe_id, source)

    def test_hash_is_independently_locked(self):
        with patch.object(audit, 'SOURCE_HASH', '0' * 64), self.assertRaises(ValueError):
            audit.audit_fixed_source(audit.PROBE_ID, audit.EXPECTED_SOURCE)

    def test_mock_apply_reads_only_count_and_ppq_without_assuming_host_return(self):
        class Score:
            PPQ = 96
            noteCount = 3
            def getNote(self, index):
                raise AssertionError('门1不得读取音符内容')
        namespace = {}
        # 只在替代模块上执行，不触及真实宿主；此测试不认证宿主返回合同。
        with patch.dict('sys.modules', {'flpianoroll': SimpleNamespace(score=Score())}):
            exec(compile(audit.EXPECTED_SOURCE, '<固定探针模拟>', 'exec'), namespace)
        self.assertEqual(namespace['apply'](None), {'ppq': 96, 'note_count': 3})
