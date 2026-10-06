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

SETTINGS_DIR_OVERRIDE = None
UPSTREAM_SCRIPT_OVERRIDE = None
CONTROLLER_BUILD_ID = "source-uninstalled"
CONTROLLER_VERSION = "phase0.8-bootstrap-trace-v1"
PROTOCOL_VERSION = "dawloop-midi-json-v1"
HEARTBEAT_INTERVAL_SECONDS = 3.0
_REPLACE_UNAVAILABLE = False
_CHANNEL_SELECTION_OPERATIONS = set()
_PIANO_ROLL_OPEN_OPERATIONS = set()
_TARGET_NAVIGATION_OPERATIONS = {}


def _resolve_runtime_root() -> Path:
    if SETTINGS_DIR_OVERRIDE:
        settings = Path(SETTINGS_DIR_OVERRIDE).expanduser().resolve()
        return (settings / "Hardware" / "DAWLoopMCP").resolve()
    return Path(__file__).resolve().parent


try:
    SCRIPT_DIR = _resolve_runtime_root()
    _RUNTIME_ROOT_ERROR = None
except Exception as error:
    SCRIPT_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
    _RUNTIME_ROOT_ERROR = error
RUNTIME_ROOT = str(SCRIPT_DIR)
COMMAND_FILE = SCRIPT_DIR / "mcp_command.json"
RESPONSE_FILE = SCRIPT_DIR / "mcp_response.json"
STATUS_FILE = SCRIPT_DIR / "controller_status.json"
MODULE_STATUS_FILE = SCRIPT_DIR / "controller_module_status.json"
INIT_STATUS_FILE = SCRIPT_DIR / "controller_init_status.json"
BOOTSTRAP_ERROR_FILE = SCRIPT_DIR / "controller_bootstrap_error.json"
MODULE_INSTANCE_ID = uuid.uuid4().hex
UPSTREAM_SCRIPT = Path(UPSTREAM_SCRIPT_OVERRIDE) if UPSTREAM_SCRIPT_OVERRIDE else (
    SCRIPT_DIR / "upstream_backend.py"
)


class _DiagnosticWriteError(Exception):
    def __init__(self, stage: str, original: Exception):
        super().__init__(type(original).__name__)
        self.stage = stage
        self.original = original


def _atomic_write_json(path: Path, payload: dict, stage_prefix: str) -> None:
    global _REPLACE_UNAVAILABLE
    temporary = path.with_name(f".{path.name}.{MODULE_INSTANCE_ID}.tmp")
    stage = f"{stage_prefix}_PARENT_CREATE"
    try:
        if not os.path.isdir(str(path.parent)):
            os.makedirs(str(path.parent), exist_ok=True)
        stage = f"{stage_prefix}_TEMP_WRITE"
        with open(str(temporary), "w", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, ensure_ascii=True)
            output.flush()
        stage = f"{stage_prefix}_REPLACE"
        try:
            if _REPLACE_UNAVAILABLE:
                raise SystemError('replace unavailable')
            os.replace(str(temporary), str(path))
        except SystemError:
            # 宿主嵌入环境允许写文件但拒绝替换；读端拒绝不完整 JSON，不宣称原子性。
            _REPLACE_UNAVAILABLE = True
            with open(str(path), 'w', encoding='utf-8', newline='\n') as output:
                json.dump(payload, output, ensure_ascii=True)
                output.flush()
    except Exception as error:
        try:
            if temporary.exists():
                temporary.unlink()
        except Exception:
            pass
        raise _DiagnosticWriteError(stage, error)


def _record_bootstrap_error(stage: str, error: Exception) -> None:
    if isinstance(error, _DiagnosticWriteError):
        stage = error.stage
        error = error.original
    payload = {
        "build_id": CONTROLLER_BUILD_ID,
        "module_instance_id": MODULE_INSTANCE_ID,
        "stage": stage,
        "exception_type": type(error).__name__,
        "safe_message": "文件系统操作失败" if isinstance(error, OSError) else "Controller 初始化阶段失败",
        "observed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
    }
    try:
        _atomic_write_json(BOOTSTRAP_ERROR_FILE, payload, "BOOTSTRAP_ERROR_WRITE")
    except Exception as marker_error:
        try:
            fallback = BOOTSTRAP_ERROR_FILE.with_suffix(".marker")
            with open(str(fallback), "w", encoding="utf-8", newline="\n") as output:
                output.write(
                    f"{CONTROLLER_BUILD_ID}\n{MODULE_INSTANCE_ID}\n"
                    f"{stage}\n{type(error).__name__}\n"
                )
        except Exception:
            print(f"DAWLOOP_BOOTSTRAP_ERROR_WRITE_FAILED error={type(marker_error).__name__}")


