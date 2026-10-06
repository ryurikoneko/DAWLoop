"""目标语义研究专用入口；默认只发现，不接收调用者源码。"""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.adapters.gopher_native.catalog import catalog_hash, known_catalog
from dawloop.adapters.gopher_native.transport import CDPTransport
from runtime_v2_fixed_probe_live import redact

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/gopher_target_write'
PROBE_ID = 'target_semantics_v1'
SOURCE_HASH = 'cb2b35af5004a20f78da6d12fb67890edf45cabc8516372953c12cbefc6bce4b'
FIXTURE_HASH = 'a2f9922d6b8cdc7f7627428d0d7072ed7dcab0a4f666fef42145c0c6e91b006f'
CATALOG_HASH = '514d035244b0aea4d94fbb5ce8cad79415878e76dca6c85d94e1ebf692f4234e'
SOURCE = (b'import flpianoroll as flp\n\ndef apply(form):\n'
          b'    note = flp.Note()\n    note.number = 120\n    note.time = 0\n'
          b'    note.length = flp.score.PPQ\n    note.velocity = 0.5\n    flp.score.addNote(note)\n')


def prepare_source():
    actual = (ROOT / 'research/piano_roll_probe/target_semantics_v1.pyscript').read_bytes()
    if actual != SOURCE or hashlib.sha256(actual).hexdigest() != SOURCE_HASH:
        raise ValueError('固定探针源码不匹配')
    return actual


