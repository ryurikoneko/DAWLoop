# name=FL Studio MCP Controller
# url=https://github.com/karl-andres/fl-studio-mcp
# supportedDevices=FL Studio MCP

"""
FL Studio MIDI Controller Script for MCP Integration.

This script runs inside FL Studio and receives MIDI trigger messages from the
MCP server. When triggered, it reads a command from a JSON file, executes the
corresponding FL Studio API function, and writes the response to another JSON file.

Communication flow:
1. MCP server writes command to mcp_command.json
2. MCP server sends MIDI note 127 (trigger)
3. This script receives the trigger via OnMidiMsg()
4. Script reads command JSON, executes FL Studio API
5. Script writes response to mcp_response.json
6. MCP server reads response
"""

import json
import os
import sys
from pathlib import Path

# FL Studio API modules (available when running inside FL Studio)
import channels
import general
import math
import mixer
import plugins
import transport


def _get_script_dir() -> Path:
    """Get the script directory path.

    FL Studio's Python environment doesn't support __file__, so we construct
    the path based on the platform's standard FL Studio settings location.
    """
    if sys.platform == "darwin":
        # macOS
        base = Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings"
    elif sys.platform == "win32":
        # Windows
        userprofile = os.environ.get("USERPROFILE", "~")
        base = Path(userprofile) / "Documents" / "Image-Line" / "FL Studio" / "Settings"
    else:
        # Linux (unlikely but handle it)
        base = Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings"

    return base / "Hardware" / "FLStudioMCP"


# File paths for JSON communication
SCRIPT_DIR = _get_script_dir()
COMMAND_FILE = SCRIPT_DIR / "mcp_command.json"
RESPONSE_FILE = SCRIPT_DIR / "mcp_response.json"

# MIDI trigger note
TRIGGER_NOTE = 127


def OnInit():
    """Called when the script is loaded."""
    print("FL Studio MCP Controller initialized")
    print(f"Command file: {COMMAND_FILE}")
    print(f"Response file: {RESPONSE_FILE}")


def OnDeInit():
    """Called when the script is unloaded."""
    print("FL Studio MCP Controller deinitialized")


def OnMidiMsg(event):
    """Called when a MIDI message is received."""
    # Check for trigger note (Note On, note 127)
    if event.midiId == 0x90 and event.data1 == TRIGGER_NOTE and event.data2 > 0:
        execute_pending_command()
        event.handled = True


def OnIdle():
    """Called periodically when FL Studio is idle."""
    pass  # Required FL Studio API hook; no polling needed


def execute_pending_command():
    """Read command from JSON file, execute it, and write response."""
    response = {"success": False, "error": None}

    try:
        # Read command file
        if not COMMAND_FILE.exists():
            response["error"] = "No command file found"
            write_response(response)
            return

        command_text = COMMAND_FILE.read_text()
        command = json.loads(command_text)

        action = command.get("action", "")
        params = command.get("params", {})

        # Execute command and get result
        result = dispatch_command(action, params)
        response = {"success": True, **result}

    except json.JSONDecodeError as e:
        response["error"] = f"Invalid JSON in command file: {e}"
    except Exception as e:
        response["error"] = f"Error executing command: {e}"

    write_response(response)


def write_response(response: dict):
    """Write response to JSON file."""
    try:
        RESPONSE_FILE.write_text(json.dumps(response, indent=2))
    except Exception as e:
        print(f"Error writing response: {e}")


