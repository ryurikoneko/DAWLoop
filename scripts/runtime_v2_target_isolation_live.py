"""独立宿主会话中的固定目标实验；禁止重试、撤销及保存。"""

from release_environment import fl_executable

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.adapters.gopher_native.catalog import catalog_hash, known_catalog
from dawloop.adapters.gopher_native.response import decode_script_acceptance
from dawloop.adapters.gopher_native.transport import CDPTransport
from runtime_v2_executor_probe_live import SOURCE_HASH, CATALOG_HASH

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/target_isolation'
TRIALS = ('aligned', 'channel_mismatch', 'pattern_mismatch')
FIXTURE_HASH = 'a2f9922d6b8cdc7f7627428d0d7072ed7dcab0a4f666fef42145c0c6e91b006f'


def write(directory, name, data):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / name).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def read(directory, name):
    return json.loads((directory / name).read_text(encoding='utf-8'))


def fixture():
    path = Path(os.environ['TEMP']) / 'DAWLoop_RuntimeV2_PianoRollProbe.flp'
    if hashlib.sha256(path.read_bytes()).hexdigest() != FIXTURE_HASH:
        raise ValueError('BASELINE_INTEGRITY_FAILED')
    return path


def session_gate(trial):
    if (OUTPUT / 'summary.json').exists():
        raise ValueError('本阶段已结束')
    position = TRIALS.index(trial)
    if position:
        previous = read(OUTPUT / TRIALS[position-1], 'recovery.json')
        if (previous.get('host_closed') is not True or previous.get('debug_port_closed') is not True
                or previous.get('fixture_hash_before') != FIXTURE_HASH
                or previous.get('fixture_hash_after') != FIXTURE_HASH):
            raise ValueError('PREVIOUS_SESSION_RECOVERY_UNPROVEN')


def identity():
    data = asyncio.run(ControllerIdentityBackend('FLSkill MCP IN 2').read_identity())
    return {key:data.get(key) for key in ('controller_session','project_generation','project_loading',
        'pattern_number','pattern_name','channel_index','channel_name','selected_channels','ppq',
        'fl_studio_version','observed_at')}


