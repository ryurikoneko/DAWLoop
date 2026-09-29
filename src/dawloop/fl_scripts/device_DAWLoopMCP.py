# name=DAWLoop MCP Controller

"""在原有 MCP MIDI/JSON 通道中增加只读目标身份查询。"""

import json
import os
import sys
from pathlib import Path

import channels
import general
import patterns
import ui


def _controller_dir():
    if sys.platform == "win32":
        base = Path(os.environ.get("USERPROFILE", "~"))
    else:
        base = Path.home()
    return base / "Documents" / "Image-Line" / "FL Studio" / "Settings" / "Hardware" / "FLStudioMCP"


sys.path.insert(0, str(_controller_dir()))
import device_FLStudioMCP as upstream


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


def OnInit():
    upstream.OnInit()


def OnDeInit():
    upstream.OnDeInit()


def OnIdle():
    upstream.OnIdle()


def OnMidiMsg(event):
    if event.midiId != 0x90 or event.data1 != upstream.TRIGGER_NOTE or event.data2 <= 0:
        upstream.OnMidiMsg(event)
        return
    try:
        command = json.loads(upstream.COMMAND_FILE.read_text(encoding="utf-8"))
        if not isinstance(command, dict) or command.get("action") != "dawloop.getTargetIdentity":
            upstream.OnMidiMsg(event)
            return
        upstream.write_response({"success": True, "target": read_target_identity()})
    except Exception as error:
        upstream.write_response({"success": False, "error": type(error).__name__})
    event.handled = True
