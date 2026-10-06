# name=DAWLoop Target Identity (development only / transitional)

"""通过独立 MIDI/JSON 通道只读取当前目标身份。"""

import json
import os
from pathlib import Path

import channels
import general
import patterns
import ui


SETTINGS_DIR_OVERRIDE = None
SETTINGS_DIR = Path(SETTINGS_DIR_OVERRIDE) if SETTINGS_DIR_OVERRIDE else (
    Path(os.environ.get("USERPROFILE", str(Path.home())))
    / "Documents" / "Image-Line" / "FL Studio" / "Settings"
)
SCRIPT_DIR = SETTINGS_DIR / "Hardware" / "DAWLoopMCP"
COMMAND_FILE = SCRIPT_DIR / "identity_command.json"
RESPONSE_FILE = SCRIPT_DIR / "identity_response.json"
def _read(call):
    try:
        return call()
    except Exception:
        return None


def read_target_identity():
    number = _read(patterns.patternNumber)
    index = _read(lambda: channels.selectedChannel(1, 0, 1))
    safe = _read(general.safeToEdit)
    return {
        "project_title": _read(general.getProjectTitle),
        "pattern_number": number,
        "pattern_name": _read(lambda: patterns.getPatternName(number)) if type(number) is int and number > 0 else None,
        "channel_index": index,
        "channel_name": _read(lambda: channels.getChannelName(index, True)) if type(index) is int and index >= 0 else None,
        "channel_index_type": "global",
        "ppq": _read(general.getRecPPQ),
        "safe_to_edit": bool(safe) if safe in (0, 1, False, True) else None,
        "api_version": _read(general.getVersion),
        "fl_studio_version": _read(lambda: ui.getVersion(4)),
        "source": "fl_studio_midi_scripting",
    }


def OnIdle():
    if not COMMAND_FILE.is_file():
        return
    request_id = None
    try:
        command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
        request_id = command.get("request_id") if isinstance(command, dict) else None
        if not isinstance(command, dict) or command.get("action") != "dawloop.getTargetIdentity":
            response = {"success": False, "error": "UNSUPPORTED_ACTION", "request_id": request_id}
        else:
            response = {"success": True, "target": read_target_identity(), "request_id": request_id}
    except Exception as error:
        response = {"success": False, "error": type(error).__name__, "request_id": request_id}
    try:
        RESPONSE_FILE.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        COMMAND_FILE.unlink(missing_ok=True)
    except OSError:
        pass
