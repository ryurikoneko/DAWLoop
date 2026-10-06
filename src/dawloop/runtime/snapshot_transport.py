"""保留快照模型，以代次文件及完整标记替代宿主锁和原子替换。"""

import asyncio
from dataclasses import asdict
import hashlib
import inspect
import json
import math
import os
import time

from .snapshot import (EXPORTER, FreshSnapshotClient, FreshnessStatus, SnapshotResult,
                       _expected_identity, _identity_key, atomic_write)


COMPLETION_EXPORTER = EXPORTER.with_name('DAWLoop Fresh Export Transport.pyscript')
STAGES = ('transport', 'ppq', 'note_count', 'snapshot')


def response_paths(root, generation):
    return root / ('response_' + generation + '.json'), root / ('response_' + generation + '.done')


def validate_completed_response(request, stage, raw, marker):
    if not isinstance(marker, dict):
        return FreshnessStatus.INVALID, None, 'COMPLETION_INVALID'
    try:
        response = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError):
        return FreshnessStatus.INVALID, None, 'READBACK_INVALID'
    for value in (marker, response):
        if not isinstance(value, dict) or type(value.get('protocol_version')) is not int or value['protocol_version'] != 1:
            return FreshnessStatus.INVALID, None, 'READBACK_INVALID'
        if value.get('request_id') != request.request_id or value.get('generation') != request.generation:
            return FreshnessStatus.STALE, None, 'STALE_RESPONSE'
        if value.get('sampling_stage') != stage:
            return FreshnessStatus.INVALID, None, 'STAGE_MISMATCH'
    if marker.get('response_sha256') != hashlib.sha256(raw).hexdigest():
        return FreshnessStatus.INVALID, None, 'RESPONSE_DIGEST_MISMATCH'
    if response.get('producer') != 'dawloop_piano_roll_snapshot' or response.get('producer_status') != 'SUCCESS':
        return FreshnessStatus.INVALID, None, 'PRODUCER_ERROR'
    if stage != 'transport':
        if type(response.get('ppq')) is not int or response['ppq'] <= 0:
            return FreshnessStatus.INVALID, None, 'READBACK_INVALID'
        started, completed = response.get('sample_started_monotonic_ns'), response.get('sample_completed_monotonic_ns')
        if type(started) is not int or type(completed) is not int or started < 0 or completed < started:
            return FreshnessStatus.INVALID, None, 'READBACK_INVALID'
    if stage in ('note_count', 'snapshot'):
        count = response.get('note_count')
        if type(count) is not int or not 0 <= count <= 100000:
            return FreshnessStatus.INVALID, None, 'READBACK_INVALID'
    if stage == 'snapshot':
        notes = response.get('notes')
        if not isinstance(notes, list) or len(notes) != count or response.get('time_unit') != 'ticks':
            return FreshnessStatus.INVALID, None, 'READBACK_INVALID'
        for note in notes:
            if (not isinstance(note, dict) or set(note) != {'number', 'time', 'length', 'velocity'}
                    or type(note['number']) is not int or not 0 <= note['number'] <= 131
                    or type(note['time']) is not int or note['time'] < 0
                    or type(note['length']) is not int or note['length'] <= 0
                    or type(note['velocity']) not in (int, float) or not math.isfinite(note['velocity'])
                    or not 0 <= note['velocity'] <= 1):
                return FreshnessStatus.INVALID, None, 'READBACK_INVALID'
    return FreshnessStatus.FRESH, response, None


