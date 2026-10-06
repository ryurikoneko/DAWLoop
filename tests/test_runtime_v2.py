import asyncio
import unittest

from dawloop.runtime import (
    BackendError, BackendExecution, BackendRouter, Capability, ExecutionMode,
    ExecutionStatus, OperationPlan, ToolSafetyClassification as Risk, VerificationStatus,
)
from dawloop.runtime.benchmark import PerformanceTrace, note_fixture, simulated_benchmark


class FakeBackend:
    def __init__(self, name="fake", *, risk=Risk.TARGETED_WRITE, verifiable=True):
        self.name = name
        self.capability = Capability("channel.rename", name, {}, risk, writable=True, verifiable=verifiable)
        self.calls = []
        self.error = None
        self.actual = "desired"
        self.target = {"channel": 1}

    async def discover(self):
        return [self.capability]

    async def validate(self, plan, capability):
        if set(plan.parameters) != {"name"} or not isinstance(plan.parameters["name"], str):
            raise ValueError("参数错误")

    async def resolve_target(self, plan):
        return self.target

    async def execute(self, plan, capability):
        self.calls.append("execute")
        if self.error:
            raise self.error
        return BackendExecution(ExecutionStatus.SUCCESS)

    async def readback(self, plan, capability):
        self.calls.append("readback")
        if isinstance(self.actual, Exception):
            raise self.actual
        return self.actual

    def compare(self, plan, actual):
        return actual == plan.parameters["name"]


def run(backend, *, mode=ExecutionMode.FAST, target=None, parameters=None, metadata=None, others=()):
    async def execute():
        router = BackendRouter([backend, *others])
        await router.discover()
        return await router.execute(OperationPlan("channel.rename", target or {"channel": 1},
            parameters if parameters is not None else {"name": "desired"}, mode=mode, metadata=metadata or {}))
    return asyncio.run(execute())


