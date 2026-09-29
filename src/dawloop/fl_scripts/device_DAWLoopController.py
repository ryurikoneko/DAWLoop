# name=DAWLoop Controller
# supportedDevices=DAWLoop MCP IN,FLSkill MCP IN

"""DAWLoop 主控制器；沿用随包 FL Studio MCP 的 MIDI/JSON 执行通道。"""

import importlib.util
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import channels
import general
import patterns
import ui


SETTINGS_DIR_OVERRIDE = None
UPSTREAM_SCRIPT_OVERRIDE = None
CONTROLLER_BUILD_ID = "source-uninstalled"
CONTROLLER_VERSION = "phase0.7-runtime-status-v1"
PROTOCOL_VERSION = "dawloop-midi-json-v1"
HEARTBEAT_INTERVAL_SECONDS = 3.0
SETTINGS_DIR = Path(SETTINGS_DIR_OVERRIDE) if SETTINGS_DIR_OVERRIDE else (
    Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings"
)
SCRIPT_DIR = SETTINGS_DIR / "Hardware" / "DAWLoopMCP"
COMMAND_FILE = SCRIPT_DIR / "mcp_command.json"
RESPONSE_FILE = SCRIPT_DIR / "mcp_response.json"
STATUS_FILE = SCRIPT_DIR / "controller_status.json"
UPSTREAM_SCRIPT = Path(UPSTREAM_SCRIPT_OVERRIDE) if UPSTREAM_SCRIPT_OVERRIDE else (
    SCRIPT_DIR / "upstream_backend.py"
)


def _load_upstream():
    name = "dawloop_bundled_flstudio_mcp_controller"
    spec = importlib.util.spec_from_file_location(name, str(UPSTREAM_SCRIPT))
    if spec is None or spec.loader is None:
        raise ImportError("随包 FL Studio MCP 控制器不可加载")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    module.SCRIPT_DIR = SCRIPT_DIR
    module.COMMAND_FILE = COMMAND_FILE
    module.RESPONSE_FILE = RESPONSE_FILE
    return module


_UPSTREAM = _load_upstream()
_SESSION_ID = None
_INITIALIZED_AT = None
_LAST_STATUS_WRITE_MONOTONIC = 0.0


def _safe_read(call):
    try:
        return call()
    except Exception:
        return None


def _target_identity():
    pattern_number = _safe_read(patterns.patternNumber)
    channel_index = _safe_read(lambda: channels.selectedChannel(1, 0, 1))
    safe_to_edit = _safe_read(general.safeToEdit)
    return {
        "project_title": _safe_read(general.getProjectTitle),
        "pattern_number": pattern_number,
        "pattern_name": (
            _safe_read(lambda: patterns.getPatternName(pattern_number))
            if type(pattern_number) is int and pattern_number > 0 else None
        ),
        "channel_index": channel_index,
        "channel_name": (
            _safe_read(lambda: channels.getChannelName(channel_index, True))
            if type(channel_index) is int and channel_index >= 0 else None
        ),
        "channel_index_type": "global",
        "ppq": _safe_read(general.getRecPPQ),
        "safe_to_edit": (
            bool(safe_to_edit) if safe_to_edit in (0, 1, False, True) else None
        ),
        "api_version": _safe_read(general.getVersion),
        "fl_studio_version": _safe_read(lambda: ui.getVersion(4)),
        "source": "fl_studio_midi_scripting",
    }


def _identity_request_pending() -> bool:
    try:
        command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(command, dict) and command.get("action") in {
        "dawloop.getTargetIdentity", "dawloop.ping"
    }


def _request_id(command: dict | None) -> str | None:
    if not isinstance(command, dict):
        return None
    params = command.get("params")
    value = params.get("request_id") if isinstance(params, dict) else None
    return value if isinstance(value, str) else None


def _write_response(response: dict) -> None:
    temporary = RESPONSE_FILE.with_name(f".{RESPONSE_FILE.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(response, output, ensure_ascii=True)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(RESPONSE_FILE)


def _local_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _write_runtime_status(state: str = "READY") -> bool:
    global _LAST_STATUS_WRITE_MONOTONIC
    try:
        now = time.monotonic()
        if state == "READY" and now - _LAST_STATUS_WRITE_MONOTONIC < HEARTBEAT_INTERVAL_SECONDS:
            return True
        timestamp = _local_timestamp()
        payload = {
            "controller": "DAWLoop Controller",
            "build_id": CONTROLLER_BUILD_ID,
            "session_id": _SESSION_ID,
            "state": state,
            "initialized_at": _INITIALIZED_AT,
            "last_seen_at": timestamp,
            "protocol_version": PROTOCOL_VERSION,
            "controller_version": CONTROLLER_VERSION,
            "source": "fl_studio_user_script",
        }
        temporary = STATUS_FILE.with_name(f".{STATUS_FILE.name}.tmp")
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, ensure_ascii=True)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(STATUS_FILE)
        _LAST_STATUS_WRITE_MONOTONIC = now
        return True
    except Exception as error:
        print(f"DAWLOOP_RUNTIME_STATUS_WRITE_FAILED error={type(error).__name__}")
        return False


