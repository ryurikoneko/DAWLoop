from __future__ import annotations

import asyncio
import importlib.metadata
import time
from contextlib import contextmanager

from dawloop.note_plan import NoteEvent, NotePlan
from dawloop.time import MusicalGrid

from .models import BackendExecution, Capability, ExecutionStatus, OperationPlan, ToolSafetyClassification
from .router import BackendRouter


PHASES = ("planning", "backend_connect", "discovery", "target_resolution", "execution", "readback", "verification")


class PerformanceTrace:
    def __init__(self, scope, *, clock=time.perf_counter_ns):
        self.scope = scope
        self.clock = clock
        self.started = clock()
        self.durations = dict.fromkeys(PHASES)
        self.calls = 0
        self.manual_interactions = 0

    @contextmanager
    def phase(self, name):
        if name not in self.durations:
            raise ValueError("未知计时阶段")
        started = self.clock()
        try:
            yield
        finally:
            elapsed = (self.clock() - started) / 1_000_000
            self.durations[name] = (self.durations[name] or 0) + elapsed

    def report(self, result, *, catalog_digest=None, host_version=None):
        return {
            "scope": self.scope, "result": result,
            "latency_ms": {**self.durations, "total": (self.clock() - self.started) / 1_000_000},
            "backend_calls": self.calls, "manual_interactions": self.manual_interactions,
            "environment": {"dawloop_version": importlib.metadata.version("dawloop"),
                            "backend_version": "runtime-v2-poc-1", "fl_version": host_version,
                            "catalog_hash": catalog_digest},
        }


def note_fixture(count):
    if type(count) is not int or count not in {32, 64, 128}:
        raise ValueError("样本数量必须为32、64或128")
    grid = MusicalGrid(ppq=480, beats_per_bar=4, beat_unit=4)
    spacing = grid.ticks_per_bar * 8 // count
    return NotePlan("synthetic-pattern", grid, 0, 8,
                    tuple(NoteEvent(index * spacing, spacing, 60 + index % 12, 80) for index in range(count)))


class SimulatedNoteBackend:
    name = "simulated_notes"

    def __init__(self, trace):
        self.trace = trace

    async def discover(self):
        return [Capability("piano_roll.notes", self.name, {}, ToolSafetyClassification.TARGETED_WRITE,
                           writable=True, evidence="OFFLINE_TESTED")]

    async def resolve_target(self, plan):
        with self.trace.phase("target_resolution"):
            return {"pattern": "synthetic-pattern"}

    async def validate(self, plan, capability):
        if plan.note_plan is None or plan.note_plan.target_id != plan.target.get("pattern"):
            raise ValueError("音符样本目标不匹配")

    async def execute(self, plan, capability):
        with self.trace.phase("execution"):
            self.trace.calls += 1
            return BackendExecution(ExecutionStatus.SUCCESS, {"simulated_note_count": len(plan.note_plan.events)})

    async def readback(self, plan, capability):
        raise ValueError("模拟基准不提供现场读回")

    def compare(self, plan, actual):
        raise ValueError("模拟基准不提供现场验证")


async def simulated_benchmark(count, repeats=5):
    if type(repeats) is not int or not 1 <= repeats <= 100:
        raise ValueError("重复次数必须为1到100")
    reports = []
    for _ in range(repeats):
        trace = PerformanceTrace("SIMULATED")
        with trace.phase("planning"):
            plan = OperationPlan("piano_roll.notes", {"pattern": "synthetic-pattern"}, note_plan=note_fixture(count))
        router = BackendRouter([SimulatedNoteBackend(trace)])
        with trace.phase("discovery"):
            await router.discover()
        result = await router.execute(plan)
        reports.append(trace.report(result.to_dict()))
        await asyncio.sleep(0)
    return {"note_count": count, "runs": reports}
