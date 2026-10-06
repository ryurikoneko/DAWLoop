from __future__ import annotations

import asyncio
import json

from .benchmark import simulated_benchmark


def add_runtime_commands(subparsers):
    probe = subparsers.add_parser("native-probe", help="仅调用原生宿主的已知只读工具")
    probe.add_argument("--endpoint", default="http://127.0.0.1:9222")
    probe.add_argument("--timeout", type=float, default=35.0)
    probe.add_argument("--repeats", type=int, default=3)
    probe.add_argument("--plugin-target", help="明确的通道或混音轨可视索引")
    probe.add_argument("--slot-number", type=int, default=-1)
    probe.add_argument("--param-identifier")
    benchmark = subparsers.add_parser("benchmark", help="运行离线模拟基准，不写入宿主")
    benchmark.add_argument("--notes", type=int, choices=(32, 64, 128), default=64)
    benchmark.add_argument("--repeats", type=int, default=5)


def run_runtime_command(args):
    if args.command not in {"native-probe", "benchmark"}:
        return None
    try:
        if args.command == "benchmark":
            report = asyncio.run(simulated_benchmark(args.notes, args.repeats))
            code = 0
        else:
            from dawloop.adapters.gopher_native.probe import native_probe
            report = asyncio.run(native_probe(
                args.endpoint, args.timeout, args.repeats, args.plugin_target,
                args.slot_number, args.param_identifier,
            ))
            code = 0 if report["status"] == "READ_ONLY_TESTED" else 2
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return code
    except (ValueError, TypeError):
        print(json.dumps({"status": "STOPPED", "error_code": "INVALID_ARGUMENTS"}))
        return 2