def dispatch_command(action: str, params: dict) -> dict:
    """Route command to appropriate handler and return result."""

    # Transport commands
    if action == "transport.start":
        return handle_transport_start()
    elif action == "transport.stop":
        return handle_transport_stop()
    elif action == "transport.record":
        return handle_transport_record()
    elif action == "transport.getStatus":
        return handle_transport_get_status()
    elif action == "transport.setPosition":
        return handle_transport_set_position(params)
    elif action == "transport.getLength":
        return handle_transport_get_length()
    elif action == "transport.setLoopMode":
        return handle_transport_set_loop_mode(params)
    elif action == "transport.setPlaybackSpeed":
        return handle_transport_set_playback_speed(params)

    # Mixer commands
    elif action == "mixer.getTrackCount":
        return handle_mixer_get_track_count()
    elif action == "mixer.getTrackInfo":
        return handle_mixer_get_track_info(params)
    elif action == "mixer.getAllTracks":
        return handle_mixer_get_all_tracks(params)
    elif action == "mixer.setTrackVolume":
        return handle_mixer_set_track_volume(params)
    elif action == "mixer.setTrackPan":
        return handle_mixer_set_track_pan(params)
    elif action == "mixer.muteTrack":
        return handle_mixer_mute_track(params)
    elif action == "mixer.soloTrack":
        return handle_mixer_solo_track(params)
    elif action == "mixer.armTrack":
        return handle_mixer_arm_track(params)
    elif action == "mixer.setTrackName":
        return handle_mixer_set_track_name(params)
    elif action == "mixer.setTrackColor":
        return handle_mixer_set_track_color(params)
    elif action == "mixer.setStereoSep":
        return handle_mixer_set_stereo_sep(params)

    # Channel commands
    elif action == "channels.getCount":
        return handle_channels_get_count(params)
    elif action == "channels.getInfo":
        return handle_channels_get_info(params)
    elif action == "channels.getAll":
        return handle_channels_get_all()
    elif action == "channels.getSelected":
        return handle_channels_get_selected()
    elif action == "channels.select":
        return handle_channels_select(params)
    elif action == "channels.selectOne":
        return handle_channels_select_one(params)
    elif action == "channels.triggerNote":
        return handle_channels_trigger_note(params)
    elif action == "channels.setVolume":
        return handle_channels_set_volume(params)
    elif action == "channels.setPan":
        return handle_channels_set_pan(params)
    elif action == "channels.mute":
        return handle_channels_mute(params)
    elif action == "channels.solo":
        return handle_channels_solo(params)
    elif action == "channels.setName":
        return handle_channels_set_name(params)
    elif action == "channels.setColor":
        return handle_channels_set_color(params)
    elif action == "channels.routeToMixer":
        return handle_channels_route_to_mixer(params)

    # Step sequencer commands
    elif action == "channels.getGridBit":
        return handle_channels_get_grid_bit(params)
    elif action == "channels.setGridBit":
        return handle_channels_set_grid_bit(params)
    elif action == "channels.getStepSequence":
        return handle_channels_get_step_sequence(params)
    elif action == "channels.setStepSequence":
        return handle_channels_set_step_sequence(params)

    # Plugin commands
    elif action == "plugins.isValid":
        return handle_plugins_is_valid(params)
    elif action == "plugins.getName":
        return handle_plugins_get_name(params)
    elif action == "plugins.getParamCount":
        return handle_plugins_get_param_count(params)
    elif action == "plugins.getParams":
        return handle_plugins_get_params(params)
    elif action == "plugins.getParamValue":
        return handle_plugins_get_param_value(params)
    elif action == "plugins.setParamValue":
        return handle_plugins_set_param_value(params)
    elif action == "plugins.getPresetCount":
        return handle_plugins_get_preset_count(params)
    elif action == "plugins.nextPreset":
        return handle_plugins_next_preset(params)
    elif action == "plugins.prevPreset":
        return handle_plugins_prev_preset(params)
    elif action == "plugins.getColor":
        return handle_plugins_get_color(params)

    else:
        return {"error": f"Unknown action: {action}"}


# =============================================================================
# Transport Handlers
# =============================================================================


def handle_transport_start() -> dict:
    """Toggle play/pause."""
    transport.start()
    return {"is_playing": transport.isPlaying() == 1}


def handle_transport_stop() -> dict:
    """Stop playback."""
    transport.stop()
    return {"stopped": True}


def handle_transport_record() -> dict:
    """Toggle recording."""
    transport.record()
    return {"is_recording": transport.isRecording() == 1}


def handle_transport_get_status() -> dict:
    """Get transport status."""
    loop_mode = transport.getLoopMode()
    return {
        "is_playing": transport.isPlaying() == 1,
        "is_recording": transport.isRecording() == 1,
        "position": transport.getSongPosHint(),
        "loop_mode": "song" if loop_mode == 1 else "pattern",
    }


