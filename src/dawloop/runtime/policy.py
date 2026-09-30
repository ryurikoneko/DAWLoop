from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionMode(str, Enum):
    FAST = "fast"
    AUTO = "auto"
    VERIFIED = "verified"


class VerificationPolicy(str, Enum):
    SKIP = "skip"
    AUTO = "auto"
    REQUIRE = "require"


class VerificationStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    SKIPPED = "skipped"
    VERIFIED = "verified"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SafetyGuard:
    require_target_identity: bool = True
    destructive: bool = False
    require_explicit_confirmation: bool = False


@dataclass(frozen=True)
class OperationPolicy:
    mode: ExecutionMode = ExecutionMode.FAST
    verification: VerificationPolicy = VerificationPolicy.AUTO
    safety: SafetyGuard = SafetyGuard()
    operation_kind: str = "generic"


_DEFAULT_AUTO_VERIFY = frozenset({
    "create_pattern",
    "delete_pattern",
    "delete_channel",
    "delete_track",
    "replace_pattern",
    "clear_pattern",
    "destructive_routing_change",
})


def decide_verification(policy: OperationPolicy, *, user_requested: bool = False) -> bool:
    """Return whether result readback verification should run.

    Safety checks are intentionally separate from result verification. Fast mode
    skips verification except for operations that DAWLoop classifies as
    identity/destructive boundaries. Verified mode verifies whenever a verifier
    exists. Auto mode verifies the same high-risk boundaries by default.
    """
    if user_requested or policy.verification is VerificationPolicy.REQUIRE:
        return True
    if policy.verification is VerificationPolicy.SKIP:
        return False
    if policy.mode is ExecutionMode.VERIFIED:
        return True
    if policy.operation_kind in _DEFAULT_AUTO_VERIFY:
        return True
    if policy.safety.destructive:
        return True
    return False
