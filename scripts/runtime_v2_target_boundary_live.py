"""一次性目标及撤销边界实验；每个显式入口只有一个动作，没有重试。"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.adapters.gopher_native.catalog import catalog_hash, known_catalog
from dawloop.adapters.gopher_native.transport import CDPTransport
from dawloop.runtime import ScriptInvocationState, ScriptCompletionStatus
from runtime_v2_executor_probe_live import SOURCE_HASH, CATALOG_HASH

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/target_semantics'
FIXTURE_HASH = 'a2f9922d6b8cdc7f7627428d0d7072ed7dcab0a4f666fef42145c0c6e91b006f'


def save(name, data):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / name).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def read(name):
    return json.loads((OUTPUT / name).read_text(encoding='utf-8'))


def capture():
    identity = asyncio.run(ControllerIdentityBackend('FLSkill MCP IN 2').read_identity())
    keys = ('controller_session', 'project_generation', 'project_loading', 'pattern_number',
            'pattern_name', 'channel_index', 'channel_name', 'selected_channels', 'ppq',
            'fl_studio_version', 'undo_state', 'observed_at')
    return {key: identity.get(key) for key in keys}


def validate_aligned(identity):
    if (identity.get('pattern_number') != 1 or identity.get('channel_index') != 0
            or identity.get('selected_channels') != [0] or identity.get('ppq') != 96
            or identity.get('project_loading') is not False):
        raise ValueError('ALIGNED_IDENTITY_MISMATCH')
    state = identity.get('undo_state')
    if not isinstance(state, dict) or any(state.get(key) is None for key in ('position','count','last','hint','changed_flag')):
        raise ValueError('UNDO_FIELDS_UNAVAILABLE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--capture', choices=('before','after'))
    group.add_argument('--dispatch-aligned', action='store_true')
    group.add_argument('--undo-if-proven', action='store_true')
    args = parser.parse_args()
    if (OUTPUT / 'summary.json').exists():
        raise ValueError('本阶段已结束')
    fixture = Path(os.environ['TEMP']) / 'DAWLoop_RuntimeV2_PianoRollProbe.flp'
    if hashlib.sha256(fixture.read_bytes()).hexdigest() != FIXTURE_HASH:
        raise ValueError('FIXTURE_HASH_CHANGED')
    if args.capture:
        identity = capture()
        validate_aligned(identity)
        save('undo_'+args.capture+'.json', identity)
        print(json.dumps(identity, ensure_ascii=False))
        return
    if args.undo_if_proven:
        before, after = read('undo_before.json'), read('undo_after.json')
        current = capture()
        validate_aligned(current)
        observation = read('after_ui.json')
        if (not observation.get('marker_present') or not observation.get('dialog_closed')
                or time.time()-observation['observed_unix'] > 60):
            raise ValueError('UNDO_UI_EVIDENCE_UNAVAILABLE')
        for field in ('controller_session','project_generation','pattern_number','channel_index','undo_state'):
            if current[field] != after[field]:
                raise ValueError('UNDO_STATE_CHANGED')
        params = dict(trial='aligned', source_hash=SOURCE_HASH,
            controller_session=current['controller_session'], project_generation=current['project_generation'],
            before=before['undo_state'], after=after['undo_state'])
        save('undo_intent.json', params)
        try:
            result = asyncio.run(ControllerIdentityBackend('FLSkill MCP IN 2').research_undo_once(params))
            save('undo_result.json', dict(status='RETURNED', result=result))
            print(json.dumps(result, ensure_ascii=False))
        except Exception as error:
            save('undo_result.json', dict(status='REJECTED_OR_UNKNOWN', error_code=str(error)))
            raise
        return
    if (OUTPUT / 'aligned_intent.json').exists():
        raise ValueError('本轮已派发，禁止重试')
    source = (ROOT / 'research/piano_roll_probe/executor_canonical_v1.pyscript').read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH or source != (ROOT / 'evidence/runtime_v2/executor_contract/canonical_probe.py').read_bytes():
        raise ValueError('FIXED_SOURCE_MISMATCH')
    before = read('undo_before.json')
    observation = read('preflight_ui.json')
    if (not 0 <= time.time()-observation['observed_unix'] <= 60
            or not all(observation.get(key) is True for key in ('fixture_confirmed','marker_absent','piano_roll_a','no_other_calls'))
            or not (OUTPUT / observation['screenshot']).is_file()):
        raise ValueError('UI_PREFLIGHT_UNAVAILABLE')
    transport = CDPTransport(timeout=35)
    result = dict(dispatched=False, application_observed=False, completion='NOT_DISPATCHED')
    try:
        session = transport.connect()
        raw = transport.invoke('catalog')
        payload = raw['payload']
        catalog = json.loads(payload) if isinstance(payload,str) else payload
        tools = catalog if isinstance(catalog,list) else catalog['tools']
        tool = next(item for item in tools if item['name']=='run_piano_roll_script')
        reference = known_catalog()['tools']['run_piano_roll_script']
        if (catalog_hash(tools) != CATALOG_HASH or tool.get('inputSchema') != reference['input_schema']
                or tool.get('description') != reference['description']):
            raise ValueError('CATALOG_CHANGED')
        save('catalog.json', dict(catalog_hash=CATALOG_HASH, tools=tools))
        current = capture()
        validate_aligned(current)
        for key in ('controller_session','project_generation','pattern_number','channel_index','undo_state'):
            if current[key] != before[key]:
                raise ValueError('BASELINE_CHANGED')
        blocked = transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke("call","run_piano_roll_script",{},35000)')
        if blocked != dict(ok=False,code='READ_ONLY_BACKEND'):
            raise ValueError('GENERAL_SCRIPT_GUARD_FAILED')
        dispatch_unix = time.time()
        save('aligned_intent.json', dict(source_hash=SOURCE_HASH, source=source.decode('utf-8'), session=session,
            identity=current, dispatch_unix=dispatch_unix, dispatch_timestamp=datetime.now(timezone.utc).isoformat(),
            tool_request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'run_piano_roll_script','arguments':{'source':source.decode('utf-8')}}}))
        result.update(dispatched=True, completion='COMPLETION_UNKNOWN')
        started = time.monotonic_ns()
        response = transport._evaluate('window.__dawloopReadonlyBridgeV1.invokeFixedExecutorProbe(%s,%s,%s,35000)' % (
            json.dumps('executor_canonical_v1'), json.dumps(SOURCE_HASH), json.dumps(source.decode('utf-8'))))
        result.update(raw_bridge_response=response, total_ms=(time.monotonic_ns()-started)/1_000_000,
            callback_or_timeout_unix=time.time())
        if isinstance(response,dict) and response.get('ok') is True:
            result['completion']='COMPLETION_CONFIRMED'
            result['acknowledged']=transport._evaluate('window.__dawloopReadonlyBridgeV1.acknowledge(%s)' % json.dumps(transport.epoch))
        ScriptInvocationState(result['dispatched'],False,
            ScriptCompletionStatus.CONFIRMED if result['completion']=='COMPLETION_CONFIRMED' else ScriptCompletionStatus.UNKNOWN)
    except Exception as error:
        result['error_code'] = getattr(error,'code',str(error))
    finally:
        transport.close()
        result['callbacks_restored']=transport.callbacks_restored
        save('aligned_host_result.json',result)
        print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
