"""只审计固定计数探针及现有连接，不执行宿主钢琴卷帘脚本。"""

import ast
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from dawloop.adapters.gopher_native.probe import native_probe


ROOT = Path(__file__).resolve().parents[1]
PROBE_ID = 'piano_roll_count_return_v1'
SOURCE_HASH = '7a549a8b2ebb2bb309b7065986e987c5a4dd734f303c3a7750d15af150798fba'
EXPECTED_SOURCE = (b'import flpianoroll as flp\n\n\ndef apply(form):\n'
                   b"    return {'ppq': flp.score.PPQ, 'note_count': flp.score.noteCount}\n")


def audit_fixed_source(probe_id, source):
    if probe_id != PROBE_ID or type(source) is not bytes or source != EXPECTED_SOURCE:
        raise ValueError('FIXED_PROBE_MISMATCH')
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError('FIXED_PROBE_HASH_MISMATCH')
    tree = ast.parse(source.decode('utf-8'))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    if len(imports) != 1 or not isinstance(imports[0], ast.Import):
        raise ValueError('PROBE_IMPORT_INVALID')
    if [(item.name, item.asname) for item in imports[0].names] != [('flpianoroll', 'flp')]:
        raise ValueError('PROBE_IMPORT_INVALID')
    if any(isinstance(node, (ast.Call, ast.Assign, ast.AugAssign, ast.AnnAssign)) for node in ast.walk(tree)):
        raise ValueError('PROBE_MUTATION_SURFACE')
    return {'probe_id': PROBE_ID, 'source_hash': SOURCE_HASH, 'source_safety': 'PASS_STATIC_ONLY',
            'reads': ['flp.score.PPQ', 'flp.score.noteCount'], 'host_behavior': 'UNPROVEN',
            'return_channel': 'UNPROVEN', 'host_dispatch_enabled': False}


def prepare_count_probe():
    source = (ROOT / 'research/piano_roll_probe/count_return_v1.pyscript').read_bytes()
    return source, audit_fixed_source(PROBE_ID, source)


async def main():
    source, audit = prepare_count_probe()
    connection = await native_probe('http://127.0.0.1:9222', timeout=5, repeats=1)
    output = ROOT / 'evidence/runtime_v2/piano_roll_probe'
    output.mkdir(parents=True, exist_ok=True)
    def write(name, data):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write('probe_source.json', dict(audit, source_utf8=source.decode('utf-8')))
    (output / 'probe_source.sha256').write_text(SOURCE_HASH + '\n', encoding='utf-8')
    write('probe_raw_response.json', {'status': 'NOT_DISPATCHED', 'raw_host_response': None,
                                    'native_preflight': connection})
    write('runner_contract.json', {'tool_risk': 'DESTRUCTIVE', 'general_dispatch': 'BLOCKED',
        'research_dispatch_implemented': False, 'live_runner': 'UNPROVEN',
        'input_schema': '历史目录仅提供source；本轮尚无新现场目录',
        'installed_reference': {'top_level_script': 'DOCUMENTED', 'preview_entry_points': ['createDialog', 'apply'],
                                'python_return_to_mcp': 'UNPROVEN'},
        'bridge': '现有桥接仅允许五项读取；没有加入脚本例外',
        'return_channel': 'RETURN_CHANNEL_UNPROVEN'})
    write('freshness_ab.json', {'status': 'NOT_RUN_GATE_1_UNPROVEN', 'freshness': 'UNKNOWN',
        'pattern_a_count': None, 'pattern_b_count': None, 'captured_at': None,
        'fixture_revalidated': False, 'historical_fixture_counts': {'A': 3, 'B': 5}})
    write('channel_negative.json', {'status': 'NOT_RUN_GATE_1_UNPROVEN', 'target_semantics': 'UNKNOWN',
                                   'target_bound': False, 'producer_target': None})
    write('race_timeline.json', {'status': 'NOT_TESTED_LIVE', 'dispatch_start': None,
        'target_change_observed': None, 'producer_result': None, 'producer_sampling_started': None,
        'producer_sampling_completed': None,
        'interpretation': '客户端派发至收到响应的重叠，不足以证明宿主取样期间发生切换'})
    write('summary.json', {'timestamp': datetime.now(timezone.utc).isoformat(),
        'gate_1': 'UNPROVEN', 'gate_2': 'NOT_RUN', 'gate_3': 'NOT_RUN', 'source_safety': 'PASS_STATIC_ONLY',
        'host_behavior': 'UNPROVEN', 'return_channel': 'RETURN_CHANNEL_UNPROVEN',
        'native_connection': connection.get('error_code', connection['status']),
        'piano_roll_script_calls': 0, 'host_note_writes': 0, 'project_save_calls': 0,
        'host_closed_or_restarted': False, 'target_bound': False, 'write_readiness': 'NOT_READY',
        'next_step': '在保留当前未保存测试材料的前提下建立临时调试会话；当前禁止擅自保存或关闭'})
    print(json.dumps({'source_audit': audit, 'connection': connection['status'],
                      'error_code': connection.get('error_code'), 'script_dispatched': False}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