def handle_transport_set_position(params: dict) -> dict:
    """Set playback position."""
    position = params.get("position", 0)
    mode = params.get("mode", 2)  # Default: seconds
    transport.setSongPos(position, mode)
    return {"position": transport.getSongPosHint()}


def handle_transport_get_length() -> dict:
    """Get song length."""
    return {
        "ticks": transport.getSongLength(3),
        "seconds": transport.getSongLength(2),
        "milliseconds": transport.getSongLength(1),
    }


def handle_transport_set_loop_mode(params: dict) -> dict:
    """Set loop mode."""
    mode = params.get("mode", "pattern")
    current_mode = transport.getLoopMode()
    target_mode = 1 if mode.lower() == "song" else 0

    if current_mode != target_mode:
        transport.setLoopMode()

    return {"mode": mode}


def handle_transport_set_playback_speed(params: dict) -> dict:
    """Set playback speed."""
    speed = params.get("speed", 1.0)
    transport.setPlaybackSpeed(speed)
    return {"speed": speed}


# =============================================================================
# Mixer Handlers
# =============================================================================


def handle_mixer_get_track_count() -> dict:
    """Get number of mixer tracks."""
    return {"count": mixer.trackCount()}


def handle_mixer_get_track_info(params: dict) -> dict:
    """Get info about a mixer track."""
    track = params.get("track", 0)
    return {
        "index": track,
        "name": mixer.getTrackName(track),
        "volume": mixer.getTrackVolume(track),
        "volume_db": mixer.getTrackVolume(track, 1),
        "pan": mixer.getTrackPan(track),
        "stereo_separation": mixer.getTrackStereoSep(track),
        "is_muted": mixer.isTrackMuted(track) == 1,
        "is_solo": mixer.isTrackSolo(track) == 1,
        "is_armed": mixer.isTrackArmed(track) == 1,
        "color": hex(mixer.getTrackColor(track)),
    }


def handle_mixer_get_all_tracks(params: dict) -> dict:
    """Get info about all mixer tracks."""
    include_empty = params.get("include_empty", False)
    tracks = []
    track_count = mixer.trackCount()

    for i in range(track_count):
        name = mixer.getTrackName(i)

        # Skip empty tracks if requested
        if not include_empty and (not name or name.startswith("Insert ")):
            if i != 0:  # Always include master
                continue

        tracks.append({
            "index": i,
            "name": name if name else ("Master" if i == 0 else f"Insert {i}"),
            "volume": mixer.getTrackVolume(i),
            "pan": mixer.getTrackPan(i),
            "is_muted": mixer.isTrackMuted(i) == 1,
            "is_solo": mixer.isTrackSolo(i) == 1,
        })

    return {"tracks": tracks}


def handle_mixer_set_track_volume(params: dict) -> dict:
    """Set mixer track volume."""
    track = params.get("track", 0)
    volume = params.get("volume", 0.8)
    mixer.setTrackVolume(track, volume)
    return {
        "volume": mixer.getTrackVolume(track),
        "volume_db": mixer.getTrackVolume(track, 1),
    }


def handle_mixer_set_track_pan(params: dict) -> dict:
    """Set mixer track pan."""
    track = params.get("track", 0)
    pan = params.get("pan", 0.0)
    mixer.setTrackPan(track, pan)
    return {"pan": mixer.getTrackPan(track)}


def handle_mixer_mute_track(params: dict) -> dict:
    """Mute/unmute mixer track."""
    track = params.get("track", 0)
    muted = params.get("muted")  # None = toggle

    if muted is None:
        mixer.muteTrack(track, -1)
    else:
        mixer.muteTrack(track, 1 if muted else 0)

    return {
        "is_muted": mixer.isTrackMuted(track) == 1,
        "track_name": mixer.getTrackName(track),
    }


