"""通过现有控制器只读请求记录人工或电脑操控选择后的身份。"""

import asyncio
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend, controller_snapshot
from dawloop.runtime.identity import compare_target_identity


async def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    backend = ControllerIdentityBackend('FLSkill MCP IN 2', settings_dir=Path(sys.argv[2]) if len(sys.argv)>2 else None)
    rows = []
    expected_guard = None
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin:
        command = json.loads(line)
        if command['action'] == 'annotate':
            row = next(row for row in rows if row['sequence'] == command['sequence'])
            row['switch_input_to_identity_ms'] = command['elapsed_ms']
            row['switch_latency_scope'] = '电脑操控输入开始至刷新截图并收到身份；包含界面观测开销'
        else:
            started = time.perf_counter()
            row = {'sequence': command['sequence'], 'expected_pattern': command['pattern'],
                   'expected_channel': command.get('channel', 0), 'error': None,
                   'pattern_switch_to_identity_ms': None, 'switch_input_to_identity_ms': None}
            try:
                target = await backend.read_identity()
                snapshot, status = controller_snapshot(target)
                snapshot = replace(snapshot, project_title=None)
                row.update(identity_snapshot_ms=(time.perf_counter()-started)*1000,
                           actual_pattern=target['pattern_number'], actual_name=target['pattern_name'],
                           actual_channel=target['channel_index'], actual_channel_name=target['channel_name'],
                           ppq=target['ppq'], timestamp=target['observed_at'], snapshot=asdict(snapshot))
                row['mismatch'] = target['pattern_number'] != command['pattern'] or target['channel_index'] != command.get('channel', 0)
                name_map = {1: '样式 1', 2: '样式 2'}
                row['wrong_name_mapping'] = target['pattern_name'] != name_map.get(command['pattern'])
                age = (datetime.now(timezone.utc)-snapshot.pattern_index.observed_at).total_seconds()
                row['stale'] = not 0 <= age <= .25
                if command.get('capture_guard'):
                    expected_guard = snapshot
                if command.get('check_guard'):
                    try:
                        compare_target_identity(expected_guard, snapshot, status, now=datetime.now(timezone.utc))
                        row['identity_condition_guard'] = 'ALLOW'
                    except (ValueError, TypeError) as error:
                        row['identity_condition_guard'] = 'BLOCK'
                        row['guard_reason'] = str(error)
                    row['expected_guard'] = command['expected_guard']
                row['native_write_token_issued'] = False
            except Exception as error:
                code = str(error)
                if not code or not all(c.isupper() or c == '_' for c in code):
                    code = type(error).__name__
                row.update(error=code, identity_snapshot_ms=(time.perf_counter()-started)*1000,
                           mismatch=None, stale=None, wrong_name_mapping=None)
            rows.append(row)
        (output/'live_identity_rows.json').write_text(json.dumps({'rows': rows}, ensure_ascii=False, indent=2, default=lambda value: value.isoformat())+'\n', encoding='utf-8')
        print(json.dumps({'sequence': command['sequence'], 'result': rows[-1] if command['action'] != 'annotate' else 'annotated'}, ensure_ascii=False, default=lambda value: value.isoformat()), flush=True)


asyncio.run(main())
