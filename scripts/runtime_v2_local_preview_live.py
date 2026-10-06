"""固定四音符本地预览快速路径；每会话只派发一次。"""

from release_environment import fl_executable

import argparse
import asyncio
import hashlib
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from dawloop.runtime import BackendRouter, NativeWriteJournal, PianoRollBatchAddPlan, PianoRollScriptRenderer
from dawloop.runtime.diagnostics import DiagnosticTrace, observe
from dawloop.adapters.gopher_native.transport import CDPTransport
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend, CERTIFIED_CATALOG
from runtime_v2_throughput_live import baseline, BASELINE_HASH, BASELINE_SIZE
from runtime_v2_preview_onset_live import process_state, SOURCE_HASH
from runtime_v2_latency_live import checked_catalog, configure, bridge_events, write, ObservedInteraction
import runtime_v2_native_write_smoke as smoke

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research'))
from native_preview_observer import NativeEventObserver, uia_subscription_probe
from full_screen_live_diagnostic import FullScreenLiveDiagnostic, FullScreenDiagnosticInteraction
from preview_phase_interaction import PreviewPhaseInteraction
from dawloop.runtime.local_preview import LocalPreviewInteraction
from dawloop.runtime.native_write import AcceptPolicy
from controlled_visual_interaction import ControlledVisualInteraction
from dawloop.runtime.preview_viewport import NativePianoRollViewport
import numpy as np

OUTPUT = ROOT / 'evidence/runtime_v2/local_preview_fast_path'
EVIDENCE_ROOT = OUTPUT
ROUND_ID = 'original'
CONTROLLED_ROUNDS = ('controlled_accept_1', 'controlled_accept_repaired_1', 'controlled_accept_visual_1', 'controlled_accept_visual_2')
VISUAL_ROUNDS = ('controlled_accept_visual_1', 'controlled_accept_visual_2')


def previous_passed(directory, *, strict=False):
    result = json.loads((directory/'result.json').read_text(encoding='utf-8'))
    observation = json.loads((directory/'local_observation.json').read_text(encoding='utf-8'))
    recovery = json.loads((directory/'recovery.json').read_text(encoding='utf-8'))
    value = result.get('value') or {}
    passed = (value.get('preview_status') == 'LOCAL_PREVIEW_READY'
        and value.get('commit_status') == 'ACCEPTED'
        and value.get('application_status') == 'APPLICATION_OBSERVED'
        and result.get('callbacks_restored') is True and observation.get('error') is None
        and observation.get('observer_stopped') is True and observation.get('observation') is not None
        and recovery.get('host_closed') is True and recovery.get('debug_port_closed') is True
        and recovery.get('baseline_sha256') == BASELINE_HASH)
    if strict:
        full = json.loads((directory/'full_screen_observation.json').read_text(encoding='utf-8'))
        events = json.loads((directory/'winevents.json').read_text(encoding='utf-8'))
        passed = (passed and result.get('execution_status') == 'SUCCESS'
            and value.get('completion_status') == 'COMPLETION_CONFIRMED'
            and result.get('resource_cleanup_status') == 'COMPLETE' and result.get('cleanup_errors') == []
            and full.get('observer_stopped') is True and full.get('error') is None
            and events.get('unhooked') is True and events.get('error') is None
            and not (directory/'full_screen_cleanup_error.json').exists())
    return passed