def handle_mixer_solo_track(params: dict) -> dict:
    """Solo/unsolo mixer track."""
    track = params.get("track", 0)
    solo = params.get("solo")  # None = toggle
    mode = params.get("mode", 3)

    if solo is None:
        mixer.soloTrack(track, -1, mode)
    else:
        mixer.soloTrack(track, 1 if solo else 0, mode)

    return {
        "is_solo": mixer.isTrackSolo(track) == 1,
        "track_name": mixer.getTrackName(track),
    }


def handle_mixer_arm_track(params: dict) -> dict:
    """Toggle arm state of mixer track."""
    track = params.get("track", 0)
    mixer.armTrack(track)
    return {
        "is_armed": mixer.isTrackArmed(track) == 1,
        "track_name": mixer.getTrackName(track),
    }


def handle_mixer_set_track_name(params: dict) -> dict:
    """Set mixer track name."""
    track = params.get("track", 0)
    name = params.get("name", "")
    mixer.setTrackName(track, name)
    return {"name": name}


def handle_mixer_set_track_color(params: dict) -> dict:
    """Set mixer track color."""
    track = params.get("track", 0)
    r = params.get("r", 0)
    g = params.get("g", 0)
    b = params.get("b", 0)
    # FL Studio's scripting API takes 0xRRGGBB
    color = (r << 16) | (g << 8) | b
    mixer.setTrackColor(track, color)
    return {"color": f"RGB({r}, {g}, {b})"}


def handle_mixer_set_stereo_sep(params: dict) -> dict:
    """Set mixer track stereo separation."""
    track = params.get("track", 0)
    separation = params.get("separation", 0.0)
    mixer.setTrackStereoSep(track, separation)
    return {"separation": separation}


# =============================================================================
# Channel Handlers
# =============================================================================


def handle_channels_get_count(params: dict) -> dict:
    """Get number of channels."""
    global_count = params.get("global_count", True)
    return {"count": channels.channelCount(global_count)}


def handle_channels_get_info(params: dict) -> dict:
    """Get info about a channel."""
    index = params.get("index", 0)
    use_global = params.get("use_global", True)

    return {
        "index": index,
        "name": channels.getChannelName(index, use_global),
        "color": hex(channels.getChannelColor(index, use_global)),
        "volume": channels.getChannelVolume(index, use_global),
        "pan": channels.getChannelPan(index, use_global),
        "pitch": channels.getChannelPitch(index, useGlobalIndex=use_global),
        "is_muted": channels.isChannelMuted(index, use_global) == 1,
        "is_solo": channels.isChannelSolo(index, use_global) == 1,
        "is_selected": channels.isChannelSelected(index, use_global) == 1,
        "target_fx_track": channels.getTargetFxTrack(index, use_global),
    }


def handle_channels_get_all() -> dict:
    """Get info about all channels."""
    channels_list = []
    count = channels.channelCount(True)

    for i in range(count):
        channels_list.append({
            "index": i,
            "name": channels.getChannelName(i, True),
            "is_muted": channels.isChannelMuted(i, True) == 1,
            "is_selected": channels.isChannelSelected(i, True) == 1,
            "target_fx_track": channels.getTargetFxTrack(i, True),
        })

    return {"channels": channels_list}


def handle_channels_get_selected() -> dict:
    """Get currently selected channel."""
    index = channels.selectedChannel(canBeNone=True, indexGlobal=True)

    if index is None or index < 0:
        return {"channel": None}

    return {
        "channel": {
            "index": index,
            "name": channels.getChannelName(index, True),
            "volume": channels.getChannelVolume(index, True),
            "pan": channels.getChannelPan(index, True),
            "is_muted": channels.isChannelMuted(index, True) == 1,
            "is_solo": channels.isChannelSolo(index, True) == 1,
        }
    }


