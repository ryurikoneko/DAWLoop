"""只验证固定输出探针；失败停止，不派发后续取样脚本。"""

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

from _runtime_v2_file_route import require_open_file_snapshot_route

from dawloop.runtime.snapshot import install_snapshot_exporter
from dawloop.runtime.snapshot_output import OUTPUT_PROBE, OUTPUT_PROBE_SHA256, OutputProbeClient
from dawloop.setup import default_settings_dir


async def main():
    require_open_file_snapshot_route()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    if hashlib.sha256(OUTPUT_PROBE.read_bytes()).hexdigest() != OUTPUT_PROBE_SHA256:
        raise ValueError('固定源码摘要不符')
    if args.install:
        print(json.dumps(install_snapshot_exporter(default_settings_dir(), exporter=OUTPUT_PROBE)))
        return
    output = Path(__file__).resolve().parents[1] / 'evidence/runtime_v2/output_only'
    if (output / 'transport_probe.json').exists():
        raise FileExistsError('已有现场记录，拒绝覆盖')
    print(json.dumps({'status': 'READY', 'script_name': OUTPUT_PROBE.name, 'source_hash': OUTPUT_PROBE_SHA256}), flush=True)
    idle = json.loads(sys.stdin.readline())
    async def trigger():
        print(json.dumps({'status': 'TRIGGER_REQUIRED', 'source_hash': OUTPUT_PROBE_SHA256}), flush=True)
        return json.loads(await asyncio.to_thread(sys.stdin.readline))
    client = OutputProbeClient(timeout=5)
    result = await client.run(installed_probe=default_settings_dir() / 'Piano roll scripts' / OUTPUT_PROBE.name,
                              confirm_idle=lambda: idle.get('no_pending_invocation') is True, trigger=trigger)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'transport_probe.json').write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': 'RESULT', **asdict(result)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