def _write_lifecycle_marker(path: Path, event: str, session_id: str | None = None) -> bool:
    payload = {
        "controller": "DAWLoop Controller",
        "event": event,
        "build_id": CONTROLLER_BUILD_ID,
        "module_instance_id": MODULE_INSTANCE_ID,
        "session_id": session_id,
        "observed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
        "runtime_root": RUNTIME_ROOT,
        "source": "fl_studio_user_script",
    }
    try:
        _atomic_write_json(path, payload, f"{event}_STATUS_WRITE")
        return True
    except Exception as error:
        _record_bootstrap_error(f"{event}_STATUS_WRITE", error)
        print(f"DAWLOOP_BOOTSTRAP_STATUS_WRITE_FAILED stage={getattr(error, 'stage', event)} error={type(getattr(error, 'original', error)).__name__}")
        return False


if _RUNTIME_ROOT_ERROR is not None:
    _record_bootstrap_error("MODULE_RUNTIME_ROOT_RESOLVE", _RUNTIME_ROOT_ERROR)
_write_lifecycle_marker(MODULE_STATUS_FILE, "MODULE_LOADED")


try:
    import channels
    import general
    import patterns
    import ui
except Exception as error:
    _record_bootstrap_error("PROJECT_IMPORT", error)
    raise

try:
    import plugins
except ImportError:
    plugins = None


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


try:
    _UPSTREAM = _load_upstream()
except Exception as error:
    _record_bootstrap_error("PROJECT_IMPORT", error)
    raise
_SESSION_ID = None
_INITIALIZED_AT = None
_LAST_STATUS_WRITE_MONOTONIC = 0.0
_PROJECT_GENERATION = uuid.uuid4().hex
_PROJECT_LOADING = False
UNDO_RESEARCH_ENABLED = False
_UNDO_RESEARCH_ATTEMPTS = set()


def _undo_state():
    return {key: _safe_read(getattr(general, method, lambda: None)) for key, method in (
        ('position', 'getUndoHistoryPos'), ('count', 'getUndoHistoryCount'),
        ('last', 'getUndoHistoryLast'), ('hint', 'getUndoLevelHint'),
        ('changed_flag', 'getChangedFlag'))}


def _research_undo_once(params):
    if UNDO_RESEARCH_ENABLED is not True:
        raise ValueError('UNDO_RESEARCH_DISABLED')
    trial = params.get('trial')
    if trial not in ('aligned', 'channel_mismatch', 'pattern_mismatch') or trial in _UNDO_RESEARCH_ATTEMPTS:
        raise ValueError('UNDO_RESEARCH_BUDGET_EXHAUSTED')
    if (params.get('source_hash') != 'bbf82b82bc172858d09ac9a3fd95818e3069d30a10ce152c1db1591ba6753570'
            or params.get('controller_session') != _SESSION_ID
            or params.get('project_generation') != _PROJECT_GENERATION or _PROJECT_LOADING):
        raise ValueError('UNDO_RESEARCH_CONTEXT_MISMATCH')
    before, after = params.get('before'), params.get('after')
    current = _undo_state()
    if not isinstance(before, dict) or not isinstance(after, dict) or current != after:
        raise ValueError('UNDO_HISTORY_CHANGED')
    if any(type(value.get(key)) is not int for value in (before, after) for key in ('position', 'count', 'last')):
        raise ValueError('UNDO_HISTORY_UNAVAILABLE')
    # 只认新增且位于末尾的一层；不猜测循环历史或跨层撤销。
    if (after['count'] != before['count'] + 1 or after['position'] != before['position'] + 1
            or after['last'] != before['last'] + 1
            or before['position'] != before['count'] or before['last'] != before['count'] - 1
            or after['position'] != after['count'] or after['last'] != after['count'] - 1):
        raise ValueError('UNDO_NEW_LEVEL_UNPROVEN')
    if general.safeToEdit() != 1:
        raise ValueError('UNDO_HOST_NOT_SAFE')
    _UNDO_RESEARCH_ATTEMPTS.add(trial)
    result = general.undoUp()
    return {'api_result': result, 'undo_before_call': current, 'undo_after_call': _undo_state()}


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


def _controller_identity_binding():
    return dict(controller_build_id=CONTROLLER_BUILD_ID,
                controller_session_id=_SESSION_ID,
                project_generation=_PROJECT_GENERATION,
                controller_version=CONTROLLER_VERSION)