class CompletionSnapshotClient(FreshSnapshotClient):
    async def request_piano_roll_snapshot(self, request, *, read_identity, trigger, sampling_stage='snapshot'):
        if sampling_stage not in STAGES:
            raise ValueError('取样关卡无效')
        async with self.lock:
            result = SnapshotResult(FreshnessStatus.UNKNOWN)
            result.latency = dict.fromkeys(('identity_before_ms', 'request_write_ms', 'trigger_ms', 'producer_ms',
                                          'response_wait_ms', 'parse_ms', 'identity_after_ms', 'total_ms'))
            started = time.monotonic()
            descriptor = None
            lock_path = self.root / 'client.lock'
            response_path, done_path = response_paths(self.root, request.generation)
            issued_path = self.root / ('issued_' + request.generation + '.json')
            try:
                if self.poisoned:
                    result.error_code = 'SNAPSHOT_CLIENT_POISONED'
                    return result
                self.root.mkdir(parents=True, exist_ok=True)
                # 互斥只由外部客户端实施，宿主不创建、读取或删除此锁。
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                if any(path.exists() for path in (response_path, done_path, issued_path)):
                    result.freshness, result.error_code = FreshnessStatus.INVALID, 'GENERATION_COLLISION'
                    return result
                request_path = self.root / 'snapshot_request.json'
                if request_path.exists():
                    prior = json.loads(request_path.read_text(encoding='utf-8'))
                    if not isinstance(prior, dict):
                        raise ValueError('REQUEST_INVALID')
                    if prior.get('request_id') == request.request_id or prior.get('generation') == request.generation:
                        result.freshness, result.error_code = FreshnessStatus.STALE, 'REQUEST_REUSED'
                        return result
                phase = time.monotonic()
                result.identity_before = await read_identity()
                result.latency['identity_before_ms'] = (time.monotonic() - phase) * 1000
                if not _expected_identity(request, result.identity_before):
                    result.error_code = 'TARGET_CHANGED'
                    return result
                payload = dict(asdict(request), sampling_stage=sampling_stage)
                phase = time.monotonic()
                atomic_write(issued_path, payload)
                atomic_write(request_path, payload)
                result.latency['request_write_ms'] = (time.monotonic() - phase) * 1000
                phase = time.monotonic()
                observation = trigger()
                if inspect.isawaitable(observation):
                    await observation
                result.latency['trigger_ms'] = (time.monotonic() - phase) * 1000
                phase = time.monotonic()
                deadline = phase + self.timeout
                partial_marker = False
                while time.monotonic() < deadline:
                    try:
                        marker_raw = done_path.read_bytes()
                    except FileNotFoundError:
                        await asyncio.sleep(.01)
                        continue
                    parse_started = time.monotonic()
                    marker_incomplete = False
                    try:
                        marker = json.loads(marker_raw.decode('utf-8'))
                    except (ValueError, UnicodeError):
                        # 标记也是普通写入，完整JSON形成前只等待，不接受已有响应。
                        partial_marker = True
                        marker_incomplete = True
                    finally:
                        result.latency['parse_ms'] = (result.latency['parse_ms'] or 0) + (time.monotonic() - parse_started) * 1000
                    if marker_incomplete:
                        await asyncio.sleep(.01)
                        continue
                    try:
                        raw = response_path.read_bytes()
                    except FileNotFoundError:
                        result.freshness, result.error_code = FreshnessStatus.INVALID, 'COMPLETION_WITHOUT_RESPONSE'
                        return result
                    parse_started = time.monotonic()
                    state, response, code = validate_completed_response(request, sampling_stage, raw, marker)
                    result.latency['parse_ms'] += (time.monotonic() - parse_started) * 1000
                    result.freshness, result.snapshot, result.error_code = state, response, code
                    if state != FreshnessStatus.FRESH:
                        return result
                    if sampling_stage != 'transport':
                        result.latency['producer_ms'] = (response['sample_completed_monotonic_ns'] - response['sample_started_monotonic_ns']) / 1_000_000
                    break
                else:
                    self.poisoned = True
                    result.freshness = FreshnessStatus.INVALID if partial_marker else FreshnessStatus.TIMEOUT
                    result.error_code = 'COMPLETION_INVALID' if partial_marker else 'SNAPSHOT_TIMEOUT'
                    return result
                result.latency['response_wait_ms'] = (time.monotonic() - phase) * 1000
                phase_after = time.monotonic()
                result.identity_after = await read_identity()
                result.latency['identity_after_ms'] = (time.monotonic() - phase_after) * 1000
                if (not _expected_identity(request, result.identity_after)
                        or _identity_key(result.identity_before, check_age=False) != _identity_key(result.identity_after, check_age=False)
                        or (sampling_stage != 'transport' and response['ppq'] != result.identity_before['ppq'])):
                    result.freshness, result.snapshot, result.error_code = FreshnessStatus.UNKNOWN, None, 'TARGET_CHANGED'
                return result
            except asyncio.CancelledError:
                self.poisoned = True
                raise
            except Exception as error:
                self.poisoned = True
                result.freshness, result.snapshot = FreshnessStatus.UNKNOWN, None
                result.error_code = str(error) if isinstance(error, ValueError) else type(error).__name__
                return result
            finally:
                if result.latency['trigger_ms'] is not None and result.latency['response_wait_ms'] is None:
                    result.latency['response_wait_ms'] = (time.monotonic() - phase) * 1000
                if descriptor is not None:
                    os.close(descriptor)
                    lock_path.unlink(missing_ok=True)
                result.latency['total_ms'] = (time.monotonic() - started) * 1000
