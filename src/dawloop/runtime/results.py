from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .policy import VerificationStatus


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class OperationResult:
    execution_status: ExecutionStatus
    verification_status: VerificationStatus
    operation: str
    backend: str
    target: dict[str, Any] = field(default_factory=dict)
    data: Any = None
    message: str = ""

    @property
    def user_label(self) -> str:
        if self.execution_status is not ExecutionStatus.SUCCESS:
            return "Stopped"
        if self.verification_status is VerificationStatus.VERIFIED:
            return "Verified"
        return "Executed"
