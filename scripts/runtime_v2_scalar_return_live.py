"""固定标量返回合同；一次研究派发，原始响应先落盘，再解析。"""

from release_environment import fl_executable

from release_environment import controller_settings

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.adapters.gopher_native.backend import GopherNativeBackend
from dawloop.adapters.gopher_native.response import decode_script_acceptance
from research.scalar_return_contract import assess_scalar_response
from runtime_v2_throughput_live import baseline, process_state, write

OUTPUT = ROOT / 'evidence/runtime_v2/scalar_return/session_1'
SOURCE = ROOT / 'research/piano_roll_probe/scalar_return_v1.pyscript'
HASH = '48ecc28054787affb34d377daa85e2c804b4a60c4c950f98a73329ac0eaa09c2'
CATALOG = '514d035244b0aea4d94fbb5ce8cad79415878e76dca6c85d94e1ebf692f4234e'
BUILD = 'git:22ad4ec09b693f71201c4dabdab82c850ec75632+controller:455eb364d9966d60'
SETTINGS = None
KEYS = ('controller_build_id', 'controller_session_id', 'controller_session',
        'project_generation', 'pattern_number', 'pattern_name', 'channel_index',
        'channel_name', 'selected_channels', 'ppq')
PROBE_ID = 'SCALAR_RETURN_PROBE_V1'
BRIDGE_METHOD = 'invokeFixedScalarProbe'
OPERATION_ID = 'scalar-return-session-1'
ASSESSOR = assess_scalar_response


def read(name):
    return json.loads((OUTPUT / name).read_text(encoding='utf-8'))


def freeze():
    names = ('scripts/runtime_v2_scalar_return_live.py',
             'research/scalar_return_contract.py',
             'research/piano_roll_probe/scalar_return_v1.pyscript',
             'src/dawloop/adapters/gopher_native/bridge.js',
             'src/dawloop/adapters/gopher_native/backend.py',
             'src/dawloop/adapters/gopher_native/transport.py',
             'src/dawloop/adapters/gopher_native/response.py',
             'src/dawloop/adapters/fl_controller_identity.py')
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def guard():
    baseline()
    if Path(sys.executable).resolve() != (ROOT / '.venv/Scripts/python.exe').resolve():
        raise ValueError('PROJECT_INTERPRETER_REQUIRED')
    for name in ('websocket', 'jsonschema', 'mido', 'rtmidi', 'win32gui'):
        __import__(name)
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != HASH:
        raise ValueError('FIXED_SOURCE_CHANGED')


async def identity():
    target = await ControllerIdentityBackend('FLSkill MCP IN 2', settings_dir=controller_settings(SETTINGS)).read_identity()
    if (target.get('controller_build_id') != BUILD or target.get('pattern_number') != 1
            or target.get('channel_index') != 0 or target.get('channel_name') != '808 Kick'
            or target.get('selected_channels') != [0] or target.get('ppq') != 96
            or target.get('project_loading') is not False):
        raise ValueError('INITIAL_TARGET_OR_BUILD_MISMATCH')
    # 工程标题不进入公开证据，生产者实际目标仍未认证。
    return {key: value for key, value in target.items() if key != 'project_title'}


def dialog():
    import win32gui
    import win32process
    pid = read('launch.json')['pid']
    found = {}
    def inspect(hwnd, _):
        if (win32process.GetWindowThreadProcessId(hwnd)[1] == pid
                and win32gui.IsWindowVisible(hwnd)
                and win32gui.GetClassName(hwnd) == 'TScriptDialog'):
            found[hwnd] = dict(hwnd=hwnd, title=win32gui.GetWindowText(hwnd),
                               class_name='TScriptDialog')
    def top(hwnd, _):
        inspect(hwnd, None)
        if win32process.GetWindowThreadProcessId(hwnd)[1] == pid:
            win32gui.EnumChildWindows(hwnd, inspect, None)
    win32gui.EnumWindows(top, None)
    return list(found.values())