def _validate_identity_build_request(params):
    binding = _controller_identity_binding()
    if (not isinstance(binding['controller_build_id'], str)
            or not binding['controller_build_id'].strip()
            or binding['controller_build_id'] == 'source-uninstalled'):
        raise ValueError('CONTROLLER_BUILD_ID_UNBOUND')
    expected = dict(expected_controller_build_id=binding['controller_build_id'],
                    controller_session_id=binding['controller_session_id'],
                    project_generation=binding['project_generation'])
    if any(params.get(key) != value for key, value in expected.items()) or _PROJECT_LOADING:
        raise ValueError('CONTROLLER_BUILD_CONTEXT_MISMATCH')


def _identity_snapshot():
    target = _target_identity()
    count = _safe_read(channels.channelCount)
    visible = []
    if type(count) is int and 0 <= count <= 10000:
        for index in range(count):
            visible.append({'visual_index': index+1,
                            'global_index': _safe_read(lambda: channels.getChannelIndex(index)),
                            'name': _safe_read(lambda: channels.getChannelName(index)),
                            'plugin_name': _safe_read(lambda: plugins.getPluginName(index, -1, 0, False)) if plugins else None})
    selected_plugin = (_safe_read(lambda: plugins.getPluginName(target['channel_index'], -1, 0, True))
                       if plugins and type(target.get('channel_index')) is int and target['channel_index'] >= 0 else None)
    target.update(**_controller_identity_binding(), project_identity=None, controller_session=_SESSION_ID,
                  project_loading=_PROJECT_LOADING,
                  selected_channels=([index for index in range(channels.channelCount(1))
                                      if channels.isChannelSelected(index, True)]
                                     if hasattr(channels, 'isChannelSelected') else None),
                  visible_channels=visible, existing_patterns=_existing_patterns(),
                  plugin_name=selected_plugin, undo_state=_undo_state(),
                  observed_at=_local_timestamp())
    return target


def _existing_patterns():
    maximum = _safe_read(lambda: patterns.patternMax())
    if type(maximum) is not int or not 1 <= maximum <= 10000:
        return None
    return [{'index': index, 'name': _safe_read(lambda: patterns.getPatternName(index)),
             'is_default': _safe_read(lambda: patterns.isPatternDefault(index))}
            for index in range(1, maximum + 1)]


def _navigate_target_once(params):
    base = {k: v for k, v in params.items() if k not in ('pattern_index', 'pattern_name')}
    index = _validate_channel_navigation_request(base)
    pattern = params.get('pattern_index')
    name = params.get('pattern_name')
    rows = _existing_patterns()
    if (type(pattern) is not int or not isinstance(name, str) or not name.strip()
            or rows is None or sum(row['index'] == pattern and row['name'] == name
                and row['is_default'] in (False, 0) for row in rows) != 1):
        raise ValueError('EXISTING_PATTERN_UNCONFIRMED')
    import midi
    if not all(callable(fn) for fn in (getattr(patterns, 'jumpToPattern', None),
            getattr(channels, 'selectOneChannel', None), getattr(ui, 'openEventEditor', None))):
        raise ValueError('NAVIGATION_API_UNAVAILABLE')
    event_id, editor_mode = _piano_roll_event_target(index)
    operation = params['operation_id']
    if operation in _TARGET_NAVIGATION_OPERATIONS or len(_TARGET_NAVIGATION_OPERATIONS) >= 1024:
        raise ValueError('NAVIGATION_TRANSACTION_BUDGET_EXHAUSTED')
    record = dict(status='EXECUTED_UNVERIFIED', operation_id=operation,
        request_id=params['request_id'], global_index=index, channel_name=params['channel_name'],
        pattern_index=pattern, pattern_name=name, controller_session=_SESSION_ID,
        navigation_transactions=1, primitives=[], **_controller_identity_binding())
    # 事务在首个基础动作之前消费；任一未知都停止，不继续或补动作。
    _TARGET_NAVIGATION_OPERATIONS[operation] = record
    steps = [('select_pattern', lambda: patterns.jumpToPattern(pattern)),
             ('select_channel_global', lambda: channels.selectOneChannel(index, True)),
             ('targeted_open_piano_roll', lambda: ui.openEventEditor(event_id, editor_mode))]
    for step, call in steps:
        row = dict(primitive=step, status='UNKNOWN', started_monotonic=time.monotonic())
        record['primitives'].append(row)
        try:
            call()
            if patterns.patternNumber() != pattern or patterns.getPatternName(pattern) != name:
                raise ValueError('NAVIGATION_PATTERN_MISMATCH')
            if step != 'select_pattern' and (channels.selectedChannel(1, 0, 1) != index or
                    [i for i in range(channels.channelCount(True)) if channels.isChannelSelected(i, True)] != [index]):
                raise ValueError('NAVIGATION_CHANNEL_MISMATCH')
            _validate_identity_build_request(params)
            row['status'] = 'EXECUTED_UNVERIFIED'
        finally:
            row['completed_monotonic'] = time.monotonic()
    return record


