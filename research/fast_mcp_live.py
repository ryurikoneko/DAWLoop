"""MCP 的受限现场接线；复用既有执行器，不拥有启动、接受或保存权限。"""

import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
import time
import re
import urllib.request
from uuid import uuid4

from dawloop.adapters.fl_controller_identity import validate_controller_build_binding
from dawloop.adapters.fl_target_navigation import ControllerTargetNavigator
from dawloop.adapters.fl_target_preparation import ControllerTargetPreparer
from dawloop.adapters.gopher_native.backend import GopherNativeBackend
from dawloop.adapters.gopher_native.transport import CDPTransport, find_target, validate_endpoint
from dawloop.adapters.gopher_native.write_backend import (
    CERTIFIED_CATALOG, CERTIFIED_VERSION, GopherNativeWriteBackend)
from dawloop.runtime.fast_music import FastMusicRuntime
from dawloop.runtime.human_reports import acceptance_receipt
from dawloop.runtime.native_write import NativeWriteJournal
from dawloop.runtime.run_manager import RunManager
from research.observation_handoff import FileMailbox, ObservationExchange
from research.practical_music_slice import TARGET, HumanSliceInteraction


def alive(pid):
    import win32api
    import win32con
    import win32process
    try:
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
        try:
            return win32process.GetExitCodeProcess(handle) == 259
        finally:
            handle.Close()
    except Exception:
        return False


def window_state(pid, hwnd, expected_class):
    import win32api
    import win32con
    import win32gui
    import win32process
    if (not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != pid
            or win32gui.GetClassName(hwnd) != expected_class or not alive(pid)):
        raise ValueError('HOST_WINDOW_CHANGED')
    handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
    try:
        if Path(win32process.GetModuleFileNameEx(handle, 0)).name.lower() not in ('fl64.exe', 'fl.exe'):
            raise ValueError('HOST_PROCESS_CHANGED')
    finally:
        handle.Close()
    candidates = {}
    def inspect(candidate, _):
        if (win32process.GetWindowThreadProcessId(candidate)[1] == pid
                and win32gui.IsWindowVisible(candidate) and win32gui.IsWindowEnabled(candidate)
                and win32gui.GetClassName(candidate) == 'TScriptDialog'
                and win32gui.GetWindowText(candidate) == 'DAWLoop Native Add'):
            candidates[candidate] = dict(hwnd=candidate, parent=win32gui.GetParent(candidate),
                class_name='TScriptDialog', title='DAWLoop Native Add')
    def top(candidate, _):
        inspect(candidate, None)
        if win32process.GetWindowThreadProcessId(candidate)[1] == pid:
            win32gui.EnumChildWindows(candidate, inspect, None)
    win32gui.EnumWindows(top, None)
    if len(candidates) > 1:
        raise ValueError('PREVIEW_WINDOW_AMBIGUOUS')
    return next(iter(candidates.values()), None)