async def discover(backend):
    await backend.discover()
    if backend.catalog_digest != CATALOG:
        raise ValueError('CATALOG_CHANGED')
    tools = [cap.raw_tool for cap in backend.capabilities]
    script = next(tool for tool in tools if tool['name'] == 'run_piano_roll_script')
    schema = script['inputSchema']
    if (schema.get('required') != ['source'] or set(schema.get('properties', {})) != {'source'}
            or schema['properties']['source'].get('type') != 'string'):
        raise ValueError('SCRIPT_SCHEMA_CHANGED')
    return tools


async def ready():
    guard()
    backend = GopherNativeBackend(timeout=60)
    try:
        tools = await discover(backend)
        target = await identity()
        write(OUTPUT / 'catalog.json', dict(hash=backend.catalog_digest, tools=tools))
        write(OUTPUT / 'ready.json', dict(identity=target, session=backend.session,
              checked_unix=time.time(), script_dispatches=0))
        print(json.dumps(dict(ready=True, tool_count=len(tools), identity={key:target.get(key) for key in KEYS}), ensure_ascii=True), flush=True)
    finally:
        await backend.close()
        write(OUTPUT / 'ready_bridge_cleanup.json', dict(callbacks_restored=backend.transport.callbacks_restored))


async def run():
    guard()
    if read('version.json') != freeze() or (OUTPUT / 'dispatch_intent.json').exists():
        raise ValueError('FROZEN_VERSION_OR_SINGLE_DISPATCH_GUARD')
    ui = read('target_observation.json')
    if (ui.get('channel_title') != '808 Kick' or ui.get('baseline_visible_notes') != 3
            or ui.get('observer') != 'agent_current_ui' or not 0 <= time.time()-ui['observed_unix'] <= 60):
        raise ValueError('FRESH_INITIAL_UI_REQUIRED')
    backend = GopherNativeBackend(timeout=60)
    started = None
    try:
        await discover(backend)
        target = await identity()
        old = read('ready.json')['identity']
        if any(target.get(key) != old.get(key) for key in KEYS):
            raise ValueError('PRE_DISPATCH_CONTEXT_CHANGED')
        write(OUTPUT / 'identity_before.json', target)
        source = SOURCE.read_text(encoding='utf-8')
        request = dict(jsonrpc='2.0', id=1, method='tools/call',
                       params=dict(name='run_piano_roll_script', arguments=dict(source=source)))
        write(OUTPUT / 'dispatch_intent.json', dict(operation_id=OPERATION_ID,
              request_id=PROBE_ID+'-once', session=backend.session,
              source_sha256=HASH, expected_count=3, expected_count_basis='baseline_UI_observation',
              timeout_ms=60000, max_dispatches=1, retry=0, fallback=0,
              auto_accept=False, observed_unix=time.time()))
        write(OUTPUT / 'tool_request.json', request)
        expression = 'window.__dawloopReadonlyBridgeV1.%s(%s,%s,%s,60000)' % (
            BRIDGE_METHOD, json.dumps(PROBE_ID), json.dumps(HASH), json.dumps(source))
        started = time.monotonic()
        task = asyncio.create_task(asyncio.to_thread(backend.transport._evaluate, expression))
        done, _ = await asyncio.wait({task}, timeout=3)
        write(OUTPUT / 'pre_accept_phase.json', dict(callback_received=bool(done),
              elapsed_ms=(time.monotonic()-started)*1000, dialogs=dialog(),
              user_accept_report=None, clock_domain='scalar_coordinator_monotonic'))
        print('PRE_ACCEPT_PHASE: '+('CALLBACK_AVAILABLE' if done else 'WAITING_FOR_MANUAL_ACCEPT'), flush=True)
        response = await task
        # 必须先保存完整桥接结果及原始payload，任何解析异常都不能吞掉宿主证据。
        write(OUTPUT / 'raw_bridge_response.json', response)
        payload = response.get('payload') if isinstance(response, dict) else None
        if isinstance(payload, str):
            raw = payload.encode('utf-8')
            (OUTPUT / 'raw_tools_call_response.txt').write_bytes(raw)
            write(OUTPUT / 'raw_payload_identity.json', dict(sha256=hashlib.sha256(raw).hexdigest(),
                  bytes=len(raw), capture='exact_callback_string_UTF8',
                  internal_ilmcp_return='UNAVAILABLE'))
        report = ASSESSOR(response, 3)
        report.update(total_ms=(time.monotonic()-started)*1000,
                      script_dispatches=1, note_dispatches=0, navigation_transactions=0,
                      retry=0, fallback=0, internal_ilmcp_return='UNAVAILABLE',
                      apply_invocation_count=None)
        write(OUTPUT / 'assessment.json', report)
        write(OUTPUT / 'existing_decoder_result.json', asdict(decode_script_acceptance(response)))
        if isinstance(response, dict) and response.get('ok') is True:
            ack = backend.transport._evaluate('window.__dawloopReadonlyBridgeV1.acknowledge(%s)' % json.dumps(backend.transport.epoch))
            write(OUTPUT / 'acknowledgement.json', dict(acknowledged=ack))
        else:
            backend.transport.poisoned_epoch = backend.transport.epoch
        after = await identity()
        write(OUTPUT / 'identity_after.json', after)
        write(OUTPUT / 'identity_comparison.json', dict(unchanged=all(target.get(key)==after.get(key) for key in KEYS),
              producer_target_verified=False, freshness_verified=False))
        print(json.dumps(report), flush=True)
    except Exception as error:
        write(OUTPUT / 'run_error.json', dict(error=type(error).__name__, code=getattr(error, 'code', str(error)),
              dispatch_intent_exists=(OUTPUT / 'dispatch_intent.json').exists()))
        raise
    finally:
        await backend.close()
        write(OUTPUT / 'bridge_cleanup.json', dict(callbacks_restored=backend.transport.callbacks_restored))


