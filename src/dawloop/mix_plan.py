# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""混音离线合同与语义编译；本模块不连接或写入宿主。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math


SCHEMA_VERSION = "dawloop-mix-plan-v1"


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _text(value):
    return type(value) is str and bool(value.strip())


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _unit(value):
    return _number(value) and 0 <= value <= 1


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _digest(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _load(cls, value, **conversions):
    _require(type(value) is dict and set(value) == {f.name for f in fields(cls)}, "FIELDS_INVALID")
    row = dict(value)
    for key, convert in conversions.items():
        row[key] = convert(row[key])
    return cls(**row)


def _tuple(value, convert=lambda x: x):
    _require(type(value) is list, "ARRAY_REQUIRED")
    return tuple(convert(item) for item in value)


@dataclass(frozen=True)
class PluginFingerprint:
    plugin_name: str
    api_version: int
    parameter_names: tuple[str, ...]
    plugin_version: str | None = None
    plugin_format: str | None = None

    def __post_init__(self):
        _require(_text(self.plugin_name) and _integer(self.api_version, 26), "PLUGIN_IDENTITY_INVALID")
        _require(type(self.parameter_names) is tuple and all(_text(n) for n in self.parameter_names),
                 "PARAMETER_LAYOUT_INVALID")
        _require(all(v is None or _text(v) for v in (self.plugin_version, self.plugin_format)),
                 "OPTIONAL_IDENTITY_INVALID")

    @property
    def layout_hash(self):
        return _hash(asdict(self))

    @classmethod
    def from_dict(cls, value):
        return _load(cls, value, parameter_names=_tuple)


def decode_plugin_scan(response):
    """拒绝截断或旧响应；显示字符串缺失不冒充核心参数读取失败。"""
    _require(type(response) is dict and response.get("schema_version") == "plugin-parameter-scan-v1",
             "SCAN_CONTRACT_UNSUPPORTED")
    _require(response.get("success", True) is True and response.get("error") is None, "SCAN_FAILED")
    count = response.get("parameter_count")
    _require(response.get("complete") is True and response.get("truncated") is False
             and response.get("errors") == [] and _integer(count)
             and _integer(response.get("parameter_count_after"))
             and response["parameter_count_after"] == count, "SCAN_INCOMPLETE")
    rows = response.get("params")
    _require(type(rows) is list and len(rows) == count, "SCAN_COUNT_MISMATCH")
    names, values = [], []
    for index, row in enumerate(rows):
        _require(type(row) is dict and type(row.get("index")) is int and row["index"] == index
                 and _text(row.get("name")) and _unit(row.get("value")), "SCAN_PARAMETER_INVALID")
        _require(row.get("value_string") is None or type(row["value_string"]) is str,
                 "DISPLAY_VALUE_INVALID")
        names.append(row["name"])
        values.append(row["value"])
    fingerprint = PluginFingerprint(response.get("plugin_name"), response.get("api_version"), tuple(names))
    return fingerprint, tuple(values)


@dataclass(frozen=True)
class MixTarget:
    controller_build_id: str
    controller_session_id: str
    project_generation: int
    host_generation: str
    track_index: int
    slot_index: int | None
    chain_revision: str

    def __post_init__(self):
        _require(all(_text(v) for v in (self.controller_build_id, self.controller_session_id,
                 self.host_generation, self.chain_revision)), "TARGET_CONTEXT_REQUIRED")
        _require(_integer(self.project_generation) and _integer(self.track_index, 1), "TARGET_RANGE_INVALID")
        _require(self.slot_index is None or _integer(self.slot_index), "SLOT_INVALID")

    @classmethod
    def from_dict(cls, value):
        return _load(cls, value)


@dataclass(frozen=True)
class MixSourceSnapshot:
    request_id: str
    target: MixTarget
    clock_domain: str
    capture_started_at: float
    capture_completed_at: float
    fingerprint: PluginFingerprint | None
    parameter_values: tuple[float, ...]
    fader_value: float | None
    fader_db: float | None
    calibration_hash: str | None

    def __post_init__(self):
        _require(_text(self.request_id) and _text(self.clock_domain) and type(self.target) is MixTarget,
                 "SNAPSHOT_CONTEXT_INVALID")
        _require(_number(self.capture_started_at) and _number(self.capture_completed_at)
                 and 0 <= self.capture_started_at <= self.capture_completed_at, "CAPTURE_INTERVAL_INVALID")
        _require(type(self.parameter_values) is tuple and all(_unit(v) for v in self.parameter_values),
                 "PARAMETER_VALUES_INVALID")
        if self.target.slot_index is None:
            _require(self.fingerprint is None and not self.parameter_values and _unit(self.fader_value)
                     and _number(self.fader_db) and _digest(self.calibration_hash), "FADER_SNAPSHOT_INVALID")
        else:
            _require(type(self.fingerprint) is PluginFingerprint
                     and len(self.parameter_values) == len(self.fingerprint.parameter_names)
                     and self.fader_value is None and self.fader_db is None and self.calibration_hash is None,
                     "PLUGIN_SNAPSHOT_INVALID")

    @property
    def snapshot_hash(self):
        return _hash(asdict(self))

    @classmethod
    def from_dict(cls, value):
        return _load(cls, value, target=MixTarget.from_dict,
            fingerprint=lambda v: None if v is None else PluginFingerprint.from_dict(v), parameter_values=_tuple)


@dataclass(frozen=True)
class ParameterMapping:
    semantic: str
    parameter_index: int
    expected_name: str
    unit: str
    physical_min: float
    physical_max: float
    normalized_min: float
    normalized_max: float
    curve: str
    tolerance: float

    def __post_init__(self):
        units = {"frequency": "Hz", "gain": "dB", "q": "Q"}
        _require(type(self.semantic) is str and self.semantic in units
                 and self.unit == units[self.semantic], "SEMANTIC_UNIT_INVALID")
        _require(_integer(self.parameter_index) and _text(self.expected_name), "PARAMETER_MAPPING_INVALID")
        _require(_number(self.physical_min) and _number(self.physical_max)
                 and self.physical_min < self.physical_max, "PHYSICAL_RANGE_INVALID")
        _require(_unit(self.normalized_min) and _unit(self.normalized_max)
                 and self.normalized_min != self.normalized_max, "NORMALIZED_RANGE_INVALID")
        _require(type(self.curve) is str and self.curve in ("linear", "log") and _number(self.tolerance)
                 and 0 < self.tolerance <= 0.01, "CONVERSION_INVALID")
        _require((self.semantic == "gain" or self.physical_min > 0)
                 and (self.curve != "log" or self.physical_min > 0), "LOG_DOMAIN_INVALID")

    def encode(self, value):
        _require(_number(value) and self.physical_min <= value <= self.physical_max, "PHYSICAL_VALUE_OUT_OF_RANGE")
        ratio = ((value - self.physical_min) / (self.physical_max - self.physical_min)
                 if self.curve == "linear" else
                 math.log(value / self.physical_min) / math.log(self.physical_max / self.physical_min))
        return self.normalized_min + ratio * (self.normalized_max - self.normalized_min)

    def decode(self, value):
        _require(_unit(value) and min(self.normalized_min, self.normalized_max) <= value
                 <= max(self.normalized_min, self.normalized_max), "NORMALIZED_VALUE_OUT_OF_RANGE")
        ratio = (value - self.normalized_min) / (self.normalized_max - self.normalized_min)
        return (self.physical_min + ratio * (self.physical_max - self.physical_min)
                if self.curve == "linear" else self.physical_min * (self.physical_max / self.physical_min) ** ratio)


@dataclass(frozen=True)
class ParameterCondition:
    parameter_index: int
    expected_name: str
    expected_value: float
    tolerance: float

    def __post_init__(self):
        _require(_integer(self.parameter_index) and _text(self.expected_name) and _unit(self.expected_value)
                 and _number(self.tolerance) and 0 < self.tolerance <= 0.01, "PARAMETER_CONDITION_INVALID")


@dataclass(frozen=True)
class PluginCapabilityProfile:
    profile_id: str
    adapter_version: str
    fingerprint: PluginFingerprint
    band_id: str
    mappings: tuple[ParameterMapping, ...]
    conditions: tuple[ParameterCondition, ...]
    provenance: str

    def __post_init__(self):
        _require(all(_text(v) for v in (self.profile_id, self.adapter_version, self.band_id, self.provenance))
                 and type(self.fingerprint) is PluginFingerprint, "CAPABILITY_IDENTITY_INVALID")
        _require(type(self.mappings) is tuple and all(type(m) is ParameterMapping for m in self.mappings)
                 and len(self.mappings) == 3 and {m.semantic for m in self.mappings} == {"frequency", "gain", "q"}
                 and len({m.parameter_index for m in self.mappings}) == 3, "EQ_CAPABILITY_INVALID")
        _require(type(self.conditions) is tuple and all(type(c) is ParameterCondition for c in self.conditions)
                 and len({c.parameter_index for c in self.conditions}) == len(self.conditions), "CONDITIONS_INVALID")
        _require(not ({m.parameter_index for m in self.mappings} & {c.parameter_index for c in self.conditions}),
                 "MAPPING_CONDITION_CONFLICT")
        for item in self.mappings + self.conditions:
            _require(item.parameter_index < len(self.fingerprint.parameter_names)
                     and self.fingerprint.parameter_names[item.parameter_index] == item.expected_name,
                     "MAPPING_LAYOUT_MISMATCH")

    @property
    def profile_hash(self):
        return _hash(asdict(self))

    @classmethod
    def from_dict(cls, value):
        return _load(cls, value, fingerprint=PluginFingerprint.from_dict,
            mappings=lambda v: _tuple(v, lambda x: _load(ParameterMapping, x)),
            conditions=lambda v: _tuple(v, lambda x: _load(ParameterCondition, x)))

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, allow_nan=False)

    @classmethod
    def from_json(cls, value):
        return cls.from_dict(json.loads(value))


