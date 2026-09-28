from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import platform
import math
import sys
import wave


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
            connection_status = "PASS" if connected else "STOP"
            connection_detail = detail
        except Exception as error:
            connection_status, connection_detail = "STOP", str(error)
    else:
        connection_status, connection_detail = "NOT_CHECKED", "需显式使用 --probe-fl 并启动 FL Studio 和 MCP 控制脚本"

    for name, passed, detail in checks:
        print(f"{name:<24} {'PASS' if passed else 'STOP':<6} {detail}")
    print(f"{'FL Studio communication':<24} {connection_status:<18} {connection_detail}")

    from flskill.production.environment import EnvironmentStatus, inspect_environment
    profile = inspect_environment()
    profile_checks = {check.name: check for check in profile.checks}
    production_rows = [
        ("numpy", profile_checks["numpy"].status, 'pip install "flskill[production]"'),
        ("Production SMF analysis", EnvironmentStatus.AVAILABLE, "stdlib-only; no numpy required"),
        ("Production audio analysis", profile_checks["numpy"].status, 'pip install "flskill[production]"'),
        ("Production Windows loopback", profile_checks["WASAPI"].status, 'pip install "flskill[production-loopback]"'),
        ("spectrum-peak", profile_checks["spectrum-peak"].status, "environment-specific optional dependency"),
        ("MuseScore", profile_checks["MuseScore"].status, "not required by current Production Pipeline APIs"),
        ("FluidSynth", profile_checks["FluidSynth"].status, "not required by current Production Pipeline APIs"),
    ]
    print("\nProduction Pipeline optional environment checks")
    for name, status, detail in production_rows:
        print(f"{name:<24} {status.value:<18} {detail}")
    print(f"{'Production environment profile':<32} {profile.portable_status:<18} OS={profile.os_name}; Python={profile.python_version}")
    return 0 if all(passed for _, passed, _ in checks) else 1


def _midi_inspect(path: str, beats_per_bar: int, window_bars: int) -> int:
    from flskill.production.smf import parse_smf, recommend_dense_window

    try:
        summary = parse_smf(path)
    except (OSError, ValueError) as error:
        print(f"midi-inspect: {error}", file=sys.stderr)
        return 2
    rows = []
    for track in summary.tracks:
        window = recommend_dense_window(
            track,
            division=summary.division,
            beats_per_bar=beats_per_bar,
            window_bars=window_bars,
        )
        rows.append({
            "index": track.index,
            "name": track.name,
            "note_count": len(track.notes),
            "recommended_window_bars": list(window) if window else None,
        })
    print(json.dumps({
        "format": summary.format,
        "division": summary.division,
        "beats_per_bar": beats_per_bar,
        "tracks": rows,
    }, ensure_ascii=False, indent=2))
    return 0


def _measure_wav(paths: list[str], frame_ms: int, floor_dbfs: float) -> int:
    try:
        from flskill.production.mix import active_rms
    except ImportError as error:
        print(f"measure-wav: {error}", file=sys.stderr)
        return 2

    rows = []
    for path in paths:
        try:
            result = active_rms(path, frame_ms=frame_ms, floor_dbfs=floor_dbfs)
        except (EOFError, OSError, ValueError, wave.Error) as error:
            print(f"measure-wav: {path}: {error}", file=sys.stderr)
            return 2
        finite = lambda value: value if math.isfinite(value) else None
        rows.append({
            "path": path,
            "all_rms_dbfs": finite(result.all_rms_dbfs),
            "active_rms_dbfs": finite(result.active_rms_dbfs),
            "active_ratio": result.active_ratio,
            "peak_dbfs": finite(result.peak_dbfs),
            "max_frame_dbfs": finite(result.max_frame_dbfs),
        })
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


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

    midi_parser = subparsers.add_parser("midi-inspect", help="检查 MIDI 轨道和高密度小节窗口")
    midi_parser.add_argument("path")
    midi_parser.add_argument("--beats-per-bar", type=int, default=4)
    midi_parser.add_argument("--window-bars", type=int, default=3)

    level_parser = subparsers.add_parser("measure-wav", help="计算 WAV 的整段与活跃帧 RMS")
    level_parser.add_argument("paths", nargs="+")
    level_parser.add_argument("--frame-ms", type=int, default=100)
    level_parser.add_argument("--floor-dbfs", type=float, default=-65.0)

    args = parser.parse_args()

    if args.command == "doctor":
        return _doctor(args.probe_fl)
    if args.command == "install-fl-scripts":
        from pathlib import Path
        from flskill.setup import install_user_scripts
        for destination in install_user_scripts(Path(args.settings_dir)):
            print(f"已安装：{destination}")
        return 0
    if args.command == "midi-inspect":
        return _midi_inspect(args.path, args.beats_per_bar, args.window_bars)
    if args.command == "measure-wav":
        return _measure_wav(args.paths, args.frame_ms, args.floor_dbfs)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