def main():
    action = argparse.ArgumentParser()
    action.add_argument('action', choices=('prepare', 'launch', 'ready', 'run', 'recover'))
    args = action.parse_args()
    guard()
    if args.action == 'prepare':
        if OUTPUT.exists():
            raise ValueError('EVIDENCE_DIRECTORY_EXISTS')
        OUTPUT.mkdir(parents=True)
        write(OUTPUT / 'version.json', freeze())
        write(OUTPUT / 'scope.json', dict(probe=PROBE_ID, source_sha256=HASH,
              max_script_dispatches=1, musical_writes=0, navigation=0, manual_accept_max=1,
              output_files_are_runtime_evidence=True, producer_file_IO=False))
    elif args.action == 'launch':
        if read('version.json') != freeze() or not all(process_state().values()):
            raise ValueError('HOST_OPEN_OR_VERSION_CHANGED')
        write(OUTPUT / 'launch_intent.json', dict(observed_unix=time.time()))
        env = dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222')
        process = subprocess.Popen([fl_executable(), str(baseline())], env=env,
                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  creationflags=subprocess.DETACHED_PROCESS)
        write(OUTPUT / 'launch.json', dict(pid=process.pid, debug_scope='CHILD_PROCESS_ENVIRONMENT_ONLY'))
        print(json.dumps(dict(pid=process.pid)))
    elif args.action in ('ready', 'run'):
        asyncio.run(ready() if args.action == 'ready' else run())
    else:
        state = process_state()
        if not all(state.values()):
            raise ValueError('HOST_OR_PORT_OPEN')
        path = baseline()
        write(OUTPUT / 'recovery.json', dict(**state, baseline_size=path.stat().st_size,
              baseline_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), no_save_exit='UI_EVIDENCE_REQUIRED'))
        print(json.dumps(state))


if __name__ == '__main__':
    main()
