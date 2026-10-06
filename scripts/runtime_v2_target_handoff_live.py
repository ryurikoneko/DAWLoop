"""冻结协调器的现场交接入口，仅允许导航和独立观察回执。"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import tempfile
import urllib.request

import win32gui
import win32process

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.target_navigation_handoff import NavigationHandoff
from research.observation_handoff import ObservationExchange, FileMailbox, stamp
from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.adapters.gopher_native.backend import GopherNativeBackend
from dawloop.adapters.gopher_native.transport import CDPTransport, find_target
from runtime_v2_throughput_live import baseline, process_state, write

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'evidence/runtime_v2/target_preparation/live_5'
STEPS = ('select_pattern', 'focus_channel_rack', 'select_channel', 'open_piano_roll')
TARGETS = dict(A=dict(expected_pattern_index=1, expected_pattern_name='样式 1', expected_channel_index=0, expected_channel_name='808 Kick'),
               B=dict(expected_pattern_index=2, expected_pattern_name='样式 2', expected_channel_index=1, expected_channel_name='808 Clap'))


async def main():
    pid, hwnd = int(sys.argv[1]), int(sys.argv[2])
    manifest = json.loads((OUTPUT/'version.json').read_text(encoding='utf-8'))
    for name, digest in manifest['source_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('FROZEN_SOURCE_CHANGED')
    baseline()
    transport = CDPTransport()
    backend = GopherNativeBackend(transport=transport)
    if len(sys.argv) != 4:
        raise ValueError('EXPLICIT_CONTROLLER_SETTINGS_REQUIRED')
    settings_dir = Path(sys.argv[3]).resolve()
    if hashlib.sha256(str(settings_dir).encode('utf-8')).hexdigest() != '850f9e7a5806244b3e7093f4f8748d9db0f980a44f60f5cf38923383ab580a82':
        raise ValueError('CONTROLLER_CONFIG_ROOT_MISMATCH')
    reader = ControllerIdentityBackend('FLSkill MCP IN 2', settings_dir=settings_dir)
    request_index = 0
    observation_exchange = ObservationExchange()
    mailbox = FileMailbox(Path(tempfile.gettempdir())/'DAWLoop_NavigationLive5_mailbox', observation_exchange)

    async def exchange(action, **metadata):
        nonlocal request_index
        request_index += 1
        if action == 'OBSERVE_UI':
            binding = dict(controller_session=handoff.context[0], project_generation=handoff.context[1],
                           **metadata['session'])
            request = observation_exchange.begin(binding, handoff.last_identity_complete)
        else:
            request = dict(operation_id=observation_exchange.operation_id,
                           request_id=__import__('uuid').uuid4().hex)
        payload = dict(request_index=request_index, action=action, request=request, **metadata)
        print(json.dumps(payload, ensure_ascii=True), flush=True)
        result = await mailbox.request(payload)
        if action == 'OBSERVE_UI':
            value = observation_exchange.receive(result)
            if value is False:
                raise ValueError('OBSERVATION_REQUEST_TERMINATED')
            value.pop('capture_artifact', None)
        else:
            if result.get('request') != request or result.get('request_index') != request_index:
                raise ValueError('EXCHANGE_REQUEST_MISMATCH')
            value = result['value']
        reply = mailbox.directory / (request['request_id'] + '.result.json')
        reply.rename(reply.with_suffix('.consumed'))
        return value

    async def session():
        if not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != pid:
            raise ValueError('WINDOW_CHANGED')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:9222/json/list', timeout=3) as response:
            target = find_target(json.loads(response.read().decode('utf-8')))
        bridge = transport._evaluate('window.__dawloopReadonlyBridgeV1 && ({epoch:window.__dawloopReadonlyBridgeV1.epoch,attached:window.__dawloopReadonlyBridgeV1.attached,poisoned:window.__dawloopReadonlyBridgeV1.poisoned})')
        if not isinstance(bridge, dict) or bridge.get('attached') is not True or bridge.get('poisoned') is not False:
            raise ValueError('BRIDGE_UNAVAILABLE')
        return dict(session=bridge['epoch'], bridge_epoch=bridge['epoch'],
                    host_generation=transport.host_generation, target_id=target['id'])

    class Identity:
        async def read_identity(self):
            value = await reader.read_identity()
            if not any(row.get('global_index') == 1 and row.get('name') == '808 Clap' for row in value.get('visible_channels', [])):
                raise ValueError('B_CHANNEL_MISSING')
            return value

    async def primitive(name, target, invocation):
        result = await exchange('NAVIGATION_PRIMITIVE', primitive=name, target=target, session=invocation)
        write(OUTPUT/f'primitive_{request_index}.json', dict(primitive=name, target=target, **result))
        return result.get('outcome', 'UNKNOWN')

    async def ui(target, invocation):
        return await exchange('OBSERVE_UI', target=target, session=invocation, pid=pid, hwnd=hwnd)

    async def recover():
        mailbox.write('operation.cancel.json', dict(operation_id=observation_exchange.operation_id, cancel=True))
        errors = []
        no_save_exit = False
        unchanged = False
        try:
            await exchange('NO_SAVE_EXIT')
            no_save_exit = True
        except Exception as error:
            errors.append(str(error) or type(error).__name__)
        try:
            baseline()
            unchanged = True
        except Exception as error:
            errors.append(str(error) or type(error).__name__)
        try:
            state = process_state()
        except Exception as error:
            errors.append(str(error) or type(error).__name__)
            state = dict(host_closed=False, debug_port_closed=False)
        return dict(**state, baseline_unchanged=unchanged, no_save_exit=no_save_exit,
                    cleanup_errors=errors, external_observer_exit_confirmed=False)

    preflight = json.loads((OUTPUT/'material_preflight.json').read_text(encoding='utf-8'))
    if preflight.get('patterns') != {'1':'样式 1', '2':'样式 2'} or not 0 <= time.time()-preflight['observed_unix'] <= 60:
        raise ValueError('PATTERN_MATERIAL_UNCONFIRMED')
    handoff = NavigationHandoff(backend, Identity(), session, primitive, ui, recover,
        targets=copy.deepcopy(TARGETS), steps=dict(A_TO_B=STEPS, B_TO_A=STEPS),
        window_identity=dict(pid=pid, hwnd=hwnd), expected_catalog_hash=manifest['catalog_hash'], scope='LIVE_NAVIGATION')
    handoff.observation_exchange = observation_exchange
    result = await handoff.run()
    mailbox.quarantine()
    result['handoff_diagnostics'] = observation_exchange.diagnostics
    result['input_thread_teardown'] = dict(input_worker_threads=0, blocking_stdin=False)
    result['classification'] = ('PASS' if result['status']=='HANDOFF_PASSED' else
        'FAIL_DURING_OR_AFTER_NAVIGATION' if result['navigation_transactions'] else 'FAIL_BEFORE_NAVIGATION')
    write(OUTPUT/'summary.json', result)
    print(json.dumps(dict(classification=result['classification'], error_code=result.get('error_code'))), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