class ObservationClient:
    def __init__(self, directory, *, window_identity, process_alive=alive):
        self.directory = Path(directory).resolve()
        self.process_alive = process_alive
        self.window_identity = copy.deepcopy(window_identity)

    def readiness(self):
        try:
            value = json.loads((self.directory / 'observer.json').read_text(encoding='utf-8'))
            generation = value['observer_generation']
            ready = (value['ready'] is True and value['review_ready'] is True
                and value['source'] == 'CaptureIntervalObserver'
                and type(generation) is str and bool(generation)
                and type(value['pid']) is int and value['pid'] > 0 and self.process_alive(value['pid'])
                and type(value['observed_at']) in (int, float)
                and 0 <= time.time() - value['observed_at'] <= 60)
            return dict(ready=ready, request_generation=generation if ready else None)
        except (OSError, ValueError, KeyError, TypeError):
            return dict(ready=False, request_generation=None)

    async def observe(self, context, stage, target, binding):
        state = self.readiness()
        if not state['ready'] or state['request_generation'] != context.readiness['observation']['request_generation']:
            raise ValueError('OBSERVATION_NOT_READY')
        request = dict(request_id=uuid4().hex, operation_id=context.operation_id,
            run_id=context.run_id, session_id=context.session_id, stage=stage,
            target=copy.deepcopy(target), binding=copy.deepcopy(binding),
            window_identity=copy.deepcopy(self.window_identity),
            observer_generation=state['request_generation'])
        mailbox = FileMailbox(self.directory / 'mailbox', ObservationExchange())
        reply = await mailbox.request(dict(request=request))
        if reply.get('request') != request or self.readiness() != state:
            raise ValueError('OBSERVATION_GENERATION_MISMATCH')
        capture, review = reply.get('capture', {}), reply.get('review', {})
        artifact = Path(reply.get('artifact', ''))
        start, end = capture.get('capture_started_at', {}), capture.get('capture_completed_at', {})
        if (capture.get('request_id') != request['request_id']
                or capture.get('operation_id') != context.operation_id
                or capture.get('observer_generation') != request['observer_generation']
                or capture.get('binding') != request
                or capture.get('window_id') != self.window_identity['hwnd']
                or not artifact.is_file() or not isinstance(capture.get('image_hash'), str)
                or hashlib.sha256(artifact.read_bytes()).hexdigest() != capture['image_hash']
                or review.get('image_hash') != capture['image_hash']
                or review.get('request_id') != request['request_id']
                or review.get('observer_generation') != request['observer_generation']):
            raise ValueError('IMAGE_REVIEW_BINDING_FAILED')
        values = [row.get(key) for row in (start, end) for key in ('monotonic_ms', 'wall_unix_ms')]
        if (start.get('clock_domain') != end.get('clock_domain') or not start.get('clock_domain')
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)
                or start['monotonic_ms'] > end['monotonic_ms']
                or start['wall_unix_ms'] > end['wall_unix_ms']
                or not 0 <= time.time() - start['wall_unix_ms'] / 1000 <= 60):
            raise ValueError('CAPTURE_TIMESTAMP_UNAVAILABLE')
        if (review.get('observer') not in ('agent_visual_review', 'human')
                or review.get('confirmed') is not True or review.get('visible') is not True
                or review.get('pattern_number') != target['expected_pattern_index']
                or review.get('channel_name') != target['expected_channel_name']
                or review.get('window_pid') != self.window_identity['pid']
                or review.get('window_hwnd') != self.window_identity['hwnd']):
            raise ValueError('PIANO_ROLL_TARGET_UNCONFIRMED')
        # 私人图像留在观察端，公开运行证据只保存绑定摘要及实际审阅。
        evidence = dict(request=request, capture=capture, review=review)
        filename = stage.lower() + '_' + request['request_id'] + '.json'
        with (context.directory / filename).open('x', encoding='utf-8') as stream:
            json.dump(evidence, stream, ensure_ascii=False, allow_nan=False)
        return dict(visible=True, confirmed=True, observer=review['observer'], evidence_ref=filename,
            pattern_number=review['pattern_number'], channel_name=review['channel_name'],
            window_pid=review.get('window_pid'), window_hwnd=review.get('window_hwnd'), session=binding,
            observed_unix=start['wall_unix_ms'] / 1000, image_hash=capture['image_hash'],
            request_id=request['request_id'], observer_generation=request['observer_generation'],
            review=review, capture_interval=dict(start=start, end=end))


