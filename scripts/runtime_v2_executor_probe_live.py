"""执行器合同对照；默认仅发现，明确开关才派发一次规范固定探针。"""

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
from dawloop.adapters.gopher_native.response import decode_script_acceptance
from dawloop.adapters.gopher_native.transport import CDPTransport
from runtime_v2_fixed_probe_live import redact

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/executor_contract'
SOURCE_HASH = 'bbf82b82bc172858d09ac9a3fd95818e3069d30a10ce152c1db1591ba6753570'
CATALOG_HASH = '514d035244b0aea4d94fbb5ce8cad79415878e76dca6c85d94e1ebf692f4234e'


def write(name, data):
    (OUTPUT / name).write_text(json.dumps(redact(data), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def check_gate():
    if (OUTPUT / 'gopher_intent.json').exists() or (OUTPUT / 'summary.json').exists():
        raise ValueError('本轮已派发或结束，禁止重复调用')
    source = (ROOT / 'research/piano_roll_probe/executor_canonical_v1.pyscript').read_bytes()
    standard = json.loads((OUTPUT / 'standard_runner.json').read_text(encoding='utf-8'))
    if (hashlib.sha256(source).hexdigest() != SOURCE_HASH or source != (OUTPUT / 'canonical_probe.py').read_bytes()
            or standard.get('source_hash') != SOURCE_HASH or standard.get('canonical_script_valid') is not True
            or standard.get('undo') is not True or standard.get('marker_after_undo') is not False):
        raise ValueError('标准运行器合同或同字节门槛不通过')
    observation = json.loads((OUTPUT / 'gopher_preflight.json').read_text(encoding='utf-8'))
    if not 0 <= time.time()-observation['observed_unix'] <= 60 or not all(observation.get(k) is True for k in
            ('fixture_confirmed', 'marker_absent', 'piano_roll_channel_a_visible', 'no_other_calls')):
        raise ValueError('原生对照界面证据缺失或过期')
    if not (OUTPUT / observation['screenshot']).is_file():
        raise ValueError('原生对照界面截图缺失')
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dispatch-fixed', action='store_true')
    args = parser.parse_args()
    source = check_gate() if args.dispatch_fixed else None
    fixture = Path(os.environ['TEMP']) / 'DAWLoop_RuntimeV2_PianoRollProbe.flp'
    if hashlib.sha256(fixture.read_bytes()).hexdigest() != 'a2f9922d6b8cdc7f7627428d0d7072ed7dcab0a4f666fef42145c0c6e91b006f':
        raise ValueError('测试工程摘要变化')
    transport = CDPTransport(timeout=35)
    report = dict(timestamp=datetime.now(timezone.utc).isoformat(), source_hash=SOURCE_HASH,
                  execution_status='NOT_DISPATCHED', script_application_status='NOT_CHECKED')
    try:
        session = transport.connect()
        raw = transport.invoke('catalog')
        payload = raw['payload']
        catalog = json.loads(payload) if isinstance(payload, str) else payload
        tools = catalog if isinstance(catalog, list) else catalog['tools']
        tool = next(t for t in tools if t['name']=='run_piano_roll_script')
        reference = known_catalog()['tools']['run_piano_roll_script']
        if catalog_hash(tools) != CATALOG_HASH or tool.get('description') != reference['description'] or tool.get('inputSchema') != reference['input_schema']:
            raise ValueError('现场工具合同变化')
        write('catalog.json', dict(raw_callback=raw, tools=tools, catalog_hash=CATALOG_HASH))
        report.update(host='CONNECTED', tool_count=len(tools), catalog_hash=CATALOG_HASH, session=session)
        if not args.dispatch_fixed:
            return
        blocked = transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke("call","run_piano_roll_script",{},35000)')
        if blocked != {'ok': False, 'code': 'READ_ONLY_BACKEND'}:
            raise ValueError('通用脚本拒绝未确认')
        report['general_script_guard'] = blocked
        identity = asyncio.run(ControllerIdentityBackend('FLSkill MCP IN 2').read_identity())
        if (identity.get('pattern_number') != 1 or identity.get('pattern_name') != '样式 1'
                or identity.get('channel_index') != 0 or identity.get('channel_name') != '808 Kick'
                or identity.get('selected_channels') != [0] or identity.get('ppq') != 96
                or identity.get('project_loading') is not False):
            raise ValueError('现场身份不匹配')
        request = dict(raw_tool_request={'jsonrpc':'2.0', 'id':1, 'method':'tools/call',
                       'params':{'name':'run_piano_roll_script', 'arguments':{'source':source.decode('utf-8')}}},
                       source_hash=SOURCE_HASH, session=session,
                       identity={k:identity.get(k) for k in ('pattern_number','pattern_name','channel_index','channel_name','ppq','observed_at')})
        with (OUTPUT / 'gopher_intent.json').open('x', encoding='utf-8') as stream:
            json.dump(redact(request), stream, ensure_ascii=False, indent=2)
        report.update(execution_status='UNKNOWN', script_application_status='UNKNOWN')
        started = time.monotonic_ns()
        response = transport._evaluate('window.__dawloopReadonlyBridgeV1.invokeFixedExecutorProbe(%s,%s,%s,35000)' % (
            json.dumps('executor_canonical_v1'),json.dumps(SOURCE_HASH),json.dumps(source.decode('utf-8'))))
        report.update(raw_bridge_response=response, total_ms=(time.monotonic_ns()-started)/1_000_000)
        decoded = decode_script_acceptance(response)
        report.update(execution_status=decoded.status.value, script_application_status=decoded.script_application_status.value,
                      response_status=decoded.response_status.value, error_code=decoded.error_code)
        if isinstance(response, dict) and response.get('ok'):
            report['acknowledged'] = transport._evaluate('window.__dawloopReadonlyBridgeV1.acknowledge(%s)' % json.dumps(transport.epoch)) is True
    except Exception as error:
        report['error_code'] = getattr(error,'code',str(error))
    finally:
        transport.close()
        report['callbacks_restored'] = transport.callbacks_restored
        write('gopher_host_result.json' if args.dispatch_fixed else 'discovery.json', report)
        print(json.dumps(redact(report), ensure_ascii=False))


if __name__ == '__main__':
    main()