@dataclass(frozen=True)
class FaderAction:
    action_id: str
    snapshot_hash: str
    delta_db: float
    max_change_db: float

    def __post_init__(self):
        _require(_text(self.action_id) and _digest(self.snapshot_hash), "ACTION_IDENTITY_INVALID")
        _require(_number(self.delta_db) and _number(self.max_change_db)
                 and 0 < self.max_change_db <= 3 and abs(self.delta_db) <= self.max_change_db,
                 "FADER_CHANGE_LIMIT")


@dataclass(frozen=True)
class EQAction:
    action_id: str
    snapshot_hash: str
    profile_hash: str
    band_id: str
    frequency_hz: float
    gain_db: float
    q: float
    max_gain_change_db: float

    def __post_init__(self):
        _require(_text(self.action_id) and _digest(self.snapshot_hash) and _digest(self.profile_hash)
                 and _text(self.band_id), "ACTION_IDENTITY_INVALID")
        _require(_number(self.frequency_hz) and self.frequency_hz > 0 and _number(self.gain_db)
                 and _number(self.q) and self.q > 0 and _number(self.max_gain_change_db)
                 and 0 < self.max_gain_change_db <= 3, "EQ_VALUE_INVALID")


@dataclass(frozen=True)
class MixPlan:
    schema_version: str
    operation_id: str
    plan_id: str
    mix_goal: str
    analysis_start_seconds: float
    analysis_end_seconds: float
    capture_config_hash: str
    actions: tuple[FaderAction | EQAction, ...]
    parameter_write_budget: int
    provenance: str

    def __post_init__(self):
        _require(self.schema_version == SCHEMA_VERSION and all(_text(v) for v in
            (self.operation_id, self.plan_id, self.mix_goal, self.provenance)), "PLAN_IDENTITY_INVALID")
        _require(_number(self.analysis_start_seconds) and _number(self.analysis_end_seconds)
                 and 0 <= self.analysis_start_seconds < self.analysis_end_seconds
                 and _digest(self.capture_config_hash), "ANALYSIS_CONTEXT_INVALID")
        _require(type(self.actions) is tuple and 1 <= len(self.actions) <= 4
                 and all(type(a) in (FaderAction, EQAction) for a in self.actions)
                 and len({a.action_id for a in self.actions}) == len(self.actions), "ACTIONS_INVALID")
        _require(_integer(self.parameter_write_budget, 1) and self.parameter_write_budget <= 12,
                 "WRITE_BUDGET_INVALID")
        _require(sum(1 if type(a) is FaderAction else 3 for a in self.actions) <= self.parameter_write_budget,
                 "WRITE_BUDGET_EXCEEDED")

    def to_json(self):
        row = asdict(self)
        row["actions"] = [{"kind": "fader" if type(a) is FaderAction else "eq_bell", **asdict(a)}
                          for a in self.actions]
        return json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False)

    @classmethod
    def from_json(cls, value):
        def action(row):
            _require(type(row) is dict and row.get("kind") in ("fader", "eq_bell"), "UNSUPPORTED_ACTION")
            return _load(FaderAction if row["kind"] == "fader" else EQAction,
                         {k: v for k, v in row.items() if k != "kind"})
        return _load(cls, json.loads(value), actions=lambda v: _tuple(v, action))


