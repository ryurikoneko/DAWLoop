# name=DAWLoop Controller
# supportedDevices=DAWLoop MCP IN,FLSkill MCP IN

"""DAWLoop 主控制器；沿用随包 FL Studio MCP 的 MIDI/JSON 执行通道。"""

import importlib.util
import json
import sys
from pathlib import Path

import channels
import general
import patterns
import ui


SETTINGS_DIR_OVERRIDE = None
UPSTREAM_SCRIPT_OVERRIDE = None
SETTINGS_DIR = Path(SETTINGS_DIR_OVERRIDE) if SETTINGS_DIR_OVERRIDE else (
    Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings"
)
SCRIPT_DIR = SETTINGS_DIR / "Hardware" / "DAWLoopMCP"
COMMAND_FILE = SCRIPT_DIR / "mcp_command.json"
RESPONSE_FILE = SCRIPT_DIR / "mcp_response.json"
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
    return isinstance(command, dict) and command.get("action") == "dawloop.getTargetIdentity"


def _handle_identity_request() -> None:
    request_id = None
    try:
        command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
        if command.get("action") != "dawloop.getTargetIdentity":
            return
        params = command.get("params", {})
        request_id = params.get("request_id") if isinstance(params, dict) else None
        response = {
            "success": True,
            "target": _target_identity(),
            "request_id": request_id,
        }
    except Exception as error:
        response = {"success": False, "error": type(error).__name__, "request_id": request_id}
    RESPONSE_FILE.write_text(json.dumps(response, ensure_ascii=True), encoding="utf-8")
    try:
        COMMAND_FILE.unlink()
    except OSError:
        pass


def OnInit():
    print("DAWLoop Controller initialized")
    _UPSTREAM.OnInit()


def OnDeInit():
    _UPSTREAM.OnDeInit()
    print("DAWLoop Controller stopped")


def OnMidiMsg(event):
    if event.midiId == 0x90 and event.data1 == _UPSTREAM.TRIGGER_NOTE and event.data2 > 0:
        if _identity_request_pending():
            _handle_identity_request()
            event.handled = True
            return
    _UPSTREAM.OnMidiMsg(event)


def OnSysEx(event):
    callback = getattr(_UPSTREAM, "OnSysEx", None)
    if callback is not None:
        callback(event)