def dispatch_gate(trial, directory):
    session_gate(trial)
    fixture()
    if (directory / 'intent.json').exists() or (directory / 'result.json').exists():
        raise ValueError('SINGLE_DISPATCH_BUDGET_EXHAUSTED')
    source = (ROOT / 'research/piano_roll_probe/executor_canonical_v1.pyscript').read_bytes()
    if (hashlib.sha256(source).hexdigest() != SOURCE_HASH
            or source != (ROOT / 'tests/native_fixtures/executor_canonical.py').read_bytes()):
        raise ValueError('FIXED_SOURCE_MISMATCH')
    observed = read(directory, 'preflight.json')
    if (not 0 <= time.time()-observed['observed_unix'] <= 60
            or observed.get('state_representable') is not True
            or not all(observed.get(key) is True for key in ('fixture_confirmed','marker_absent','no_other_calls'))
            or not (directory / observed['screenshot']).is_file()):
        raise ValueError('TARGET_UI_EVIDENCE_UNAVAILABLE')
    return source, observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial', required=True, choices=TRIALS)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--launch-session', action='store_true')
    group.add_argument('--read-identity', action='store_true')
    group.add_argument('--dispatch-fixed', action='store_true')
    args = parser.parse_args()
    session_gate(args.trial)
    directory = OUTPUT / args.trial
    path = fixture()
    if args.launch_session:
        if directory.exists():
            raise ValueError('本组会话已经建立，禁止重复启动')
        running = subprocess.run(['powershell','-NoProfile','-Command',
            'Get-Process FL64 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],
            capture_output=True,text=True,timeout=5)
        if running.stdout.strip():
            raise ValueError('EXISTING_HOST_NOT_CLOSED')
        directory.mkdir(parents=True)
        write(directory, 'launch_intent.json', dict(fixture_hash=FIXTURE_HASH, trial=args.trial,
            timestamp=datetime.now(timezone.utc).isoformat()))
        environment = dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222')
        process = subprocess.Popen([fl_executable(),str(path)],env=environment,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS)
        write(directory, 'session_start.json', dict(pid=process.pid, fixture_hash_before=FIXTURE_HASH,
            debug_scope='CHILD_PROCESS_ENVIRONMENT_ONLY', launched_unix=time.time()))
        print(json.dumps(dict(trial=args.trial,pid=process.pid)))
        return
    if args.read_identity:
        print(json.dumps(identity(),ensure_ascii=False))
        return
    source, observation = dispatch_gate(args.trial,directory)
    transport = CDPTransport(timeout=35)
    report = dict(dispatched=False, completion='NOT_DISPATCHED')
    try:
        session = transport.connect()
        for previous in TRIALS[:TRIALS.index(args.trial)]:
            old_file = OUTPUT / previous / 'intent.json'
            if old_file.exists() and read(OUTPUT / previous,'intent.json')['session']['host_generation'] == session['host_generation']:
                raise ValueError('OLD_PAGE_CONTEXT_REUSED')
        raw = transport.invoke('catalog')
        payload = raw['payload']
        catalog = json.loads(payload) if isinstance(payload,str) else payload
        tools = catalog if isinstance(catalog,list) else catalog['tools']
        tool = next(item for item in tools if item['name']=='run_piano_roll_script')
        reference = known_catalog()['tools']['run_piano_roll_script']
        if (catalog_hash(tools) != CATALOG_HASH or tool.get('inputSchema') != reference['input_schema']
                or tool.get('description') != reference['description']):
            raise ValueError('CATALOG_CHANGED')
        write(directory,'catalog.json',dict(tools=tools,catalog_hash=CATALOG_HASH))
        current = identity()
        expected = observation['controller_expected']
        if (current.get('project_loading') is not False or current.get('ppq') != 96
                or current.get('selected_channels') != [expected['channel_index']]
                or any(current.get(key) != value for key,value in expected.items())):
            raise ValueError('CONTROLLER_TARGET_CHANGED')
        blocked = transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke("call","run_piano_roll_script",{},35000)')
        if blocked != dict(ok=False,code='READ_ONLY_BACKEND'):
            raise ValueError('GENERAL_SCRIPT_GUARD_FAILED')
        fixture()
        dispatch_unix = time.time()
        write(directory,'intent.json',dict(source_hash=SOURCE_HASH,source=source.decode('utf-8'),
            session=session,identity=current,dispatch_unix=dispatch_unix,
            raw_tool_request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
                'name':'run_piano_roll_script','arguments':{'source':source.decode('utf-8')}}}))
        report.update(dispatched=True,completion='COMPLETION_UNKNOWN')
        started=time.monotonic_ns()
        response=transport._evaluate('window.__dawloopReadonlyBridgeV1.invokeFixedExecutorProbe(%s,%s,%s,35000)' % (
            json.dumps('executor_canonical_v1'),json.dumps(SOURCE_HASH),json.dumps(source.decode('utf-8'))))
        decoded=decode_script_acceptance(response)
        report.update(raw_bridge_response=response,total_ms=(time.monotonic_ns()-started)/1_000_000,
            callback_or_timeout_unix=time.time(),execution_status=decoded.status.value,
            script_application_status=decoded.script_application_status.value)
        if isinstance(response,dict) and response.get('ok') is True:
            report['completion']='COMPLETION_CONFIRMED'
            report['acknowledged']=transport._evaluate('window.__dawloopReadonlyBridgeV1.acknowledge(%s)' % json.dumps(transport.epoch))
    except Exception as error:
        report['error_code']=getattr(error,'code',str(error))
    finally:
        transport.close()
        report['callbacks_restored']=transport.callbacks_restored
        write(directory,'result.json',report)
        print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