@dataclass(frozen=True)
class CompiledParameterChange:
    action_id: str
    target: MixTarget
    parameter_index: int | None
    expected_name: str
    expected_before: float
    absolute_value: float
    tolerance: float

    def __post_init__(self):
        _require(_text(self.action_id) and type(self.target) is MixTarget and _text(self.expected_name),
                 "COMPILED_TARGET_INVALID")
        _require((self.parameter_index is None and self.target.slot_index is None)
                 or (_integer(self.parameter_index) and self.target.slot_index is not None),
                 "COMPILED_PARAMETER_INVALID")
        _require(_unit(self.expected_before) and _unit(self.absolute_value)
                 and _number(self.tolerance) and 0 < self.tolerance <= 0.01, "COMPILED_VALUE_INVALID")


@dataclass(frozen=True)
class CompiledMixPlan:
    plan_hash: str
    changes: tuple[CompiledParameterChange, ...]
    execution_permission: str = "OFFLINE_ONLY"

    def __post_init__(self):
        _require(_digest(self.plan_hash) and type(self.changes) is tuple and bool(self.changes)
                 and all(type(c) is CompiledParameterChange for c in self.changes)
                 and self.execution_permission == "OFFLINE_ONLY", "COMPILED_PLAN_INVALID")


def compile_mix_plan(plan, snapshots, profiles=(), *, fader_calibrations=()):
    """原值及身份进入绝对目标；未知映射拒绝整计划，不产生宿主操作。"""
    _require(type(plan) is MixPlan and type(snapshots) is tuple and type(profiles) is tuple,
             "COMPILE_INPUT_INVALID")
    _require(all(type(s) is MixSourceSnapshot for s in snapshots)
             and all(type(p) is PluginCapabilityProfile for p in profiles), "COMPILE_INPUT_INVALID")
    sources = {s.snapshot_hash: s for s in snapshots}
    adapters = {p.profile_hash: p for p in profiles}
    _require(len(sources) == len(snapshots) and len(adapters) == len(profiles), "DUPLICATE_SOURCE_OR_PROFILE")
    changes, touched = [], set()
    for action in plan.actions:
        _require(action.snapshot_hash in sources, "SOURCE_SNAPSHOT_MISSING")
        source = sources[action.snapshot_hash]
        if type(action) is FaderAction:
            from dawloop.production.mix import FaderCalibration
            _require(source.target.slot_index is None, "FADER_TARGET_MISMATCH")
            candidates = [c for c in fader_calibrations if type(c) is FaderCalibration
                          and _hash(asdict(c)) == source.calibration_hash]
            _require(len(candidates) == 1, "FADER_CALIBRATION_MISSING_OR_AMBIGUOUS")
            calibration = candidates[0]
            _require(calibration.points[0][0] <= source.fader_value <= calibration.points[-1][0]
                     and abs(calibration.db_for_value(source.fader_value) - source.fader_db) <= 1e-6,
                     "FADER_BASELINE_MISMATCH")
            target_db = source.fader_db + action.delta_db
            _require(calibration.points[0][1] <= target_db <= calibration.points[-1][1], "FADER_TARGET_OUT_OF_RANGE")
            changes.append(CompiledParameterChange(action.action_id, source.target, None, "fader",
                source.fader_value, calibration.value_for_db(target_db), 1e-6))
        else:
            _require(action.profile_hash in adapters, "PLUGIN_CAPABILITY_UNSUPPORTED")
            profile = adapters[action.profile_hash]
            _require(source.fingerprint == profile.fingerprint and action.band_id == profile.band_id,
                     "PLUGIN_FINGERPRINT_OR_BAND_MISMATCH")
            for condition in profile.conditions:
                _require(abs(source.parameter_values[condition.parameter_index] - condition.expected_value)
                         <= condition.tolerance, "PLUGIN_MODE_PRECONDITION_FAILED")
            values = {"frequency": action.frequency_hz, "gain": action.gain_db, "q": action.q}
            for mapping in profile.mappings:
                before = source.parameter_values[mapping.parameter_index]
                original = mapping.decode(before)
                if mapping.semantic == "gain":
                    _require(abs(action.gain_db - original) <= action.max_gain_change_db + 1e-9,
                             "EQ_GAIN_CHANGE_LIMIT")
                after = mapping.encode(values[mapping.semantic])
                changes.append(CompiledParameterChange(action.action_id, source.target, mapping.parameter_index,
                    mapping.expected_name, before, after, mapping.tolerance))
        for change in changes:
            key = (change.target.track_index, change.target.slot_index, change.parameter_index)
            if change.action_id == action.action_id:
                _require(key not in touched, "DUPLICATE_PARAMETER_WRITE")
                touched.add(key)
    contexts = {(s.target.controller_build_id, s.target.controller_session_id,
                 s.target.project_generation, s.target.host_generation) for s in snapshots}
    _require(len(contexts) == 1, "MIX_CONTEXT_DISAGREEMENT")
    return CompiledMixPlan(_hash(json.loads(plan.to_json())), tuple(changes))


