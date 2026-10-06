"""三个高层工具的 stdio 入口；现场依赖缺失时拒绝执行。"""

import argparse
from contextlib import asynccontextmanager
from pathlib import Path
import json
import sys

from dawloop.runtime.run_manager import RunManager


def create_server(manager, *, cleanup=None):
    from fastmcp import FastMCP

    @asynccontextmanager
    async def lifespan(server):
        try:
            yield {}
        finally:
            await manager.close()
            if cleanup is not None:
                await cleanup()

    mcp = FastMCP('DAWLoop FAST', lifespan=lifespan, strict_input_validation=True,
        instructions='只接结构化16音符测试计划。人工Accept与实际回执领取分开；'
        'COMPLETED_UNVERIFIED不表示Exact Set或producer目标已验证。未知写入不得重试。')

    @mcp.tool(annotations=dict(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
    async def fast_write_music(operation_id: str, target: dict, musical_plan: dict) -> dict:
        """校验并提交一次后台FAST事务；相同operation返回原run，返回不代表写入完成。"""
        return await manager.create(operation_id, target, musical_plan)

    @mcp.tool(annotations=dict(readOnlyHint=True))
    async def status(run_id: str | None = None) -> dict:
        """读取组合就绪状态或指定run进度、不可变结果与人工报告。"""
        return await manager.status(run_id)

    @mcp.tool(annotations=dict(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
    def submit_human_report(report: dict) -> dict:
        """转交真实用户回报；必须明确run/session/report身份，不执行Accept。"""
        return manager.submit_human_report(report)

    return mcp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-dir', type=Path, required=True)
    parser.add_argument('--expected-build', required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--live-config', type=Path)
    parser.add_argument('--repository', type=Path)
    args = parser.parse_args()
    # CLI不从未知目录或工厂自动获得写权限；现场接入由受审配置显式注入。
    cleanup = None
    if args.live_config is not None:
        if (args.repository is None or not args.repository.is_absolute()
                or not args.settings_dir.is_absolute()
                or not args.live_config.is_absolute()
                or not (args.repository / 'research' / 'fast_mcp_live.py').is_file()):
            raise ValueError('EXPLICIT_LIVE_REPOSITORY_AND_CONFIGURATION_REQUIRED')
        sys.path.insert(0, str(args.repository.resolve()))
        from research.fast_mcp_live import build_manager
        manager, wiring = build_manager(json.loads(args.live_config.read_text(encoding='utf-8')),
            directory=args.data_dir, settings_dir=args.settings_dir, expected_build=args.expected_build)
        cleanup = wiring.close
    else:
        manager = RunManager(args.data_dir, settings_dir=args.settings_dir, expected_build=args.expected_build)
    create_server(manager, cleanup=cleanup).run(transport='stdio')


if __name__ == '__main__':
    main()
