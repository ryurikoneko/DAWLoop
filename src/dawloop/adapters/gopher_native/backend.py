from __future__ import annotations

import asyncio
import copy
import json
import time
from contextlib import nullcontext

from dawloop.runtime import (
    BackendError, BackendExecution, ExecutionStatus, OperationPlan,
    SafetyGuard, ToolSafetyClassification,
)

from .catalog import READ_TOOLS, catalog_hash, normalize_catalog
from .transport import CDPTransport
from .response import decode_response
from dawloop.runtime.health import BackendState, CapabilityHealth, CertificationState, tool_contract_hash


class GopherNativeBackend:
    name = "gopher_native"

    def __init__(self, endpoint="http://127.0.0.1:9222", timeout=35.0, *, transport=None, trace=None, fl_version=None):
        self.transport = transport or CDPTransport(endpoint, timeout)
        self.lock = asyncio.Lock()
        self.capabilities = []
        self.catalog_digest = None
        self.session = None
        self.observations = []
        self.trace = trace
        self.fl_version = fl_version
        self.capability_health = {}

    @property
    def backend_state(self):
        if self.transport.poisoned_epoch and (self.session is None or self.transport.poisoned_epoch == self.session['session']):
            return BackendState.POISONED
        if self.session is None:
            return BackendState.DISCONNECTED
        if any(h.state == CertificationState.QUARANTINED for h in self.capability_health.values()):
            return BackendState.DEGRADED
        return BackendState.CONNECTED

    def apply_certification(self, operation, health):
        capability = next(c for c in self.capabilities if c.name == operation)
        if health.schema_hash != tool_contract_hash(capability.raw_tool) or health.fl_version != self.fl_version or not self.fl_version:
            raise ValueError('认证目录或宿主版本不匹配')
        if self.capability_health[operation].state == CertificationState.QUARANTINED:
            raise ValueError('隔离能力需要明确的新验证，不能直接覆盖认证')
        if health.state != CertificationState.LIVE_CERTIFIED or not capability.dispatch_supported:
            raise ValueError('认证状态或实现不匹配')
        self.capability_health[operation] = copy.deepcopy(health)

    def apply_certification_report(self, report):
        if report.get('catalog_hash') != self.catalog_digest or not isinstance(report.get('capabilities'), dict):
            raise ValueError('认证报告不匹配当前目录')
        pending = []
        for operation, record in report['capabilities'].items():
            if record.get('state') == CertificationState.LIVE_CERTIFIED:
                record = dict(record, state=CertificationState(record['state']))
                pending.append((operation, CapabilityHealth(**record)))
        previous = copy.deepcopy(self.capability_health)
        try:
            for operation, health in pending:
                self.apply_certification(operation, health)
        except Exception:
            self.capability_health = previous
            raise

    def phase(self, name):
        return self.trace.phase(name) if self.trace else nullcontext()

    async def _run(self, function, *args):
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # 取消等待不等于宿主取消；等待工作线程退出后才能释放队列锁。
            self.transport.poisoned_epoch = self.transport.epoch
            try:
                await task
            except Exception:
                pass
            raise

    async def connect(self):
        async with self.lock:
            self.capabilities = []
            self.catalog_digest = None
            self.session = None
            self.session = await self._run(self.transport.connect)
            return copy.deepcopy(self.session)

    async def discover(self):
        async with self.lock:
            if self.session is None:
                self.session = await self._run(self.transport.connect)
            self.capabilities = []
            self.catalog_digest = None
            if self.trace:
                self.trace.calls += 1
            result = await self._run(self.transport.invoke, "catalog")
            payload = result["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            tools = payload if isinstance(payload, list) else payload.get("tools")
            self.capabilities = normalize_catalog(tools)
            self.catalog_digest = catalog_hash(tools)
            old_health = self.capability_health
            self.capability_health = {}
            for cap in self.capabilities:
                digest = tool_contract_hash(cap.raw_tool)
                prior = old_health.get(cap.name)
                if prior and prior.schema_hash == digest and prior.fl_version == self.fl_version:
                    self.capability_health[cap.name] = prior
                    continue
                state = CertificationState.CLASSIFIED if cap.classification_reason else CertificationState.DISCOVERED
                health = CapabilityHealth(state, digest, fl_version=self.fl_version)
                if cap.name == 'system.session_context' and cap.classification_reason:
                    health.state = CertificationState.QUARANTINED
                    health.last_error = 'DECODE_ERROR'
                    health.evidence = 'runtime_v2/native_read_hardening/read_results.json'
                    health.evidence_level = 'LIVE_TESTED_INVALID'
                self.capability_health[cap.name] = health
            return copy.deepcopy(self.capabilities)

    async def resolve_target(self, plan):
        with self.phase("target_resolution"):
            if self.session is None or self.transport.poisoned_epoch == self.session["session"]:
                raise BackendError("SESSION_UNAVAILABLE")
            if not self.capabilities:
                raise BackendError("CATALOG_REQUIRED")
            if plan.target.get("session") != self.session["session"]:
                raise ValueError("PAGE_SESSION_REQUIRED")
            # 只读目标是页面会话；工程、片段及通道身份尚不能由此推定。
            resolved = dict(self.session)
            if plan.operation.startswith("plugin.parameter."):
                resolved.update(plugin_target=plan.parameters.get("target"),
                                slot_number=plan.parameters.get("slot_number"))
            return resolved

    async def validate(self, plan, capability):
        if capability not in self.capabilities or capability.backend != self.name:
            raise ValueError("STALE_CAPABILITY")
        if capability.safety != ToolSafetyClassification.READ_ONLY or capability.writable:
            raise ValueError("READ_ONLY_BACKEND")
        health = self.capability_health.get(capability.name)
        if health and health.state == CertificationState.QUARANTINED:
            raise BackendError('CAPABILITY_QUARANTINED')
        if health and health.state == CertificationState.LIVE_CERTIFIED:
            if any(plan.parameters.get(key) != value for key,value in health.scope.get('parameters', {}).items()):
                raise BackendError('CERTIFICATION_SCOPE_MISMATCH')
        name = capability.raw_tool["name"]
        if name not in READ_TOOLS or plan.operation != capability.name or plan.note_plan is not None:
            raise ValueError("UNKNOWN_TOOL")
        try:
            from jsonschema import Draft202012Validator
        except ImportError as error:
            raise BackendError("NATIVE_DEPENDENCY_MISSING") from error
        schema = copy.deepcopy(capability.raw_tool["inputSchema"])
        schema["additionalProperties"] = False
        Draft202012Validator.check_schema(schema)
        if list(Draft202012Validator(schema).iter_errors(plan.parameters)):
            raise ValueError("INVALID_PARAMETERS")
        json.dumps(plan.parameters, allow_nan=False)
        if name.startswith("get_plugin_parameter"):
            target = plan.parameters["target"]
            slot = plan.parameters["slot_number"]
            if not target.isdecimal() or int(target) < (1 if slot == -1 else 0):
                raise ValueError("插件读取只接受明确的可视索引")
            if type(slot) is not int or slot not in {-1, *range(1, 11)}:
                raise ValueError("INVALID_PLUGIN_SLOT")
            if plan.target.get("plugin_target") != target or plan.target.get("slot_number") != slot:
                raise ValueError("PLUGIN_TARGET_REQUIRED")
            if "param_identifier" in plan.parameters and not plan.parameters["param_identifier"].strip():
                raise ValueError("PARAMETER_REQUIRED")

    async def execute(self, plan, capability):
        async with self.lock:
            started = time.perf_counter()
            plan = copy.deepcopy(plan)
            await self.validate(plan, capability)
            SafetyGuard().check(plan, capability, await self.resolve_target(plan))
            with self.phase("execution"):
                if self.trace:
                    self.trace.calls += 1
                try:
                    result = await self._run(self.transport.invoke, "call", capability.raw_tool["name"], plan.parameters)
                except BackendError as error:
                    health = self.capability_health.get(capability.name)
                    if health:
                        health.last_error = error.code
                    raise
            self.observations.append({"interference": result.get("interference", 0)})
            decoded = decode_response(capability.raw_tool['name'], result, plan.parameters)
            health = self.capability_health.get(capability.name)
            if health:
                from dawloop.runtime import OperationResult
                health.observe(OperationResult(decoded.status, value=decoded.value, error_code=decoded.error_code,
                                               data_status=decoded.data_status, response_status=decoded.response_status),
                               (time.perf_counter()-started)*1000, fl_version=self.fl_version)
            return decoded

    async def readback(self, plan, capability):
        raise BackendError("VERIFICATION_UNSUPPORTED")

    def compare(self, plan, actual):
        raise BackendError("VERIFICATION_UNSUPPORTED")

    async def close(self):
        async with self.lock:
            await self._run(self.transport.close)
            self.session = None
            self.capabilities = []
