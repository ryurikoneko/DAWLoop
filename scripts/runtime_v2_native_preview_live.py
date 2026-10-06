"""原生预览事件诊断；固定四音符、独立会话与持久单次预算。"""

from release_environment import fl_executable

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from dawloop.runtime import NativeWriteJournal, PianoRollBatchAddPlan, PianoRollScriptRenderer
from dawloop.runtime.diagnostics import DiagnosticTrace, observe
from dawloop.adapters.gopher_native.transport import CDPTransport
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from runtime_v2_throughput_live import baseline, BASELINE_HASH, BASELINE_SIZE
from runtime_v2_preview_onset_live import process_state, SOURCE_HASH
from runtime_v2_latency_live import checked_catalog, configure, bridge_events, write, ObservedInteraction
import runtime_v2_native_write_smoke as smoke

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research'))
from native_preview_observer import NativeEventObserver, uia_subscription_probe

OUTPUT = ROOT / 'evidence/runtime_v2/native_preview_onset'


async def run(directory, events):
    baseline()
    write(directory / 'execution_intent.json', dict(dispatch_budget=1))
    operation = 'native-preview-' + directory.name
    smoke.EVENTS, smoke.OPERATION_ID = events, operation
    trace = DiagnosticTrace(operation, operation)
    transport = CDPTransport(timeout=35)
    backend = GopherNativeWriteBackend(enabled=True, transport=transport,
        target_preparer=smoke.TargetPreparation(), interaction=ObservedInteraction(trace),
        journal=NativeWriteJournal(OUTPUT / 'dispatch_intents'), disposable_guard=smoke.fixture_guard)
    backend.diagnostics = trace
    observer = None
    capture = None
    report = {}
    try:
        await backend.discover()
        for previous in OUTPUT.glob('*/session.json'):
            if json.loads(previous.read_text(encoding='utf-8'))['host_generation'] == transport.host_generation:
                raise ValueError('OLD_HOST_GENERATION_REUSED')
        write(directory / 'session.json', backend.session)
        write(directory / 'catalog.json', dict(tools=checked_catalog(transport),
            catalog_hash=backend.catalog_digest))
        configure(transport, trace)
        if transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke("call","run_piano_roll_script",{},35000)') != dict(ok=False, code='READ_ONLY_BACKEND'):
            raise ValueError('ARBITRARY_SCRIPT_GUARD_FAILED')
        plan = PianoRollBatchAddPlan(dict(expected_pattern_index=1, expected_pattern_name='样式 1',
            expected_channel_index=0, expected_channel_name='808 Kick'),
            tuple(dict(number=84+i, time=3072+i*48, length=24, velocity=0.5) for i in range(4)),
            operation).operation_plan()
        rendered = PianoRollScriptRenderer().render(plan.parameters['notes'])
        if rendered.sha256 != SOURCE_HASH:
            raise ValueError('FIXED_SOURCE_CHANGED')
        await backend.validate(plan, backend.capabilities[0])
        await backend.resolve_target(plan)
        write(directory / 'uia_subscription.json', uia_subscription_probe())
        launch = json.loads((directory / 'launch.json').read_text(encoding='utf-8'))
        observer = NativeEventObserver(launch['pid'], operation)
        before = observer.snapshot()
        write(directory / 'native_before.json', before)
        if any(w['fixed_probe_title_match'] for w in before['windows']):
            raise ValueError('PREVIEW_ALREADY_EXISTS')
        observer.start()
        observe(trace, 'native_observer_ready', 'observer')
        write(directory / 'native_after_install.json', observer.snapshot())
        async def capture_preview():
            await smoke.ManualInteraction().wait_preview(operation)
            observe(trace, 'preview_known_visible_by', 'observer', first_appearance_proven=False)
            after = await asyncio.to_thread(observer.snapshot)
            write(directory / 'native_at_preview.json', after)
            await asyncio.to_thread(observer.stop)
        capture = asyncio.create_task(capture_preview())
        result = await backend.execute(plan, backend.capabilities[0])
        report = asdict(result)
        await capture
        report['bridge_events'] = bridge_events(transport)
    finally:
        if capture and not capture.done():
            capture.cancel()
            try:
                await capture
            except asyncio.CancelledError:
                pass
        if observer:
            observer.stop()
            write(directory / 'winevents.json', observer.result())
        await backend.close()
        report['callbacks_restored'] = transport.callbacks_restored
        write(directory / 'result.json', report)
        write(directory / 'trace.json', trace.events + report.get('bridge_events', []))
    print(json.dumps(dict(status=report.get('status'), callbacks_restored=transport.callbacks_restored)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('launch', 'run', 'recover'))
    parser.add_argument('--trial', choices=('discovery', 'repeat1', 'repeat2'), required=True)
    args = parser.parse_args()
    if (OUTPUT / 'summary.json').exists():
        raise ValueError('STAGE_CLOSED')
    directory = OUTPUT / args.trial
    events = Path(os.environ['TEMP']) / ('DAWLoop_RuntimeV2_native_preview_' + args.trial)
    if args.action == 'launch':
        baseline()
        if directory.exists() or events.exists() or not all(process_state().values()):
            raise ValueError('HOST_NOT_CLOSED_OR_TRIAL_EXISTS')
        for old in OUTPUT.glob('*/launch.json'):
            if not (old.parent / 'recovery.json').exists():
                raise ValueError('PREVIOUS_SESSION_NOT_RECOVERED')
        if args.trial != 'discovery' and not (OUTPUT / 'candidate_analysis.json').exists():
            raise ValueError('CANDIDATE_NOT_REVIEWED')
        directory.mkdir(parents=True)
        events.mkdir()
        process = subprocess.Popen([fl_executable(), str(baseline())],
            env=dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222'),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS)
        write(directory / 'launch.json', dict(pid=process.pid, baseline_size=BASELINE_SIZE,
            baseline_sha256=BASELINE_HASH, observed_unix=time.time()))
        print(json.dumps(dict(pid=process.pid)))
    elif args.action == 'run':
        if not (directory / 'launch.json').exists():
            raise ValueError('EXPERIMENT_NOT_LAUNCHED')
        asyncio.run(run(directory, events))
    else:
        state = process_state()
        baseline()
        if not all(state.values()):
            raise ValueError('HOST_OR_PORT_STILL_OPEN')
        write(directory / 'recovery.json', dict(**state, no_save_exit=True,
            baseline_size=BASELINE_SIZE, baseline_sha256=BASELINE_HASH))
        print(json.dumps(state))


if __name__ == '__main__':
    main()
