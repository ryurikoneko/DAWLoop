from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import math
import sys
import wave
from pathlib import Path


def _midi_inventory() -> tuple[list[str], list[str]]:
    try:
        import mido
        return mido.get_input_names(), mido.get_output_names()
    except Exception:
        return [], []


def _fl_setup_report(settings_dir: Path, dry_run: bool = False) -> dict:
    from dawloop.midi_setup import (
        DAWLOOP_CONTROLLER_NAME, fl_studio_running, inspect_loopmidi,
        locate_fl_studio_executable,
    )
    from dawloop.setup import configured_scripts, discover_project_controllers, user_script_status

    midi_inputs, midi_outputs = _midi_inventory()
    loopmidi = inspect_loopmidi(midi_inputs, midi_outputs)
    scripts = configured_scripts(settings_dir)
    status = user_script_status(settings_dir)
    controller_source = Path(__file__).resolve().parent / "fl_scripts" / "device_DAWLoopController.py"
    header = "\n".join(controller_source.read_text(encoding="utf-8").splitlines()[:3])
    binding_available = "# supportedDevices=DAWLoop MCP IN" in header
    settings_status = "FOUND" if settings_dir.is_dir() else "DEFAULT_CANDIDATE"
    manual_actions = []
    if not loopmidi["installed"]:
        manual_actions.append("安装 loopMIDI；DAWLoop 不包含 virtualMIDI SDK 或虚拟端口驱动。")
    elif not loopmidi["running"]:
        manual_actions.append("先启动 loopMIDI 并重新运行检查；只有端口仍缺失时才在 loopMIDI 中创建固定名称端口。")
    elif loopmidi["ports"]["names_status"] in {"DAWLOOP_MIDI_PORT_MISSING", "PARTIAL_MIDI_PORTS"}:
        manual_actions.append("在 loopMIDI 中创建固定端口 DAWLoop MCP IN 与 DAWLoop MCP OUT；当前没有确认到受支持的自动端口配置接口。")
    elif loopmidi["ports"]["names_status"] == "LEGACY_MIDI_PORT_NAMES":
        manual_actions.append("检测到旧 FLSkill 端口名，迁移兼容路径可继续使用；新环境建议改用 DAWLoop MCP IN / OUT。")
    if loopmidi["autostart"] != "ENABLED":
        manual_actions.append("在 loopMIDI 自带设置中启用登录启动；DAWLoop 不修改未知配置或注册表。")
    if not binding_available:
        manual_actions.append("安装后首次在 FL Studio MIDI 设置中选择 DAWLoop Controller 并确认端口关联。")
    manual_actions.append("Controller 自动关联能力来自官方 supportedDevices 声明；仍需一次 FL 现场加载确认，之后的重启持久性尚未验证。")
    return {
        "settings_dir": {"status": settings_status, "exists": settings_dir.is_dir()},
        "fl_studio": {
            "installed": locate_fl_studio_executable() is not None,
            "running": fl_studio_running(),
        },
        "loopmidi": loopmidi,
        "user_scripts": status,
        "detected_project_controllers": list(discover_project_controllers(settings_dir)),
        "controller": {
            "name": DAWLOOP_CONTROLLER_NAME,
            "supported_devices_configured": binding_available,
            "binding_status": "AVAILABLE_NOT_CONFIRMED" if binding_available else "NOT_CONFIRMED",
        },
        "would_install": [
            str(scripts[key]) for key in ("controller", "backend", "license", "piano_roll")
            if not status[key]
        ],
        "dry_run": dry_run,
        "manual_actions": manual_actions,
    }


