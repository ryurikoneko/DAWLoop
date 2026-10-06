import ast
import asyncio
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dawloop.runtime.snapshot import ReadSnapshotRequest, FreshnessStatus, atomic_write
from dawloop.runtime.snapshot_transport import (COMPLETION_EXPORTER, CompletionSnapshotClient,
                                               response_paths, validate_completed_response)


def identity(pattern=1):
    return {'source': 'fl_studio_midi_scripting', 'controller_session': 'session', 'project_generation': 'project',
            'project_loading': False, 'pattern_number': pattern, 'pattern_name': '甲' if pattern == 1 else '乙',
            'channel_index': 0, 'channel_name': '测试', 'channel_index_type': 'global', 'selected_channels': [0],
            'ppq': 96, 'observed_at': datetime.now(timezone.utc).isoformat()}


class Score:
    PPQ = 96
    def __init__(self, count=3):
        self.noteCount = count
        self.reads = 0
    def getNote(self, index):
        self.reads += 1
        return SimpleNamespace(number=60 + index, time=index * 24, length=12, velocity=.8)


class CompletionTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'DAWLoop_RuntimeV2_FreshSnapshot'
        self.root.mkdir()
        self.request = ReadSnapshotRequest(1, '甲', 0, '测试')

    def produce(self, request=None, stage='snapshot', score=None, publish=True):
        request = request or self.request
        if publish:
            atomic_write(self.root / 'snapshot_request.json', dict(asdict(request), sampling_stage=stage))
        with patch.dict('os.environ', {'TEMP': str(self.root.parent)}), \
                patch.dict('sys.modules', {'flpianoroll': SimpleNamespace(score=score or Score())}):
            exec(compile(COMPLETION_EXPORTER.read_bytes(), '<普通文件只读导出>', 'exec'), {})
        response, done = response_paths(self.root, request.generation)
        return response.read_bytes(), json.loads(done.read_text(encoding='utf-8'))

    def test_transport_probe_does_not_access_score(self):
        class Forbidden:
            def __getattribute__(self, name):
                raise AssertionError('传输探针不得访问工程')
        raw, marker = self.produce(stage='transport', score=Forbidden())
        state, value, error = validate_completed_response(self.request, 'transport', raw, marker)
        self.assertEqual(state, FreshnessStatus.FRESH)
        self.assertNotIn('ppq', value)
        self.assertNotIn('notes', value)

    def test_staged_probes_only_sample_requested_fields(self):
        for stage in ('ppq', 'note_count'):
            request = ReadSnapshotRequest(1, '甲', 0, '测试')
            score = Score()
            raw, marker = self.produce(request, stage, score)
            state, value, error = validate_completed_response(request, stage, raw, marker)
            self.assertEqual(state, FreshnessStatus.FRESH)
            self.assertEqual(score.reads, 0)
            self.assertNotIn('notes', value)
            self.assertEqual('note_count' in value, stage == 'note_count')

    def test_five_same_pattern_generations_really_sample_again(self):
        score = Score()
        generations = set()
        for _ in range(5):
            request = ReadSnapshotRequest(1, '甲', 0, '测试')
            raw, marker = self.produce(request, score=score)
            self.assertEqual(validate_completed_response(request, 'snapshot', raw, marker)[0], FreshnessStatus.FRESH)
            generations.add(request.generation)
        self.assertEqual(len(generations), 5)
        self.assertEqual(score.reads, 15)

    def test_duplicate_invocation_never_overwrites_files_or_resamples(self):
        score = Score()
        first = self.produce(score=score)
        second = self.produce(score=score, publish=False)
        self.assertEqual(first, second)
        self.assertEqual(score.reads, 3)

    def test_digest_stale_marker_stage_and_invalid_notes_are_rejected(self):
        raw, marker = self.produce()
        self.assertEqual(validate_completed_response(self.request, 'snapshot', raw + b' ', marker)[0], FreshnessStatus.INVALID)
        for changed in (dict(marker, request_id='a'*32), dict(marker, generation='b'*32)):
            self.assertEqual(validate_completed_response(self.request, 'snapshot', raw, changed)[0], FreshnessStatus.STALE)
        self.assertEqual(validate_completed_response(self.request, 'ppq', raw, marker)[0], FreshnessStatus.INVALID)
        response = json.loads(raw)
        for field, value in (('note_count', 2), ('notes', None), ('ppq', True), ('producer_status', 'ERROR')):
            altered = json.dumps(dict(response, **{field: value})).encode('utf-8')
            digest = dict(marker, response_sha256=hashlib.sha256(altered).hexdigest())
            self.assertEqual(validate_completed_response(self.request, 'snapshot', altered, digest)[0], FreshnessStatus.INVALID)

    def test_static_host_has_no_forbidden_file_or_music_operations(self):
        tree = ast.parse(COMPLETION_EXPORTER.read_text(encoding='utf-8'))
        attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertFalse(attributes & {'mkdir', 'makedirs', 'replace', 'rename', 'unlink', 'remove', 'fsync',
                                       'addNote', 'deleteNote', 'clear', 'clearNotes', 'addMarker', 'deleteMarker'})
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertFalse(node.func.attr == 'open')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'open':
                self.assertIn(node.args[1].value, ('r', 'w'))
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                self.assertFalse(any(isinstance(target, ast.Attribute) for target in targets))

    def test_write_queue_untouched(self):
        queue = self.root / 'mcp_request.json'
        queue.write_bytes(b'[{"action":"clear"}]')
        original = queue.read_bytes()
        self.produce()
        self.assertEqual(queue.read_bytes(), original)

    def test_collision_in_any_artifact_refuses_before_trigger(self):
        async def check():
            for suffix in ('.json', '.done'):
                request = ReadSnapshotRequest(1, '甲', 0, '测试')
                (self.root / ('response_' + request.generation + suffix)).write_text('{}', encoding='utf-8')
                client = CompletionSnapshotClient(self.root, timeout=.05)
                async def read():
                    return identity()
                result = await client.request_piano_roll_snapshot(request, read_identity=read,
                                                                 trigger=lambda: self.fail('碰撞不得派发'))
                self.assertEqual(result.error_code, 'GENERATION_COLLISION')
        asyncio.run(check())

    def test_missing_done_marker_does_not_accept_complete_response(self):
        async def check():
            async def read():
                return identity()
            def trigger():
                self.produce(publish=False)
                response, done = response_paths(self.root, self.request.generation)
                done.unlink()
            client = CompletionSnapshotClient(self.root, timeout=.03)
            result = await client.request_piano_roll_snapshot(self.request, read_identity=read, trigger=trigger)
            self.assertEqual(result.freshness, FreshnessStatus.TIMEOUT)
            self.assertIsNone(result.snapshot)
            self.assertIsNone(result.latency['parse_ms'])
            blocked = await client.request_piano_roll_snapshot(ReadSnapshotRequest(1, '甲', 0, '测试'),
                                                               read_identity=read, trigger=lambda: self.fail('超时后拒绝'))
            self.assertEqual(blocked.error_code, 'SNAPSHOT_CLIENT_POISONED')
        asyncio.run(check())

    def test_partial_marker_waits_until_complete_without_premature_acceptance(self):
        async def check():
            async def read():
                return identity()
            pending = None
            partial_observed = asyncio.Event()
            read_bytes = Path.read_bytes
            def observe_partial(path):
                raw = read_bytes(path)
                if path.suffix == '.done' and raw == b'{':
                    partial_observed.set()
                return raw
            def trigger():
                nonlocal pending
                raw, marker = self.produce(publish=False)
                response, done = response_paths(self.root, self.request.generation)
                done.write_text('{', encoding='utf-8')
                async def finish():
                    await partial_observed.wait()
                    done.write_text(json.dumps(marker), encoding='utf-8')
                pending = asyncio.create_task(finish())
            client = CompletionSnapshotClient(self.root, timeout=.1)
            # 验证部分标记必须先被观察；共享 runner 的调度耗时不属于此协议测试。
            clock = SimpleNamespace(monotonic=lambda: next(ticks))
            ticks = itertools.count(step=.001)
            with patch('dawloop.runtime.snapshot_transport.time', clock), \
                    patch.object(Path, 'read_bytes', observe_partial):
                result = await client.request_piano_roll_snapshot(self.request, read_identity=read, trigger=trigger)
            await pending
            self.assertTrue(partial_observed.is_set())
            self.assertEqual(result.freshness, FreshnessStatus.FRESH)
            self.assertFalse(result.target_bound)
        asyncio.run(check())

    def test_done_with_partial_response_is_invalid(self):
        async def check():
            async def read():
                return identity()
            def trigger():
                self.produce(publish=False)
                response, done = response_paths(self.root, self.request.generation)
                response.write_bytes(b'{')
            result = await CompletionSnapshotClient(self.root).request_piano_roll_snapshot(
                self.request, read_identity=read, trigger=trigger)
            self.assertEqual(result.freshness, FreshnessStatus.INVALID)
            self.assertIsNone(result.snapshot)
        asyncio.run(check())

    def test_client_identity_change_rejects_valid_snapshot(self):
        async def check():
            calls = iter((1, 2))
            async def read():
                return identity(next(calls))
            result = await CompletionSnapshotClient(self.root).request_piano_roll_snapshot(
                self.request, read_identity=read, trigger=lambda: self.produce(publish=False))
            self.assertEqual(result.error_code, 'TARGET_CHANGED')
            self.assertIsNone(result.snapshot)
        asyncio.run(check())

    def test_plain_host_request_read_failure_never_samples_or_publishes(self):
        atomic_write(self.root / 'snapshot_request.json', dict(asdict(self.request), sampling_stage='transport'))
        score = Score()
        with patch.dict('os.environ', {'TEMP': str(self.root.parent)}), \
                patch.dict('sys.modules', {'flpianoroll': SimpleNamespace(score=score)}), \
                patch('builtins.open', side_effect=SystemError('宿主普通文件打开失败')):
            with self.assertRaises(SystemError):
                exec(compile(COMPLETION_EXPORTER.read_bytes(), '<普通打开失败拒绝>', 'exec'), {})
        self.assertEqual(score.reads, 0)
        self.assertFalse(any(path.exists() for path in response_paths(self.root, self.request.generation)))