@dataclass(frozen=True)
class MixExecutionResult:
    operation_id: str
    plan_hash: str
    terminal_state: str
    attempted_parameters: int
    matched_parameters: int
    failed_parameters: int
    unknown_parameters: int
    audio_comparison: str
    human_audition: str
    restoration: str
    binding_strength: str = "SCOPE_BOUND_NOT_EXACT_INSTANCE"

    def __post_init__(self):
        _require(_text(self.operation_id) and _digest(self.plan_hash), "RESULT_IDENTITY_INVALID")
        _require(self.terminal_state in ("OFFLINE_COMPILED", "STOPPED_BEFORE_APPLY", "PARTIAL_APPLY",
                 "APPLIED_READBACK_MATCHED", "STOPPED_AFTER_APPLY_UNKNOWN"), "RESULT_STATE_INVALID")
        _require(all(_integer(v) for v in (self.attempted_parameters, self.matched_parameters,
                 self.failed_parameters, self.unknown_parameters)) and self.attempted_parameters <= 12
                 and self.matched_parameters + self.failed_parameters + self.unknown_parameters
                 == self.attempted_parameters, "RESULT_COUNTS_INVALID")
        _require(self.audio_comparison in ("NOT_MEASURED", "MEASURED_CHANGED", "MEASURED_UNCHANGED")
                 and self.human_audition in ("NOT_REPORTED", "PREFERRED", "NOT_PREFERRED")
                 and self.restoration in ("NOT_ATTEMPTED", "PARAMETERS_RESTORED", "FAILED", "UNKNOWN")
                 and self.binding_strength == "SCOPE_BOUND_NOT_EXACT_INSTANCE", "RESULT_EVIDENCE_INVALID")
        if self.terminal_state in ("OFFLINE_COMPILED", "STOPPED_BEFORE_APPLY"):
            _require(self.attempted_parameters == 0 and self.audio_comparison == "NOT_MEASURED"
                     and self.human_audition == "NOT_REPORTED" and self.restoration == "NOT_ATTEMPTED",
                     "OFFLINE_RESULT_CANNOT_CLAIM_APPLICATION")
        if self.terminal_state == "APPLIED_READBACK_MATCHED":
            _require(self.attempted_parameters > 0 and self.matched_parameters == self.attempted_parameters
                     and self.unknown_parameters == 0, "READBACK_RESULT_INCONSISTENT")
        if self.terminal_state == "PARTIAL_APPLY":
            _require(0 < self.matched_parameters < self.attempted_parameters, "PARTIAL_RESULT_INCONSISTENT")
        if self.terminal_state == "STOPPED_AFTER_APPLY_UNKNOWN":
            _require(self.unknown_parameters > 0, "UNKNOWN_RESULT_INCONSISTENT")

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, allow_nan=False)

    @classmethod
    def from_json(cls, value):
        return _load(cls, json.loads(value))