class RuntimeTests(unittest.TestCase):
    def test_fast_does_not_read_back(self):
        backend = FakeBackend()
        result = run(backend)
        self.assertEqual(result.execution_status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.verification_status, VerificationStatus.NOT_REQUESTED)
        self.assertEqual(backend.calls, ["execute"])

    def test_verified_compares_without_changing_execution_success(self):
        backend = FakeBackend()
        self.assertEqual(run(backend, mode=ExecutionMode.VERIFIED).verification_status, VerificationStatus.VERIFIED)
        backend.actual = "wrong"
        result = run(backend, mode=ExecutionMode.VERIFIED)
        self.assertEqual(result.verification_status, VerificationStatus.MISMATCH)
        self.assertEqual(result.execution_status, ExecutionStatus.SUCCESS)
        backend.actual = RuntimeError()
        self.assertEqual(run(backend, mode=ExecutionMode.VERIFIED).verification_status, VerificationStatus.READ_ERROR)

    def test_unsupported_verification_stops_before_dispatch(self):
        backend = FakeBackend(verifiable=False)
        result = run(backend, mode=ExecutionMode.VERIFIED)
        self.assertEqual(result.verification_status, VerificationStatus.UNSUPPORTED)
        self.assertEqual(backend.calls, [])

    def test_unknown_and_invalid_targets_do_not_execute(self):
        for risk, target, parameters in ((Risk.UNKNOWN, {"channel": 1}, {"name": "desired"}),
                                        (Risk.TARGETED_WRITE, {"channel": 2}, {"name": "desired"}),
                                        (Risk.TARGETED_WRITE, {"channel": 1}, {"name": 123})):
            backend = FakeBackend(risk=risk)
            self.assertEqual(run(backend, target=target, parameters=parameters).execution_status,
                             ExecutionStatus.NOT_DISPATCHED)
            self.assertEqual(backend.calls, [])

    def test_auto_destructive_requires_authorization_and_verification(self):
        backend = FakeBackend(risk=Risk.DESTRUCTIVE)
        self.assertEqual(run(backend, mode=ExecutionMode.AUTO).execution_status, ExecutionStatus.NOT_DISPATCHED)
        self.assertEqual(run(backend, mode=ExecutionMode.AUTO, metadata={"destructive_authorized": True}).verification_status,
                         VerificationStatus.VERIFIED)

    def test_unknown_dispatch_never_falls_back(self):
        backend, fallback = FakeBackend(), FakeBackend("fallback")
        backend.error = BackendError("TIMEOUT", dispatched=True)
        self.assertEqual(run(backend, others=(fallback,)).execution_status, ExecutionStatus.UNKNOWN)
        self.assertEqual(fallback.calls, [])

    def test_only_undispatched_error_may_fall_back(self):
        backend, fallback = FakeBackend(), FakeBackend("fallback")
        backend.error = BackendError("UNAVAILABLE")
        self.assertEqual(run(backend, others=(fallback,)).backend, "fallback")
        self.assertEqual(fallback.calls, ["execute"])

    def test_unexpected_execution_error_is_unknown(self):
        backend, fallback = FakeBackend(), FakeBackend("fallback")
        backend.error = RuntimeError()
        self.assertEqual(run(backend, others=(fallback,)).execution_status, ExecutionStatus.UNKNOWN)
        self.assertEqual(fallback.calls, [])

    def test_confirmed_execution_failure_does_not_retry_or_verify(self):
        backend, fallback = FakeBackend(), FakeBackend("fallback")
        async def failed(plan, capability):
            backend.calls.append("execute")
            return BackendExecution(ExecutionStatus.FAILED, error_code="HOST_REJECTED")
        backend.execute = failed
        self.assertEqual(run(backend, mode=ExecutionMode.VERIFIED, others=(fallback,)).execution_status,
                         ExecutionStatus.FAILED)
        self.assertEqual(backend.calls, ["execute"])
        self.assertEqual(fallback.calls, [])

    def test_auto_marks_creation_and_overwrite_as_requiring_verification(self):
        from dawloop.runtime import VerificationPolicy
        policy = VerificationPolicy()
        capability = FakeBackend().capability
        for operation in ("pattern.create", "pattern.clear", "pattern.replace", "channel.delete"):
            self.assertTrue(policy.required(OperationPlan(operation, {"channel": 1}, mode=ExecutionMode.AUTO), capability))
        self.assertTrue(policy.required(OperationPlan("channel.rename", {"channel": 1}, mode=ExecutionMode.AUTO,
                                                      metadata={"overwrites_existing": True}), capability))

    def test_registry_replaces_catalog_and_priority_is_complete(self):
        async def check():
            router = BackendRouter([FakeBackend()])
            await router.discover()
            router.registry.replace("fake", [])
            return await router.execute(OperationPlan("channel.rename", {"channel": 1}))
        self.assertEqual(asyncio.run(check()).execution_status, ExecutionStatus.NOT_DISPATCHED)
        with self.assertRaises(ValueError):
            BackendRouter([FakeBackend()], ("missing",))

    def test_unavailable_discovery_does_not_hide_other_backend_or_keep_stale_catalog(self):
        async def check():
            primary, secondary = FakeBackend(), FakeBackend("fallback")
            router = BackendRouter([primary, secondary])
            await router.discover()
            async def unavailable():
                raise BackendError("HOST_DISCONNECTED")
            primary.discover = unavailable
            errors = await router.discover()
            self.assertEqual(errors, {"fake": "HOST_DISCONNECTED"})
            result = await router.execute(OperationPlan("channel.rename", {"channel": 1}, {"name": "desired"}))
            self.assertEqual(result.backend, "fallback")
            self.assertEqual(primary.calls, [])
        asyncio.run(check())

    def test_benchmark_has_fixed_fixtures_and_no_invented_unmeasured_durations(self):
        for count in (32, 64, 128):
            self.assertEqual(len(note_fixture(count).events), count)
            report = asyncio.run(simulated_benchmark(count, 1))["runs"][0]
            self.assertEqual(report["scope"], "SIMULATED")
            self.assertEqual(report["backend_calls"], 1)
            self.assertIsNone(report["latency_ms"]["readback"])
            self.assertIsNone(report["environment"]["fl_version"])
        values = iter((0, 1000000, 3000000, 4000000))
        trace = PerformanceTrace("SIMULATED", clock=lambda: next(values))
        with trace.phase("execution"):
            pass
        self.assertEqual(trace.report("SUCCESS")["latency_ms"]["execution"], 2)
