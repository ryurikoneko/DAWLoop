"""独立新鲜快照协议；身份守卫与实际生产方目标绑定分开。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4


PROTOCOL_VERSION = 1
EXPORTER = Path(__file__).resolve().parents[1] / 'fl_scripts' / 'DAWLoop Snapshot Exporter.pyscript'


class FreshnessStatus(str, Enum):
    FRESH = 'FRESH'
    STALE = 'STALE'
    UNKNOWN = 'UNKNOWN'
    INVALID = 'INVALID'
    TIMEOUT = 'TIMEOUT'


@dataclass(frozen=True)
class ReadSnapshotRequest:
    expected_pattern_index: int
    expected_pattern_name: str
    expected_channel_index: int
    expected_channel_name: str
    protocol_version: int = PROTOCOL_VERSION
    operation: str = 'read_snapshot'
    request_id: str = field(default_factory=lambda: uuid4().hex)
    generation: str = field(default_factory=lambda: uuid4().hex)
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if type(self.protocol_version) is not int or self.protocol_version != PROTOCOL_VERSION or self.operation != 'read_snapshot':
            raise ValueError('快照请求协议无效')
        for key in ('request_id', 'generation'):
            value = getattr(self, key)
            if not isinstance(value, str) or len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('请求编号与代次必须是独立生成的十六进制编号')
        for key in ('expected_pattern_name', 'expected_channel_name'):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError('目标名称无效')
        for key, minimum in (('expected_pattern_index', 1), ('expected_channel_index', 0)):
            value = getattr(self, key)
            if type(value) is not int or value < minimum:
                raise ValueError('目标索引无效')
        stamp = datetime.fromisoformat(self.requested_at)
        if stamp.tzinfo is None:
            raise ValueError('请求时间必须含时区')


@dataclass
class SnapshotResult:
    freshness: FreshnessStatus
    snapshot: dict | None = None
    identity_before: dict | None = None
    identity_after: dict | None = None
    latency: dict = field(default_factory=dict)
    error_code: str | None = None
    target_bound: bool = False


def atomic_write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_response(request: ReadSnapshotRequest, response, *, previous=None):
    if not isinstance(response, dict) or type(response.get('protocol_version')) is not int or response['protocol_version'] != PROTOCOL_VERSION:
        return FreshnessStatus.INVALID, 'READBACK_INVALID'
    if not isinstance(response.get('request_id'), str) or not isinstance(response.get('generation'), str):
        return FreshnessStatus.INVALID, 'READBACK_INVALID'
    if response['request_id'] != request.request_id or response['generation'] != request.generation:
        return FreshnessStatus.STALE, 'STALE_RESPONSE'
    if response.get('producer_status') != 'SUCCESS':
        return FreshnessStatus.INVALID, 'PRODUCER_ERROR'
    for key in ('producer_epoch', 'producer_invocation'):
        if not isinstance(response.get(key), str) or len(response[key]) != 32 or any(c not in '0123456789abcdef' for c in response[key]):
            return FreshnessStatus.INVALID, 'READBACK_INVALID'
    sequence, ppq, count, notes = (response.get(key) for key in ('sample_sequence', 'ppq', 'note_count', 'notes'))
    if (type(sequence) is not int or sequence < 1 or type(ppq) is not int or ppq < 1
            or type(count) is not int or not 0 <= count <= 100000 or not isinstance(notes, list) or count != len(notes)
            or response.get('time_unit') != 'ticks'):
        return FreshnessStatus.INVALID, 'READBACK_INVALID'
    for note in notes:
        if (not isinstance(note, dict) or set(note) != {'number', 'time', 'length', 'velocity'}
                or type(note['number']) is not int or not 0 <= note['number'] <= 131
                or type(note['time']) is not int or note['time'] < 0
                or type(note['length']) is not int or note['length'] <= 0
                or type(note['velocity']) not in (int, float) or not math.isfinite(note['velocity'])
                or not 0 <= note['velocity'] <= 1):
            return FreshnessStatus.INVALID, 'READBACK_INVALID'
    started, completed = response.get('sample_started_monotonic_ns'), response.get('sample_completed_monotonic_ns')
    if type(started) is not int or type(completed) is not int or started < 0 or completed < started:
        return FreshnessStatus.INVALID, 'READBACK_INVALID'
    written = response.get('response_written_at')
    if type(written) not in (int, float) or not math.isfinite(written) or written <= 0:
        return FreshnessStatus.INVALID, 'READBACK_INVALID'
    if previous is not None:
        if response['producer_epoch'] != previous['producer_epoch']:
            return FreshnessStatus.UNKNOWN, 'PRODUCER_EPOCH_CHANGED'
        if sequence <= previous['sample_sequence'] or response['producer_invocation'] == previous['producer_invocation']:
            return FreshnessStatus.STALE, 'PRODUCER_INVOCATION_REUSED'
    return FreshnessStatus.FRESH, None


def _identity_key(value, *, check_age=True):
    keys = ('controller_session', 'project_generation', 'pattern_number', 'pattern_name',
            'channel_index', 'channel_name', 'ppq')
    if not isinstance(value, dict) or any(value.get(key) is None for key in keys) or value.get('project_loading') is not False:
        raise ValueError('IDENTITY_UNAVAILABLE')
    from dawloop.adapters.fl_controller_identity import controller_snapshot
    from dawloop.runtime.identity import IdentityFieldStatus
    snapshot, status = controller_snapshot(value)
    if any(status.get(key) != IdentityFieldStatus.AVAILABLE for key in ('pattern_index', 'pattern_name', 'channel_index', 'channel_name', 'ppq')):
        raise ValueError('IDENTITY_UNAVAILABLE')
    if check_age:
        age = (datetime.now(timezone.utc) - snapshot.pattern_index.observed_at).total_seconds()
        if not 0 <= age <= .25:
            raise ValueError('IDENTITY_STALE')
    return tuple(value[key] for key in keys)


def _expected_identity(request, identity):
    _identity_key(identity)
    return (identity['pattern_number'], identity['pattern_name'], identity['channel_index'], identity['channel_name']) == (
        request.expected_pattern_index, request.expected_pattern_name, request.expected_channel_index, request.expected_channel_name)


class FreshSnapshotClient:
    def __init__(self, root=None, *, timeout=10):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError('快照超时必须大于零且不超过六十秒')
        self.root = Path(root) if root else Path(tempfile.gettempdir()) / 'DAWLoop_RuntimeV2_FreshSnapshot'
        self.timeout = timeout
        self.previous = None
        self.poisoned = False
        self.lock = asyncio.Lock()

    async def request_piano_roll_snapshot(self, request, *, read_identity, trigger):
        async with self.lock:
            result = SnapshotResult(FreshnessStatus.UNKNOWN)
            result.latency = dict.fromkeys(('identity_before_ms', 'request_write_ms', 'trigger_ms',
                                          'producer_ms', 'response_wait_ms', 'parse_ms', 'identity_after_ms', 'total_ms'))
            started = time.monotonic()
            lock_path = self.root / 'client.lock'
            descriptor = None
            try:
                if self.poisoned:
                    result.error_code = 'SNAPSHOT_CLIENT_POISONED'
                    return result
                self.root.mkdir(parents=True, exist_ok=True)
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                for name in ('snapshot_request.json', 'snapshot_response.json', 'producer_state.json'):
                    path = self.root / name
                    if path.exists():
                        try:
                            existing = json.loads(path.read_text(encoding='utf-8'))
                        except (OSError, ValueError, UnicodeError):
                            result.freshness, result.error_code = FreshnessStatus.INVALID, 'READBACK_INVALID'
                            return result
                        if isinstance(existing, dict) and (existing.get('request_id') == request.request_id
                                                          or existing.get('generation') == request.generation):
                            result.freshness, result.error_code = FreshnessStatus.STALE, 'REQUEST_REUSED'
                            return result
                phase = time.monotonic()
                result.identity_before = await read_identity()
                result.latency['identity_before_ms'] = (time.monotonic() - phase) * 1000
                if not _expected_identity(request, result.identity_before):
                    result.error_code = 'TARGET_CHANGED'
                    return result
                phase = time.monotonic()
                atomic_write(self.root / 'snapshot_request.json', asdict(request))
                result.latency['request_write_ms'] = (time.monotonic() - phase) * 1000
                phase = time.monotonic()
                observation = trigger()
                if inspect.isawaitable(observation):
                    await observation
                result.latency['trigger_ms'] = (time.monotonic() - phase) * 1000
                phase = time.monotonic()
                deadline = phase + self.timeout
                while time.monotonic() < deadline:
                    raw = None
                    try:
                        raw = (self.root / 'snapshot_response.json').read_text(encoding='utf-8')
                    except FileNotFoundError:
                        pass
                    except (OSError, ValueError, UnicodeError):
                        result.freshness, result.error_code = FreshnessStatus.INVALID, 'READBACK_INVALID'
                        result.latency['response_wait_ms'] = (time.monotonic() - phase) * 1000
                        return result
                    response = None
                    if raw is not None:
                        parse_started = time.monotonic()
                        try:
                            response = json.loads(raw)
                        except ValueError:
                            result.freshness, result.error_code = FreshnessStatus.INVALID, 'READBACK_INVALID'
                            result.latency['response_wait_ms'] = (time.monotonic() - phase) * 1000
                            return result
                        finally:
                            result.latency['parse_ms'] = (result.latency['parse_ms'] or 0) + (time.monotonic() - parse_started) * 1000
                    if response is not None:
                        state, code = validate_response(request, response, previous=self.previous)
                        if state != FreshnessStatus.STALE:
                            result.freshness, result.error_code = state, code
                            if state != FreshnessStatus.FRESH:
                                result.latency['response_wait_ms'] = (time.monotonic() - phase) * 1000
                                return result
                            result.snapshot = response
                            self.previous = response
                            result.latency['producer_ms'] = (response['sample_completed_monotonic_ns'] - response['sample_started_monotonic_ns']) / 1_000_000
                            break
                    await asyncio.sleep(.01)
                else:
                    self.poisoned = True
                    result.freshness, result.error_code = FreshnessStatus.TIMEOUT, 'SNAPSHOT_TIMEOUT'
                    result.latency['response_wait_ms'] = (time.monotonic() - phase) * 1000
                    return result
                result.latency['response_wait_ms'] = (time.monotonic() - phase) * 1000
                phase = time.monotonic()
                result.identity_after = await read_identity()
                result.latency['identity_after_ms'] = (time.monotonic() - phase) * 1000
                if (not _expected_identity(request, result.identity_after)
                        or _identity_key(result.identity_before, check_age=False) != _identity_key(result.identity_after, check_age=False)
                        or result.snapshot['ppq'] != result.identity_before['ppq']):
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
                if descriptor is not None:
                    os.close(descriptor)
                    lock_path.unlink(missing_ok=True)
                result.latency['total_ms'] = (time.monotonic() - started) * 1000


def install_snapshot_exporter(settings_dir: Path, *, reviewed_previous_hash=None, exporter=EXPORTER):
    destination = settings_dir / 'Piano roll scripts' / exporter.name
    source = exporter.read_bytes()
    if destination.exists():
        previous = destination.read_bytes()
        if previous != source:
            if reviewed_previous_hash is None or hashlib.sha256(previous).hexdigest() != reviewed_previous_hash:
                raise FileExistsError('现有同名导出器不同，拒绝覆盖')
            backup = destination.with_name(destination.name + '.bak-' + reviewed_previous_hash[:12])
            with backup.open('xb') as stream:
                stream.write(previous)
            temporary = destination.with_name(destination.name + '.' + uuid4().hex + '.tmp')
            try:
                with temporary.open('xb') as stream:
                    stream.write(source)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(source)
    return {'script_name': destination.name, 'sha256': hashlib.sha256(source).hexdigest(),
            'write_queue_reachable': False}