def _handle_diagnostic_request() -> None:
    request_id = None
    action = None
    stage = "command_read"
    print(f"DAWLOOP_TRACE IDENTITY_HANDLER_ENTER path={COMMAND_FILE}")
    try:
        command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
        print("DAWLOOP_TRACE COMMAND_FILE_FOUND")
        if not isinstance(command, dict):
            raise ValueError("IDENTITY_COMMAND_INVALID")
        action = command.get("action")
        params = command.get("params", {})
        request_id = _request_id(command)
        if not isinstance(params, dict) or not request_id:
            raise ValueError("IDENTITY_COMMAND_INVALID")
        print(f"DAWLOOP_TRACE COMMAND_PARSE_OK request_id={request_id}")
        if action == "dawloop.ping":
            response = {
                "request_id": request_id,
                "status": "PASS",
                "success": True,
                "stage": "midi_callback",
            }
        elif action == "dawloop.getTargetIdentity":
            stage = "identity_read"
            print(f"DAWLOOP_TRACE IDENTITY_READ_BEGIN request_id={request_id}")
            target = _target_identity()
            required = (
                "project_title", "pattern_number", "pattern_name", "channel_index",
                "channel_name", "ppq", "safe_to_edit", "api_version", "fl_studio_version",
            )
            missing = [key for key in required if target.get(key) is None]
            if missing:
                print(f"DAWLOOP_TRACE IDENTITY_READ_STOP request_id={request_id} missing_fields={','.join(missing)}")
                response = {
                    "success": False,
                    "status": "STOP",
                    "error_code": "FL_IDENTITY_FIELDS_UNAVAILABLE",
                    "stage": "identity_read",
                    "fields": None,
                    "missing_fields": missing,
                    "request_id": request_id,
                }
            else:
                print(f"DAWLOOP_TRACE IDENTITY_READ_OK request_id={request_id}")
                response = {
                    "success": True,
                    "status": "PASS",
                    "target": target,
                    "request_id": request_id,
                }
        else:
            raise ValueError("IDENTITY_COMMAND_INVALID")
    except Exception as error:
        code = str(error) if isinstance(error, ValueError) else type(error).__name__
        response = {
            "success": False,
            "status": "STOP",
            "error_code": code,
            "stage": stage,
            "fields": None,
            "request_id": request_id,
        }
        print(f"DAWLOOP_TRACE IDENTITY_READ_STOP request_id={request_id} error={type(error).__name__}")
    try:
        print(f"DAWLOOP_TRACE RESPONSE_WRITE_BEGIN request_id={request_id}")
        _write_response(response)
        print(f"DAWLOOP_TRACE RESPONSE_WRITE_OK request_id={request_id}")
    except Exception as error:
        print(f"DAWLOOP_TRACE RESPONSE_WRITE_STOP request_id={request_id} error={type(error).__name__}")
        raise
    try:
        COMMAND_FILE.unlink()
    except OSError:
        pass


def OnInit():
    global _SESSION_ID, _INITIALIZED_AT, _LAST_STATUS_WRITE_MONOTONIC
    print("DAWLoop Controller initialized")
    print(f"DAWLOOP_TRACE command_path={COMMAND_FILE} response_path={RESPONSE_FILE}")
    _UPSTREAM.OnInit()
    _SESSION_ID = uuid.uuid4().hex
    _INITIALIZED_AT = _local_timestamp()
    _LAST_STATUS_WRITE_MONOTONIC = 0.0
    _write_runtime_status()


def OnDeInit():
    _write_runtime_status("STOPPED")
    _UPSTREAM.OnDeInit()
    print("DAWLoop Controller stopped")


def OnIdle():
    _write_runtime_status()


def OnMidiMsg(event):
    _write_runtime_status()
    if event.midiId == 0x90 and event.data1 == _UPSTREAM.TRIGGER_NOTE and event.data2 > 0:
        command = None
        try:
            command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        request_id = _request_id(command)
        print(
            "DAWLOOP_TRACE callback=OnMidiMsg "
            f"status={getattr(event, 'status', event.midiId)} "
            f"data1={event.data1} data2={event.data2} "
            f"port={getattr(event, 'port', 'unknown')} request_id={request_id}"
        )
        if _identity_request_pending():
            _handle_diagnostic_request()
            event.handled = True
            return
    _UPSTREAM.OnMidiMsg(event)


def OnMidiIn(event):
    _write_runtime_status()
    if getattr(event, "data1", None) == _UPSTREAM.TRIGGER_NOTE and getattr(event, "data2", 0) > 0:
        print(
            "DAWLOOP_TRACE callback=OnMidiIn "
            f"status={getattr(event, 'status', 'unknown')} "
            f"data1={event.data1} data2={event.data2} "
            f"port={getattr(event, 'port', 'unknown')}"
        )
    # 保持未处理状态，让 FL 按官方事件顺序继续调用 OnMidiMsg。

def OnSysEx(event):
    callback = getattr(_UPSTREAM, "OnSysEx", None)
    if callback is not None:
        callback(event)
