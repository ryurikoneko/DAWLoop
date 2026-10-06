from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from dawloop.note_plan import NotePlan


class ExecutionMode(str, Enum):
    FAST = "FAST"
    AUTO = "AUTO"
    VERIFIED = "VERIFIED"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NOT_DISPATCHED = "NOT_DISPATCHED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    READ_ERROR = "READ_ERROR"
    UNSUPPORTED = "UNSUPPORTED"


class DataStatus(str, Enum):
    NOT_CHECKED = "NOT_CHECKED"
    VALID = "VALID"
    INVALID = "INVALID"
    TOOL_ERROR = "TOOL_ERROR"


class ResponseStatus(str, Enum):
    TRANSPORT_SUCCESS = "TRANSPORT_SUCCESS"
    DECODE_ERROR = "DECODE_ERROR"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    SEMANTIC_ERROR = "SEMANTIC_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    TIMEOUT = "TIMEOUT"
    RESULT_UNKNOWN = "RESULT_UNKNOWN"
    SUCCESS = "SUCCESS"


class ScriptApplicationStatus(str, Enum):
    NOT_CHECKED = "NOT_CHECKED"
    SOURCE_ACCEPTED = "SOURCE_ACCEPTED"
    SCRIPT_APPLIED = "SCRIPT_APPLIED"
    SCRIPT_EFFECT_CONFIRMED = "SCRIPT_EFFECT_CONFIRMED"
    UNKNOWN = "UNKNOWN"


class ScriptCompletionStatus(str, Enum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    PENDING = "PENDING"
    CONFIRMED = "COMPLETION_CONFIRMED"
    UNKNOWN = "COMPLETION_UNKNOWN"


@dataclass(frozen=True)
class ScriptInvocationState:
    dispatched: bool = False
    application_observed: bool = False
    completion: ScriptCompletionStatus = ScriptCompletionStatus.NOT_DISPATCHED

    def __post_init__(self):
        if type(self.dispatched) is not bool or type(self.application_observed) is not bool:
            raise TypeError('脚本派发与观察状态必须是布尔值')
        if not isinstance(self.completion, ScriptCompletionStatus):
            raise TypeError('脚本完成状态无效')
        if not self.dispatched and (self.application_observed or self.completion != ScriptCompletionStatus.NOT_DISPATCHED):
            raise ValueError('未派发不能标记应用或完成状态')
        if self.dispatched and self.completion == ScriptCompletionStatus.NOT_DISPATCHED:
            raise ValueError('已派发必须单独表达完成状态')


class ToolSafetyClassification(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK_WRITE = "LOW_RISK_WRITE"
    TARGETED_WRITE = "TARGETED_WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OperationPlan:
    operation: str
    target: dict[str, Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    preconditions: dict[str, Any] = field(default_factory=dict)
    mode: ExecutionMode = ExecutionMode.FAST
    metadata: dict[str, Any] = field(default_factory=dict)
    note_plan: NotePlan | None = None

    def __post_init__(self):
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise ValueError("操作名称不能为空")
        if not isinstance(self.mode, ExecutionMode):
            raise TypeError("执行模式必须是 ExecutionMode")
        if any(not isinstance(value, dict) for value in (
            self.target, self.parameters, self.preconditions, self.metadata
        )):
            raise TypeError("目标、参数、前置条件和元数据必须是字典")
        if self.note_plan is not None and not isinstance(self.note_plan, NotePlan):
            raise TypeError("音符载荷必须是 NotePlan")


@dataclass(frozen=True)
class Capability:
    name: str
    backend: str
    raw_tool: dict[str, Any]
    safety: ToolSafetyClassification = ToolSafetyClassification.UNKNOWN
    readable: bool = False
    writable: bool = False
    verifiable: bool = False
    version_constraints: dict[str, Any] = field(default_factory=dict)
    evidence: str = "IMPLEMENTED"
    latency_ms: float | None = None
    reliability: float | None = None
    dispatch_supported: bool = True
    classification_reason: str | None = None
    confidence: str | None = None
    experimental: bool = False
    allowed_modes: tuple[ExecutionMode, ...] = tuple(ExecutionMode)


@dataclass(frozen=True)
class OperationResult:
    execution_status: ExecutionStatus
    verification_status: VerificationStatus = VerificationStatus.NOT_REQUESTED
    backend: str | None = None
    value: Any = None
    error_code: str | None = None
    message: str | None = None
    data_status: DataStatus = DataStatus.NOT_CHECKED
    response_status: ResponseStatus | None = None
    script_application_status: ScriptApplicationStatus = ScriptApplicationStatus.NOT_CHECKED
    script_invocation: ScriptInvocationState | None = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class BackendExecution:
    status: ExecutionStatus
    value: Any = None
    error_code: str | None = None
    data_status: DataStatus = DataStatus.NOT_CHECKED
    response_status: ResponseStatus | None = None
    script_application_status: ScriptApplicationStatus = ScriptApplicationStatus.NOT_CHECKED
    script_invocation: ScriptInvocationState | None = None


class BackendError(Exception):
    def __init__(self, code: str, *, dispatched: bool = False):
        super().__init__(code)
        self.code = code
        self.dispatched = dispatched
