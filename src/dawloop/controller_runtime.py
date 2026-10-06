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
_MODULE_EVENT = "MODULE_LOADED"
_INIT_EVENT = "ON_INIT_ENTERED"


def controller_runtime_paths(controller_script: Path) -> dict[str, Path]:
    """以已安装 Controller 所在目录作为唯一绝对 runtime root。"""
    root = controller_script.expanduser().resolve().parent
    return {
        "root": root,
        "module": root / "controller_module_status.json",
        "init": root / "controller_init_status.json",
        "ready": root / "controller_status.json",
        "error": root / "controller_bootstrap_error.json",
        "error_marker": root / "controller_bootstrap_error.marker",
    }


def _read_current_marker(path: Path, expected_build_id: str | None) -> tuple[dict | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "MALFORMED"
    if not isinstance(payload, dict):
        return None, "MALFORMED"
    if expected_build_id and payload.get("build_id") != expected_build_id:
        return None, "STALE_BUILD"
    return payload, None


def inspect_controller_lifecycle(
    controller_script: Path,
    expected_build_id: str | None,
    *,
    now: datetime | None = None,
) -> dict:
    paths = controller_runtime_paths(controller_script)
    module, module_error = _read_current_marker(paths["module"], expected_build_id)
    init, init_error = _read_current_marker(paths["init"], expected_build_id)
    runtime = inspect_runtime_status(paths["ready"], expected_build_id, now=now)
    error, error_read_error = _read_current_marker(paths["error"], expected_build_id)
    fallback_error = None
    if paths["error_marker"].is_file():
        try:
            candidate = paths["error_marker"].read_text(encoding="utf-8")[:500]
            lines = candidate.splitlines()
            if (
                len(lines) >= 2
                and lines[0] == expected_build_id
                and (module is None or lines[1] == module.get("module_instance_id"))
            ):
                fallback_error = candidate
        except (OSError, UnicodeError):
            fallback_error = "UNREADABLE"

    current_module_id = module.get("module_instance_id") if module else None
    if error is not None and current_module_id is not None and error.get("module_instance_id") != current_module_id:
        error = None
    error_is_current = error is not None and (
        current_module_id is None or error.get("module_instance_id") == current_module_id
    )
    if error_is_current:
        verification = "STOP"
    elif fallback_error or module_error == "MALFORMED" or init_error == "MALFORMED" or error_read_error == "MALFORMED":
        verification = "STOP"
    elif module is None:
        verification = "RELOAD_REQUIRED"
    elif (
        module.get("event") != _MODULE_EVENT
        or not isinstance(module.get("module_instance_id"), str)
        or not module.get("module_instance_id")
        or Path(str(module.get("runtime_root", ""))).resolve() != paths["root"]
    ):
        verification = "STOP"
    elif init is None:
        verification = "STOP"
    elif (
        init.get("event") != _INIT_EVENT
        or init.get("module_instance_id") != module.get("module_instance_id")
        or not isinstance(init.get("session_id"), str)
        or not init.get("session_id")
    ):
        verification = "STOP"
    elif runtime.code == "CONTROLLER_RUNTIME_STALE":
        verification = "RELOAD_REQUIRED"
    elif not runtime.ready:
        verification = "STOP"
    elif runtime.payload.get("session_id") != init.get("session_id"):
        verification = "STOP"
    else:
        verification = "PASS"

    return {
        "paths": paths,
        "module": module,
        "module_error": module_error,
        "init": init,
        "init_error": init_error,
        "runtime": runtime,
        "error": error,
        "error_read_error": error_read_error,
        "fallback_error": fallback_error,
        "verification": verification,
    }


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
    if not build_id or not build_id.strip() or build_id == "source-uninstalled":
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
    if not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
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
    return inspect_runtime_status(controller_runtime_paths(controller)["ready"], expected_build_id, now=now)
