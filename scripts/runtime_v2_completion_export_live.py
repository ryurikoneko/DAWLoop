"""分关验证普通文件导出，由电脑操控选择专用菜单入口。"""

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys

from _runtime_v2_file_route import require_open_file_snapshot_route

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.runtime.snapshot import ReadSnapshotRequest, install_snapshot_exporter
from dawloop.runtime.snapshot_transport import COMPLETION_EXPORTER, CompletionSnapshotClient, STAGES
from dawloop.setup import default_settings_dir


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/fresh_export_transport'
IDENTITY_FIELDS = ('source', 'controller_session', 'project_generation', 'project_loading',
                   'pattern_number', 'pattern_name', 'channel_index', 'channel_name', 'channel_index_type',
                   'selected_channels', 'ppq', 'observed_at')


async def main():
    require_open_file_snapshot_route()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    if args.install:
        print(json.dumps(install_snapshot_exporter(default_settings_dir(), exporter=COMPLETION_EXPORTER)))
        return
    if (OUTPUT / 'live_rows.json').exists():
        raise FileExistsError('已有现场记录，拒绝覆盖')
    identity = ControllerIdentityBackend('FLSkill MCP IN 2')
    client = CompletionSnapshotClient(timeout=5)
    rows = []
    gate = 0
    print(json.dumps({'status': 'READY', 'script_name': COMPLETION_EXPORTER.name}), flush=True)
    async def read_identity():
        value = await identity.read_identity()
        return {key: value.get(key) for key in IDENTITY_FIELDS}
    for line in sys.stdin:
        command = json.loads(line)
        if command.get('action') == 'stop':
            break
        stage = command['stage']
        if stage != STAGES[min(gate, 3)]:
            raise ValueError('前一关未通过，拒绝越级')
        request = ReadSnapshotRequest(command['pattern'], command['pattern_name'], 0, '808 Kick')
        async def trigger():
            print(json.dumps({'status': 'TRIGGER_REQUIRED', 'stage': stage, 'request': asdict(request)}, ensure_ascii=False), flush=True)
            acknowledged = json.loads(await asyncio.to_thread(sys.stdin.readline))
            if acknowledged.get('action') != 'triggered':
                raise ValueError('TRIGGER_NOT_CONFIRMED')
        result = await client.request_piano_roll_snapshot(request, read_identity=read_identity,
                                                          trigger=trigger, sampling_stage=stage)
        row = {'sequence': len(rows)+1, 'sampling_stage': stage, 'request': asdict(request), 'result': asdict(result)}
        rows.append(row)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / 'live_rows.json').write_text(json.dumps({'rows': rows}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'status': 'RESULT', **row}, ensure_ascii=False), flush=True)
        if result.freshness.value != 'FRESH':
            print(json.dumps({'status': 'STOP', 'reason': 'GATE_FAILED'}), flush=True)
            break
        gate += 1


if __name__ == '__main__':
    asyncio.run(main())