def write(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(redact(value), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def check_observation(phase):
    observation = json.loads((OUTPUT / (phase + '_preflight.json')).read_text(encoding='utf-8'))
    age = time.time() - observation['observed_unix']
    expected_channel = 0 if phase == 'simple' else 1
    if not 0 <= age <= 60 or not all(observation.get(k) is True for k in
            ('fixture_confirmed', 'marker_absent', 'piano_roll_channel_a_visible', 'no_other_calls')):
        raise ValueError('界面证据缺失或过期')
    if observation.get('selected_channel') != expected_channel or observation.get('pattern_number') != 1:
        raise ValueError('实验目标不匹配')
    if not (OUTPUT / observation['screenshot']).is_file():
        raise ValueError('界面截图缺失')
    if phase == 'mismatch':
        simple = json.loads((OUTPUT / 'simple_target.json').read_text(encoding='utf-8'))
        undo = json.loads((OUTPUT / 'undo.json').read_text(encoding='utf-8'))
        if simple.get('status') != 'MATCHED_SIMPLE_TARGET' or undo.get('baseline_restored') is not True:
            raise ValueError('第一次写入及撤销未确认')
    return observation


def reserve(phase, request):
    if phase == 'mismatch' and not (OUTPUT / 'simple_request.json').exists():
        raise ValueError('第一实验未执行')
    # 意图在派发前独占写入，崩溃、超时及换进程都不能重新消费同一次预算。
    with (OUTPUT / (phase + '_request.json')).open('x', encoding='utf-8') as stream:
        json.dump(redact(request), stream, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('discover', 'simple', 'mismatch'), default='discover')
    args = parser.parse_args()
    if args.phase != 'discover':
        if (OUTPUT / (args.phase + '_request.json')).exists():
            raise ValueError('本实验已有持久派发意图；禁止重复调用')
        summary = OUTPUT / 'summary.json'
        if summary.exists() and json.loads(summary.read_text(encoding='utf-8')).get('experiment_closed') is True:
            raise ValueError('本轮实验已结束；禁止继续写入')
    source = prepare_source()
    fixture = Path(os.environ['TEMP']) / 'DAWLoop_RuntimeV2_PianoRollProbe.flp'
    if hashlib.sha256(fixture.read_bytes()).hexdigest() != FIXTURE_HASH:
        raise ValueError('一次性测试文件摘要变化')
    transport = CDPTransport(timeout=35)
    report = {'phase': args.phase, 'timestamp': datetime.now(timezone.utc).isoformat(),
              'fixed_probe_hash': SOURCE_HASH, 'execution_status': 'NOT_DISPATCHED',
              'production_write_ready': False}
    try:
        session = transport.connect()
        catalog = transport.invoke('catalog')
        payload = catalog['payload']
        decoded = json.loads(payload) if isinstance(payload, str) else payload
        tools = decoded if isinstance(decoded, list) else decoded['tools']
        digest = catalog_hash(tools)
        tool = next(t for t in tools if t['name'] == 'run_piano_roll_script')
        reference = known_catalog()['tools']['run_piano_roll_script']
        if digest != CATALOG_HASH or tool.get('inputSchema') != reference['input_schema'] or tool.get('description') != reference['description']:
            raise ValueError('现场工具合同变化')
        report.update(host='CONNECTED', catalog_hash=digest, tool_count=len(tools), session=session)
        write('catalog.json', {'raw_callback': catalog, 'tools': tools, 'catalog_hash': digest})
        blocked = transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke("call","run_piano_roll_script",{},35000)')
        if blocked != {'ok': False, 'code': 'READ_ONLY_BACKEND'}:
            raise ValueError('通用脚本拒绝未确认')
        write('general_dispatch_guard.json', blocked)
        if args.phase == 'discover':
            return
        observation = check_observation(args.phase)
        identity = asyncio.run(ControllerIdentityBackend('FLSkill MCP IN 2').read_identity())
        selected = 0 if args.phase == 'simple' else 1
        if (identity.get('pattern_number') != 1
                or identity.get('channel_index') != selected or identity.get('selected_channels') != [selected]
                or identity.get('channel_index_type') != 'global' or identity.get('ppq') != 96
                or identity.get('channel_name') != ('808 Kick' if selected == 0 else '808 Clap')
                or identity.get('pattern_name') != '样式 1'
                or identity.get('project_loading') is not False):
            raise ValueError('现场身份不匹配')
        filtered = {k: identity.get(k) for k in ('controller_session', 'project_generation', 'pattern_number',
                   'pattern_name', 'channel_index', 'channel_name', 'selected_channels', 'ppq', 'observed_at', 'fl_studio_version')}
        ordinal = 1 if args.phase == 'simple' else 2
        request = {'raw_tool_request': {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                  'params': {'name': 'run_piano_roll_script', 'arguments': {'source': source.decode('utf-8')}}},
                  'fixed_probe_hash': SOURCE_HASH, 'ordinal': ordinal, 'identity': filtered,
                  'ui_observation': observation, 'session': session, 'dispatch_monotonic_ns': time.monotonic_ns()}
        reserve(args.phase, request)
        report['execution_status'] = 'UNKNOWN'
        started = time.monotonic_ns()
        raw = transport._evaluate('window.__dawloopReadonlyBridgeV1.invokeFixedTargetProbe(%s,%s,%s,%s,35000)' % (
            json.dumps(PROBE_ID), json.dumps(SOURCE_HASH), json.dumps(source.decode('utf-8')), ordinal))
        report.update(raw_bridge_response=raw, total_ms=(time.monotonic_ns()-started)/1_000_000)
        if isinstance(raw, dict) and raw.get('ok'):
            report['callback_received'] = True
            report['acknowledged'] = transport._evaluate('window.__dawloopReadonlyBridgeV1.acknowledge(%s)' % json.dumps(transport.epoch)) is True
            report['execution_status'] = 'HOST_CALLBACK_ONLY'
        elif isinstance(raw, dict) and not raw.get('dispatched'):
            report['execution_status'] = 'NOT_DISPATCHED'
    except Exception as error:
        report['error_code'] = getattr(error, 'code', str(error))
    finally:
        transport.close()
        report['callbacks_restored'] = transport.callbacks_restored
        write(args.phase + '_host_result.json', report)
        print(json.dumps(redact(report), ensure_ascii=False))


if __name__ == '__main__':
    main()
