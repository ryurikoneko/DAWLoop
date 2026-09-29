"""仅供维护者显式运行的 FL Studio 音符往返证据采集器。"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import inspect
import json
import os
import platform
import subprocess
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dawloop.adapters.fl_studio_mcp import FLStudioMCPAdapter, TargetIdentity
from dawloop.adapters.fl_studio_mcp.adapter import UPSTREAM_COMMIT, probe_connection
from dawloop.note_plan import NoteEvent, NotePlan
from dawloop.time import MusicalGrid


PROJECT_NAME = "DAWLoop_Live_Verification"
PATTERN_NAME = "DAWLoop Live Test"
CHANNEL_NAME = "DAWLoop Test"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "evidence" / "live_fl" / "note_roundtrip"


def synthetic_plan(ppq: int) -> NotePlan:
    if type(ppq) is not int or ppq < 4 or ppq % 4:
        raise ValueError("PPQ 必须为可精确四等分的正整数")
    return NotePlan(
        target_id=PATTERN_NAME,
        grid=MusicalGrid(ppq=ppq),
        section_start_tick=0,
        section_bars=1,
        events=(
            NoteEvent(0, ppq // 2, 60, 64),
            NoteEvent(ppq, ppq // 2, 64, 80),
            NoteEvent(2 * ppq, ppq // 2, 67, 96),
            NoteEvent(3 * ppq, ppq // 2, 72, 112),
        ),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_test_target(identity: TargetIdentity) -> None:
    if (
        identity.project_id != PROJECT_NAME
        or identity.pattern_id != PATTERN_NAME
        or identity.channel_name != CHANNEL_NAME
        or any(character in identity.fl_studio_version for character in "\\/:\r\n")
    ):
        raise ValueError("现场目标不是指定的独立测试工程、Pattern 和 Channel")


def _load_reader(specification: str):
    module_name, separator, callable_name = specification.partition(":")
    if not separator or not module_name or not callable_name:
        raise ValueError("身份读取器格式应为 module:function")
    reader = getattr(importlib.import_module(module_name), callable_name)
    if not callable(reader):
        raise TypeError("身份读取器必须可调用")
    return reader


async def _identity(reader) -> TargetIdentity:
    result = reader()
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, TargetIdentity):
        raise TypeError("身份读取器必须返回 TargetIdentity")
    _require_test_target(result)
    return result


def _duplicate_mismatches(planned: list[dict], actual: list[dict]) -> list[dict]:
    def counts(events):
        return Counter(tuple(sorted(item.items())) for item in events)

    planned_counts, actual_counts = counts(planned), counts(actual)
    return [
        {
            "event": dict(key),
            "planned_count": planned_counts[key],
            "actual_count": actual_counts[key],
        }
        for key in sorted(planned_counts.keys() | actual_counts.keys())
        if planned_counts[key] != actual_counts[key]
        and max(planned_counts[key], actual_counts[key]) > 1
    ]


def _write_json(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _reader_fingerprint(reader) -> dict:
    name = f"{getattr(reader, '__module__', 'unknown')}:{getattr(reader, '__name__', 'unknown')}"
    try:
        source = inspect.getsourcefile(reader)
        digest = hashlib.sha256(Path(source).read_bytes()).hexdigest() if source else None
    except (OSError, TypeError):
        digest = None
    return {
        "callable": name,
        "source_sha256": digest,
    }


def _fresh(stage: dict) -> bool:
    before = stage.get("state_mtime_before_ns")
    after = stage.get("state_mtime_after_ns")
    return type(before) is int and type(after) is int and after > before


async def capture_note_roundtrip(
    identity_reader,
    ppq: int,
    output_root: Path = DEFAULT_OUTPUT,
    *,
    adapter: FLStudioMCPAdapter | None = None,
    connection_probe=probe_connection,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = output_root / ".capture.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        return await _capture_once(identity_reader, ppq, output_root, adapter, connection_probe)
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


async def _capture_once(identity_reader, ppq, output_root, adapter, connection_probe) -> Path:
    plan = synthetic_plan(ppq)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = output_root / run_id
    run_dir.mkdir(mode=0o700)
    stages: dict[str, dict] = {}
    stage_times: dict[str, str] = {}
    target: TargetIdentity | None = None
    report = None
    failure_stage = "checkout"
    error_type = None
    connection_ok = False
    checkout_clean = False
    try:
        checkout = subprocess.run(
            ["git", "status", "--porcelain"], cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False,
        )
        checkout_clean = checkout.returncode == 0 and not checkout.stdout.strip()
        if not checkout_clean:
            raise RuntimeError("采集代码所在 Git 工作树必须干净")
        failure_stage = "connection"
        connected, _ = await connection_probe()
        if not connected:
            raise RuntimeError("FL Studio 未连接")
        connection_ok = True
        failure_stage = "identity"
        target = await _identity(identity_reader)
        failure_stage = "adapter"
        def record_stage(stage: str, data: dict) -> None:
            stages[stage] = data
            stage_times[stage] = _utc_now()

        report = await (adapter or FLStudioMCPAdapter()).execute(
            plan, target, identity_reader=identity_reader,
            evidence_observer=record_stage,
        )
    except Exception as error:
        error_type = type(error).__name__

    planned = [item.to_dict() for item in plan.events]
    actual = stages.get("readback", {}).get("events", [])
    required_stages = {
        "target_before", "pre_state", "write_attempt", "write_queued",
        "target_before_trigger", "target_after", "readback",
    }
    complete = (
        required_stages <= stages.keys()
        and target is not None
        and stages["target_before"] == target.to_dict()
        and stages["target_before_trigger"] == target.to_dict()
        and stages["target_after"] == target.to_dict()
        and stages["pre_state"].get("note_count") == 0
        and stages["pre_state"].get("ppq") == ppq
        and _fresh(stages["pre_state"])
        and _fresh(stages["readback"])
        and stages["write_attempt"].get("requested_count") == len(planned)
        and stages["write_queued"].get("accepted") is True
        and report is not None
        and report.planned_count == len(planned)
        and list(report.planned_events) == planned
        and report.actual_count == len(actual)
        and list(report.actual_events) == actual
    )
    status = "PASS" if (
        report is not None and report.status == "PASS" and complete
        and not report.errors and not report.missing and not report.extra and not report.mismatches
    ) else "STOP"
    if status == "STOP" and error_type is None:
        if stages.get("pre_state", {}).get("note_count", 0) > 0:
            failure_stage = "pre_state_nonempty"
        else:
            failure_stage = next((stage for stage in (
                "target_before", "pre_state", "write_attempt", "write_queued",
                "target_before_trigger", "target_after", "readback"
            ) if stage not in stages), "verification")
    verification = {
        "operation": "piano_roll_note_roundtrip",
        "run_id": run_id,
        "planned_count": len(planned),
        "actual_count": len(actual),
        "missing": list(report.missing) if report and complete else [],
        "extra": list(report.extra) if report and complete else [],
        "unexpected": list(report.extra) if report and complete else [],
        "duplicate_mismatches": _duplicate_mismatches(planned, actual) if complete else [],
        "mismatches": list(report.mismatches) if report and complete else [],
        "comparison_performed": bool(complete and report is not None),
        "write_error": "write_attempt" in stages and "write_queued" not in stages,
        "read_error": "target_before_trigger" in stages and "readback" not in stages,
        "adapter_status": report.status if report else None,
        "status": status,
        "failure_stage": failure_stage if status == "STOP" else None,
        "error_type": error_type,
        "observed_at_utc": _utc_now(),
    }
    # 实际错误文本可能含本机路径；公开证据只保留阶段与异常类型。
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, check=False,
    )
    _write_json(run_dir / "environment.json", {
        "run_id": run_id,
        "scope": "live_fl_studio_note_roundtrip",
        "python_version": platform.python_version(),
        "os": platform.system(),
        "dawloop_version": report.dawloop_version if report else "0.2.0a0",
        "dawloop_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "source_checkout_clean": checkout_clean,
        "identity_reader": _reader_fingerprint(identity_reader),
        "dependency_versions": {
            name: _package_version(name)
            for name in ("fastmcp", "mido", "python-rtmidi", "pynput")
        },
        "fl_studio_version": target.fl_studio_version if target else None,
        "upstream_mcp_commit": UPSTREAM_COMMIT,
        "connection_probe_passed": connection_ok,
        "created_at_utc": _utc_now(),
    })
    _write_json(run_dir / "target_identity.json", {
        "run_id": run_id,
        "expected": target.to_dict() if target else {
            "project_id": PROJECT_NAME, "pattern_id": PATTERN_NAME, "channel_name": CHANNEL_NAME
        },
        "observed_before": stages.get("target_before"),
        "observed_before_trigger": stages.get("target_before_trigger"),
        "observed_after": stages.get("target_after"),
        "observed_before_at_utc": stage_times.get("target_before"),
        "observed_before_trigger_at_utc": stage_times.get("target_before_trigger"),
        "observed_after_at_utc": stage_times.get("target_after"),
        "identity_reader_required": True,
    })
    _write_json(run_dir / "plan.json", {
        "run_id": run_id,
        "plan": plan.to_dict(),
        "time_mapping": "start_tick / ppq and duration / ppq become upstream quarter-note units",
        "ppq_source": "operator supplied; adapter confirms against fresh FL state before write",
    })
    _write_json(run_dir / "pre_state.json", {
        "run_id": run_id,
        "observed": "pre_state" in stages,
        "note_count": stages.get("pre_state", {}).get("note_count"),
        "ppq": stages.get("pre_state", {}).get("ppq"),
        "state_mtime_before_ns": stages.get("pre_state", {}).get("state_mtime_before_ns"),
        "state_mtime_after_ns": stages.get("pre_state", {}).get("state_mtime_after_ns"),
        "observed_at_utc": stage_times.get("pre_state"),
    })
    _write_json(run_dir / "execution.json", {
        "run_id": run_id,
        "write_attempted": "write_attempt" in stages,
        "requested_count": stages.get("write_attempt", {}).get("requested_count"),
        "backend_queued": stages.get("write_queued", {}).get("accepted", False),
        "queue_cleared_before_trigger": "queue_cleared" in stages,
        "write_attempted_at_utc": stage_times.get("write_attempt"),
        "backend_queued_at_utc": stage_times.get("write_queued"),
        "backend_success_is_not_verification": True,
    })
    _write_json(run_dir / "readback.json", {
        "run_id": run_id,
        "observed": "readback" in stages,
        "source": "fresh FL Studio Piano Roll state after an independent script trigger",
        "actual_events": actual,
        "state_mtime_before_ns": stages.get("readback", {}).get("state_mtime_before_ns"),
        "state_mtime_after_ns": stages.get("readback", {}).get("state_mtime_after_ns"),
        "observed_at_utc": stage_times.get("readback"),
    })
    _write_json(run_dir / "verification.json", verification)
    (run_dir / "README.md").write_text(
        "# 现场音符往返尝试\n\n"
        f"运行编号：`{run_id}`  \n结果：`{status}`\n\n"
        "此记录针对独立的合成测试目标。机器可读文件依次记录连接、目标身份、计划音符、"
        "写前空白状态、后端排队、FL Studio 现场新读回及 Exact-Set 比较。排队成功不构成 PASS。\n\n"
        "主动归档或公开前，请逐项检查这些文件是否含敏感信息。\n",
        encoding="utf-8", newline="\n",
    )
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="采集独立测试工程的现场音符往返证据")
    parser.add_argument("--identity-reader", required=True, help="现场身份读取器 module:function")
    parser.add_argument("--ppq", required=True, type=int, help="FL Studio 当前工程的 PPQ；写前现场核对")
    parser.add_argument("--confirm-disposable-project", required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.confirm_disposable_project != PROJECT_NAME:
        parser.error(f"必须明确确认独立测试工程：{PROJECT_NAME}")
    try:
        reader = _load_reader(args.identity_reader)
    except (ImportError, AttributeError, TypeError, ValueError):
        def reader():
            raise RuntimeError("无法载入独立的现场身份读取器")

    result_dir = asyncio.run(capture_note_roundtrip(reader, args.ppq, args.output_root))
    result = json.loads((result_dir / "verification.json").read_text(encoding="utf-8"))
    print(f"{result['status']} | {result_dir}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
