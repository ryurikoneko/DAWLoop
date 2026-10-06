"""普通宿主现场采样；由电脑操控选择唯一导出器，不调用旧刷新快捷键。"""

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys

from _runtime_v2_file_route import require_open_file_snapshot_route

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.runtime.snapshot import FreshSnapshotClient, ReadSnapshotRequest, install_snapshot_exporter
from dawloop.setup import default_settings_dir


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/fresh_export'
IDENTITY_FIELDS = ('source', 'controller_session', 'project_generation', 'project_loading',
                   'pattern_number', 'pattern_name', 'channel_index', 'channel_name', 'channel_index_type',
                   'selected_channels', 'ppq', 'observed_at')


async def main():
    require_open_file_snapshot_route()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--replace-reviewed-hash')
    args = parser.parse_args()
    if args.install:
        print(json.dumps(install_snapshot_exporter(default_settings_dir(), reviewed_previous_hash=args.replace_reviewed_hash), ensure_ascii=False))
        return
    identity = ControllerIdentityBackend('FLSkill MCP IN 2')
    client = FreshSnapshotClient(timeout=5)
    rows = []
    print(json.dumps({'status': 'READY', 'trigger': 'EXACT_SCRIPT_MENU_ONLY'}), flush=True)

    async def read_identity():
        value = await identity.read_identity()
        return {key: value.get(key) for key in IDENTITY_FIELDS}

    for line in sys.stdin:
        command = json.loads(line)
        if command.get('action') == 'stop':
            break
        request = ReadSnapshotRequest(command['pattern'], command['pattern_name'], 0, '808 Kick')

        async def trigger():
            print(json.dumps({'status': 'TRIGGER_REQUIRED', 'request': asdict(request)}, ensure_ascii=False), flush=True)
            acknowledged = json.loads(await asyncio.to_thread(sys.stdin.readline))
            if acknowledged.get('action') != 'triggered':
                raise ValueError('TRIGGER_NOT_CONFIRMED')

        result = await client.request_piano_roll_snapshot(request, read_identity=read_identity, trigger=trigger)
        row = {'sequence': len(rows)+1, 'request': asdict(request), 'result': asdict(result)}
        rows.append(row)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / 'live_rows.json').write_text(json.dumps({'rows': rows}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'status': 'RESULT', **row}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
