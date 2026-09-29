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
from dawloop.adapters.fl_studio_mcp.identity import read_current_target
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


def _require_test_target(identity: TargetIdentity, pattern_number: int, channel_index: int, ppq: int) -> None:
    checks = (
        (identity.project_id == PROJECT_NAME, "PROJECT_TITLE_MISMATCH"),
        (identity.pattern_number == pattern_number, "PATTERN_NUMBER_MISMATCH"),
        (identity.pattern_id == PATTERN_NAME, "PATTERN_NAME_MISMATCH"),
        (identity.channel_index_type == "global", "CHANNEL_INDEX_TYPE_MISMATCH"),
        (identity.channel_index == channel_index, "CHANNEL_INDEX_MISMATCH"),
        (identity.channel_name == CHANNEL_NAME, "CHANNEL_NAME_MISMATCH"),
        (identity.ppq == ppq, "PPQ_MISMATCH"),
        (identity.safe_to_edit is True, "FL_NOT_SAFE_TO_EDIT"),
    )
    for valid, code in checks:
        if not valid:
            raise ValueError(code)
    if any(character in identity.fl_studio_version for character in "\\/:\r\n"):
        raise ValueError("FL_STUDIO_VERSION_UNAVAILABLE")


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


def _same_identity_observation(expected: TargetIdentity, observed: dict | None) -> bool:
    if not isinstance(observed, dict):
        return False
    reference = expected.to_dict()
    return all(
        observed.get(key) == value for key, value in reference.items()
        if key != "observed_at_utc"
    )


def _require_backend_port(expected_port: str) -> None:
    from fl_studio_mcp.utils.midi_connection import MIDIConnection

    if not isinstance(expected_port, str) or not expected_port.strip():
        raise ValueError("BACKEND_MIDI_PORT_REQUIRED")
    connection = MIDIConnection()
    try:
        if not connection.connect() or connection.get_status()["port_name"] != expected_port:
            raise ValueError("BACKEND_MIDI_PORT_MISMATCH")
    finally:
        connection.disconnect()


async def capture_note_roundtrip(
    identity_reader,
    ppq: int,
    output_root: Path = DEFAULT_OUTPUT,
    *,
    expected_pattern_number: int,
    expected_channel_index: int,
    midi_port: str | None = None,
    adapter: FLStudioMCPAdapter | None = None,
    connection_probe=probe_connection,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = output_root / ".capture.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        return await _capture_once(
            identity_reader, ppq, output_root, adapter, connection_probe,
            expected_pattern_number, expected_channel_index, midi_port,
        )
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


