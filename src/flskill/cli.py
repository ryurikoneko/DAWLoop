from __future__ import annotations

import argparse
import asyncio
import importlib.util
import platform
import sys


def _doctor(probe_fl: bool) -> int:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python", sys.version_info >= (3, 11), platform.python_version()))

    try:
        import flskill
        checks.append(("FLSkill Core", True, "可导入"))
    except Exception as error:
        checks.append(("FLSkill Core", False, str(error)))

    vendor = importlib.util.find_spec("fl_studio_mcp")
    checks.append(("Bundled FL Studio MCP", vendor is not None, "已找到" if vendor else "未找到"))

    from flskill.setup import default_settings_dir, user_script_status
    scripts = user_script_status(default_settings_dir())
    missing_scripts = [name for name, installed in scripts.items() if not installed]
    checks.append((
        "FL Studio User Scripts",
        not missing_scripts,
        "已安装" if not missing_scripts else "缺少脚本；运行 install-fl-scripts 并指定 Settings 目录",
    ))

    for module in ("fastmcp", "mido", "rtmidi", "pynput"):
        installed = importlib.util.find_spec(module) is not None
        checks.append((module, installed, "已安装" if installed else "未安装；使用 flstudio extra 安装"))

    ports: list[str] = []
    if importlib.util.find_spec("mido") is not None:
        try:
            import mido
            ports = mido.get_output_names()
            checks.append(("MIDI 输出端口", bool(ports), ", ".join(ports) if ports else "未发现端口"))
        except Exception as error:
            checks.append(("MIDI 输出端口", False, str(error)))
    else:
        checks.append(("MIDI 输出端口", False, "mido 未安装"))

    if probe_fl and importlib.util.find_spec("fastmcp") is not None and vendor is not None:
        try:
            from flskill.adapters.fl_studio_mcp.adapter import probe_connection
            connected, detail = asyncio.run(probe_connection())
            checks.append(("FL Studio 通信", connected, detail))
        except Exception as error:
            checks.append(("FL Studio 通信", False, str(error)))
    else:
        checks.append(("FL Studio 通信", False, "未探测；需先启动 FL Studio 和 MCP 控制脚本"))

    for name, passed, detail in checks:
        print(f"{name:<24} {'PASS' if passed else 'STOP':<6} {detail}")
    return 0 if all(passed for _, passed, _ in checks) else 1


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(prog="flskill")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="检查 Python、依赖和 FL Studio 通信")
    doctor_parser.add_argument("--probe-fl", action="store_true", help="发送只读状态查询以探测 FL Studio 通信")
    install_parser = subparsers.add_parser("install-fl-scripts", help="安装上游所需的 FL Studio 脚本")
    install_parser.add_argument("--settings-dir", required=True, help="FL Studio Settings 目录，由用户明确指定")
    args = parser.parse_args()

    if args.command == "doctor":
        return _doctor(args.probe_fl)
    if args.command == "install-fl-scripts":
        from pathlib import Path
        from flskill.setup import install_user_scripts
        for destination in install_user_scripts(Path(args.settings_dir)):
            print(f"已安装：{destination}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
