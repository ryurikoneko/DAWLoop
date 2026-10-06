"""预览时序分解；每个独立会话最多单次四音符派发。"""

from release_environment import fl_executable

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import statistics
import subprocess
import time

from dawloop.runtime import BackendRouter, NativeWriteJournal, PianoRollBatchAddPlan, PianoRollScriptRenderer, ExecutionStatus
from dawloop.runtime.diagnostics import DiagnosticTrace, observe
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend, CERTIFIED_CATALOG
from dawloop.adapters.gopher_native.catalog import catalog_hash, known_catalog, normalize_catalog
from dawloop.adapters.gopher_native.response import decode_response
from dawloop.adapters.gopher_native.transport import CDPTransport
from runtime_v2_throughput_live import baseline, process_state, BASELINE_HASH, BASELINE_SIZE
import runtime_v2_native_write_smoke as smoke


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/preview_latency'


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def checked_catalog(transport):
    result = transport.invoke('catalog')['payload']
    result = json.loads(result) if isinstance(result, str) else result
    tools = result if isinstance(result, list) else result['tools']
    if catalog_hash(tools) != CERTIFIED_CATALOG:
        raise ValueError('CATALOG_CHANGED')
    for name in ('get_tempo', 'run_piano_roll_script'):
        current = next(t for t in tools if t['name'] == name)
        known = known_catalog()['tools'][name]
        if current.get('inputSchema') != known['input_schema'] or current.get('description') != known['description']:
            raise ValueError('TOOL_CONTRACT_CHANGED')
    tempo = next(c for c in normalize_catalog(tools) if c.raw_tool['name'] == 'get_tempo')
    if tempo.writable or tempo.safety != 'READ_ONLY':
        raise ValueError('READ_CLASSIFICATION_FAILED')
    return tools


def configure(transport, trace):
    trace.host_generation = transport.host_generation
    transport.diagnostics = trace
    values = [trace.trace_id, trace.operation_id, trace.host_generation]
    if transport._evaluate('window.__dawloopReadonlyBridgeV1.configureDiagnostics(%s)' %
            ','.join(json.dumps(v) for v in values)) is not True:
        raise ValueError('DIAGNOSTICS_NOT_CONFIGURED')


def bridge_events(transport):
    return transport._evaluate('window.__dawloopReadonlyBridgeV1.diagnostics.events')


def cheap(transport, directory):
    rows = []
    for index in range(20):
        trace = DiagnosticTrace(directory.name + '-cheap-%02d' % index, 'tempo-%02d' % index)
        configure(transport, trace)
        observe(trace, 'client_call_start', 'client')
        started = time.perf_counter_ns()
        result = transport.invoke('call', 'get_tempo', {})
        ended = time.perf_counter_ns()
        observe(trace, 'client_call_end', 'client')
        decoded = decode_response('get_tempo', result, {})
        if decoded.error_code or decoded.status != ExecutionStatus.SUCCESS:
            raise ValueError('CHEAP_READ_FAILED')
        bridge = bridge_events(transport)
        rows.append(dict(trace_id=trace.trace_id, host_generation=trace.host_generation,
            total_ms=(ended-started)/1000000, result=decoded.value,
            host_call_started=None, events=trace.events + bridge))
    values = sorted(r['total_ms'] for r in rows)
    write(directory/'cheap.json', dict(n=len(rows), median=statistics.median(values),
        p50=statistics.median(values), p95=values[18], p95_method='nearest_rank', max=max(values), calls=rows))


class ObservedInteraction(smoke.ManualInteraction):
    def __init__(self, trace):
        self.trace = trace

    async def event(self, name):
        result = await super().event(name)
        observe(self.trace, name + '_marker_received', 'observer',
            observer_event=result.get('observer_event'),
            first_appearance_proven=False)
        return result