def _identity_request_pending() -> bool:
    try:
        command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(command, dict) and command.get("action") in {
        "dawloop.getTargetIdentity", "dawloop.getIdentitySnapshot", "dawloop.ping",
        "dawloop.researchUndoOnce", "dawloop.selectOneChannelOnce", "dawloop.openPianoRollOnce",
        "dawloop.navigateTargetOnce"
    }


def _validate_channel_navigation_request(params):
    _validate_identity_build_request(params)
    required = {'request_id', 'operation_id', 'expected_controller_build_id',
                'controller_session_id', 'project_generation', 'global_index', 'channel_name'}
    if set(params) != required or any(not isinstance(params[key], str) or not params[key].strip()
                                     for key in required - {'global_index'}):
        raise ValueError('CHANNEL_SELECTION_REQUEST_INVALID')
    index = params['global_index']
    count = channels.channelCount(True)
    if type(index) is not int or type(count) is not int or not 0 <= index < count:
        raise ValueError('CHANNEL_GLOBAL_INDEX_INVALID')
    if channels.getChannelName(index, True) != params['channel_name']:
        raise ValueError('CHANNEL_NAME_MISMATCH')
    if general.safeToEdit() != 1:
        raise ValueError('CHANNEL_SELECTION_UNSAFE_CONTEXT')
    return index


def _select_one_channel_once(params):
    index = _validate_channel_navigation_request(params)
    operation = params['operation_id']
    if operation in _CHANNEL_SELECTION_OPERATIONS:
        raise ValueError('CHANNEL_SELECTION_BUDGET_EXHAUSTED')
    if len(_CHANNEL_SELECTION_OPERATIONS) >= 1024:
        raise ValueError('CHANNEL_SELECTION_LEDGER_FULL')
    # 执行前消耗预算，异常或回执丢失均不能再次派发同一操作。
    _CHANNEL_SELECTION_OPERATIONS.add(operation)
    channels.selectOneChannel(index, True)
    return dict(status='EXECUTED_UNVERIFIED', operation_id=operation,
                request_id=params['request_id'], global_index=index,
                channel_name=params['channel_name'], controller_session=_SESSION_ID,
                **_controller_identity_binding())


def _piano_roll_event_target(index):
    import midi
    if (not callable(getattr(ui, 'openEventEditor', None)) or
            not callable(getattr(channels, 'getRecEventId', None)) or
            type(getattr(midi, 'REC_Chan_PianoRoll', None)) is not int or
            type(getattr(midi, 'EE_PR', None)) is not int):
        raise ValueError('PIANO_ROLL_OPEN_API_UNAVAILABLE')
    event_base = channels.getRecEventId(index, True)
    if type(event_base) is not int or event_base < 0:
        raise ValueError('PIANO_ROLL_EVENT_ID_INVALID')
    return event_base + midi.REC_Chan_PianoRoll, midi.EE_PR


def _open_piano_roll_once(params):
    index = _validate_channel_navigation_request(params)
    selected = [i for i in range(channels.channelCount(True)) if channels.isChannelSelected(i, True)]
    if channels.selectedChannel(1, 0, 1) != index or selected != [index]:
        raise ValueError('PIANO_ROLL_CHANNEL_NOT_UNIQUE')
    operation = params['operation_id']
    if operation in _PIANO_ROLL_OPEN_OPERATIONS:
        raise ValueError('PIANO_ROLL_OPEN_BUDGET_EXHAUSTED')
    if len(_PIANO_ROLL_OPEN_OPERATIONS) >= 1024:
        raise ValueError('PIANO_ROLL_OPEN_LEDGER_FULL')
    event_id, editor_mode = _piano_roll_event_target(index)
    # 显示窗口不能绑定通道；事件身份从宿主全局索引推导，仍须独立界面确认。
    _PIANO_ROLL_OPEN_OPERATIONS.add(operation)
    ui.openEventEditor(event_id, editor_mode)
    return dict(status='EXECUTED_UNVERIFIED', operation_id=operation,
                request_id=params['request_id'], global_index=index,
                channel_name=params['channel_name'], controller_session=_SESSION_ID,
                **_controller_identity_binding())


