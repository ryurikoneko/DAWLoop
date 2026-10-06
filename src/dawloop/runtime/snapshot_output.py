"""固定输出探针的受控事务；超时后的未决状态跨客户端重建保留。"""

import asyncio
from dataclasses import dataclass, field
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from .snapshot import EXPORTER, atomic_write


OUTPUT_PROBE = EXPORTER.with_name('DAWLoop Output Only Probe.pyscript')
OUTPUT_PROBE_SHA256 = '47dd6123b375908762c0e6bb6654b2e87bf231b502a45936f361d9e986f2f81a'


@dataclass
class FreshnessEvidence:
    artifact_absent_before_dispatch: bool = False
    single_flight: bool = False
    no_pending_invocation: bool = False
    dispatch_observed: bool = False
    invocation_completed: bool = False
    artifact_created_after_dispatch: bool = False
    snapshot_id: str | None = None
    snapshot_id_new: bool = False
    valid_payload: bool = False


@dataclass
class OutputSnapshotResult:
    freshness: str = 'UNKNOWN'
    snapshot: dict | None = None
    evidence: FreshnessEvidence = field(default_factory=FreshnessEvidence)
    latency: dict = field(default_factory=dict)
    error_code: str | None = None
    target_bound: bool = False


def validate_output_probe(value):
    if (not isinstance(value, dict) or set(value) != {'protocol_version', 'producer', 'snapshot_id'}
            or type(value.get('protocol_version')) is not int or value['protocol_version'] != 1
            or value.get('producer') != 'dawloop_piano_roll_snapshot'):
        return False
    identifier = value.get('snapshot_id')
    return (isinstance(identifier, str) and len(identifier) == 32
            and all(c in '0123456789abcdef' for c in identifier))


async def _resolve(value):
    return await value if inspect.isawaitable(value) else value


class OutputProbeClient:
    def __init__(self, root=None, *, timeout=5):
        if type(timeout) not in (int, float) or not 0 < timeout <= 60:
            raise ValueError('输出等待时间无效')
        self.root = Path(root) if root else Path(tempfile.gettempdir()) / 'DAWLoop_RuntimeV2_OutputSnapshot'
        self.timeout = timeout
        self.lock = asyncio.Lock()

    async def run(self, *, installed_probe, confirm_idle, trigger):
        async with self.lock:
            result = OutputSnapshotResult()
            result.latency = dict.fromkeys(('preparation_ms', 'trigger_ms', 'response_wait_ms', 'parse_ms', 'total_ms'))
            started = time.monotonic()
            descriptor = None
            lock_path = self.root / 'client.lock'
            artifact = self.root / 'snapshot.json'
            ledger = self.root / 'client_invocation.json'
            try:
                for source in (OUTPUT_PROBE, Path(installed_probe)):
                    if hashlib.sha256(source.read_bytes()).hexdigest() != OUTPUT_PROBE_SHA256:
                        result.error_code = 'FIXED_PROBE_HASH_MISMATCH'
                        return result
                self.root.mkdir(parents=True, exist_ok=True)
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                result.evidence.single_flight = True
                state = json.loads(ledger.read_text(encoding='utf-8')) if ledger.exists() else None
                if state is not None and (not isinstance(state, dict) or state.get('status') != 'IDLE'):
                    result.error_code = 'PRIOR_INVOCATION_PENDING_OR_UNKNOWN'
                    return result
                if state is None and artifact.exists():
                    result.error_code = 'PRIOR_INVOCATION_UNKNOWN'
                    return result
                idle = await _resolve(confirm_idle())
                if idle is not True:
                    result.error_code = 'NO_PENDING_INVOCATION_UNPROVEN'
                    return result
                result.evidence.no_pending_invocation = True
                seen = state['seen_snapshot_ids'] if state else []
                if not isinstance(seen, list) or any(not isinstance(item, str) for item in seen):
                    result.error_code = 'INVOCATION_LEDGER_INVALID'
                    return result
                phase = time.monotonic()
                if artifact.exists():
                    archive = self.root / 'archive'
                    archive.mkdir(exist_ok=True)
                    artifact.replace(archive / (uuid4().hex + '.json'))
                if artifact.exists():
                    result.error_code = 'ARTIFACT_NOT_ABSENT'
                    return result
                result.evidence.artifact_absent_before_dispatch = True
                # 未决记录先持久化；崩溃、取消或超时不能通过重建客户端假装没有迟到执行。
                atomic_write(ledger, {'status': 'PENDING', 'seen_snapshot_ids': seen, 'probe_sha256': OUTPUT_PROBE_SHA256})
                result.latency['preparation_ms'] = (time.monotonic() - phase) * 1000
                phase = time.monotonic()
                observation = await _resolve(trigger())
                result.latency['trigger_ms'] = (time.monotonic() - phase) * 1000
                if not isinstance(observation, dict) or type(observation.get('dispatch_count')) is not int or observation['dispatch_count'] != 1:
                    result.error_code = 'SINGLE_DISPATCH_UNPROVEN'
                    return result
                result.evidence.dispatch_observed = observation.get('dispatch_observed') is True
                result.evidence.invocation_completed = observation.get('invocation_completed') is True
                if observation.get('host_error'):
                    result.error_code = observation['host_error']
                    return result
                if not result.evidence.dispatch_observed or not result.evidence.invocation_completed:
                    result.error_code = 'INVOCATION_COMPLETION_UNPROVEN'
                    return result
                phase = time.monotonic()
                deadline = phase + self.timeout
                partial = False
                while time.monotonic() < deadline:
                    try:
                        raw = artifact.read_bytes()
                    except FileNotFoundError:
                        await asyncio.sleep(.01)
                        continue
                    result.evidence.artifact_created_after_dispatch = True
                    parse_started = time.monotonic()
                    try:
                        value = json.loads(raw.decode('utf-8'))
                    except (ValueError, UnicodeError):
                        partial = True
                        value = None
                    finally:
                        result.latency['parse_ms'] = (result.latency['parse_ms'] or 0) + (time.monotonic() - parse_started) * 1000
                    if value is None:
                        await asyncio.sleep(.01)
                        continue
                    result.evidence.valid_payload = validate_output_probe(value)
                    if not result.evidence.valid_payload:
                        result.freshness, result.error_code = 'INVALID', 'OUTPUT_PAYLOAD_INVALID'
                        break
                    result.evidence.snapshot_id = value['snapshot_id']
                    result.evidence.snapshot_id_new = value['snapshot_id'] not in seen
                    if not result.evidence.snapshot_id_new:
                        result.freshness, result.error_code = 'INVALID', 'SNAPSHOT_ID_REUSED'
                        break
                    atomic_write(ledger, {'status': 'IDLE', 'seen_snapshot_ids': seen + [value['snapshot_id']],
                                          'probe_sha256': OUTPUT_PROBE_SHA256})
                    result.freshness, result.snapshot = 'FRESH_FOR_TRANSACTION', value
                    break
                else:
                    result.freshness = 'INVALID' if partial else 'TIMEOUT'
                    result.error_code = 'OUTPUT_PAYLOAD_INCOMPLETE' if partial else 'SNAPSHOT_TIMEOUT'
                result.latency['response_wait_ms'] = (time.monotonic() - phase) * 1000
                return result
            except asyncio.CancelledError:
                raise
            except Exception as error:
                result.error_code = type(error).__name__
                return result
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                    lock_path.unlink(missing_ok=True)
                result.latency['total_ms'] = (time.monotonic() - started) * 1000