def _print_integration_doctor(settings_dir: Path, probe_fl: bool, midi_port: str | None) -> tuple[bool, bool]:
    del midi_port
    from dawloop.midi_setup import inspect_loopmidi
    from dawloop.controller_runtime import (
        inspect_controller_lifecycle, installed_controller_identity,
    )
    from dawloop.setup import configured_scripts, user_script_status

    midi_inputs, midi_outputs = _midi_inventory()
    loop = inspect_loopmidi(midi_inputs, midi_outputs)
    ports = loop["ports"]
    scripts = user_script_status(settings_dir)
    setup_report = _fl_setup_report(settings_dir)
    fl_installed = setup_report["fl_studio"]["installed"]
    script_paths = configured_scripts(settings_dir)
    expected_build_id, installed_sha = installed_controller_identity(script_paths["controller"])
    controller_source = Path(__file__).resolve().parent / "fl_scripts" / "device_DAWLoopController.py"
    identity_code_available = scripts["controller"] and (
        "dawloop.getTargetIdentity" in controller_source.read_text(encoding="utf-8")
    )
    rows: list[tuple[str, str, str]] = [
        ("FL Studio installation", "PASS" if fl_installed else "NOT_FOUND", "检测到可执行文件或运行中的 FL64" if fl_installed else "未找到 FL64"),
        ("Controller installed", "PASS" if scripts["controller"] else "FL_USER_SCRIPT_MISSING", "主控制器文件"),
        ("Bundled MCP script", "PASS" if scripts["backend"] else "FL_USER_SCRIPT_MISSING", "非独立 Controller 的后端模块"),
        ("loopMIDI installed", "PASS" if loop["installed"] else "LOOPMIDI_NOT_INSTALLED", ""),
        ("loopMIDI running", "PASS" if loop["running"] else "LOOPMIDI_NOT_RUNNING", ""),
        ("Python → FL MIDI port", "PASS" if ports["canonical_input_available"] or ports["legacy_input_available"] else "DAWLOOP_MIDI_PORT_MISSING", "FL 脚本接收控制请求"),
        ("FL → Python MIDI port", "AVAILABLE_UNUSED" if ports["canonical_output_available"] or ports["legacy_output_available"] else "NOT_REQUIRED_BY_FILE_RPC", "当前 bundled RPC 响应通过 JSON 文件返回"),
        ("Transitional identity script", "PRESENT" if scripts["identity_controller"] else "ABSENT", "独立脚本不再由正常安装流程要求"),
        ("MIDI port names", str(ports["names_status"]), "canonical 与 legacy 名称检测"),
        ("loopMIDI autostart", str(loop["autostart"]), "通过当前用户登录启动项检测"),
        ("Controller auto-binding", setup_report["controller"]["binding_status"], "官方声明可自动关联；需现场加载确认"),
    ]
    runtime_code = "NOT_CHECKED"
    runtime_observation = None
    lifecycle = None
    if probe_fl:
        if not expected_build_id:
            runtime_code = "STOP"
        else:
            lifecycle = inspect_controller_lifecycle(script_paths["controller"], expected_build_id)
            runtime_observation = lifecycle["runtime"]
            runtime_code = lifecycle["verification"]
    rows.extend([
        ("Installed controller build", expected_build_id or "UNAVAILABLE", "从已安装脚本读取，未用磁盘 SHA 代替"),
        ("Installed script SHA256", installed_sha or "UNAVAILABLE", "磁盘文件摘要；不证明 FL 内存版本"),
        ("Controller runtime", runtime_code if probe_fl else "NOT_CHECKED", runtime_observation.code if runtime_observation else "CONTROLLER_BUILD_ID_MISSING" if probe_fl else ""),
        ("Runtime build id", runtime_observation.payload.get("build_id") if runtime_observation and runtime_observation.payload else "NOT_OBSERVED", "来自 FL 进程写出的状态文件"),
        ("Runtime session id", runtime_observation.payload.get("session_id") if runtime_observation and runtime_observation.payload else "NOT_OBSERVED", "每次 OnInit 变化"),
        ("Runtime initialized at", runtime_observation.payload.get("initialized_at") if runtime_observation and runtime_observation.payload else "NOT_OBSERVED", "Controller 本机观察时间"),
        ("Runtime last seen", runtime_observation.payload.get("last_seen_at") if runtime_observation and runtime_observation.payload else "NOT_OBSERVED", "OnIdle 节流心跳"),
        ("Runtime freshness", f"{runtime_observation.age_seconds:.1f}s" if runtime_observation and runtime_observation.age_seconds is not None else runtime_code, "阈值 10 秒"),
        ("Canonical runtime root", str(lifecycle["paths"]["root"]) if lifecycle else "NOT_CHECKED", "由已安装 Controller 的绝对路径确定"),
        ("Module load observed", "PASS" if lifecycle and lifecycle["module"] else "MISSING" if lifecycle else "NOT_CHECKED", lifecycle["module_error"] or "" if lifecycle else ""),
        ("Module build", lifecycle["module"].get("build_id", "NOT_OBSERVED") if lifecycle and lifecycle["module"] else "NOT_OBSERVED", "只接受当前已安装 build"),
        ("Module instance", lifecycle["module"].get("module_instance_id", "NOT_OBSERVED") if lifecycle and lifecycle["module"] else "NOT_OBSERVED", "每次模块加载生成"),
        ("OnInit observed", "PASS" if lifecycle and lifecycle["init"] else "MISSING" if lifecycle else "NOT_CHECKED", lifecycle["init_error"] or "" if lifecycle else ""),
        ("Init session", lifecycle["init"].get("session_id", "NOT_OBSERVED") if lifecycle and lifecycle["init"] else "NOT_OBSERVED", "与模块实例关联"),
        ("Controller READY", "PASS" if runtime_observation and runtime_observation.ready else "MISSING" if runtime_observation and runtime_observation.code == "CONTROLLER_RUNTIME_STATUS_MISSING" else "STOP" if probe_fl else "NOT_CHECKED", runtime_observation.code if runtime_observation else ""),
        ("Bootstrap error", lifecycle["error"].get("stage", "UNKNOWN") if lifecycle and lifecycle["error"] else "PRESENT" if lifecycle and lifecycle["fallback_error"] else "NONE" if lifecycle else "NOT_CHECKED", lifecycle["error"].get("exception_type", "") if lifecycle and lifecycle["error"] else lifecycle["fallback_error"] or "" if lifecycle else ""),
        ("ControllerReloadVerification", runtime_code if probe_fl else "NOT_CHECKED", "需要当前 build、OnInit、READY 与新鲜心跳"),
        ("RPC transport", "NOT_CHECKED", "本次仅读取本机运行状态，不发送 MIDI/RPC 请求"),
        ("Target identity capability", "AVAILABLE_NOT_PROBED" if identity_code_available else "NOT_INSTALLED", "本次未发身份请求"),
        ("Port number 42", "NOT_REQUIRED_BY_BUNDLED_BACKEND", "当前 bundled MCP 使用命名 MIDI 端口，不使用 Port 42"),
    ])
    print("\nDAWLoop FL Integration")
    for name, status, detail in rows:
        print(f"{name:<28} {status:<34} {detail}")
    required_ok = all((scripts["controller"], scripts["backend"]))
    lifecycle_ok = bool(lifecycle and lifecycle["verification"] == "PASS")
    return required_ok, lifecycle_ok if probe_fl else False


