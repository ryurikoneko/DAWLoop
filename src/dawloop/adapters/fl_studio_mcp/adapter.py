from __future__ import annotations

import asyncio
import importlib.metadata
import inspect
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from dawloop.mix_plan import decode_plugin_scan
from dawloop.note_plan import NotePlan
from dawloop.verification import compare_events

from .identity import TargetIdentity, require_same_target
from .mapping import plan_to_mcp_notes, state_to_events


UPSTREAM_COMMIT = "f89f66f8ca00d1f1fc27ed18ae4a9611551f98d0"
IdentityReader = Callable[[], TargetIdentity | Awaitable[TargetIdentity]]
EvidenceObserver = Callable[[str, dict], None]


@dataclass(frozen=True)
class LiveExecutionReport:
    status: str
    evidence_scope: str
    target: dict[str, str | int]
    planned_count: int
    actual_count: int
    planned_events: tuple[dict[str, int], ...]
    actual_events: tuple[dict[str, int], ...]
    missing: tuple[dict[str, int], ...]
    extra: tuple[dict[str, int], ...]
    mismatches: tuple[dict[str, object], ...]
    errors: tuple[str, ...]
    timestamp_utc: str
    dawloop_version: str
    upstream_commit: str = UPSTREAM_COMMIT

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _server_script() -> Path:
    source = Path(__file__).resolve().parents[2] / "fl_mcp_server.py"
    if source.is_file():
        return source
    raise FileNotFoundError("找不到 DAWLoop FL Studio MCP 启动适配器")


async def _call(client, name: str, arguments: dict | None = None):
    result = await client.call_tool(name, arguments or {})
    if result.is_error:
        raise RuntimeError(f"MCP 工具 {name} 返回错误")
    return result.data


def _event_dict(event) -> dict[str, int]:
    return event.to_dict()


def _report(plan: NotePlan, target: TargetIdentity, actual=(), errors=()) -> LiveExecutionReport:
    missing, extra, mismatches = compare_events(plan.events, actual)
    mismatch_rows = tuple({
        "planned": _event_dict(item.planned),
        "actual": _event_dict(item.actual),
        "fields": list(item.fields),
    } for item in mismatches)
    return LiveExecutionReport(
        status="STOP",
        evidence_scope="live_fl_studio",
        target=target.to_dict(),
        planned_count=len(plan.events),
        actual_count=len(actual),
        planned_events=tuple(_event_dict(item) for item in plan.events),
        actual_events=tuple(_event_dict(item) for item in actual),
        missing=tuple(_event_dict(item) for item in missing),
        extra=tuple(_event_dict(item) for item in extra),
        mismatches=mismatch_rows,
        errors=tuple(errors),
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        dawloop_version=_dawloop_version(),
    )


def _dawloop_version() -> str:
    try:
        return importlib.metadata.version("dawloop")
    except importlib.metadata.PackageNotFoundError:
        return "0.2.0a0"


