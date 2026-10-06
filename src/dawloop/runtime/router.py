from __future__ import annotations

import copy
from .diagnostics import observe

from .backend import Backend
from .models import (
    BackendError, Capability, DataStatus, ExecutionStatus, OperationPlan, OperationResult, ResponseStatus,
    VerificationStatus,
)
from .policy import SafetyGuard, VerificationPolicy
from .health import BackendState, CertificationState


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: dict[str, list[Capability]] = {}

    def replace(self, backend: str, capabilities: list[Capability]) -> None:
        if any(item.backend != backend for item in capabilities):
            raise ValueError("能力与后端名称不匹配")
        self._capabilities[backend] = list(capabilities)

    def for_operation(self, operation: str) -> list[Capability]:
        return [item for items in self._capabilities.values() for item in items if item.name == operation]


class BackendRouter:
    def __init__(self, backends: list[Backend], priority: tuple[str, ...] = (), *, require_live_certified=False):
        self.backends = {backend.name: backend for backend in backends}
        if len(self.backends) != len(backends):
            raise ValueError("后端名称重复")
        self.priority = priority or tuple(self.backends)
        if set(self.priority) != set(self.backends) or len(self.priority) != len(self.backends):
            raise ValueError("优先级必须包含每个后端一次")
        self.registry = CapabilityRegistry()
        self.guard = SafetyGuard()
        self.policy = VerificationPolicy()
        self.discovery_errors: dict[str, str] = {}
        self.require_live_certified = require_live_certified

    async def discover(self):
        self.discovery_errors = {}
        for backend in self.backends.values():
            self.registry.replace(backend.name, [])
            try:
                self.registry.replace(backend.name, await backend.discover())
            except BackendError as error:
                self.discovery_errors[backend.name] = error.code
            except Exception:
                self.discovery_errors[backend.name] = "DISCOVERY_ERROR"
        return dict(self.discovery_errors)

    async def execute(self, plan: OperationPlan) -> OperationResult:
        diagnostics = getattr(self, 'diagnostics', None)
        observe(diagnostics, 'routing_begin')
        # 复制计划以免等待目标查询时外部修改参数，绕过已完成的检查。
        plan = copy.deepcopy(plan)
        candidates = sorted(self.registry.for_operation(plan.operation),
                            key=lambda item: self.priority.index(item.backend))
        if not candidates:
            return OperationResult(ExecutionStatus.NOT_DISPATCHED, error_code="CAPABILITY_UNAVAILABLE")
        last = OperationResult(ExecutionStatus.NOT_DISPATCHED, error_code="CAPABILITY_UNAVAILABLE")
        for capability in candidates:
            backend = self.backends[capability.backend]
            if plan.mode not in capability.allowed_modes:
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name,
                    error_code='EXECUTION_MODE_UNSUPPORTED')
                continue
            if capability.experimental and plan.metadata.get('experimental_authorized') is not True:
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name,
                    error_code='EXPERIMENTAL_AUTHORIZATION_REQUIRED')
                continue
            if getattr(backend, 'backend_state', None) in {BackendState.POISONED, BackendState.DISCONNECTED}:
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name, error_code='BACKEND_UNAVAILABLE')
                continue
            health = getattr(backend, 'capability_health', {}).get(capability.name)
            if health and health.state == CertificationState.QUARANTINED:
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name, error_code='CAPABILITY_QUARANTINED')
                continue
            if self.require_live_certified and (not health or health.state != CertificationState.LIVE_CERTIFIED):
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name, error_code='LIVE_CERTIFICATION_REQUIRED')
                continue
            if not capability.dispatch_supported:
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name,
                                       error_code="DISPATCH_UNSUPPORTED")
                continue
            verify = self.policy.required(plan, capability)
            if verify and not capability.verifiable:
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, VerificationStatus.UNSUPPORTED,
                                       backend.name, error_code="VERIFICATION_UNSUPPORTED")
                continue
            try:
                observe(diagnostics, 'backend_selected', backend=backend.name)
                await backend.validate(plan, capability)
                resolved = await backend.resolve_target(plan)
                self.guard.check(plan, capability, resolved)
            except BackendError as error:
                if error.dispatched:
                    return OperationResult(ExecutionStatus.UNKNOWN, backend=backend.name, error_code=error.code,
                                           response_status=ResponseStatus.RESULT_UNKNOWN)
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name, error_code=error.code)
                continue
            except (ValueError, TypeError) as error:
                return OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name,
                                       error_code="SAFETY_REJECTED", message=str(error))
            except Exception:
                return OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name,
                                       error_code="PREFLIGHT_ERROR")
            try:
                execution = await backend.execute(plan, capability)
            except BackendError as error:
                if error.code == 'VIEWPORT_INVALIDATED' and not error.dispatched:
                    return OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name,
                                           error_code=error.code)
                if error.dispatched:
                    return OperationResult(ExecutionStatus.UNKNOWN, backend=backend.name, error_code=error.code,
                                           response_status=ResponseStatus.TIMEOUT if error.code in {"EXECUTION_TIMEOUT", "TIMEOUT"}
                                           else ResponseStatus.RESULT_UNKNOWN)
                last = OperationResult(ExecutionStatus.NOT_DISPATCHED, backend=backend.name, error_code=error.code)
                continue
            except Exception:
                return OperationResult(ExecutionStatus.UNKNOWN, backend=backend.name, error_code="EXECUTION_UNKNOWN",
                                       response_status=ResponseStatus.RESULT_UNKNOWN)
            if execution.status == ExecutionStatus.NOT_DISPATCHED:
                if execution.error_code == 'VIEWPORT_INVALIDATED':
                    return OperationResult(execution.status, backend=backend.name,
                                           error_code=execution.error_code)
                last = OperationResult(execution.status, backend=backend.name, error_code=execution.error_code)
                continue
            if execution.status != ExecutionStatus.SUCCESS or execution.data_status in {DataStatus.INVALID, DataStatus.TOOL_ERROR} or not verify:
                return OperationResult(execution.status, backend=backend.name, value=execution.value,
                                       error_code=execution.error_code, data_status=execution.data_status,
                                       response_status=execution.response_status,
                                       script_application_status=execution.script_application_status,
                                       script_invocation=execution.script_invocation)
            try:
                actual = await backend.readback(plan, capability)
                status = VerificationStatus.VERIFIED if backend.compare(plan, actual) else VerificationStatus.MISMATCH
            except Exception:
                status = VerificationStatus.READ_ERROR
            return OperationResult(execution.status, status, backend.name, execution.value,
                                   data_status=execution.data_status, response_status=execution.response_status,
                                   script_application_status=execution.script_application_status,
                                   script_invocation=execution.script_invocation)
        return last
