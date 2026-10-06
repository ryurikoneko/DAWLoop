from .models import Capability, ExecutionMode, OperationPlan, ToolSafetyClassification


class SafetyGuard:
    def check(self, plan: OperationPlan, capability: Capability, resolved: dict) -> None:
        if capability.safety == ToolSafetyClassification.UNKNOWN:
            raise ValueError("UNKNOWN_TOOL")
        if not capability.readable and not capability.writable:
            raise ValueError("CAPABILITY_UNAVAILABLE")
        if not plan.target or not resolved:
            raise ValueError("TARGET_REQUIRED")
        if any(resolved.get(key) != value for key, value in plan.target.items()):
            raise ValueError("TARGET_CHANGED")
        if any(resolved.get(key) != value for key, value in plan.preconditions.items()):
            raise ValueError("PRECONDITION_FAILED")
        if capability.safety == ToolSafetyClassification.DESTRUCTIVE:
            if plan.metadata.get("destructive_authorized") is not True:
                raise ValueError("DESTRUCTIVE_AUTHORIZATION_REQUIRED")


class VerificationPolicy:
    def required(self, plan: OperationPlan, capability: Capability) -> bool:
        if plan.mode == ExecutionMode.VERIFIED:
            return True
        if plan.mode != ExecutionMode.AUTO:
            return False
        action = plan.operation.rsplit(".", 1)[-1]
        return (
            capability.safety == ToolSafetyClassification.DESTRUCTIVE
            or action in {"create", "delete", "remove", "clear", "replace", "overwrite"}
            or plan.metadata.get("overwrites_existing") is True
            or plan.metadata.get("identity_critical") is True
        )