class LiveInteraction:
    local_preview = False
    accept_observer = 'human'
    accept_window_seconds = None
    event_wait_seconds = 65
    bind_dispatch_task = HumanSliceInteraction.bind_dispatch_task
    pending = HumanSliceInteraction.pending
    completed_response = HumanSliceInteraction.completed_response
    wait_preview = HumanSliceInteraction.wait_preview
    wait_accept = HumanSliceInteraction.wait_accept
    wait_application = HumanSliceInteraction.wait_application
    guarded_auto_accept = HumanSliceInteraction.guarded_auto_accept

    def __init__(self, context, store, wiring, preparation, backend):
        self.context, self.report_store, self.wiring = context, store, wiring
        self.preparation, self.backend = preparation, backend
        self.operation_id = context.operation_id
        self.clock, self.sleep = time.monotonic, asyncio.sleep
        self.task = self.started = self.preview = self.accept_receipt = None
        self.events = []
        self.verify_target = self.confirm

    async def confirm(self):
        value = await self.wiring.controller.read_identity()
        self.wiring.check_controller(value)
        before = self.backend.prepared['identity']
        keys = ('pattern_number', 'pattern_name', 'channel_index', 'channel_name', 'selected_channels', 'ppq')
        if any(value.get(key) != before.get(key) for key in keys):
            raise ValueError('MUSIC_TARGET_CHANGED')
        self.wiring.check_native(self.backend.session)

    async def event(self, name, *, pending=False):
        deadline = self.clock() + self.event_wait_seconds
        if name == 'accept':
            self.report_store.begin_accept()
        try:
            while self.clock() < deadline:
                if pending:
                    self.pending()
                if name == 'preview':
                    window = self.wiring.window_probe(self.wiring.config['pid'], self.wiring.config['hwnd'])
                    if window is not None:
                        self.report_store.bind_preview(window)
                        return dict(operation_id=self.operation_id, observed=True, host_preview_present=True,
                            observer='agent_visual_review', evidence_ref='HOST_PREVIEW_WINDOW_PRESENT', window=window)
                elif name == 'accept':
                    report = self.report_store.claim_accept(deadline=deadline, clock=self.clock)
                    if report is not None:
                        return acceptance_receipt(report, self.operation_id)
                elif name == 'application':
                    if self.wiring.window_probe(self.wiring.config['pid'], self.wiring.config['hwnd']) is None:
                        receipt = await self.wiring.observer.observe(self.context, 'APPLICATION', TARGET,
                            self.preparation.binding)
                        review = receipt['review']
                        if (review.get('preview_closed') is not True or review.get('phrase_visible') is not True):
                            raise ValueError('APPLICATION_REVIEW_REQUIRED')
                        return dict(operation_id=self.operation_id, observed=True, preview_closed=True,
                            phrase_visible=True, observer=receipt['observer'], evidence_ref=receipt['evidence_ref'])
                if name in ('accept', 'application'):
                    self.completed_response()
                await self.sleep(.05)
            raise ValueError('HUMAN_EVENT_TIMEOUT')
        finally:
            if name == 'accept':
                self.report_store.end_accept()


class LivePreparation:
    def __init__(self, wiring, context):
        self.wiring, self.context = wiring, context
        self.binding = None
        self.preparer = ControllerTargetPreparer(self, self.navigate, self.observe_ui,
            window_identity=dict(pid=wiring.config['pid'], hwnd=wiring.config['hwnd']))

    async def read_identity(self):
        self.wiring.check_native(self.binding)
        value = await self.wiring.controller.read_identity()
        self.wiring.check_controller(value)
        return value

    async def navigate(self, target, binding):
        await self.wiring.controller.navigate_once(target, self.wiring.controller_binding, self.context.operation_id)

    async def observe_ui(self, target, binding):
        value = await self.wiring.observer.observe(self.context, 'TARGET', target, binding)
        review = value['review']
        if (review.get('active_region_empty') is not True or review.get('region') != [1536, 3072]
                or review.get('preview_absent') is not True or review.get('human_available') is not True):
            raise ValueError('MUSIC_SLICE_PREPARATION_REQUIRED')
        self.wiring.check_native(binding)
        return value

    async def prepare(self, target, session):
        if target != TARGET:
            raise ValueError('MUSIC_SLICE_SCOPE_MISMATCH')
        if session != self.wiring.session:
            raise ValueError('NATIVE_CONTEXT_CHANGED')
        self.binding = copy.deepcopy(session)
        return await self.preparer.prepare(target, session)

    async def confirm(self, target, session):
        return await self.preparer.confirm(target, session)