async def _capture_once(identity_reader, ppq, output_root, adapter, connection_probe,
                        expected_pattern_number, expected_channel_index, midi_port) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = output_root / run_id
    run_dir.mkdir(mode=0o700)
    plan: NotePlan | None = None
    stages: dict[str, dict] = {}
    stage_times: dict[str, str] = {}
    target: TargetIdentity | None = None
    identity_match = False
    report = None
    failure_stage = "plan"
    error_type = None
    error_code = None
    connection_ok = False
    checkout_clean = False
    initial_commit = None
    initial_branch = None
    try:
        plan = synthetic_plan(ppq)
        if type(expected_pattern_number) is not int or expected_pattern_number < 1:
            raise ValueError("预期 Pattern 编号必须为正整数")
        if type(expected_channel_index) is not int or expected_channel_index < 0:
            raise ValueError("预期全局 Channel 索引必须为非负整数")
        failure_stage = "checkout"
        checkout = subprocess.run(
            ["git", "status", "--porcelain"], cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False,
        )
        checkout_clean = checkout.returncode == 0 and not checkout.stdout.strip()
        if not checkout_clean:
            raise RuntimeError("采集代码所在 Git 工作树必须干净")
        revision_before = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False,
        )
        branch_before = subprocess.run(
            ["git", "branch", "--show-current"], cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False,
        )
        if revision_before.returncode != 0 or branch_before.returncode != 0 or not branch_before.stdout.strip():
            raise RuntimeError("无法确定采集代码的提交和分支")
        initial_commit = revision_before.stdout.strip()
        initial_branch = branch_before.stdout.strip()
        if adapter is None:
            failure_stage = "routing"
            _require_backend_port(midi_port)
        failure_stage = "connection"
        connected, _ = await connection_probe()
        if not connected:
            raise RuntimeError("FL Studio 未连接")
        connection_ok = True
        failure_stage = "identity"
        target = await _identity(identity_reader)
        _require_test_target(target, expected_pattern_number, expected_channel_index, ppq)
        identity_match = True
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
        if failure_stage == "identity":
            known_codes = {
                "PROJECT_TITLE_MISMATCH", "PATTERN_NUMBER_MISMATCH", "PATTERN_NAME_MISMATCH",
                "CHANNEL_INDEX_TYPE_MISMATCH", "CHANNEL_INDEX_MISMATCH", "CHANNEL_NAME_MISMATCH",
                "PPQ_MISMATCH", "FL_NOT_SAFE_TO_EDIT", "FL_STUDIO_VERSION_UNAVAILABLE",
                "PATTERN_IDENTITY_UNAVAILABLE", "CHANNEL_IDENTITY_UNAVAILABLE",
                "PPQ_UNAVAILABLE", "FL_SAFE_TO_EDIT_UNAVAILABLE", "FL_API_VERSION_UNAVAILABLE",
                "PROJECT_TITLE_UNAVAILABLE", "PATTERN_NAME_UNAVAILABLE", "CHANNEL_NAME_UNAVAILABLE",
            }
            if isinstance(error, ValueError) and str(error) in known_codes:
                error_code = str(error)
            elif isinstance(error, TimeoutError):
                error_code = "TARGET_IDENTITY_TIMEOUT"
            else:
                error_code = "PATTERN_IDENTITY_READER_MISSING"

    final_checkout = subprocess.run(
        ["git", "status", "--porcelain"], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, check=False,
    )
    final_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, check=False,
    )
    final_branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, check=False,
    )
    source_consistent = bool(
        checkout_clean and initial_commit and initial_branch
        and final_checkout.returncode == 0 and not final_checkout.stdout.strip()
        and final_revision.returncode == 0 and final_revision.stdout.strip() == initial_commit
        and final_branch.returncode == 0 and final_branch.stdout.strip() == initial_branch
    )

    planned = [item.to_dict() for item in plan.events] if plan else []
    actual = stages.get("readback", {}).get("events", [])
    required_stages = {
        "target_before", "pre_state", "write_attempt", "write_queued",
        "target_before_trigger", "target_after", "readback",
    }
    complete = (
        required_stages <= stages.keys()
        and plan is not None
        and target is not None
        and _same_identity_observation(target, stages["target_before"])
        and _same_identity_observation(target, stages["target_before_trigger"])
        and _same_identity_observation(target, stages["target_after"])
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
        report is not None and report.status == "PASS" and complete and source_consistent
        and not report.errors and not report.missing and not report.extra and not report.mismatches
    ) else "STOP"
    if status == "STOP" and error_type is None:
        if initial_commit and not source_consistent:
            failure_stage = "checkout_changed"
        elif stages.get("pre_state", {}).get("note_count", 0) > 0:
            failure_stage = "pre_state_nonempty"
        else:
            failure_stage = next((stage for stage in (
                "target_before", "pre_state", "write_attempt", "write_queued",
                "target_before_trigger", "target_after", "readback"
            ) if stage not in stages), "verification")
    if status == "STOP" and error_code is None:
        error_code = {
            "plan": "INVALID_NOTE_PLAN_OR_PPQ",
            "checkout": "DIRTY_OR_UNAVAILABLE_GIT_WORKTREE",
            "checkout_changed": "SOURCE_CHANGED_DURING_RUN",
            "connection": "FL_CONNECTION_UNAVAILABLE",
            "pre_state_nonempty": "UNSAFE_NONBLANK_TARGET",
            "readback": "READBACK_UNAVAILABLE",
            "verification": "EXACT_SET_MISMATCH",
        }.get(failure_stage, "TARGET_OR_EXECUTION_STOP")
    verification = {
        "operation": "piano_roll_note_roundtrip",
        "run_id": run_id,
        "planned_count": len(planned) if plan else None,
        "actual_count": len(actual) if "readback" in stages else None,
        "missing": list(report.missing) if report and complete else None,
        "extra": list(report.extra) if report and complete else None,
        "unexpected": list(report.extra) if report and complete else None,
        "duplicate_mismatches": _duplicate_mismatches(planned, actual) if complete else None,
        "mismatches": list(report.mismatches) if report and complete else None,
        "comparison_performed": bool(complete and report is not None),
        "write_error": "write_attempt" in stages and "write_queued" not in stages,
        "read_error": "target_before_trigger" in stages and "readback" not in stages,
        "adapter_status": report.status if report else None,
        "status": status,
        "failure_stage": failure_stage if status == "STOP" else None,
        "error_code": error_code if status == "STOP" else None,
        "error_type": error_type,
        "observed_at_utc": _utc_now(),
    }
    # 实际错误文本可能含本机路径；公开证据只保留阶段与异常类型。
    _write_json(run_dir / "environment.json", {
        "run_id": run_id,
        "scope": "live_fl_studio_note_roundtrip",
        "repository": "ryurikoneko/DAWLoop",
        "branch": initial_branch,
        "commit_sha": initial_commit,
        "dirty_worktree": not (
            checkout_clean and final_checkout.returncode == 0 and not final_checkout.stdout.strip()
        ),
        "source_consistent_through_run": source_consistent,
        "python_version": platform.python_version(),
        "os": platform.system(),
        "dawloop_version": report.dawloop_version if report else "0.2.0a0",
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
        "expected": {
            "project_id": PROJECT_NAME, "pattern_number": expected_pattern_number,
            "pattern_id": PATTERN_NAME, "channel_index": expected_channel_index,
            "channel_index_type": "global", "channel_name": CHANNEL_NAME,
            "ppq": ppq, "safe_to_edit": True,
        },
        "actual": target.to_dict() if target else {
            "project_id": None, "pattern_number": None, "pattern_id": None,
            "channel_index": None, "channel_index_type": None,
            "channel_name": None, "ppq": None, "safe_to_edit": None,
            "api_version": None, "fl_studio_version": None,
        },
        "status": "PASS" if identity_match else "STOP",
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
        "plan": plan.to_dict() if plan else None,
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
        "source": (
            "FL Studio Piano Roll state requested after an independent script trigger"
            if "readback" in stages else None
        ),
        "observation_clock": "local UTC host time; not a DAW timestamp",
        "state_mtime_clock": "local filesystem modification time; not a DAW revision",
        "actual_events": actual if "readback" in stages else None,
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
        "字段为 null 或 false 时，表示相应阶段未取得证据；不能按零差异理解。\n\n"
        "主动归档或公开前，请逐项检查这些文件是否含敏感信息。\n",
        encoding="utf-8", newline="\n",
    )
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="采集独立测试工程的现场音符往返证据")
    parser.add_argument("--identity-reader", help="可选；默认使用 DAWLoop 只读身份读取器")
    parser.add_argument("--midi-port", required=True, help="与 DAWLoop 控制器对应的精确 MIDI 输出端口名")
    parser.add_argument("--ppq", required=True, type=int, help="FL Studio 当前工程的 PPQ；写前现场核对")
    parser.add_argument("--expected-pattern-number", required=True, type=int)
    parser.add_argument("--expected-channel-index", required=True, type=int, help="全局 Channel 索引")
    parser.add_argument("--confirm-disposable-project", required=True)
    args = parser.parse_args(argv)
    if args.confirm_disposable_project != PROJECT_NAME:
        parser.error(f"必须明确确认独立测试工程：{PROJECT_NAME}")
    try:
        reader = _load_reader(args.identity_reader) if args.identity_reader \
            else lambda: read_current_target(args.midi_port)
    except (ImportError, AttributeError, TypeError, ValueError):
        reader = None
    if reader is None:
        def reader():
            raise RuntimeError("无法载入独立的现场身份读取器")

    result_dir = asyncio.run(capture_note_roundtrip(
        reader, args.ppq, expected_pattern_number=args.expected_pattern_number,
        expected_channel_index=args.expected_channel_index, midi_port=args.midi_port,
    ))
    result = json.loads((result_dir / "verification.json").read_text(encoding="utf-8"))
    print(f"LiveNoteRoundTripVerification: {result['status']} | {result_dir}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
