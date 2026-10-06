"""零派发的初始目标观察，真实契约夹住独立界面证据。"""

import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys
import time

import win32gui
import win32process

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.adapters.fl_target_preparation import ControllerTargetPreparer
from dawloop.adapters.gopher_native.backend import GopherNativeBackend
from dawloop.adapters.gopher_native.transport import CDPTransport
from runtime_v2_throughput_live import baseline, write


async def discover_catalog(transport, session):
    backend = GopherNativeBackend(transport=transport)
    backend.session = session
    await backend.discover()
    return backend.catalog_digest


async def main():
    directory = Path(sys.argv[1])
    pid, hwnd = int(sys.argv[2]), int(sys.argv[3])
    baseline()
    transport = CDPTransport()
    result = dict(note_dispatch_count=0, navigation_count=0, script_calls=0,
                  producer_target_verified=False, exact_target_binding=False,
                  automation_production_ready=False, live_pass=False)
    timings = []
    try:
        session = transport.connect()
        digest = await discover_catalog(transport, session)
        if digest != '514d035244b0aea4d94fbb5ce8cad79415878e76dca6c85d94e1ebf692f4234e':
            raise ValueError('CATALOG_CHANGED')
        result.update(session=session, catalog_hash=digest)
        backend = ControllerIdentityBackend('FLSkill MCP IN 2')

        def check_host():
            bridge = transport._evaluate('window.__dawloopReadonlyBridgeV1 && ({epoch:window.__dawloopReadonlyBridgeV1.epoch,attached:window.__dawloopReadonlyBridgeV1.attached,poisoned:window.__dawloopReadonlyBridgeV1.poisoned})')
            if (not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != pid
                    or transport.host_generation != session['host_generation']
                    or transport.target_id != session['target_id']
                    or not isinstance(bridge, dict) or bridge.get('epoch') != session['bridge_epoch']
                    or bridge.get('attached') is not True or bridge.get('poisoned') is not False):
                raise ValueError('HOST_OR_WINDOW_CHANGED')

        class CheckedIdentity:
            async def read_identity(self):
                check_host()
                started = time.perf_counter()
                value = await backend.read_identity()
                timings.append((time.perf_counter()-started)*1000)
                check_host()
                if value.get('ppq') != 96:
                    raise ValueError('PPQ_MISMATCH')
                return value

        async def forbidden_navigation(*args):
            raise ValueError('NAVIGATION_NOT_AUTHORIZED_IN_INITIAL_OBSERVATION')

        async def observe_ui(target, invocation):
            check_host()
            print(json.dumps(dict(action='OBSERVE_A_UI', session=invocation, pid=pid, hwnd=hwnd)), flush=True)
            line = await asyncio.wait_for(asyncio.to_thread(sys.stdin.readline), timeout=55)
            ui = json.loads(line)
            check_host()
            if not ui.get('capture_started_unix', 0) <= ui.get('observed_unix', 0) <= ui.get('capture_completed_unix', 0):
                raise ValueError('UI_CAPTURE_INTERVAL_INVALID')
            return ui

        checked = CheckedIdentity()
        initial = await checked.read_identity()
        rows = initial.get('visible_channels', [])
        if not any(row.get('global_index') == 1 and row.get('name') == '808 Clap' for row in rows):
            raise ValueError('B_CHANNEL_MISSING')
        target = dict(expected_pattern_index=1, expected_pattern_name='样式 1',
                      expected_channel_index=0, expected_channel_name='808 Kick')
        preparer = ControllerTargetPreparer(checked, forbidden_navigation, observe_ui,
                                            window_identity=dict(pid=pid, hwnd=hwnd))
        started = time.perf_counter()
        evidence = await preparer.observe(target, session, preparer.identity(initial, target))
        before = datetime.fromisoformat(evidence['binding']['identity_before']['observed_at']).timestamp()
        after = datetime.fromisoformat(evidence['binding']['identity_after']['observed_at']).timestamp()
        ui = evidence['ui']
        if not before < ui['capture_started_unix'] <= ui['observed_unix'] <= ui['capture_completed_unix'] < after:
            raise ValueError('STRICT_UI_BRACKET_FAILED')
        result.update(a_confirmed=True, evidence=evidence, confirmation_duration_ms=(time.perf_counter()-started)*1000,
                      identity_read_ms=timings, status='A_CONFIRMED_NAVIGATION_PENDING')
    except Exception as error:
        result.update(a_confirmed=False, status='STOPPED', error_code=str(error) if isinstance(error, ValueError) else type(error).__name__)
    finally:
        transport.close()
        result['callbacks_restored'] = transport.callbacks_restored
        write(directory/'initial_a.json', result)
        print(json.dumps(dict(status=result['status'], a_confirmed=result['a_confirmed'], error_code=result.get('error_code'))), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