class LiveWiring:
    def __init__(self, config, *, settings_dir, expected_build, controller=None,
                 transport=None, observer=None, window_probe=None, targets=None):
        self.config = copy.deepcopy(config)
        required = {'pid', 'hwnd', 'window_class', 'endpoint', 'port_name', 'fixture', 'fixture_sha256', 'fixture_size',
                    'project_title', 'controller_session_id', 'project_generation', 'observer_dir',
                    'experimental_authorized'}
        if set(config) != required or config['experimental_authorized'] is not True:
            raise ValueError('EXPLICIT_LIVE_FIXTURE_CONFIGURATION_REQUIRED')
        if any(type(config[k]) is not int or config[k] <= 0 for k in ('pid', 'hwnd', 'fixture_size')):
            raise ValueError('LIVE_WINDOW_CONFIGURATION_INVALID')
        if config['project_title'] is not None and type(config['project_title']) is not str:
            raise ValueError('PROJECT_TITLE_TYPE_INVALID')
        for k in required - {'pid', 'hwnd', 'fixture_size', 'experimental_authorized', 'project_title'}:
            if type(config[k]) is not str or not config[k].strip():
                raise ValueError('LIVE_CONFIGURATION_FIELD_INVALID')
        if any(not Path(config[k]).is_absolute() for k in ('fixture', 'observer_dir')):
            raise ValueError('EXPLICIT_LIVE_PATH_REQUIRED')
        if (config['fixture_sha256'] != 'a2f9922d6b8cdc7f7627428d0d7072ed7dcab0a4f666fef42145c0c6e91b006f'
                or config['fixture_size'] != 53498):
            raise ValueError('CERTIFIED_DISPOSABLE_FIXTURE_REQUIRED')
        self.endpoint = validate_endpoint(config['endpoint'])
        self.controller_binding = dict(controller_build_id=expected_build,
            controller_session_id=config['controller_session_id'], project_generation=config['project_generation'])
        self.controller = controller or ControllerTargetNavigator(config['port_name'], settings_dir=settings_dir)
        self.transport = transport or CDPTransport(self.endpoint, timeout=3)
        self.probe = GopherNativeBackend(transport=self.transport)
        self.observer = observer or ObservationClient(config['observer_dir'],
            window_identity=dict(pid=config['pid'], hwnd=config['hwnd']))
        self.window_probe = window_probe or (lambda pid, hwnd: window_state(pid, hwnd, config['window_class']))
        self.targets = targets or self.discover_target
        self.lock = asyncio.Lock()
        self.backend = None
        self.session = None

    def discover_target(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(self.endpoint + '/json/list', timeout=3) as response:
            return find_target(json.loads(response.read(1024 * 1024).decode('utf-8')))

    def fixture_valid(self):
        fixture = Path(self.config['fixture'])
        return (fixture.is_file() and fixture.stat().st_size == self.config['fixture_size']
            and hashlib.sha256(fixture.read_bytes()).hexdigest() == self.config['fixture_sha256'])

    def check_controller(self, identity):
        validate_controller_build_binding(identity, self.controller_binding)
        if identity.get('project_title') is not None and type(identity['project_title']) is not str:
            raise ValueError('PROJECT_TITLE_TYPE_INVALID')
        if (identity.get('project_loading') is not False
                or identity.get('ppq') != 96 or identity.get('fl_studio_version') != CERTIFIED_VERSION):
            raise ValueError('DISPOSABLE_CONTROLLER_CONTEXT_CHANGED')

    def check_native(self, session):
        if (not session or self.transport.socket is None
                or any(session.get(k) != getattr(self.transport, attr) for k, attr in (
                    ('host_generation', 'host_generation'), ('bridge_epoch', 'epoch'), ('target_id', 'target_id')))
                or self.transport.poisoned_epoch == session['session']):
            raise ValueError('NATIVE_CONTEXT_CHANGED')

    async def readiness(self):
        async with self.lock:
            snapshot = dict(controller={}, gopher={}, observation=self.observer.readiness(),
                            disposable_session=False, reasons=[])
            identity = {}
            try:
                self.window_probe(self.config['pid'], self.config['hwnd'])
                if not self.fixture_valid():
                    raise ValueError('FIXTURE_INTEGRITY_FAILED')
                identity = await self.controller.read_identity()
                self.check_controller(identity)
                snapshot['controller'] = dict(connected=True, build_id=identity['controller_build_id'],
                    session_generation=identity['controller_session_id'], project_generation=identity['project_generation'],
                    project_title=identity.get('project_title'),
                    project_title_status=('EMPTY_ACCEPTED' if identity.get('project_title') == '' else
                        'UNKNOWN_ACCEPTED' if identity.get('project_title') is None else 'DESCRIPTION_ONLY'))
                snapshot['disposable_session'] = True
            except Exception as error:
                snapshot['reasons'].append('CONTROLLER_OR_FIXTURE_NOT_READY')
                code = getattr(error, 'code', str(error))
                if re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', code):
                    snapshot['reasons'].append(code)
            try:
                target = await asyncio.to_thread(self.targets)
                snapshot['gopher'] = dict(discovered=True, bootstrap_required=False)
                if self.session is None:
                    await self.probe.discover()
                    self.session = copy.deepcopy(self.probe.session)
                # 运行中的派发线程拥有桥接；status只查目录/本地上下文，不更换回调。
                if target['id'] != self.session['target_id']:
                    raise ValueError('GOPHER_CONTEXT_CHANGED')
                if self.backend is None:
                    state = await self.probe._run(self.transport._evaluate,
                        "(() => { const s = window.__dawloopReadonlyBridgeV1; return s ? "
                        "{epoch:s.epoch, attached:s.attached, poisoned:s.poisoned, "
                        "unacknowledged:s.unacknowledged, write_attempted:!!s.executorProbeAttempted} : null; })()")
                    if (not isinstance(state, dict) or state.get('epoch') != self.session['bridge_epoch']
                            or state.get('attached') is not True or state.get('poisoned') is not False
                            or state.get('unacknowledged') is not False):
                        raise ValueError('GOPHER_CONTEXT_UNAVAILABLE')
                    if state.get('write_attempted') is not False:
                        snapshot['reasons'].append('HOST_WRITE_BUDGET_CONSUMED')
                self.check_native(self.session)
                snapshot['gopher'].update(bridge_connected=True, host_generation=self.session['host_generation'],
                    bridge_epoch=self.session['bridge_epoch'], target_id=target['id'],
                    catalog_hash=self.probe.catalog_digest, fl_version=identity.get('fl_studio_version'), poisoned=False)
                if self.probe.catalog_digest != CERTIFIED_CATALOG:
                    snapshot['reasons'].append('NATIVE_WRITE_CONTRACT_CHANGED')
            except Exception as error:
                code = getattr(error, 'code', str(error))
                bootstrap = code in ('HOST_NOT_FOUND', 'HOST_UNAVAILABLE', 'BRIDGE_UNAVAILABLE')
                snapshot['gopher'].update(bridge_connected=False, poisoned=bool(self.transport.poisoned_epoch),
                                          bootstrap_required=bootstrap)
                snapshot['reasons'].append('GOPHER_BOOTSTRAP_REQUIRED' if bootstrap else 'GOPHER_NOT_READY')
                if re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', code):
                    snapshot['reasons'].append(code)
            if not snapshot['observation'].get('ready'):
                snapshot['reasons'].append('OBSERVATION_REVIEW_NOT_READY')
            snapshot['observed_at'] = time.time()
            return snapshot

    def factory(self, context, store):
        self.check_native(self.session)
        expected = context.readiness['gopher']
        if any(expected[k] != self.session[k] for k in ('host_generation', 'bridge_epoch', 'target_id')):
            raise ValueError('RUN_CONTEXT_CHANGED')
        preparation = LivePreparation(self, context)
        self.transport.timeout = 60
        self.backend = GopherNativeWriteBackend(enabled=True, transport=self.transport,
            target_preparer=preparation, journal=NativeWriteJournal(context.ledger_directory),
            disposable_guard=self.fixture_valid)
        self.backend.interaction = LiveInteraction(context, store, self, preparation, self.backend)
        return FastMusicRuntime(self.backend)

    async def close(self):
        await self.probe.close()


def build_manager(config, *, directory, settings_dir, expected_build):
    wiring = LiveWiring(config, settings_dir=settings_dir, expected_build=expected_build)
    target = dict(pattern_index=TARGET['expected_pattern_index'], pattern_name=TARGET['expected_pattern_name'],
        channel_global_index=TARGET['expected_channel_index'], expected_channel_name=TARGET['expected_channel_name'])
    manager = RunManager(directory, settings_dir=settings_dir, expected_build=expected_build,
        runtime_factory=wiring.factory, readiness=wiring.readiness,
        experimental_authorized=True, allowed_target=target)
    return manager, wiring
