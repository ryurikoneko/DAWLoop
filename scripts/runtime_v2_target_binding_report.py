"""汇总现场身份样本与被动缓存检查，不触发宿主脚本。"""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/runtime_v2/target_binding'


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def stats(values):
    values = sorted(values)
    return {'count': len(values), 'median_ms': statistics.median(values) if values else None,
            'p95_ms': values[math.ceil(.95 * len(values))-1] if values else None,
            'max_ms': max(values) if values else None, 'method': 'p95采用最近秩'}


rows = json.loads((OUT / 'live_identity_rows.json').read_text(encoding='utf-8'))['rows']
switch = [r for r in rows if 5 <= r['sequence'] <= 24]
assert len(switch) == 20
assert all(not r['error'] and not r['mismatch'] and not r['stale'] and not r['wrong_name_mapping'] for r in rows)
matrix = []
for label, sample in [('A_X', [r for r in switch if r['expected_pattern'] == 1]),
                      ('B_X', [r for r in switch if r['expected_pattern'] == 2]),
                      ('A_Y', [r for r in rows if 26 <= r['sequence'] <= 35]),
                      ('A_X_RESTORED', [r for r in rows if 36 <= r['sequence'] <= 45])]:
    assert len(sample) == 10
    assert all(r['identity_condition_guard'] == r['expected_guard'] for r in sample)
    matrix.append({'case': label, 'count': len(sample), 'expected': sample[0]['expected_guard'],
                   'mismatches': 0, 'sequences': [r['sequence'] for r in sample]})

write('pattern_switch.json', {'status': 'LIVE_CERTIFIED', 'scope': '两个测试片段，界面刷新后采样；不认证切换瞬态或其他工程',
      'initial_sequence': [1, 2, 3, 4], 'alternating_count': 20, 'mismatches': 0,
      'stale_at_sample': 0, 'wrong_name_mapping': 0, 'transient_stale_window_ms': None,
      'pattern_switch_to_identity_ms': None,
      'switch_input_to_identity_ms': stats([r['switch_input_to_identity_ms'] for r in switch]),
      'measurement_scope': '操控输入开始至刷新截图并收到身份，包含界面观测开销', 'samples': switch})
write('guard_matrix.json', {'status': 'PASS', 'scope': '现有守卫共用的身份条件比较，每个条件10次读取；非10个完整切换周期',
      'cases': matrix, 'native_write_token_issued': False, 'full_composite_token_live_retested': False})

# 直接构造缓存候选路径，避免上游路径辅助函数的创建目录副作用。
candidates = [('UPSTREAM_DEFAULT', Path.home() / 'Documents/Image-Line/FL Studio/Settings/Piano roll scripts/piano_roll_state.json'),
              ('CONFIGURED_SETTINGS', Path(sys.argv[1]) / 'Piano roll scripts/piano_roll_state.json')]
cache = []
for label, path in candidates:
    item = {'candidate': label, 'exists': path.is_file(), 'freshness': 'UNKNOWN',
            'target_bound': False, 'community_parse_ms': None}
    if path.is_file():
        started = time.perf_counter()
        raw = path.read_bytes()
        try:
            data = json.loads(raw.decode('utf-8'))
            item.update(payload_sha256=hashlib.sha256(raw).hexdigest(),
                        known_fields={key: key in data for key in ('ppq', 'noteCount', 'notes', 'pattern_index', 'channel_index', 'request_id', 'generation', 'export_timestamp')},
                        note_count=data.get('noteCount'), ppq=data.get('ppq'))
        except (ValueError, UnicodeError):
            item['parse_status'] = 'INVALID'
        item['community_parse_ms'] = (time.perf_counter()-started)*1000
    cache.append(item)
write('community_freshness.json', {'status': 'COMMUNITY_READBACK_NOT_TARGET_SAFE', 'freshness': 'UNKNOWN',
      'target_bound': False, 'cache_inspection': cache, 'latency_scope': 'CACHE_PARSE_ONLY；不代表现场刷新',
      'community_refresh_ms': None, 'target_bound_read_ms': None,
      'audit': {'getter': 'fl_get_piano_roll_state → _read_state → 最后导出文件',
                'refresh': 'fl_trigger_script → 快捷键 → ComposeWithLLM.apply',
                'refresh_processes_pending_writes_first': True,
                'export_fields': ['ppq', 'noteCount', 'notes'],
                'adapter_refresh_check': '文件mtime增加，不含请求代次或生产方实际目标',
                'unsafe_refresh_dispatched': False},
      'fresh_ab_note_count_test': 'NOT_TESTED_LIVE', 'reason': '刷新链先处理未知待执行写队列；禁止触发或清空队列'})
write('target_binding.json', {'status': 'UNPROVEN', 'target_bound': False,
      'required_proof': ['请求与生产方导出代次一致', '可信同一单调时钟下导出取样开始不早于请求',
                         '首尾身份与预期一致', '生产方证明实际读取对象身份'],
      'community_producer_proof_available': False,
      'piano_roll_target': 'UNAVAILABLE', 'selected_channel_is_piano_roll_target': False,
      'native_read_only_script': {'static_template': 'PASS', 'mock_structure': 'PASS',
          'live_tested': False, 'structured_return': 'UNPROVEN', 'score_binding': 'UNPROVEN',
          'safety_model': '固定表达式AST精确匹配；不是通用沙箱；未接入宿主执行器'}})
write('race_test.json', {'offline': 'PASS', 'cases': ['片段改变', '通道改变', '首尾一致但生产方读取另一片段',
      '导出代次错误', '取样开始早于请求', '生产方目标未证明'],
      'live_fresh_read_race': 'NOT_TESTED_LIVE', 'reason': '没有已证实安全的新鲜宿主音符读取入口',
      'live_identity_guard_change': 'PASS', 'live_readback_race_rejection': None})
write('summary.json', {'timestamp': datetime.now(timezone.utc).isoformat(),
      'fl_version': rows[0]['snapshot']['fl_version']['value'], 'identity_samples': len(rows),
      'pattern_identity': 'LIVE_CERTIFIED', 'identity_certification_scope': '测试片段1、2及采样时刻',
      'identity_snapshot_ms': stats([r['identity_snapshot_ms'] for r in rows]),
      'pattern_channel_identity_guard': 'PASS', 'community_readback': 'COMMUNITY_READBACK_NOT_TARGET_SAFE',
      'native_note_readback': 'NATIVE_NOTE_READBACK_UNPROVEN', 'write_readiness': 'NOT_READY',
      'tests': {'passed': 159, 'failed': 0},
      'fixture_preparation': {'authorization': '用户明确授权代为准备测试材料', 'existing_pattern_used': 1,
          'patterns_created_via_ui': 1, 'notes_inserted_via_ui': 8, 'visual_note_counts': {'A': 3, 'B': 5},
          'note_count_evidence': '界面观察；不冒充音符API读回', 'native_write_calls': 0, 'project_save_calls': 0},
      'environment': {'startup': '普通启动', 'debug_restart_performed': False,
          'final_target': 'A_X', 'test_session_left_open_unsaved': True},
      'bootstrap': {'formal_sample_errors': 0, 'collector_startup_errors_occurred': True,
          'errors': ['采集脚本语法', '显式设置目录缺失', '日期序列化'], 'host_safety_claim': '不计为正式身份样本'}})
print(json.dumps({'samples': len(rows), 'identity_ms': stats([r['identity_snapshot_ms'] for r in rows]),
                  'switch_ms': stats([r['switch_input_to_identity_ms'] for r in switch]), 'cache': cache}, ensure_ascii=False))