class FLStudioMCPAdapter:
    """通过随包 MCP 服务执行音符写入，并以现场读回决定 PASS / STOP。"""

    async def discover(self) -> dict:
        from fastmcp import Client

        async with Client(str(_server_script()), timeout=10) as client:
            channels = await _call(client, "fl_get_all_channels")
            selected = await _call(client, "fl_get_selected_channel")
            piano = await _call(client, "fl_get_piano_roll_info")
            mixer = await _call(client, "fl_get_all_mixer_tracks", {"include_empty": True})
            return {
                "channels": channels,
                "selected_channel": selected,
                "piano_roll": piano,
                "mixer": mixer,
                "pattern_identity": {
                    "status": "STOP",
                    "reason": "上游 Piano Roll 状态不包含 Pattern 标识，需由外部目标读取器确认",
                },
            }

    async def inspect_plugin(self, index: int, slot_index: int = -1) -> dict:
        """只读查询已加载的 Channel 插件或 Mixer effect 参数。"""
        from fastmcp import Client

        async with Client(str(_server_script()), timeout=10) as client:
            valid = await _call(client, "fl_is_plugin_valid", {
                "index": index,
                "slot_index": slot_index,
            })
            if valid is not True:
                return {
                    "status": "STOP",
                    "reason": "插件不存在或 FL Studio 查询未成功；未读取参数",
                    "index": index,
                    "slot_index": slot_index,
                }
            scan = await _call(client, "fl_get_plugin_params", {
                "index": index,
                "slot_index": slot_index,
                "max_params": None,
                "include_metadata": True,
            })
            try:
                fingerprint, _ = decode_plugin_scan(scan)
            except ValueError as error:
                return {"status": "STOP", "reason": str(error), "scan": scan,
                        "index": index, "slot_index": slot_index}
            return {
                "status": "READBACK_RECEIVED",
                "evidence_scope": "live_fl_studio_plugin_read",
                "index": index, "slot_index": slot_index,
                "plugin_name": fingerprint.plugin_name,
                "plugin_user_name": scan.get("plugin_user_name"),
                "parameters": scan["params"], "scan": scan,
                "fingerprint": asdict(fingerprint), "layout_hash": fingerprint.layout_hash,
                "producer_instance_binding": "NOT_VERIFIED",
            }

    async def execute(
        self,
        plan: NotePlan,
        target: TargetIdentity,
        identity_reader: IdentityReader | None = None,
        evidence_observer: EvidenceObserver | None = None,
    ) -> LiveExecutionReport:
        if identity_reader is None:
            return _report(plan, target, errors=("缺少现场 Pattern / Channel 身份读取器；未写入",))

        actual_events = ()
        write_attempted = False
        def observe(stage: str, data: dict) -> None:
            if evidence_observer is not None:
                evidence_observer(stage, data)

        try:
            plan_notes = plan_to_mcp_notes(plan)
            from fastmcp import Client

            async with Client(str(_server_script()), timeout=15) as client:
                initial_identity = await _read_identity(identity_reader)
                require_same_target(target, initial_identity)
                _require_plan_target(plan, target)
                _require_selected_channel(await _call(client, "fl_get_selected_channel"), target)
                observe("target_before", initial_identity.to_dict())

                piano_info = await _call(client, "fl_get_piano_roll_info")
                if piano_info.get("request_file_exists"):
                    raise RuntimeError("上游请求队列已有内容；为避免执行他人操作，未继续")
                state_file = Path(piano_info["state_file"])
                before = state_file.stat().st_mtime_ns if state_file.exists() else 0
                refreshed = await _trigger_and_require_refresh(client, state_file, before)
                initial_state = await _call(client, "fl_get_piano_roll_state")
                initial_events = state_to_events(initial_state, plan.grid.ppq)
                observe("pre_state", {
                    "ppq": initial_state["ppq"],
                    "note_count": len(initial_events),
                    "state_mtime_before_ns": before,
                    "state_mtime_after_ns": refreshed,
                })
                if initial_events:
                    raise RuntimeError("目标 Piano Roll 非空；请使用专用空白测试 Pattern，未写入")

                require_same_target(target, await _read_identity(identity_reader))
                _require_selected_channel(await _call(client, "fl_get_selected_channel"), target)
                piano_info = await _call(client, "fl_get_piano_roll_info")
                if piano_info.get("request_file_exists"):
                    raise RuntimeError("上游请求队列在写入前发生变化；未继续")

                write_attempted = True
                observe("write_attempt", {"requested_count": len(plan_notes)})
                queued = await _call(client, "fl_send_notes", {
                    "notes": plan_notes,
                    "mode": "add",
                    "auto_trigger": False,
                })
                if not isinstance(queued, str) or not queued.startswith("Queued "):
                    raise RuntimeError(f"上游未确认请求已排队：{queued!r}")
                observe("write_queued", {"accepted": True})

                try:
                    queued_identity = await _read_identity(identity_reader)
                    require_same_target(target, queued_identity)
                    _require_selected_channel(await _call(client, "fl_get_selected_channel"), target)
                except Exception:
                    await _call(client, "fl_clear_request_queue")
                    observe("queue_cleared", {"reason": "target_changed_before_trigger"})
                    raise
                observe("target_before_trigger", queued_identity.to_dict())

                before = state_file.stat().st_mtime_ns if state_file.exists() else 0
                refreshed = await _trigger_and_require_refresh(client, state_file, before)
                candidate_events = state_to_events(
                    await _call(client, "fl_get_piano_roll_state"), plan.grid.ppq
                )
                final_identity = await _read_identity(identity_reader)
                require_same_target(target, final_identity)
                _require_selected_channel(await _call(client, "fl_get_selected_channel"), target)
                actual_events = candidate_events
                observe("target_after", final_identity.to_dict())
                observe("readback", {
                    "events": [_event_dict(item) for item in actual_events],
                    "state_mtime_before_ns": before,
                    "state_mtime_after_ns": refreshed,
                })

            report = _report(plan, target, actual_events)
            if not report.missing and not report.extra and not report.mismatches:
                return LiveExecutionReport(**{**asdict(report), "status": "PASS"})
            return report
        except Exception as error:
            phase = "写入后" if write_attempted else "写入前"
            return _report(plan, target, actual_events, (f"{phase}停止：{type(error).__name__}: {error}",))


async def _read_identity(reader: IdentityReader) -> TargetIdentity:
    value = reader()
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, TargetIdentity):
        raise TypeError("目标读取器必须返回 TargetIdentity")
    return value


def _require_plan_target(plan: NotePlan, target: TargetIdentity) -> None:
    if plan.target_id != target.pattern_id:
        raise ValueError("NotePlan target_id 必须与已确认的 Pattern 标识一致")


def _require_selected_channel(selected: dict | None, target: TargetIdentity) -> None:
    if not isinstance(selected, dict):
        raise ValueError("上游没有读到明确选中的 Channel")
    if selected.get("index") != target.channel_index or selected.get("name") != target.channel_name:
        raise ValueError("FL Studio 当前选中 Channel 与计划目标不一致")


async def _trigger_and_require_refresh(client, state_file: Path, previous_mtime: int) -> int:
    response = await _call(client, "fl_trigger_script")
    if not isinstance(response, str) or "triggered successfully" not in response.lower():
        raise RuntimeError(f"FL Studio 脚本未确认触发：{response!r}")
    # 上游触发函数只确认按键已发送，状态文件由 FL Studio 异步刷新。
    for _ in range(50):
        if state_file.exists():
            current_mtime = state_file.stat().st_mtime_ns
            if current_mtime > previous_mtime:
                return current_mtime
        await asyncio.sleep(0.1)
    raise RuntimeError("没有观察到新的 Piano Roll 状态读回")


async def probe_connection() -> tuple[bool, str]:
    from fastmcp import Client

    async with Client(str(_server_script()), timeout=8) as client:
        status = await _call(client, "fl_get_transport_status")
    if isinstance(status, dict) and "error" not in status:
        return True, "FL Studio 状态查询有响应"
    return False, f"FL Studio 状态查询失败：{status!r}"
