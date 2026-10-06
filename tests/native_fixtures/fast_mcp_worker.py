"""真实stdio子进程测试：只替换宿主与观察输入，绝不连接FL。"""

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from test_fast_mcp import ReportInteraction
from test_fast_music import Host, inputs
from test_native_write_runtime import Target
from dawloop.adapters.gopher_native.write_backend import (
    CERTIFIED_CATALOG, CERTIFIED_VERSION, GopherNativeWriteBackend)
from dawloop.fast_mcp_server import create_server
from dawloop.runtime.fast_music import FastMusicRuntime
from dawloop.runtime.native_write import NativeWriteJournal
from dawloop.runtime.run_manager import RunManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings-dir', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()

    async def readiness():
        return dict(observed_at=time.time(), disposable_session=True,
            controller=dict(connected=True, build_id='offline-build',
                session_generation='offline-controller', project_generation='offline-project'),
            gopher=dict(discovered=True, bridge_connected=True, host_generation='generation',
                bridge_epoch='epoch', target_id='target', catalog_hash=CERTIFIED_CATALOG,
                fl_version=CERTIFIED_VERSION, bootstrap_required=False, poisoned=False),
            observation=dict(ready=True, request_generation='offline-observer'))

    def factory(context, store):
        return FastMusicRuntime(GopherNativeWriteBackend(enabled=True, transport=Host(),
            target_preparer=Target(), interaction=ReportInteraction(store),
            journal=NativeWriteJournal(context.ledger_directory), disposable_guard=lambda: True))

    manager = RunManager(args.data_dir, settings_dir=args.settings_dir, expected_build='offline-build',
        runtime_factory=factory, readiness=readiness, experimental_authorized=True, allowed_target=inputs()[0])
    create_server(manager).run(transport='stdio')


if __name__ == '__main__':
    main()
