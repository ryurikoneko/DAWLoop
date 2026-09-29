"""读取并判定本机 FL Studio Controller 的运行状态。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


FRESHNESS_SECONDS = 10.0
_BUILD_ID_RE = re.compile(r'^CONTROLLER_BUILD_ID\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


@dataclass(frozen=True)
class RuntimeObservation:
    code: str
    status: str
    payload: dict | None
    age_seconds: float | None

    @property
    def ready(self) -> bool:
        return self.code == "CONTROLLER_RUNTIME_READY"


def installed_controller_identity(script_path: Path) -> tuple[str | None, str | None]:
    """返回已安装脚本内嵌 build id 与独立的磁盘文件 SHA256。"""
    try:
        content = script_path.read_bytes()
    except OSError:
        return None, None
    text = content.decode("utf-8", errors="replace")
    match = _BUILD_ID_RE.search(text)
    build_id = match.group(1) if match else None
    if build_id == "source-uninstalled":
        build_id = None
    return build_id, hashlib.sha256(content).hexdigest().upper()


def inspect_runtime_status(
    status_path: Path,
    expected_build_id: str | None,
    *,
    now: datetime | None = None,
    freshness_seconds: float = FRESHNESS_SECONDS,
) -> RuntimeObservation:
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return RuntimeObservation("CONTROLLER_RUNTIME_STATUS_MISSING", "RELOAD_REQUIRED", None, None)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return RuntimeObservation("CONTROLLER_RUNTIME_STATUS_MALFORMED", "STOP", None, None)

    required = ("controller", "build_id", "session_id", "state", "initialized_at", "last_seen_at")
    if not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
        return RuntimeObservation("CONTROLLER_RUNTIME_STATUS_MALFORMED", "STOP", None, None)
    if payload["controller"] != "DAWLoop Controller":
        return RuntimeObservation("CONTROLLER_RUNTIME_STATUS_MALFORMED", "STOP", None, None)
    if expected_build_id and payload["build_id"] != expected_build_id:
        return RuntimeObservation("CONTROLLER_RUNTIME_BUILD_MISMATCH", "RELOAD_REQUIRED", payload, None)
    if payload["state"] != "READY":
        return RuntimeObservation("CONTROLLER_RUNTIME_NOT_READY", "STOP", payload, None)

    try:
        last_seen = datetime.fromisoformat(payload["last_seen_at"])
        initialized = datetime.fromisoformat(payload["initialized_at"])
        if last_seen.tzinfo is None or initialized.tzinfo is None:
            raise ValueError("timezone required")
    except ValueError:
        return RuntimeObservation("CONTROLLER_RUNTIME_STATUS_MALFORMED", "STOP", None, None)

    observed_now = now or datetime.now(timezone.utc).astimezone()
    age = (observed_now - last_seen).total_seconds()
    if age < -30.0:
        return RuntimeObservation("CONTROLLER_RUNTIME_STATUS_MALFORMED", "STOP", payload, age)
    if age > freshness_seconds:
        return RuntimeObservation("CONTROLLER_RUNTIME_STALE", "RELOAD_REQUIRED", payload, age)
    return RuntimeObservation("CONTROLLER_RUNTIME_READY", "PASS", payload, max(0.0, age))


def ping_preflight(settings_dir: Path, *, now: datetime | None = None) -> RuntimeObservation:
    """仅在已安装 build 与新鲜 READY runtime 一致时允许后续 PING。"""
    from dawloop.setup import configured_scripts

    controller = configured_scripts(settings_dir)["controller"]
    expected_build_id, _ = installed_controller_identity(controller)
    if not expected_build_id:
        return RuntimeObservation("CONTROLLER_BUILD_ID_MISSING", "RELOAD_REQUIRED", None, None)
    return inspect_runtime_status(
        controller.with_name("controller_status.json"), expected_build_id, now=now
    )
