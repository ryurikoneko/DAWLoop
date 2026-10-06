"""固定规模吞吐研究，每个独立宿主会话仅允许一次派发。"""

from release_environment import fl_executable

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.adapters.gopher_native.catalog import catalog_hash, known_catalog
from dawloop.adapters.gopher_native.transport import CDPTransport
from runtime_v2_executor_probe_live import CATALOG_HASH

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/native_throughput'
COUNTS = (1, 4, 32, 64, 128)
BASELINE_HASH = 'a2f9922d6b8cdc7f7627428d0d7072ed7dcab0a4f666fef42145c0c6e91b006f'
BASELINE_SIZE = 53498


def source_for(count):
    if type(count) is not int or count not in COUNTS:
        raise ValueError('UNSUPPORTED_BATCH_SIZE')
    return ('''import flpianoroll as flp

NOTE_COUNT = %d

def createDialog() -> flp.ScriptDialog:
    return flp.ScriptDialog("DAWLoop Throughput Probe", "Adds a fixed disposable grid.")

def apply(form: flp.ScriptDialog) -> None:
    ppq = flp.score.PPQ
    for index in range(NOTE_COUNT):
        note = flp.Note()
        note.number = 84 + index // 16
        note.time = 32 * ppq + (index %% 16) * (ppq // 2)
        note.length = ppq // 4
        note.velocity = 0.5
        flp.score.addNote(note)
''' % count).encode('utf-8')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def baseline():
    path = Path(os.environ['TEMP']) / 'DAWLoop_RuntimeV2_PianoRollProbe.flp'
    data = path.read_bytes()
    if len(data) != BASELINE_SIZE or hashlib.sha256(data).hexdigest() != BASELINE_HASH:
        raise ValueError('BASELINE_INTEGRITY_FAILED')
    return path