def _doctor(probe_fl: bool, settings_dir: Path | None = None, midi_port: str | None = None) -> int:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python", sys.version_info >= (3, 11), platform.python_version()))

    try:
        import dawloop
        checks.append(("DAWLoop Core", True, "可导入"))
    except Exception as error:
        checks.append(("DAWLoop Core", False, str(error)))

    vendor = importlib.util.find_spec("fl_studio_mcp")
    checks.append(("Bundled FL Studio MCP", vendor is not None, "已找到" if vendor else "未找到"))

    from dawloop.setup import default_settings_dir, user_script_status
    settings_dir = settings_dir or default_settings_dir()
    scripts = user_script_status(settings_dir)
    missing_scripts = [name for name in ("controller", "backend", "license") if not scripts[name]]
    checks.append((
        "DAWLoop FL User Scripts",
        not missing_scripts,
        "已安装" if not missing_scripts else "缺少统一控制器或后端；运行 setup-fl",
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

    for name, passed, detail in checks:
        print(f"{name:<24} {'PASS' if passed else 'STOP':<6} {detail}")
    integration_ok, identity_ok = _print_integration_doctor(settings_dir, probe_fl, midi_port)

    from dawloop.production.environment import EnvironmentStatus, inspect_environment
    profile = inspect_environment()
    profile_checks = {check.name: check for check in profile.checks}
    production_rows = [
        ("numpy", profile_checks["numpy"].status, 'pip install "dawloop[production]"'),
        ("Production SMF analysis", EnvironmentStatus.AVAILABLE, "stdlib-only; no numpy required"),
        ("Production audio analysis", profile_checks["numpy"].status, 'pip install "dawloop[production]"'),
        ("Production Windows loopback", profile_checks["WASAPI"].status, 'pip install "dawloop[production-loopback]"'),
        ("spectrum-peak", profile_checks["spectrum-peak"].status, "environment-specific optional dependency"),
        ("MuseScore", profile_checks["MuseScore"].status, "not required by current Production Pipeline APIs"),
        ("FluidSynth", profile_checks["FluidSynth"].status, "not required by current Production Pipeline APIs"),
    ]
    print("\nProduction Pipeline optional environment checks")
    for name, status, detail in production_rows:
        print(f"{name:<24} {status.value:<18} {detail}")
    print(f"{'Production environment profile':<32} {profile.portable_status:<18} OS={profile.os_name}; Python={profile.python_version}")
    return 0 if all(passed for _, passed, _ in checks) and integration_ok and (identity_ok or not probe_fl) else 1


def _setup_fl(settings_dir: Path | None, dry_run: bool) -> int:
    from dawloop.setup import default_settings_dir, install_user_scripts

    target = (settings_dir or default_settings_dir()).expanduser()
    report = _fl_setup_report(target, dry_run)
    if not dry_run:
        try:
            installed = install_user_scripts(target)
        except FileExistsError as error:
            code = "USER_SCRIPT_CONFLICT"
            reason = str(error)
        except FileNotFoundError as error:
            code = "BUNDLED_MCP_FILE_MISSING"
            reason = str(error)
        except ValueError as error:
            code = "DAWLOOP_CONFIG_INVALID"
            reason = str(error)
        except OSError as error:
            code = "INSTALL_WRITE_FAILED"
            reason = type(error).__name__
        else:
            report["installation"] = {"status": "INSTALLED", "files": [path.name for path in installed]}
            from dawloop.controller_runtime import installed_controller_identity
            controller_path = next(path for path in installed if path.name.startswith("device_DAWLoop"))
            expected_build_id, installed_sha = installed_controller_identity(controller_path)
            report["controller_runtime"] = {
                "status": "RELOAD_REQUIRED",
                "expected_build_id": expected_build_id,
                "installed_script_sha256": installed_sha,
                "message": "FL Studio must reload the MIDI script before this build is active.",
            }
            report["settings_dir"] = {"status": "FOUND", "exists": True}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if "installation" not in report:
            report["installation"] = {"status": "STOP", "code": code, "reason": reason}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1
    else:
        report["installation"] = {"status": "DRY_RUN", "files_changed": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _midi_inspect(path: str, beats_per_bar: int, window_bars: int) -> int:
    from dawloop.production.smf import parse_smf, recommend_dense_window

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
        from dawloop.production.mix import active_rms
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
    parser = argparse.ArgumentParser(prog="dawloop")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="检查 Python、依赖和 FL Studio 通信")
    doctor_parser.add_argument("--probe-fl", action="store_true", help="只读检查 FL Controller 运行状态文件；不发送 MIDI 或 RPC")
    doctor_parser.add_argument("--settings-dir", type=Path, help="活动 FL Studio Settings 目录")
    doctor_parser.add_argument("--midi-port", help="指定精确的 DAWLoop MCP IN MIDI 输出端口")
    setup_parser = subparsers.add_parser("setup-fl", help="检查并安装统一的 FL Studio 控制器")
    setup_parser.add_argument("--settings-dir", type=Path, help="活动 FL Studio Settings 目录")
    setup_parser.add_argument("--dry-run", action="store_true", help="只检查并显示计划，不写入文件")
    install_parser = subparsers.add_parser("install-fl-scripts", help="安装统一 DAWLoop Controller 与随包后端")
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
        if args.settings_dir:
            import os
            os.environ["DAWLOOP_FL_SETTINGS_DIR"] = str(args.settings_dir.expanduser())
        return _doctor(args.probe_fl, args.settings_dir, args.midi_port)
    if args.command == "setup-fl":
        return _setup_fl(args.settings_dir, args.dry_run)
    if args.command == "install-fl-scripts":
        from dawloop.setup import install_user_scripts
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