def handle_channels_select(params: dict) -> dict:
    """Select/deselect a channel."""
    index = params.get("index", 0)
    select = params.get("select", True)
    channels.selectChannel(index, 1 if select else 0, True)
    return {
        "selected": select,
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_select_one(params: dict) -> dict:
    """Select only one channel, deselecting others."""
    index = params.get("index", 0)
    channels.selectOneChannel(index, True)
    return {"channel_name": channels.getChannelName(index, True)}


def handle_channels_trigger_note(params: dict) -> dict:
    """Trigger a MIDI note on a channel."""
    channel = params.get("channel", 0)
    note = params.get("note", 60)
    velocity = params.get("velocity", 100)
    midi_channel = params.get("midi_channel", -1)
    channels.midiNoteOn(channel, note, velocity, midi_channel)
    return {"triggered": True, "note": note, "velocity": velocity}


def handle_channels_set_volume(params: dict) -> dict:
    """Set channel volume."""
    index = params.get("index", 0)
    volume = params.get("volume", 0.8)
    channels.setChannelVolume(index, volume, True)
    return {
        "volume": channels.getChannelVolume(index, True),
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_set_pan(params: dict) -> dict:
    """Set channel pan."""
    index = params.get("index", 0)
    pan = params.get("pan", 0.0)
    channels.setChannelPan(index, pan, True)
    return {
        "pan": channels.getChannelPan(index, True),
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_mute(params: dict) -> dict:
    """Mute/unmute channel."""
    index = params.get("index", 0)
    muted = params.get("muted")  # None = toggle

    if muted is None:
        channels.muteChannel(index, -1, True)
    else:
        channels.muteChannel(index, 1 if muted else 0, True)

    return {
        "is_muted": channels.isChannelMuted(index, True) == 1,
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_solo(params: dict) -> dict:
    """Solo/unsolo channel."""
    index = params.get("index", 0)
    solo = params.get("solo")  # None = toggle

    if solo is None:
        channels.soloChannel(index, -1, True)
    else:
        channels.soloChannel(index, 1 if solo else 0, True)

    return {
        "is_solo": channels.isChannelSolo(index, True) == 1,
        "channel_name": channels.getChannelName(index, True),
    }


def handle_channels_set_name(params: dict) -> dict:
    """Set channel name."""
    index = params.get("index", 0)
    name = params.get("name", "")
    channels.setChannelName(index, name, True)
    return {"name": name}


def handle_channels_set_color(params: dict) -> dict:
    """Set channel color."""
    index = params.get("index", 0)
    r = params.get("r", 0)
    g = params.get("g", 0)
    b = params.get("b", 0)
    # FL Studio's scripting API takes 0xRRGGBB
    color = (r << 16) | (g << 8) | b
    channels.setChannelColor(index, color, True)
    return {"color": f"RGB({r}, {g}, {b})"}


def handle_channels_route_to_mixer(params: dict) -> dict:
    """Route channel to mixer track."""
    channel_index = params.get("channel_index", 0)
    mixer_track = params.get("mixer_track", 0)
    channels.setTargetFxTrack(channel_index, mixer_track, True)
    return {
        "channel_name": channels.getChannelName(channel_index, True),
        "mixer_track": mixer_track,
    }


# =============================================================================
# Step Sequencer Handlers
# =============================================================================


def handle_channels_get_grid_bit(params: dict) -> dict:
    """Get whether a step is active."""
    channel = params.get("channel", 0)
    position = params.get("position", 0)
    return {"value": channels.getGridBit(channel, position, True) == 1}


def handle_channels_set_grid_bit(params: dict) -> dict:
    """Set a step on or off."""
    channel = params.get("channel", 0)
    position = params.get("position", 0)
    value = params.get("value", False)
    channels.setGridBit(channel, position, 1 if value else 0, True)
    return {
        "value": value,
        "channel_name": channels.getChannelName(channel, True),
    }


def handle_channels_get_step_sequence(params: dict) -> dict:
    """Get step sequence for a channel."""
    channel = params.get("channel", 0)
    steps = params.get("steps", 16)
    sequence = []

    for i in range(steps):
        sequence.append(channels.getGridBit(channel, i, True) == 1)

    return {"sequence": sequence}


def handle_channels_set_step_sequence(params: dict) -> dict:
    """Set complete step sequence for a channel."""
    channel = params.get("channel", 0)
    pattern = params.get("pattern", [])

    for i, value in enumerate(pattern):
        channels.setGridBit(channel, i, 1 if value else 0, True)

    active_steps = sum(pattern)
    return {
        "active_steps": active_steps,
        "total_steps": len(pattern),
        "channel_name": channels.getChannelName(channel, True),
    }


# =============================================================================
# Plugin Handlers
# =============================================================================


def handle_plugins_is_valid(params: dict) -> dict:
    """Check if plugin exists at location."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        valid = plugins.isValid(index, slot_index, True)
    else:
        valid = plugins.isValid(index, -1, use_global)

    return {"valid": valid == 1}


def handle_plugins_get_name(params: dict) -> dict:
    """Get plugin name."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        name = plugins.getPluginName(index, slot_index, 0, True)
    else:
        name = plugins.getPluginName(index, -1, 0, use_global)

    return {"name": name}


def handle_plugins_get_param_count(params: dict) -> dict:
    """Get number of plugin parameters."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        count = plugins.getParamCount(index, slot_index, True)
    else:
        count = plugins.getParamCount(index, -1, use_global)

    return {"count": count}


def _plugin_location(params, index_key="index"):
    index = params.get(index_key)
    slot = params.get("slot_index", -1)
    global_index = params.get("use_global", True)
    if type(index) is not int or index < 0 or type(slot) is not int or slot < -1:
        raise ValueError("PLUGIN_LOCATION_INVALID")
    if type(global_index) is not bool:
        raise ValueError("PLUGIN_INDEX_MODE_INVALID")
    api_version = general.getVersion()
    if type(api_version) is not int or api_version < 26:
        raise ValueError("PLUGIN_API_VERSION_UNSUPPORTED")
    return index, slot, True if slot >= 0 else global_index, api_version


def _plugin_display_value(param_index, index, slot, global_index):
    try:
        value = plugins.getParamValueString(param_index, index, slot, global_index)
        if type(value) is not str:
            raise ValueError("DISPLAY_TYPE_INVALID")
        return value, None
    except Exception as error:
        return None, {"index": param_index, "stage": "display", "error": type(error).__name__}


def handle_plugins_get_params(params: dict) -> dict:
    """全量扫描保留失败项；调用前后校验布局，显示文本允许缺失。"""
    index, slot, global_index, api_version = _plugin_location(params)
    max_params = params.get("max_params")
    if max_params is not None and (type(max_params) is not int or max_params < 0):
        raise ValueError("PARAMETER_LIMIT_INVALID")
    if plugins.isValid(index, slot, global_index) != 1:
        raise ValueError("PLUGIN_NOT_VALID")
    plugin_name = plugins.getPluginName(index, slot, 0, global_index)
    param_count = plugins.getParamCount(index, slot, global_index)
    if type(param_count) is not int or param_count < 0:
        raise ValueError("PARAMETER_COUNT_INVALID")
    if type(plugin_name) is not str or not plugin_name.strip():
        raise ValueError("PLUGIN_NAME_INVALID")
    errors, warnings, rows = [], [], []
    try:
        user_name = plugins.getPluginName(index, slot, 1, global_index)
        if type(user_name) is not str:
            raise ValueError("USER_NAME_INVALID")
    except Exception as error:
        user_name = None
        warnings.append({"index": None, "stage": "user_name", "error": type(error).__name__})
    # 超大布局明确标记截断，避免单次观察无限占用宿主线程。
    limit = min(param_count, 4096, param_count if max_params is None else max_params)
    for i in range(limit):
        try:
            name = plugins.getParamName(i, index, slot, global_index)
            value = plugins.getParamValue(i, index, slot, global_index)
            if type(name) is not str or not name.strip():
                raise ValueError("PARAMETER_NAME_INVALID")
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("NORMALIZED_VALUE_INVALID")
        except Exception as error:
            errors.append({"index": i, "stage": "parameter", "error": type(error).__name__})
            continue
        value_string, warning = _plugin_display_value(i, index, slot, global_index)
        if warning is not None:
            warnings.append(warning)
        rows.append({"index": i, "name": name, "value": value, "value_string": value_string})
    count_after = None
    try:
        count_after = plugins.getParamCount(index, slot, global_index)
        name_after = plugins.getPluginName(index, slot, 0, global_index)
        if type(count_after) is not int or count_after != param_count or name_after != plugin_name:
            errors.append({"index": None, "stage": "identity", "error": "PLUGIN_LAYOUT_CHANGED"})
        # 参数总数不变仍可能发生重排，必须重新读取名字序列。
        for row in rows:
            if plugins.getParamName(row["index"], index, slot, global_index) != row["name"]:
                errors.append({"index": row["index"], "stage": "layout", "error": "PARAMETER_LAYOUT_CHANGED"})
    except Exception as error:
        errors.append({"index": None, "stage": "identity", "error": type(error).__name__})
    truncated = limit < param_count
    return {
        "schema_version": "plugin-parameter-scan-v1", "api_version": api_version,
        "plugin_name": plugin_name, "plugin_user_name": user_name,
        "parameter_count": param_count, "parameter_count_after": count_after,
        "params": rows, "errors": errors, "warnings": warnings,
        "truncated": truncated, "complete": not truncated and not errors and len(rows) == param_count,
    }


def handle_plugins_get_param_value(params: dict) -> dict:
    """显示字符串不可用时保留实际 normalized 读值。"""
    index, slot, global_index, _ = _plugin_location(params, "plugin_index")
    param_index = params.get("param_index")
    count = plugins.getParamCount(index, slot, global_index)
    if type(param_index) is not int or type(count) is not int or not 0 <= param_index < count:
        raise ValueError("PARAMETER_INDEX_INVALID")
    name = plugins.getParamName(param_index, index, slot, global_index)
    value = plugins.getParamValue(param_index, index, slot, global_index)
    value_string, warning = _plugin_display_value(param_index, index, slot, global_index)
    return {"index": param_index, "name": name, "value": value,
            "value_string": value_string, "display_warning": warning}


def handle_plugins_set_param_value(params: dict) -> dict:
    """保留既有写接口；所有校验在 setter 前完成，不重试。"""
    index, slot, global_index, _ = _plugin_location(params, "plugin_index")
    param_index, value = params.get("param_index"), params.get("value")
    count = plugins.getParamCount(index, slot, global_index)
    if type(param_index) is not int or type(count) is not int or not 0 <= param_index < count:
        raise ValueError("PARAMETER_INDEX_INVALID")
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("NORMALIZED_VALUE_INVALID")
    if plugins.isValid(index, slot, global_index) != 1:
        raise ValueError("PLUGIN_NOT_VALID")
    name = plugins.getParamName(param_index, index, slot, global_index)
    plugins.setParamValue(value, param_index, index, slot, 0, global_index)
    new_value = plugins.getParamValue(param_index, index, slot, global_index)
    value_string, warning = _plugin_display_value(param_index, index, slot, global_index)
    return {"name": name, "value": new_value, "value_string": value_string, "display_warning": warning}


def handle_plugins_get_preset_count(params: dict) -> dict:
    """Get number of plugin presets."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        count = plugins.getPresetCount(index, slot_index, True)
    else:
        count = plugins.getPresetCount(index, -1, use_global)

    return {"count": count}


def handle_plugins_next_preset(params: dict) -> dict:
    """Switch to next preset."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        plugin_name = plugins.getPluginName(index, slot_index, 0, True)
        plugins.nextPreset(index, slot_index, True)
    else:
        plugin_name = plugins.getPluginName(index, -1, 0, use_global)
        plugins.nextPreset(index, -1, use_global)

    return {"plugin_name": plugin_name}


def handle_plugins_prev_preset(params: dict) -> dict:
    """Switch to previous preset."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        plugin_name = plugins.getPluginName(index, slot_index, 0, True)
        plugins.prevPreset(index, slot_index, True)
    else:
        plugin_name = plugins.getPluginName(index, -1, 0, use_global)
        plugins.prevPreset(index, -1, use_global)

    return {"plugin_name": plugin_name}


def handle_plugins_get_color(params: dict) -> dict:
    """Get plugin color."""
    index = params.get("index", 0)
    slot_index = params.get("slot_index", -1)
    use_global = params.get("use_global", True)

    if slot_index >= 0:
        color = plugins.getColor(index, slot_index, 0, 0, True)
    else:
        color = plugins.getColor(index, -1, 0, 0, use_global)

    return {"color": hex(color)}