def process_state():
    result = subprocess.run(['powershell', '-NoProfile', '-Command',
        "$p=@(Get-Process FL64 -ErrorAction SilentlyContinue); "
        "$t=@(Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue); "
        "@{host_closed=($p.Count -eq 0); debug_port_closed=($t.Count -eq 0)} | ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=8)
    return json.loads(result.stdout)


def gate(count):
    if count not in COUNTS or (OUTPUT / 'summary.json').exists():
        raise ValueError('STAGE_CLOSED_OR_INVALID_SIZE')
    baseline()
    index = COUNTS.index(count)
    if index:
        old = OUTPUT / ('n%03d' % COUNTS[index-1])
        recovery = read(old / 'recovery.json')
        observed = read(old / 'observation.json')
        if (not recovery.get('host_closed') or not recovery.get('debug_port_closed')
                or recovery.get('sha256_after') != BASELINE_HASH
                or recovery.get('size_after') != BASELINE_SIZE
                or observed.get('visible_batch_effect') is not True
                or observed.get('stop_condition') is not False):
            raise ValueError('PREVIOUS_SCALE_NOT_PASSED')


def checked_source(count):
    expected = source_for(count)
    manifest = read(OUTPUT / 'probe_hashes.json')[str(count)]
    actual = (OUTPUT / ('probe_%03d.py' % count)).read_bytes()
    if actual != expected or hashlib.sha256(actual).hexdigest() != manifest['sha256']:
        raise ValueError('FIXED_SOURCE_MISMATCH')
    return actual, manifest


def identity():
    data = asyncio.run(ControllerIdentityBackend('FLSkill MCP IN 2').read_identity())
    return {key: data.get(key) for key in ('controller_session', 'project_generation',
        'project_loading', 'pattern_number', 'pattern_name', 'channel_index', 'channel_name',
        'selected_channels', 'ppq', 'fl_studio_version', 'observed_at')}


def dispatch(count, directory):
    if (directory / 'intent.json').exists() or (directory / 'result.json').exists():
        raise ValueError('SINGLE_DISPATCH_BUDGET_EXHAUSTED')
    source, manifest = checked_source(count)
    observed = read(directory / 'preflight.json')
    if (not 0 <= time.time() - observed['observed_unix'] <= 60
            or not all(observed.get(k) is True for k in ('target_confirmed', 'region_empty', 'no_other_calls'))
            or not (directory / observed['screenshot']).is_file()):
        raise ValueError('TARGET_UI_EVIDENCE_UNAVAILABLE')
    transport = CDPTransport(timeout=35)
    report = dict(dispatched=False, completion='NOT_DISPATCHED')
    try:
        session = transport.connect()
        for old_count in COUNTS[:COUNTS.index(count)]:
            previous = read(OUTPUT / ('n%03d' % old_count) / 'intent.json')
            if previous['session']['host_generation'] == session['host_generation']:
                raise ValueError('OLD_CONTEXT_REUSED')
        raw = transport.invoke('catalog')
        payload = raw['payload']
        catalog = json.loads(payload) if isinstance(payload, str) else payload
        tools = catalog if isinstance(catalog, list) else catalog['tools']
        definition = next(t for t in tools if t['name'] == 'run_piano_roll_script')
        reference = known_catalog()['tools']['run_piano_roll_script']
        if (catalog_hash(tools) != CATALOG_HASH
                or definition.get('inputSchema') != reference['input_schema']
                or definition.get('description') != reference['description']):
            raise ValueError('CATALOG_CHANGED')
        write(directory / 'catalog.json', dict(catalog_hash=CATALOG_HASH, tools=tools))
        current = identity()
        if (current['pattern_number'] != 1 or current['channel_index'] != 0
                or current['selected_channels'] != [0] or current['ppq'] != 96
                or current['project_loading'] is not False
                or current['fl_studio_version'] != 'Producer Edition v26.1.6 [build 5639]'):
            raise ValueError('TARGET_OR_VERSION_CHANGED')
        blocked = transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke("call","run_piano_roll_script",{},35000)')
        if blocked != dict(ok=False, code='READ_ONLY_BACKEND'):
            raise ValueError('GENERAL_SCRIPT_GUARD_FAILED')
        baseline()
        started = time.monotonic_ns()
        write(directory / 'intent.json', dict(note_count=count, source_hash=manifest['sha256'],
            source_size_bytes=len(source), session=session, identity=current,
            dispatch_unix=time.time(), dispatch_monotonic_ns=started,
            raw_tool_request=dict(jsonrpc='2.0', id=1, method='tools/call', params=dict(
                name='run_piano_roll_script', arguments=dict(source=source.decode('utf-8'))))))
        report['dispatched'] = True
        report['completion'] = 'COMPLETION_UNKNOWN'
        response = transport._evaluate('window.__dawloopReadonlyBridgeV1.invokeFixedThroughputProbe(%s,%s,%s,35000)' % (
            count, json.dumps(manifest['sha256']), json.dumps(source.decode('utf-8'))))
        report.update(raw_bridge_response=response, callback_or_timeout_unix=time.time(),
            total_ms=(time.monotonic_ns()-started)/1_000_000)
        if isinstance(response, dict) and response.get('ok') is True:
            report['completion'] = 'COMPLETION_CONFIRMED'
            report['acknowledged'] = transport._evaluate(
                'window.__dawloopReadonlyBridgeV1.acknowledge(%s)' % json.dumps(transport.epoch))
    except Exception as error:
        report['error_code'] = getattr(error, 'code', str(error))
    finally:
        transport.close()
        report['callbacks_restored'] = transport.callbacks_restored
        write(directory / 'result.json', report)
        print(json.dumps(report, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', required=True, type=int, choices=COUNTS)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--launch', action='store_true')
    modes.add_argument('--dispatch', action='store_true')
    modes.add_argument('--recover', action='store_true')
    modes.add_argument('--identity', action='store_true')
    args = parser.parse_args()
    gate(args.count)
    directory = OUTPUT / ('n%03d' % args.count)
    if args.identity:
        print(json.dumps(identity(), ensure_ascii=False))
    elif args.launch:
        if directory.exists() or not all(process_state().values()):
            raise ValueError('HOST_NOT_CLOSED_OR_TRIAL_EXISTS')
        directory.mkdir(parents=True)
        write(directory / 'launch_intent.json', dict(sha256_before=BASELINE_HASH, size_before=BASELINE_SIZE))
        environment = dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222')
        process = subprocess.Popen([fl_executable(), str(baseline())], env=environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS)
        write(directory / 'session_start.json', dict(pid=process.pid, launched_unix=time.time(),
            debug_scope='CHILD_PROCESS_ENVIRONMENT_ONLY'))
        print(json.dumps(dict(pid=process.pid)))
    elif args.recover:
        state = process_state()
        if not all(state.values()):
            raise ValueError('HOST_OR_DEBUG_PORT_STILL_OPEN')
        baseline()
        write(directory / 'recovery.json', dict(**state, sha256_after=BASELINE_HASH,
            size_after=BASELINE_SIZE, no_save_exit=True, verified_unix=time.time()))
        print(json.dumps(state))
    else:
        dispatch(args.count, directory)


if __name__ == '__main__':
    main()