def _request_id(command: dict | None) -> str | None:
    if not isinstance(command, dict):
        return None
    params = command.get("params")
    value = params.get("request_id") if isinstance(params, dict) else None
    return value if isinstance(value, str) else None


def _write_response(response: dict) -> None:
    _atomic_write_json(RESPONSE_FILE, response, 'RESPONSE_WRITE')


def _local_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _write_runtime_status(state: str = "READY", stage_prefix: str = "ON_IDLE_STATUS_WRITE") -> bool:
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
            "project_generation": _PROJECT_GENERATION,
            "state": state,
            "initialized_at": _INITIALIZED_AT,
            "last_seen_at": timestamp,
            "protocol_version": PROTOCOL_VERSION,
            "controller_version": CONTROLLER_VERSION,
            "source": "fl_studio_user_script",
        }
        _atomic_write_json(STATUS_FILE, payload, stage_prefix)
        _LAST_STATUS_WRITE_MONOTONIC = now
        return True
    except Exception as error:
        _record_bootstrap_error(stage_prefix, error)
        print(f"DAWLOOP_RUNTIME_STATUS_WRITE_FAILED stage={getattr(error, 'stage', stage_prefix)} error={type(getattr(error, 'original', error)).__name__}")
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
        elif action == 'dawloop.getIdentitySnapshot':
            stage = 'identity_read'
            _validate_identity_build_request(params)
            response = {'success': True, 'target': _identity_snapshot(), 'request_id': request_id}
        elif action == 'dawloop.selectOneChannelOnce':
            stage = 'channel_selection'
            response = {'success': True, 'selection': _select_one_channel_once(params),
                        'request_id': request_id}
        elif action == 'dawloop.openPianoRollOnce':
            stage = 'piano_roll_open'
            response = {'success': True, 'selection': _open_piano_roll_once(params),
                        'request_id': request_id}
        elif action == 'dawloop.navigateTargetOnce':
            stage = 'target_navigation'
            response = {'success': True, 'selection': _navigate_target_once(params),
                        'request_id': request_id}
        elif action == 'dawloop.researchUndoOnce':
            stage = 'research_undo'
            result = _research_undo_once(params)
            response = {'success': True, 'undo': result, 'request_id': request_id}
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
        if stage == 'target_navigation':
            response['navigation'] = _TARGET_NAVIGATION_OPERATIONS.get(params.get('operation_id'))
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
    except (OSError, SystemError):
        pass


def OnInit():
    global _SESSION_ID, _INITIALIZED_AT, _LAST_STATUS_WRITE_MONOTONIC, _PROJECT_GENERATION, _PROJECT_LOADING
    _CHANNEL_SELECTION_OPERATIONS.clear()
    _PIANO_ROLL_OPEN_OPERATIONS.clear()
    _TARGET_NAVIGATION_OPERATIONS.clear()
    _SESSION_ID = uuid.uuid4().hex
    _INITIALIZED_AT = _local_timestamp()
    _LAST_STATUS_WRITE_MONOTONIC = 0.0
    _PROJECT_GENERATION = uuid.uuid4().hex
    _PROJECT_LOADING = False
    _write_lifecycle_marker(INIT_STATUS_FILE, "ON_INIT_ENTERED", _SESSION_ID)
    print("DAWLoop Controller initialized")
    print(f"DAWLOOP_TRACE command_path={COMMAND_FILE} response_path={RESPONSE_FILE}")
    try:
        _UPSTREAM.OnInit()
    except Exception as error:
        _record_bootstrap_error("ON_INIT_UPSTREAM_INIT", error)
        raise
    _write_runtime_status(stage_prefix="ON_INIT_STATUS_WRITE")


def OnDeInit():
    _write_runtime_status("STOPPED", "ON_DEINIT_STATUS_WRITE")
    _UPSTREAM.OnDeInit()
    print("DAWLoop Controller stopped")


def OnIdle():
    _write_runtime_status(stage_prefix="ON_IDLE_STATUS_WRITE")


def OnProjectLoad(status):
    global _PROJECT_GENERATION, _PROJECT_LOADING
    if status == 0:
        _PROJECT_GENERATION = uuid.uuid4().hex
        _PROJECT_LOADING = True
    elif status in (100, 101):
        _PROJECT_LOADING = status != 100
    callback = getattr(_UPSTREAM, 'OnProjectLoad', None)
    if callback is not None:
        callback(status)


def OnMidiMsg(event):
    _write_runtime_status(stage_prefix="ON_MIDI_STATUS_WRITE")
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
    _write_runtime_status(stage_prefix="ON_MIDI_STATUS_WRITE")
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
