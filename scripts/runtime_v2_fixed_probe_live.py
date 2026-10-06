"""门1专用现场研究；默认只发现，显式开关才派发字节锁定的计数探针。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from dawloop.adapters.gopher_native.catalog import catalog_hash, known_catalog
from dawloop.adapters.gopher_native.transport import CDPTransport
from runtime_v2_piano_roll_probe_audit import prepare_count_probe, PROBE_ID, SOURCE_HASH, ROOT


EXPECTED_CATALOG = '514d035244b0aea4d94fbb5ce8cad79415878e76dca6c85d94e1ebf692f4234e'
OUTPUT = ROOT / 'evidence/runtime_v2/piano_roll_probe/live_20261001'


def redact(value):
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\r\n"<>]*', '<本机路径已脱敏>', value)
        value = re.sub(r'https?://[^\s"<>]+',
                       lambda match: urlsplit(match.group())._replace(query='', fragment='').geturl(), value)
        username = os.environ.get('USERNAME', '')
        if username:
            value = re.sub(r'\b' + re.escape(username) + r'\b', '<用户已脱敏>', value, flags=re.IGNORECASE)
    return value


def write(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(redact(value), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dispatch-fixed', action='store_true')
    args = parser.parse_args()
    if args.dispatch_fixed and (OUTPUT / 'request.json').exists():
        raise RuntimeError('本轮已记录派发意图；禁止自动重复执行或覆盖证据')
    source, audit = prepare_count_probe()
    transport = CDPTransport(timeout=35)
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'probe_id': PROBE_ID,
              'fixed_probe_hash': SOURCE_HASH, 'gate_1': 'UNPROVEN', 'write_readiness': 'NOT_READY',
              'script_dispatch_attempts': 0}
    try:
        session = transport.connect()
        page = transport._evaluate("({url:location.origin+location.pathname, origin:location.origin, host_object_available:typeof script_handler==='object'||!!(window.chrome&&chrome.webview&&chrome.webview.hostObjects&&chrome.webview.hostObjects.script_handler)})")
        raw_catalog = transport.invoke('catalog')
        payload = raw_catalog['payload']
        decoded_catalog = json.loads(payload) if isinstance(payload, str) else payload
        tools = decoded_catalog if isinstance(decoded_catalog, list) else decoded_catalog['tools']
        digest = catalog_hash(tools)
        tool = next(item for item in tools if item['name'] == 'run_piano_roll_script')
        reference = known_catalog()['tools']['run_piano_roll_script']
        unchanged = (tool.get('inputSchema') == reference['input_schema']
                     and tool.get('description') == reference['description'])
        report.update(host='CONNECTED', catalog_hash=digest, tool_count=len(tools),
                      schema_confirmed=unchanged, catalog_confirmed=digest == EXPECTED_CATALOG,
                      source_confirmed=hashlib.sha256(source).hexdigest() == SOURCE_HASH)
        write('catalog.json', {'raw_catalog_callback': raw_catalog, 'tools': tools, 'catalog_hash': digest})
        write('environment.json', dict(page, frame=transport.frame_id, session=session,
                                      timestamp=report['timestamp'], temporary_debug_environment=True))
        write('preflight.json', dict(report, script_tool=tool, source_audit=audit))
        if not args.dispatch_fixed:
            return
        if not (unchanged and digest == EXPECTED_CATALOG and page['host_object_available']):
            raise ValueError('PREFLIGHT_CONTRACT_CHANGED')
        # 此调用只检验本地拒绝，不会把脚本送往宿主。
        rejected = transport._evaluate('window.__dawloopReadonlyBridgeV1.invoke(%s,%s,%s,35000)' % (
            json.dumps('call'), json.dumps('run_piano_roll_script'), json.dumps({'source': source.decode('utf-8')})))
        write('general_dispatch_guard.json', rejected)
        if rejected != {'ok': False, 'code': 'READ_ONLY_BACKEND'}:
            raise ValueError('GENERAL_SCRIPT_GUARD_NOT_CONFIRMED')
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'run_piano_roll_script', 'arguments': {'source': source.decode('utf-8')}}}
        metadata = {'request_generation': str(uuid4()), 'host_generation': transport.host_generation,
                    'bridge_epoch': transport.epoch, 'dispatch_monotonic_ns': time.monotonic_ns(),
                    'fixed_probe_hash': SOURCE_HASH,
                    'invocation_correspondence': 'UNPROVEN_HOST_HAS_NO_UNIQUE_REQUEST_ID'}
        write('request.json', {'raw_tool_request': request, 'bridge_request_metadata': metadata})
        report['script_dispatch_attempts'] = 1
        started = time.monotonic_ns()
        response = transport._evaluate('window.__dawloopReadonlyBridgeV1.invokeFixedCountProbe(%s,%s,%s,35000)' % (
            json.dumps(PROBE_ID), json.dumps(SOURCE_HASH), json.dumps(source.decode('utf-8'))))
        total_ms = (time.monotonic_ns() - started) / 1_000_000
        write('probe_raw_response.json', {'raw_bridge_response': response,
                                        'raw_host_callback': response.get('payload') if isinstance(response, dict) else None})
        write('latency.json', {'category': 'LIVE_NATIVE_RESEARCH_PROBE', 'total_ms': total_ms,
                              'queue_wait_ms': None, 'dispatch_ms': None, 'host_response_ms': None,
                              'decode_ms': None})
        if isinstance(response, dict) and response.get('ok'):
            acknowledged = transport._evaluate('window.__dawloopReadonlyBridgeV1.acknowledge(%s)' % json.dumps(transport.epoch))
            report['acknowledged'] = acknowledged is True
            raw = response.get('payload')
            try:
                mcp = json.loads(raw) if isinstance(raw, str) else raw
                write('mcp_result.json', {'raw_mcp_result': mcp})
                report['mcp_result'] = mcp
            except (ValueError, TypeError):
                report['decode_status'] = 'DECODE_ERROR'
        else:
            transport.poisoned_epoch = transport.epoch
            report['execution_status'] = 'UNKNOWN'
        report['total_ms'] = total_ms
    except Exception as error:
        report['error_code'] = getattr(error, 'code', type(error).__name__)
        report['gate_1'] = 'FAIL'
    finally:
        transport.close()
        report['callbacks_restored'] = transport.callbacks_restored
        write('summary.json' if args.dispatch_fixed else 'discovery_summary.json', report)
        print(json.dumps(redact(report), ensure_ascii=False))


if __name__ == '__main__':
    main()
