"""独立预览归属诊断；每个测试会话仅允许一次既有四音符派发。"""

from release_environment import fl_executable

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess

from dawloop.runtime import NativeWriteJournal, PianoRollBatchAddPlan, PianoRollScriptRenderer
from dawloop.runtime.diagnostics import DiagnosticTrace, observe
from dawloop.adapters.gopher_native.transport import CDPTransport
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from runtime_v2_throughput_live import baseline, BASELINE_HASH, BASELINE_SIZE
from runtime_v2_latency_live import checked_catalog, configure, bridge_events, write, ObservedInteraction
import runtime_v2_native_write_smoke as smoke

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/preview_onset'
EVENTS = Path(os.environ['TEMP']) / 'DAWLoop_RuntimeV2_preview_onset'
OPERATION = 'preview-onset-one'
SOURCE_HASH = 'ac68744417a7b98f7c2a7c2293ba255b73e6d99ecd3609618af0f501f786da75'


def process_state():
    # 系统端口枚举可能超过旧诊断的八秒限时，不能将检查超时当作端口关闭。
    command = ('$p=@(Get-Process FL64 -ErrorAction SilentlyContinue); '
        '$t=@(Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue); '
        '@{host_closed=($p.Count -eq 0); debug_port_closed=($t.Count -eq 0)} | ConvertTo-Json -Compress')
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
        capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)


async def run():
    baseline()
    write(OUTPUT / 'execution_intent.json', dict(dispatch_budget=1))
    smoke.EVENTS, smoke.OPERATION_ID = EVENTS, OPERATION
    trace = DiagnosticTrace(OPERATION, OPERATION)
    transport = CDPTransport(timeout=35)
    backend = GopherNativeWriteBackend(enabled=True, transport=transport,
        target_preparer=smoke.TargetPreparation(), interaction=ObservedInteraction(trace),
        journal=NativeWriteJournal(OUTPUT / 'dispatch_intents'), disposable_guard=smoke.fixture_guard)
    backend.diagnostics = trace
    report = {}
    installed = False
    try:
        await backend.discover()
        write(OUTPUT / 'session.json', backend.session)
        write(OUTPUT / 'catalog.json', dict(tools=checked_catalog(transport),
            catalog_hash=backend.catalog_digest))
        configure(transport, trace)
        if transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke("call","run_piano_roll_script",{},35000)') != dict(ok=False, code='READ_ONLY_BACKEND'):
            raise ValueError('ARBITRARY_SCRIPT_GUARD_FAILED')
        plan = PianoRollBatchAddPlan(dict(expected_pattern_index=1, expected_pattern_name='样式 1',
            expected_channel_index=0, expected_channel_name='808 Kick'),
            tuple(dict(number=84+i, time=3072+i*48, length=24, velocity=0.5) for i in range(4)),
            OPERATION).operation_plan()
        rendered = PianoRollScriptRenderer().render(plan.parameters['notes'])
        if rendered.sha256 != SOURCE_HASH:
            raise ValueError('FIXED_SOURCE_CHANGED')
        observer = (ROOT / 'research/preview_onset_observer.js').read_text(encoding='utf-8')
        installation = transport._evaluate(observer)
        if not installation.get('installed'):
            raise ValueError('OBSERVER_NOT_INSTALLED')
        installed = True
        write(OUTPUT / 'observer_installation.json', installation)
        write(OUTPUT / 'source_identity.json', dict(sha256=rendered.sha256, source_size=rendered.source_size))
        await backend.validate(plan, backend.capabilities[0])
        await backend.resolve_target(plan)
        result = await backend.execute(plan, backend.capabilities[0])
        report = asdict(result)
        report['bridge_events'] = bridge_events(transport)
    finally:
        if installed:
            try:
                report['observer'] = transport._evaluate('window.__dawloopPreviewOnsetObservation.snapshot()')
                report['observer_disposed'] = transport._evaluate('window.__dawloopPreviewOnsetObservation.dispose()')
            except Exception as error:
                report['observer_collection_error'] = getattr(error, 'code', type(error).__name__)
        await backend.close()
        report['callbacks_restored'] = transport.callbacks_restored
        write(OUTPUT / 'result.json', report)
        write(OUTPUT / 'trace.json', trace.events + report.get('bridge_events', []))
    print(json.dumps(dict(status=report.get('status'), callbacks_restored=transport.callbacks_restored)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('launch', 'run', 'recover'))
    action = parser.parse_args().action
    if (OUTPUT / 'summary.json').exists():
        raise ValueError('STAGE_CLOSED')
    if action == 'launch':
        baseline()
        if OUTPUT.exists() or EVENTS.exists() or not all(process_state().values()):
            raise ValueError('HOST_NOT_CLOSED_OR_TRIAL_EXISTS')
        OUTPUT.mkdir(parents=True)
        EVENTS.mkdir()
        write(OUTPUT / 'launch.json', dict(baseline_size=BASELINE_SIZE, baseline_sha256=BASELINE_HASH))
        process = subprocess.Popen([fl_executable(), str(baseline())],
            env=dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222'),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS)
        print(json.dumps(dict(pid=process.pid)))
    elif action == 'run':
        if not (OUTPUT / 'launch.json').exists():
            raise ValueError('EXPERIMENT_NOT_LAUNCHED')
        asyncio.run(run())
    else:
        state = process_state()
        baseline()
        if not all(state.values()):
            raise ValueError('HOST_OR_PORT_STILL_OPEN')
        write(OUTPUT / 'recovery.json', dict(**state, baseline_size=BASELINE_SIZE,
            baseline_sha256=BASELINE_HASH, no_save_exit=True))
        print(json.dumps(state))


if __name__ == '__main__':
    main()
