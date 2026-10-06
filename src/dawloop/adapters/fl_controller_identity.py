from __future__ import annotations

import asyncio
from dataclasses import fields, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

from dawloop.controller_runtime import ping_preflight
from dawloop.setup import default_settings_dir
from dawloop.runtime.identity import IdentityFieldStatus, IdentityObservation, TargetIdentitySnapshot, CompositeTargetIdentity


METHODS = {'project_title':'general.getProjectTitle', 'pattern_index':'patterns.patternNumber',
           'pattern_name':'patterns.getPatternName', 'channel_index':'channels.selectedChannel',
           'channel_name':'channels.getChannelName', 'plugin_name':'plugins.getPluginName',
           'ppq':'general.getRecPPQ', 'fl_version':'ui.getVersion'}
KEYS = {'pattern_index':'pattern_number', 'channel_index':'channel_index', 'fl_version':'fl_studio_version'}


def controller_snapshot(target):
    if not isinstance(target, dict) or target.get('source') != 'fl_studio_midi_scripting':
        raise ValueError('控制器身份响应来源无效')
    session, generation = target.get('controller_session'), target.get('project_generation')
    if not all(isinstance(v, str) and v for v in (session, generation)) or target.get('project_loading') is not False:
        raise ValueError('控制器上下文不可用')
    timestamp = datetime.fromisoformat(target['observed_at'])
    binding = session + ':' + generation
    values = {}
    status = {f.name:IdentityFieldStatus.UNAVAILABLE for f in fields(TargetIdentitySnapshot)}
    for name, method in METHODS.items():
        value = target.get(KEYS.get(name, name))
        if value is None or value == '' or (name == 'channel_index' and value == -1):
            continue
        numeric = name in {'pattern_index', 'channel_index', 'ppq'}
        if (numeric and (type(value) is not int or value < (0 if name == 'channel_index' else 1))) or (
                not numeric and (not isinstance(value, str) or not value.strip() or '\ufffd' in value)):
            status[name] = IdentityFieldStatus.ERROR
            continue
        basis = 'pattern_1_based' if name == 'pattern_index' else 'global_0_based' if name == 'channel_index' else None
        values[name] = IdentityObservation(value, 'fl_controller', method, timestamp, binding, basis)
        status[name] = IdentityFieldStatus.AVAILABLE
    selected = target.get('selected_channels')
    if target.get('channel_index_type') != 'global' or not isinstance(selected, list) or (
            any(type(value) is not int or value < 0 for value in selected)) or selected != [target.get('channel_index')]:
        status['channel_index'] = status['channel_name'] = IdentityFieldStatus.AMBIGUOUS
    return TargetIdentitySnapshot(**values), status


def compose_controller_native(target, native_channels, *, host_generation, binding_evidence,
                              native_observed_at, now=None, max_age_seconds=0.25):
    snapshot, status = controller_snapshot(target)
    now = now or datetime.now(timezone.utc)
    if not host_generation or not binding_evidence:
        raise ValueError('跨后端组合缺少宿主绑定证据')
    observations = [getattr(snapshot, f.name) for f in fields(snapshot) if getattr(snapshot, f.name) is not None]
    times = [item.observed_at for item in observations]+[native_observed_at]
    if any(not 0 <= (now-t).total_seconds() <= max_age_seconds for t in times):
        status = {key:IdentityFieldStatus.STALE if value == IdentityFieldStatus.AVAILABLE else value for key,value in status.items()}
    visible = target.get('visible_channels')
    rows = native_channels.get('channels') if isinstance(native_channels, dict) else None
    matched = isinstance(visible, list) and isinstance(rows, list) and len(visible) == len(rows) and bool(rows)
    if matched:
        matched = all(type(a.get('global_index')) is int and a['global_index'] >= 0
                      and a.get('visual_index') == b.get('visual_index') == i+1
                      and (a.get('name') == b.get('display_name') or (
                          isinstance(a.get('plugin_name'), str) and bool(a['plugin_name'])
                          and f"{a.get('name')} [{a['plugin_name']}]" == b.get('display_name')))
                      for i,(a,b) in enumerate(zip(visible, rows)))
        matched = matched and len({row['global_index'] for row in visible}) == len(visible)
    if matched and snapshot.channel_index is not None and snapshot.channel_name is not None:
        candidates = [row for row in visible if row['global_index'] == snapshot.channel_index.value]
        matched = len(candidates) == 1 and candidates[0]['name'] == snapshot.channel_name.value
    if not matched:
        # 名称修饰、筛选或顺序不同都不靠去括号与索引加一猜测匹配。
        status['native_channel_mapping'] = IdentityFieldStatus.AMBIGUOUS
    else:
        status['native_channel_mapping'] = IdentityFieldStatus.AVAILABLE
        if snapshot.channel_name is not None:
            snapshot = replace(snapshot, channel_name=IdentityObservation(snapshot.channel_name.value, 'gopher_native',
                'list_channel_names + controller.visual_global_mapping', native_observed_at,
                snapshot.channel_name.context_binding))
    return CompositeTargetIdentity(snapshot, status, host_generation, target['controller_session'],
                                   target['project_generation'], binding_evidence)


