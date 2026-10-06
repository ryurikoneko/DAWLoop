import ast
import asyncio
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dawloop.runtime.snapshot import (EXPORTER, FreshnessStatus, FreshSnapshotClient,
                                      ReadSnapshotRequest, atomic_write, install_snapshot_exporter, validate_response)


def identity(pattern=1):
    return {'source': 'fl_studio_midi_scripting', 'controller_session': 'session', 'project_generation': 'project',
            'project_loading': False, 'pattern_number': pattern, 'pattern_name': '甲' if pattern == 1 else '乙',
            'channel_index': 0, 'channel_name': '测试', 'channel_index_type': 'global', 'selected_channels': [0],
            'ppq': 96, 'observed_at': datetime.now(timezone.utc).isoformat()}


class Score:
    PPQ = 96
    def __init__(self, count=3):
        self.count = count
        self.reads = 0
    @property
    def noteCount(self):
        return self.count
    def getNote(self, index):
        self.reads += 1
        return SimpleNamespace(number=60+index, time=index*24, length=12, velocity=.8)


def produce(root, request, score=None):
    atomic_write(root / 'snapshot_request.json', asdict(request))
    with patch.dict('os.environ', {'TEMP': str(root.parent)}), \
            patch.dict('sys.modules', {'flpianoroll': SimpleNamespace(score=score or Score())}):
        exec(compile(EXPORTER.read_bytes(), '<独立只读导出器>', 'exec'), {})
    return json.loads((root / 'snapshot_response.json').read_text(encoding='utf-8'))


class FreshSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'DAWLoop_RuntimeV2_FreshSnapshot'
        self.request = ReadSnapshotRequest(1, '甲', 0, '测试')

    def test_producer_samples_again_and_sequence_survives_module_reload(self):
        score = Score()
        first = produce(self.root, self.request, score)
        second_request = replace(self.request, request_id='1'*32, generation='2'*32)
        second = produce(self.root, second_request, score)
        self.assertEqual(score.reads, 6)
        self.assertEqual((first['sample_sequence'], second['sample_sequence']), (1, 2))
        self.assertNotEqual(first['producer_invocation'], second['producer_invocation'])
        self.assertEqual(validate_response(second_request, second, previous=first), (FreshnessStatus.FRESH, None))

    def test_old_generation_and_wrong_request_id_are_stale(self):
        response = produce(self.root, self.request)
        for altered in (dict(response, generation='1'*32), dict(response, request_id='2'*32)):
            self.assertEqual(validate_response(self.request, altered)[0], FreshnessStatus.STALE)

    def test_missing_fields_bad_count_types_nan_and_error_are_invalid(self):
        response = produce(self.root, self.request)
        for key in ('notes', 'generation', 'ppq', 'sample_sequence', 'producer_epoch', 'response_written_at'):
            altered = dict(response)
            del altered[key]
            self.assertEqual(validate_response(self.request, altered)[0], FreshnessStatus.INVALID)
        for altered in (dict(response, note_count=2), dict(response, ppq=True), dict(response, protocol_version=2),
                        dict(response, producer_status='ERROR'), dict(response, response_written_at=float('nan')),
                        dict(response, notes=[dict(n, velocity=float('nan')) for n in response['notes']])):
            self.assertEqual(validate_response(self.request, altered)[0], FreshnessStatus.INVALID)

    def test_sequence_or_invocation_reuse_is_rejected_even_for_matching_generation(self):
        first = produce(self.root, self.request)
        request = replace(self.request, request_id='1'*32, generation='2'*32)
        second = produce(self.root, request)
        for altered in (dict(second, sample_sequence=first['sample_sequence']),
                        dict(second, producer_invocation=first['producer_invocation'])):
            self.assertEqual(validate_response(request, altered, previous=first)[0], FreshnessStatus.STALE)
        self.assertEqual(validate_response(request, dict(second, producer_epoch='3'*32), previous=first)[0], FreshnessStatus.UNKNOWN)

    def test_read_exporter_never_opens_legacy_write_queue(self):
        self.root.mkdir()
        queue = self.root / 'mcp_request.json'
        queue.write_text('[{"action":"clear"}]', encoding='utf-8')
        original = queue.read_bytes()
        response = produce(self.root, self.request)
        self.assertEqual(queue.read_bytes(), original)
        self.assertEqual(response['note_count'], 3)
        tree = ast.parse(EXPORTER.read_text(encoding='utf-8'))
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertFalse(attributes & {'addNote', 'deleteNote', 'clear', 'clearNotes', 'addMarker', 'deleteMarker', 'clearMarkers'})
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                self.assertTrue(all(not isinstance(target, ast.Attribute) for target in targets))

    def test_duplicate_script_activation_does_not_resample_or_replace_response(self):
        score = Score()
        first = produce(self.root, self.request, score)
        second = produce(self.root, self.request, score)
        self.assertEqual(first, second)
        self.assertEqual(score.reads, 3)

    def test_atomic_replace_failure_preserves_existing_response(self):
        destination = self.root / 'snapshot_response.json'
        atomic_write(destination, {'old': True})
        original = destination.read_bytes()
        with patch('os.replace', side_effect=OSError), self.assertRaises(OSError):
            atomic_write(destination, {'new': True})
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_producer_bad_request_never_touches_score(self):
        self.root.mkdir()
        atomic_write(self.root / 'snapshot_request.json', dict(asdict(self.request), operation='write'))
        score = Score()
        with patch.dict('os.environ', {'TEMP': str(self.root.parent)}), \
                patch.dict('sys.modules', {'flpianoroll': SimpleNamespace(score=score)}):
            exec(compile(EXPORTER.read_bytes(), '<拒绝写请求>', 'exec'), {})
        self.assertEqual(score.reads, 0)
        self.assertFalse((self.root / 'snapshot_response.json').exists())

    def test_install_refuses_unmanaged_existing_script(self):
        settings = Path(self.temporary.name) / 'settings'
        install_snapshot_exporter(settings)
        destination = settings / 'Piano roll scripts' / EXPORTER.name
        destination.write_text('用户已有内容', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            install_snapshot_exporter(settings)
        self.assertEqual(destination.read_text(encoding='utf-8'), '用户已有内容')

    def test_request_validation_and_default_ids_are_unique(self):
        requests = [ReadSnapshotRequest(1, '甲', 0, '测试') for _ in range(20)]
        self.assertEqual(len({r.request_id for r in requests}), 20)
        self.assertEqual(len({r.generation for r in requests}), 20)
        for args in ({'protocol_version': 2}, {'expected_channel_index': True}, {'generation': 'missing'}):
            with self.assertRaises(ValueError):
                replace(self.request, **args)

    def test_client_new_sample_is_fresh_without_claiming_target_binding(self):
        async def check():
            client = FreshSnapshotClient(self.root, timeout=.1)
            async def read():
                return identity()
            result = await client.request_piano_roll_snapshot(self.request, read_identity=read,
                                                             trigger=lambda: produce(self.root, self.request))
            self.assertEqual(result.freshness, FreshnessStatus.FRESH)
            self.assertFalse(result.target_bound)
            self.assertEqual(result.snapshot['note_count'], 3)
        asyncio.run(check())

    def test_client_stale_cache_timeout_never_falls_back_and_poison_blocks_trigger(self):
        async def check():
            produce(self.root, replace(self.request, request_id='2'*32, generation='1'*32))
            client = FreshSnapshotClient(self.root, timeout=.03)
            async def read():
                return identity()
            result = await client.request_piano_roll_snapshot(self.request, read_identity=read, trigger=lambda: None)
            self.assertEqual(result.freshness, FreshnessStatus.TIMEOUT)
            self.assertIsNone(result.snapshot)
            blocked = await client.request_piano_roll_snapshot(self.request, read_identity=read,
                                                               trigger=lambda: self.fail('超时后不能继续派发'))
            self.assertEqual(blocked.error_code, 'SNAPSHOT_CLIENT_POISONED')
        asyncio.run(check())

    def test_client_target_change_rejects_snapshot_and_preflight_mismatch_never_triggers(self):
        async def check():
            client = FreshSnapshotClient(self.root, timeout=.1)
            calls = iter([1, 2])
            async def read():
                return identity(next(calls))
            result = await client.request_piano_roll_snapshot(self.request, read_identity=read,
                                                             trigger=lambda: produce(self.root, self.request))
            self.assertEqual(result.error_code, 'TARGET_CHANGED')
            self.assertIsNone(result.snapshot)
            async def wrong():
                return identity(2)
            result = await client.request_piano_roll_snapshot(ReadSnapshotRequest(1, '甲', 0, '测试'), read_identity=wrong,
                                                             trigger=lambda: self.fail('错误目标不得到达触发器'))
            self.assertEqual(result.error_code, 'TARGET_CHANGED')
        asyncio.run(check())

    def test_client_rejects_truncated_json_without_success(self):
        async def check():
            self.root.mkdir()
            (self.root / 'snapshot_response.json').write_text('{"notes":', encoding='utf-8')
            client = FreshSnapshotClient(self.root, timeout=.1)
            async def read():
                return identity()
            result = await client.request_piano_roll_snapshot(self.request, read_identity=read, trigger=lambda: None)
            self.assertEqual(result.freshness, FreshnessStatus.INVALID)
        asyncio.run(check())

    def test_request_reuse_is_blocked_after_client_recreation(self):
        async def check():
            produce(self.root, self.request)
            client = FreshSnapshotClient(self.root)
            async def read():
                return identity()
            result = await client.request_piano_roll_snapshot(self.request, read_identity=read,
                                                             trigger=lambda: self.fail('旧请求不能重新派发'))
            self.assertEqual((result.freshness, result.error_code), (FreshnessStatus.STALE, 'REQUEST_REUSED'))
        asyncio.run(check())

    def test_unavailable_host_lock_fails_before_sampling(self):
        atomic_write(self.root / 'snapshot_request.json', asdict(self.request))
        score = Score()
        with patch.dict('os.environ', {'TEMP': str(self.root.parent)}), \
                patch.dict('sys.modules', {'flpianoroll': SimpleNamespace(score=score)}), \
                patch('os.open', side_effect=TypeError('宿主文件接口不可用')):
            with self.assertRaises(TypeError):
                exec(compile(EXPORTER.read_bytes(), '<宿主兼容性拒绝>', 'exec'), {})
        self.assertEqual(score.reads, 0)
        self.assertFalse((self.root / 'snapshot_response.json').exists())
        self.assertFalse((self.root / 'producer_state.json').exists())

    def test_missing_response_leaves_unexecuted_phases_unknown(self):
        async def check():
            client = FreshSnapshotClient(self.root, timeout=.03)
            async def read():
                return identity()
            result = await client.request_piano_roll_snapshot(self.request, read_identity=read, trigger=lambda: None)
            self.assertEqual(result.freshness, FreshnessStatus.TIMEOUT)
            self.assertIsNone(result.latency['parse_ms'])
            self.assertIsNone(result.latency['producer_ms'])
            self.assertIsNone(result.latency['identity_after_ms'])
        asyncio.run(check())