async def run(mode, directory, events):
    baseline()
    write(directory/'execution_intent.json', dict(mode=mode, dispatch_budget=1))
    operation_id = 'latency-' + directory.name
    smoke.EVENTS, smoke.OPERATION_ID = events, operation_id
    plan = PianoRollBatchAddPlan(dict(expected_pattern_index=1, expected_pattern_name='样式 1',
        expected_channel_index=0, expected_channel_name='808 Kick'),
        tuple(dict(number=84+i, time=3072+i*48, length=24, velocity=0.5) for i in range(4)),
        operation_id).operation_plan()
    trace = DiagnosticTrace(operation_id, operation_id)
    observe(trace, 'operation_received' if mode == 'full' else 'raw_preflight_begin')
    transport = CDPTransport(timeout=35)
    interaction = ObservedInteraction(trace)
    backend = GopherNativeWriteBackend(enabled=True, transport=transport,
        target_preparer=smoke.TargetPreparation(), interaction=interaction,
        journal=NativeWriteJournal(OUTPUT/'dispatch_intents'), disposable_guard=smoke.fixture_guard)
    backend.diagnostics = trace
    report = {}
    try:
        observe(trace, 'discovery_begin')
        await backend.discover()
        observe(trace, 'discovery_complete')
        trace.host_generation = transport.host_generation
        old = [json.loads(p.read_text(encoding='utf-8')) for p in OUTPUT.glob('*/session.json')]
        if any(o['host_generation'] == transport.host_generation for o in old):
            raise ValueError('OLD_HOST_GENERATION_REUSED')
        write(directory/'session.json', backend.session)
        tools = checked_catalog(transport)
        write(directory/'catalog.json', dict(catalog_hash=CERTIFIED_CATALOG, tools=tools))
        if mode == 'raw' and directory.name in ('raw1', 'raw2'):
            await asyncio.to_thread(cheap, transport, directory)
        configure(transport, trace)
        if transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke("call","run_piano_roll_script",{},35000)') != dict(ok=False, code='READ_ONLY_BACKEND'):
            raise ValueError('ARBITRARY_SCRIPT_GUARD_FAILED')
        rendered = PianoRollScriptRenderer().render(plan.parameters['notes'])
        if rendered.sha256 != 'ac68744417a7b98f7c2a7c2293ba255b73e6d99ecd3609618af0f501f786da75':
            raise ValueError('FIXED_SOURCE_CHANGED')
        write(directory/'plan.json', asdict(plan))
        (directory/'source.py').write_bytes(rendered.source)
        if mode == 'full':
            router = BackendRouter([backend])
            router.diagnostics = trace
            router.registry.replace(backend.name, backend.capabilities)
            result = await router.execute(plan)
            observe(trace, 'operation_result_emitted')
            report = result.to_dict()
        else:
            await backend.validate(plan, backend.capabilities[0])
            evidence = await backend.target_preparer.confirm(plan.target, backend.session)
            backend.check_target(plan, evidence)
            write(directory/'target.json', evidence)
            backend.journal.reserve(operation_id, backend.session, rendered.sha256)
            def dispatch():
                observe(trace, 'raw_call_begin', 'client')
                try:
                    response = transport.invoke_batch(plan.parameters['notes'], rendered, operation_id)
                    return dict(response=response, completion='COMPLETION_CONFIRMED')
                except Exception as error:
                    return dict(error=getattr(error, 'code', str(error)), completion='COMPLETION_UNKNOWN')
                finally:
                    observe(trace, 'raw_call_end', 'client')
            task = asyncio.create_task(asyncio.to_thread(dispatch))
            await interaction.wait_preview(operation_id)
            observe(trace, 'runtime_preview_notification')
            await interaction.wait_accept(operation_id)
            await interaction.wait_application(operation_id)
            report = await task
        report['bridge_events'] = bridge_events(transport)
    finally:
        await backend.close()
        report['callbacks_restored'] = transport.callbacks_restored
        report['preview_first_observed'] = None
        report['host_call_started'] = None
        report['bridge_enqueue'] = report['bridge_dequeue'] = None
        write(directory/'result.json', report)
        write(directory/'trace.json', trace.events + report.get('bridge_events', []))
    print(json.dumps(dict(mode=mode, callbacks_restored=report['callbacks_restored']), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('launch', 'run', 'recover'))
    parser.add_argument('--trial', choices=('raw1', 'raw2', 'raw3', 'full1', 'full2', 'full3'), required=True)
    args = parser.parse_args()
    if (OUTPUT/'summary.json').exists():
        raise ValueError('STAGE_CLOSED')
    directory = OUTPUT/args.trial
    events = Path(os.environ['TEMP'])/('DAWLoop_RuntimeV2_3_2_' + args.trial)
    if args.action == 'launch':
        baseline()
        if directory.exists() or events.exists() or not all(process_state().values()):
            raise ValueError('HOST_NOT_CLOSED_OR_TRIAL_EXISTS')
        for old in OUTPUT.glob('*/launch.json'):
            if not (old.parent/'recovery.json').exists():
                raise ValueError('PREVIOUS_SESSION_NOT_RECOVERED')
        directory.mkdir(parents=True)
        events.mkdir()
        write(directory/'launch.json', dict(baseline_size=BASELINE_SIZE, baseline_sha256=BASELINE_HASH))
        process = subprocess.Popen([fl_executable(), str(baseline())],
            env=dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222'),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS)
        print(json.dumps(dict(pid=process.pid)))
    elif args.action == 'recover':
        state = process_state()
        baseline()
        if not all(state.values()):
            raise ValueError('HOST_OR_PORT_STILL_OPEN')
        write(directory/'recovery.json', dict(**state, no_save_exit=True, baseline_size=BASELINE_SIZE,
            baseline_sha256=BASELINE_HASH))
        print(json.dumps(state))
    else:
        if not (directory/'launch.json').exists():
            raise ValueError('EXPERIMENT_NOT_LAUNCHED')
        asyncio.run(run('raw' if args.trial.startswith('raw') else 'full', directory, events))


if __name__ == '__main__':
    main()
