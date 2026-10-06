from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import statistics

from .models import DataStatus, ExecutionStatus, ToolSafetyClassification


class BackendState(str, Enum):
    CONNECTED = 'CONNECTED'
    DEGRADED = 'DEGRADED'
    DISCONNECTED = 'DISCONNECTED'
    POISONED = 'POISONED'


class CertificationState(str, Enum):
    DISCOVERED = 'DISCOVERED'
    CLASSIFIED = 'CLASSIFIED'
    OFFLINE_TESTED = 'OFFLINE_TESTED'
    LIVE_TESTED = 'LIVE_TESTED'
    LIVE_CERTIFIED = 'LIVE_CERTIFIED'
    QUARANTINED = 'QUARANTINED'
    UNSUPPORTED = 'UNSUPPORTED'


def tool_contract_hash(tool):
    # 描述改变也使认证失效，不能只比较工具名称。
    payload = json.dumps(tool, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


@dataclass
class CapabilityHealth:
    state: CertificationState
    schema_hash: str
    fl_version: str | None = None
    last_live_success: str | None = None
    last_error: str | None = None
    evidence_level: str = 'UNTESTED'
    evidence: str | None = None
    median_latency: float | None = None
    p95_latency: float | None = None
    scope: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    def observe(self, result, latency_ms, *, fl_version=None):
        if not math.isfinite(latency_ms) or latency_ms < 0:
            raise ValueError('调用耗时无效')
        self.fl_version = fl_version or self.fl_version
        if result.execution_status == ExecutionStatus.SUCCESS and result.data_status == DataStatus.VALID:
            self.last_live_success = datetime.now(timezone.utc).isoformat()
            if self.state not in {CertificationState.QUARANTINED, CertificationState.LIVE_CERTIFIED}:
                self.state = CertificationState.LIVE_TESTED
            self.last_error = None
        else:
            self.last_error = result.error_code or result.execution_status.value
            if result.data_status in {DataStatus.INVALID, DataStatus.TOOL_ERROR}:
                self.state = CertificationState.QUARANTINED


def certify_read(capability, rows, *, fl_version, evidence, scope):
    if capability.safety != ToolSafetyClassification.READ_ONLY or not capability.dispatch_supported:
        raise ValueError('只认证已实现的只读能力')
    if not fl_version or not evidence or not scope or not rows:
        raise ValueError('认证缺少版本、来源、范围或现场数据')
    if any(row.get('tool') != capability.raw_tool['name'] or row.get('execution_status') != 'SUCCESS'
           or row.get('data_status') != 'VALID' or row.get('response_status') != 'SUCCESS' for row in rows):
        raise ValueError('无效读取不能认证')
    times = sorted(row['total_ms'] for row in rows)
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in times):
        raise ValueError('认证耗时无效')
    return CapabilityHealth(CertificationState.LIVE_CERTIFIED, tool_contract_hash(capability.raw_tool),
                            fl_version=fl_version, evidence_level='LIVE_CERTIFIED', evidence=evidence,
                            last_live_success=rows[-1].get('observed_at'),
                            median_latency=statistics.median(times), p95_latency=times[math.ceil(len(times)*.95)-1],
                            scope=scope)
