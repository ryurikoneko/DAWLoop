from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any
from enum import Enum
import math


@dataclass(frozen=True)
class IdentityObservation:
    value: Any
    backend: str
    method: str
    observed_at: datetime
    context_binding: str
    index_basis: str | None = None

    def __post_init__(self):
        if self.value is None or not all(isinstance(value, str) and value.strip()
                                         for value in (self.backend, self.method, self.context_binding)):
            raise ValueError('未知身份使用空字段，不创建伪来源')
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError('身份观测时间必须含时区')


@dataclass(frozen=True)
class TargetIdentitySnapshot:
    project: IdentityObservation | None = None
    pattern_index: IdentityObservation | None = None
    pattern_name: IdentityObservation | None = None
    channel_index: IdentityObservation | None = None
    channel_name: IdentityObservation | None = None
    plugin_name: IdentityObservation | None = None
    piano_roll_target: IdentityObservation | None = None
    ppq: IdentityObservation | None = None
    project_title: IdentityObservation | None = None
    fl_version: IdentityObservation | None = None

    def __post_init__(self):
        observations = [getattr(self, field.name) for field in fields(self) if getattr(self, field.name) is not None]
        if any(not isinstance(value, IdentityObservation) for value in observations):
            raise TypeError('身份字段必须携带观测来源')
        if len({value.context_binding for value in observations}) > 1:
            raise ValueError('身份字段缺少共同上下文绑定')
        for name, minimum in (('pattern_index', 1), ('channel_index', 0), ('ppq', 1)):
            observation = getattr(self, name)
            if observation is not None and (type(observation.value) is not int or observation.value < minimum):
                raise ValueError('身份数字超出边界')
            if name.endswith('_index') and observation is not None and not observation.index_basis:
                raise ValueError('索引必须注明基准')
        for name in ('project', 'project_title', 'fl_version', 'pattern_name', 'channel_name', 'plugin_name'):
            observation = getattr(self, name)
            if observation is not None and (not isinstance(observation.value, str) or not observation.value.strip()):
                raise ValueError('身份名称必须是明确文本')


def compose_identity(*snapshots: TargetIdentitySnapshot, max_skew_seconds: float = 2.0) -> TargetIdentitySnapshot:
    if not math.isfinite(max_skew_seconds) or max_skew_seconds < 0:
        raise ValueError('时间偏差不能为负数')
    values = {}
    observations = []
    for snapshot in snapshots:
        for field in fields(snapshot):
            current = getattr(snapshot, field.name)
            if current is None:
                continue
            previous = values.get(field.name)
            if previous is not None and (previous.value != current.value or previous.index_basis != current.index_basis):
                raise ValueError('组合身份存在字段冲突')
            observations.append(current)
            # 保留已观测来源，不靠相同显示名称证明跨后端工程身份。
            values.setdefault(field.name, current)
    if observations:
        skew = (max(value.observed_at for value in observations) - min(value.observed_at for value in observations)).total_seconds()
        if skew > max_skew_seconds:
            raise ValueError('组合身份观测时间跨度过大')
    return TargetIdentitySnapshot(**values)


class IdentityFieldStatus(str, Enum):
    AVAILABLE = 'AVAILABLE'
    UNAVAILABLE = 'UNAVAILABLE'
    AMBIGUOUS = 'AMBIGUOUS'
    STALE = 'STALE'
    ERROR = 'ERROR'


@dataclass(frozen=True)
class CompositeTargetIdentity:
    snapshot: TargetIdentitySnapshot
    field_status: dict[str, IdentityFieldStatus]
    host_generation: str
    controller_session: str
    project_generation: str
    binding_evidence: str


@dataclass(frozen=True)
class TargetGuardToken:
    pattern_index: int
    channel_index: int
    ppq: int
    host_generation: str
    controller_session: str
    project_generation: str
    timestamp: datetime
    context_binding: str


def guard_identity(expected: TargetIdentitySnapshot, actual: CompositeTargetIdentity, *, now: datetime,
                   max_age_seconds=0.25) -> TargetGuardToken:
    if not math.isfinite(max_age_seconds) or max_age_seconds < 0 or now.tzinfo is None:
        raise ValueError('目标守卫时间无效')
    if not all((actual.host_generation, actual.controller_session, actual.project_generation, actual.binding_evidence)):
        raise ValueError('目标守卫缺少会话绑定')
    if actual.field_status.get('native_channel_mapping') != IdentityFieldStatus.AVAILABLE:
        raise ValueError('跨后端通道映射未确认')
    compare_target_identity(expected, actual.snapshot, actual.field_status, now=now, max_age_seconds=max_age_seconds)
    s = actual.snapshot
    observations = [getattr(s, f.name) for f in fields(s) if getattr(s, f.name) is not None]
    return TargetGuardToken(s.pattern_index.value, s.channel_index.value, s.ppq.value,
                            actual.host_generation, actual.controller_session, actual.project_generation,
                            min(item.observed_at for item in observations), s.pattern_index.context_binding)


def compare_target_identity(expected, snapshot, field_status, *, now, max_age_seconds=0.25):
    # 条件比较可独立测量，但不会签发绕过原生绑定检查的写入令牌。
    if not math.isfinite(max_age_seconds) or max_age_seconds < 0 or now.tzinfo is None:
        raise ValueError('目标守卫时间无效')
    for name in ('pattern_index', 'pattern_name', 'channel_index', 'channel_name', 'ppq'):
        wanted, observed = getattr(expected, name), getattr(snapshot, name)
        if wanted is None or observed is None or field_status.get(name) != IdentityFieldStatus.AVAILABLE:
            raise ValueError('目标身份不完整')
        if wanted.value != observed.value or wanted.index_basis != observed.index_basis or wanted.context_binding != observed.context_binding:
            raise ValueError('目标身份已变化')
    for f in fields(expected):
        wanted, observed = getattr(expected, f.name), getattr(snapshot, f.name)
        if wanted is not None and (observed is None or field_status.get(f.name) != IdentityFieldStatus.AVAILABLE
                                  or wanted.value != observed.value or wanted.index_basis != observed.index_basis
                                  or wanted.context_binding != observed.context_binding):
            raise ValueError('计划中的额外身份条件不匹配')
    observations = [getattr(snapshot, f.name) for f in fields(snapshot) if getattr(snapshot, f.name) is not None]
    if any(not 0 <= (now-item.observed_at).total_seconds() <= max_age_seconds for item in observations):
        raise ValueError('目标身份已过期')