def validate_controller_build_binding(target, expected):
    if not isinstance(target, dict):
        raise RuntimeError('CONTROLLER_BUILD_ID_UNBOUND')
    for key in ('controller_build_id', 'controller_session_id', 'project_generation'):
        value = target.get(key)
        if not isinstance(value, str) or not value.strip() or value == 'source-uninstalled':
            raise RuntimeError('CONTROLLER_BUILD_ID_UNBOUND')
        if value != expected.get(key):
            raise RuntimeError('CONTROLLER_BUILD_CONTEXT_MISMATCH')
    if target.get('controller_session') != target['controller_session_id']:
        raise RuntimeError('CONTROLLER_SESSION_CHANGED')


class ControllerIdentityBackend:
    name = 'fl_controller_identity'
    _allowed_actions = ('dawloop.getIdentitySnapshot', 'dawloop.researchUndoOnce')

    def __init__(self, port_name, *, settings_dir=None, timeout=3):
        if not isinstance(port_name, str) or not port_name.strip() or timeout <= 0:
            raise ValueError('身份读取需要明确端口和有效超时')
        self.port_name = port_name
        self.settings_dir = settings_dir or default_settings_dir()
        self.timeout = timeout
        self.lock = asyncio.Lock()
        self.poisoned = False

    def _read(self, action='dawloop.getIdentitySnapshot', extra=None):
        if action not in self._allowed_actions:
            raise ValueError('控制器研究动作不允许')
        ready = ping_preflight(self.settings_dir)
        if not ready.ready:
            raise RuntimeError(ready.code)
        binding = dict(controller_build_id=ready.payload['build_id'],
                       controller_session_id=ready.payload['session_id'],
                       project_generation=ready.payload.get('project_generation'))
        if action == 'dawloop.getIdentitySnapshot' and (
                not isinstance(binding['project_generation'], str) or not binding['project_generation'].strip()):
            raise RuntimeError('CONTROLLER_BUILD_ID_UNBOUND')
        if self.poisoned:
            raise RuntimeError('IDENTITY_SESSION_POISONED')
        import mido
        if self.port_name not in mido.get_output_names():
            raise RuntimeError('MIDI_PORT_UNAVAILABLE')
        root = self.settings_dir / 'Hardware' / 'DAWLoopMCP'
        request = uuid4().hex
        command = root / 'mcp_command.json'
        response = root / 'mcp_response.json'
        params = {**(extra or {}), 'request_id':request}
        if action in ('dawloop.selectOneChannelOnce', 'dawloop.openPianoRollOnce', 'dawloop.navigateTargetOnce'):
            expected = dict(expected_controller_build_id=binding['controller_build_id'],
                            controller_session_id=binding['controller_session_id'],
                            project_generation=binding['project_generation'])
            if any(params.get(key) != value for key, value in expected.items()):
                raise RuntimeError('CONTROLLER_BUILD_CONTEXT_MISMATCH')
        if action == 'dawloop.getIdentitySnapshot':
            params.update(expected_controller_build_id=binding['controller_build_id'],
                          controller_session_id=binding['controller_session_id'],
                          project_generation=binding['project_generation'])
        with command.open('x', encoding='utf-8') as stream:
            json.dump({'action':action,'params':params}, stream)
        dispatched = False
        try:
            with mido.open_output(self.port_name) as port:
                dispatched = True
                port.send(mido.Message('note_on', note=127, velocity=127))
                deadline = time.monotonic()+self.timeout
                while time.monotonic() < deadline:
                    try:
                        data = json.loads(response.read_text(encoding='utf-8'))
                    except (OSError, json.JSONDecodeError, UnicodeError):
                        data = None
                    if isinstance(data, dict) and data.get('request_id') == request:
                        after = ping_preflight(self.settings_dir)
                        if not after.ready or after.payload['session_id'] != ready.payload['session_id']:
                            raise RuntimeError('CONTROLLER_SESSION_CHANGED')
                        if data.get('success') is not True:
                            raise RuntimeError(data.get('error_code','IDENTITY_READ_ERROR'))
                        if action in ('dawloop.selectOneChannelOnce', 'dawloop.openPianoRollOnce', 'dawloop.navigateTargetOnce'):
                            value = data.get('selection')
                            if not isinstance(value, dict):
                                raise RuntimeError('CHANNEL_SELECTION_RESPONSE_INVALID')
                            validate_controller_build_binding(value, binding)
                            if (value.get('operation_id') != params['operation_id'] or
                                    value.get('request_id') != request or
                                    type(value.get('global_index')) is not int or
                                    value['global_index'] != params['global_index'] or
                                    value.get('channel_name') != params['channel_name'] or
                                    value.get('status') != 'EXECUTED_UNVERIFIED' or
                                    after.payload['build_id'] != binding['controller_build_id'] or
                                    after.payload.get('project_generation') != binding['project_generation']):
                                raise RuntimeError('CHANNEL_SELECTION_RESPONSE_MISMATCH')
                            command.unlink(missing_ok=True)
                            return value
                        if action == 'dawloop.researchUndoOnce':
                            if not isinstance(data.get('undo'), dict):
                                raise RuntimeError('UNDO_RESPONSE_INVALID')
                            command.unlink(missing_ok=True)
                            return data['undo']
                        if not isinstance(data.get('target'), dict):
                            raise RuntimeError('IDENTITY_READ_ERROR')
                        if data['target'].get('controller_session') != ready.payload['session_id']:
                            raise RuntimeError('CONTROLLER_SESSION_CHANGED')
                        validate_controller_build_binding(data['target'], binding)
                        if (after.payload['build_id'] != binding['controller_build_id'] or
                                after.payload.get('project_generation') != binding['project_generation']):
                            raise RuntimeError('CONTROLLER_BUILD_CONTEXT_MISMATCH')
                        controller_snapshot(data['target'])
                        command.unlink(missing_ok=True)
                        return data['target']
                    time.sleep(.002)
                raise TimeoutError('CONTROLLER_IDENTITY_TIMEOUT')
        except BaseException:
            if dispatched:
                # 未确认结果保留队列和锁定状态，防止晚响应被下个请求认领。
                self.poisoned = True
            else:
                command.unlink(missing_ok=True)
            raise

    async def read_identity(self):
        async with self.lock:
            task = asyncio.create_task(asyncio.to_thread(self._read))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                self.poisoned = True
                try:
                    await task
                except Exception:
                    pass
                raise

    async def research_undo_once(self, params):
        async with self.lock:
            task = asyncio.create_task(asyncio.to_thread(self._read, 'dawloop.researchUndoOnce', params))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                self.poisoned = True
                try:
                    await task
                except Exception:
                    pass
                raise