def stability_version(directory, *, create=False):
    paths = set()
    for folder in ('src/dawloop/runtime', 'src/dawloop/adapters', 'research', 'scripts'):
        paths.update(path for path in (ROOT/folder).rglob('*') if path.suffix in ('.py', '.js', '.mjs', '.json', '.npz'))
    hashes = {str(path.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(paths)}
    record = dict(source_hashes=hashes, fixed_source_sha256=SOURCE_HASH,
        baseline_sha256=BASELINE_HASH, note_count=4, max_sessions=3)
    manifest = directory/'version.json'
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8')) != record:
            raise ValueError('STABILITY_VERSION_CHANGED')
    elif create:
        directory.mkdir(parents=True, exist_ok=True)
        write(manifest, record)
    else:
        raise ValueError('STABILITY_VERSION_NOT_FROZEN')


def readiness_paths(directory):
    paths = sorted(directory.glob('ready-*.json'))
    expected = [f'ready-{number:06d}.json' for number in range(1, len(paths)+1)]
    if [path.name for path in paths] != expected or (paths and not (directory/'ready.json').is_file()):
        raise ValueError('READY_HISTORY_INVALID')
    return [directory/'ready.json', *paths]


def read_ready(directory):
    # 最新失败也必须阻止派发，不能从历史成功记录中挑选有利结果。
    return smoke.read(readiness_paths(directory)[-1])


async def readiness(directory):
    if (directory/'execution_intent.json').exists():
        raise ValueError('READY_REFRESH_AFTER_EXECUTION_FORBIDDEN')
    paths = readiness_paths(directory)
    destination = paths[0] if not paths[0].exists() else directory/f'ready-{len(paths):06d}.json'
    transport = CDPTransport(timeout=35)
    backend = GopherNativeWriteBackend(enabled=True, transport=transport)
    record = dict(scope='READ_ONLY_READY_GATE', writes_dispatched=0)
    try:
        await backend.discover()
        tools = checked_catalog(transport)
        record.update(ready=True, session=backend.session, catalog_hash=backend.catalog_digest,
            tool_count=len(tools), checked_unix=time.time())
    except Exception as error:
        record.update(ready=False, error_code=getattr(error,'code',type(error).__name__))
        raise
    finally:
        await backend.close()
        record['callbacks_restored'] = transport.callbacks_restored
        write(destination, record)
    print(json.dumps(dict(ready=True, tool_count=record['tool_count'],
        callbacks_restored=record['callbacks_restored'])))


async def close_runtime_resources(interaction, observer, backend, transport, directory, report, trace):
    errors = []
    if interaction:
        try:
            await interaction.close()
            write(directory / 'local_observation.json', interaction.metrics())
            for name, frame in interaction.frames.items():
                np.save(directory / (name + '.npy'), frame)
        except Exception as error:
            errors.append(dict(resource='local_preview', error_code=type(error).__name__))
    if observer:
        try:
            observer.stop()
            write(directory / 'winevents.json', observer.result())
        except Exception as error:
            errors.append(dict(resource='native_observer', error_code=type(error).__name__))
    try:
        await backend.close()
    except Exception as error:
        errors.append(dict(resource='backend', error_code=type(error).__name__))
    if transport.callbacks_restored is not True and not any(row['resource'] == 'backend' for row in errors):
        errors.append(dict(resource='backend', error_code='CALLBACK_RESTORE_UNCONFIRMED'))
    report.update(callbacks_restored=transport.callbacks_restored,
        resource_cleanup_status='FAILED' if errors else 'COMPLETE', cleanup_errors=errors)
    write(directory / 'result.json', report)
    write(directory / 'trace.json', trace.events + report.get('bridge_events', []))
    if errors:
        raise ValueError('RUNTIME_CLEANUP_UNCONFIRMED')


def visual_round_preflight(root):
    initial = smoke.read(root/'summary.json')
    repaired = smoke.read(root/'repaired_1/summary.json')
    if (initial.get('status') != 'CLOSED_SETUP_FAILED_BEFORE_DISPATCH'
            or repaired.get('status') != 'CLOSED_ACCEPT_CONTROL_UNRESOLVED'
            or repaired.get('cumulative_live_sessions') != 2
            or repaired.get('cumulative_dispatch_count') != 1
            or repaired.get('cumulative_accept_count') != 0):
        raise ValueError('CONTROLLED_VISUAL_PREDECESSOR_MISMATCH')
    launches = list(root.rglob('launch.json'))
    if len(launches) != 2:
        raise ValueError('CONTROLLED_VISUAL_FINAL_SESSION_BUDGET')
    for launch in launches:
        recovery = smoke.read(launch.parent/'recovery.json')
        if (recovery.get('host_closed') is not True or recovery.get('debug_port_closed') is not True
                or recovery.get('baseline_sha256') != BASELINE_HASH):
            raise ValueError('CONTROLLED_VISUAL_RECOVERY_REQUIRED')


def controlled_preflight(directory, events):
    try:
        ui = smoke.read(events/'target.json')
    except (OSError, ValueError):
        raise ValueError('CONTROLLED_TARGET_MATERIAL_REQUIRED') from None
    observed = ui.get('observed_unix') if isinstance(ui, dict) else None
    if (not isinstance(ui, dict) or ui.get('visible') is not True
            or ui.get('confirmed') is not True or type(ui.get('pattern_number')) is not int
            or ui['pattern_number'] != 1 or ui.get('channel_name') != '808 Kick'
            or not isinstance(ui.get('evidence_ref'), str) or not ui['evidence_ref']
            or type(observed) not in (int, float) or not 0 <= time.time()-observed <= 60):
        raise ValueError('CONTROLLED_TARGET_MATERIAL_INVALID')
    if not (directory/'launch.json').is_file() or not (directory/'ready.json').is_file():
        raise ValueError('CONTROLLED_SESSION_NOT_PREPARED')
    try:
        launch = smoke.read(directory/'launch.json')
        ready = read_ready(directory)
    except (OSError, ValueError):
        raise ValueError('CONTROLLED_SESSION_MATERIAL_INVALID') from None
    checked = ready.get('checked_unix') if isinstance(ready, dict) else None
    if (not isinstance(launch, dict) or type(launch.get('pid')) is not int or launch['pid'] <= 0
            or not isinstance(ready, dict) or ready.get('ready') is not True
            or ready.get('callbacks_restored') is not True):
        raise ValueError('CONTROLLED_SESSION_MATERIAL_INVALID')
    if (ready.get('catalog_hash') != CERTIFIED_CATALOG
            or type(checked) not in (int, float) or not 0 <= time.time()-checked <= 180):
        raise ValueError('CONTROLLED_READY_GATE_STALE_OR_MISMATCH')


def extended_visual_preflight(root):
    closed = smoke.read(root/'visual_1/summary.json')
    if (closed.get('status') != 'CLOSED_READY_EXPIRED_BEFORE_DISPATCH'
            or closed.get('cumulative_live_sessions') != 3
            or closed.get('cumulative_dispatch_count') != 1
            or closed.get('cumulative_accept_count') != 0):
        raise ValueError('EXTENDED_VISUAL_PREDECESSOR_MISMATCH')
    launches = list(root.rglob('launch.json'))
    if len(launches) != 3:
        raise ValueError('EXTENDED_VISUAL_SINGLE_NEW_SESSION_ONLY')
    for launch in launches:
        recovery = smoke.read(launch.parent/'recovery.json')
        if (recovery.get('host_closed') is not True or recovery.get('debug_port_closed') is not True
                or recovery.get('baseline_sha256') != BASELINE_HASH):
            raise ValueError('EXTENDED_VISUAL_RECOVERY_REQUIRED')


async def run(directory, events):
    baseline()
    if ROUND_ID in CONTROLLED_ROUNDS:
        controlled_preflight(directory, events)
    if ROUND_ID in VISUAL_ROUNDS:
        sky_record = smoke.read(events/'sky_window.json')
        if (type(sky_record.get('id')) is not int or sky_record['id'] <= 0
                or type(sky_record.get('observed_unix')) not in (int, float)
                or not 0 <= time.time()-sky_record['observed_unix'] <= 60):
            raise ValueError('VISUAL_ACCEPT_SKY_SELECTION_REQUIRED')
    write(directory / 'execution_intent.json', dict(dispatch_budget=1))
    operation = 'local-preview-' + ('' if ROUND_ID == 'original' else ROUND_ID+'-') + directory.name
    smoke.EVENTS, smoke.OPERATION_ID = events, operation
    trace = DiagnosticTrace(operation, operation)
    transport = CDPTransport(timeout=35)
    backend = GopherNativeWriteBackend(enabled=True, transport=transport,
        target_preparer=smoke.TargetPreparation(), interaction=ObservedInteraction(trace),
        journal=NativeWriteJournal(EVIDENCE_ROOT / 'dispatch_intents'), disposable_guard=smoke.fixture_guard)
    backend.diagnostics = trace
    observer = None
    report = {}
    interaction = None
    full_screen = None
    router = BackendRouter([backend])
    router.diagnostics = trace
    try:
        errors = await router.discover()
        if errors:
            write(directory / 'discovery_error.json', dict(errors=errors, dispatched=False))
            raise ValueError('HOST_DISCOVERY_FAILED')
        if ROUND_ID != 'original':
            ready = read_ready(directory)
            if (ready.get('ready') is not True or ready.get('callbacks_restored') is not True
                    or ready.get('catalog_hash') != backend.catalog_digest
                    or ready.get('session',{}).get('host_generation') != transport.host_generation
                    or not 0 <= time.time()-ready.get('checked_unix',0) <= 180):
                raise ValueError('READY_GATE_STALE_OR_MISMATCH')
        for previous in EVIDENCE_ROOT.rglob('session.json'):
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
        write(directory / 'plan.json', asdict(plan))
        write(directory / 'renderer.json', dict(source_hash=rendered.sha256, note_count=4))
        await backend.validate(plan, backend.capabilities[0])
        await backend.resolve_target(plan)
        write(directory / 'uia_subscription.json', uia_subscription_probe())
        launch = json.loads((directory / 'launch.json').read_text(encoding='utf-8'))
        observer = NativeEventObserver(launch['pid'], operation)
        before = observer.snapshot()
        write(directory / 'native_before.json', before)
        if any(w['fixed_probe_title_match'] for w in before['windows']):
            raise ValueError('PREVIEW_ALREADY_EXISTS')
        viewport = NativePianoRollViewport(launch['pid'])
        def ready(operation_id, timestamp):
            print(json.dumps(dict(state='LOCAL_PREVIEW_READY', operation_id=operation_id,
                timestamp_ns=timestamp, requires_explicit_accept=True)), flush=True)
        interaction_type = LocalPreviewInteraction
        if ROUND_ID in ('diagnostic_4', 'preview_phase_1', 'stability_1', *CONTROLLED_ROUNDS):
            fingerprint = viewport.fingerprint()
            full_screen = FullScreenLiveDiagnostic(events/'full_screen_frames', ROOT, fingerprint['roi'])
            await asyncio.to_thread(full_screen.start)
            interaction_type = PreviewPhaseInteraction if ROUND_ID in ('preview_phase_1', 'stability_1', *CONTROLLED_ROUNDS) else FullScreenDiagnosticInteraction
        interaction = interaction_type(viewport, ObservedInteraction(trace), trace_id=operation,
            ready_callback=ready, **(dict(diagnostic=full_screen) if full_screen else {}))
        if ROUND_ID in VISUAL_ROUNDS:
            interaction = ControlledVisualInteraction(viewport, ObservedInteraction(trace),
                trace_id=operation, ready_callback=ready, diagnostic=full_screen,
                backend=backend, directory=events, sky_window_id=sky_record['id'])
            backend.accept_policy = AcceptPolicy.GUARDED_AUTO_ACCEPT
            backend.auto_accept_enabled = True
        backend.interaction = interaction
        observer.start()
        observe(trace, 'native_observer_ready', 'observer')
        write(directory / 'native_after_install.json', observer.snapshot())
        result = await router.execute(plan)
        report = result.to_dict()
        write(directory / 'native_at_finish.json', observer.snapshot())
        report['bridge_events'] = bridge_events(transport)
    except Exception as error:
        if not report:
            dispatched = (backend.last_execution or {}).get('dispatch_status') == 'DISPATCHED'
            report.update(execution_status='UNKNOWN' if dispatched else 'NOT_DISPATCHED',
                error_code=getattr(error, 'code', type(error).__name__),
                setup_failed=True, dispatched=dispatched)
        raise
    finally:
        if full_screen:
            try:
                await asyncio.to_thread(full_screen.close)
                write(directory/'full_screen_observation.json', full_screen.report())
            except Exception as error:
                write(directory/'full_screen_cleanup_error.json', dict(error_code=type(error).__name__,
                    scope='DIAGNOSTIC_ONLY', runtime_state_emitted=False, observer_stopped=full_screen.stop_confirmed))
        await close_runtime_resources(interaction, observer, backend, transport, directory, report, trace)
    print(json.dumps(dict(status=report.get('execution_status'), callbacks_restored=transport.callbacks_restored)))


def main():
    global OUTPUT, ROUND_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('launch', 'ready', 'run', 'recover'))
    parser.add_argument('--round', choices=('original','validation_1','diagnostic_1','diagnostic_2','diagnostic_3','diagnostic_4','preview_phase_1','stability_1',*CONTROLLED_ROUNDS), default='original')
    parser.add_argument('--trial', choices=('session_1', 'session_2', 'session_3', 'session_4', 'session_5'), required=True)
    args = parser.parse_args()
    if args.round in ('stability_1', 'controlled_accept_1') and args.trial not in ('session_1', 'session_2', 'session_3'):
        raise ValueError('STABILITY_THREE_SESSION_LIMIT')
    if args.round == 'controlled_accept_repaired_1' and args.trial not in ('session_2', 'session_3'):
        raise ValueError('CONTROLLED_REMAINING_TWO_SESSION_LIMIT')
    if args.round == 'controlled_accept_visual_1' and args.trial != 'session_3':
        raise ValueError('CONTROLLED_FINAL_SESSION_ONLY')
    if args.round == 'controlled_accept_visual_2' and args.trial != 'session_4':
        raise ValueError('EXTENDED_VISUAL_SINGLE_NEW_SESSION_ONLY')
    if args.round in ('diagnostic_1','diagnostic_2','diagnostic_3','diagnostic_4','preview_phase_1') and args.trial != 'session_1':
        raise ValueError('DIAGNOSTIC_SINGLE_SESSION_ONLY')
    ROUND_ID = args.round
    OUTPUT = EVIDENCE_ROOT if ROUND_ID == 'original' else EVIDENCE_ROOT/ROUND_ID
    if ROUND_ID == 'controlled_accept_1':
        OUTPUT = ROOT/'evidence/runtime_v2/controlled_accept'
    if ROUND_ID == 'controlled_accept_repaired_1':
        OUTPUT = ROOT/'evidence/runtime_v2/controlled_accept/repaired_1'
    if ROUND_ID == 'controlled_accept_visual_1':
        OUTPUT = ROOT/'evidence/runtime_v2/controlled_accept/visual_1'
    if ROUND_ID == 'controlled_accept_visual_2':
        OUTPUT = ROOT/'evidence/runtime_v2/controlled_accept/visual_2'
    if (OUTPUT / 'summary.json').exists():
        raise ValueError('STAGE_CLOSED')
    directory = OUTPUT / args.trial
    events = Path(os.environ['TEMP']) / ('DAWLoop_RuntimeV2_local_preview_' +
        ('' if ROUND_ID == 'original' else ROUND_ID+'_') + args.trial)
    if args.action == 'launch':
        baseline()
        if ROUND_ID == 'controlled_accept_visual_1':
            visual_round_preflight(OUTPUT.parent)
        if ROUND_ID == 'controlled_accept_visual_2':
            extended_visual_preflight(OUTPUT.parent)
        if ROUND_ID == 'controlled_accept_repaired_1':
            initial = smoke.read(OUTPUT.parent/'summary.json')
            if (initial.get('status') != 'CLOSED_SETUP_FAILED_BEFORE_DISPATCH'
                    or initial.get('live_session_count') != 1 or initial.get('writes_dispatched') != 0
                    or initial.get('accept_actions') != 0):
                raise ValueError('CONTROLLED_REPAIR_BOUNDARY_MISMATCH')
            if len(list(OUTPUT.parent.rglob('launch.json'))) >= 3:
                raise ValueError('CONTROLLED_TOTAL_SESSION_BUDGET_EXHAUSTED')
        if directory.exists() or events.exists() or not all(process_state().values()):
            raise ValueError('HOST_NOT_CLOSED_OR_TRIAL_EXISTS')
        for old in OUTPUT.glob('*/launch.json'):
            if not (old.parent / 'recovery.json').exists():
                raise ValueError('PREVIOUS_SESSION_NOT_RECOVERED')
            if ROUND_ID != 'original' and not previous_passed(old.parent, strict=ROUND_ID in ('stability_1', *CONTROLLED_ROUNDS)):
                raise ValueError('PREVIOUS_SESSION_FAILED')
        number = int(args.trial.rsplit('_',1)[1])
        expected_previous = number-(4 if ROUND_ID == 'controlled_accept_visual_2'
            else 3 if ROUND_ID == 'controlled_accept_visual_1'
            else 2 if ROUND_ID == 'controlled_accept_repaired_1' else 1)
        if ROUND_ID != 'original' and len(list(OUTPUT.glob('*/launch.json'))) != expected_previous:
            raise ValueError('SESSION_ORDER_REQUIRED')
        if ROUND_ID in ('stability_1', *CONTROLLED_ROUNDS):
            stability_version(OUTPUT, create=True)
        directory.mkdir(parents=True)
        events.mkdir()
        process = subprocess.Popen([fl_executable(), str(baseline())],
            env=dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222'),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS)
        write(directory / 'launch.json', dict(pid=process.pid, baseline_size=BASELINE_SIZE,
            baseline_sha256=BASELINE_HASH, observed_unix=time.time()))
        print(json.dumps(dict(pid=process.pid)))
    elif args.action == 'ready':
        if not (directory/'launch.json').exists():
            raise ValueError('EXPERIMENT_NOT_LAUNCHED')
        if ROUND_ID in ('stability_1', *CONTROLLED_ROUNDS):
            stability_version(OUTPUT)
        asyncio.run(readiness(directory))
    elif args.action == 'run':
        if not (directory / 'launch.json').exists():
            raise ValueError('EXPERIMENT_NOT_LAUNCHED')
        if ROUND_ID in ('stability_1', *CONTROLLED_ROUNDS):
            stability_version(OUTPUT)
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
