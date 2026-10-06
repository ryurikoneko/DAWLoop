from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sysconfig
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _vendor_root() -> Path:
    checkout = Path(__file__).resolve().parents[2] / "third_party" / "fl-studio-mcp"
    if checkout.is_dir():
        return checkout
    return Path(sysconfig.get_path("data")) / "share" / "dawloop" / "third_party" / "fl-studio-mcp"


def _config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / ".config"
    return root / "DAWLoop" / "config.json"


def save_settings_dir(settings_dir: Path) -> Path:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        raise ValueError("DAWLOOP_CONFIG_INVALID")
    if not isinstance(config, dict):
        raise ValueError("DAWLOOP_CONFIG_INVALID")
    config["fl_settings_dir"] = str(settings_dir.expanduser().resolve())
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def default_settings_dir() -> Path:
    override = os.environ.get("DAWLOOP_FL_SETTINGS_DIR")
    if override:
        return Path(override).expanduser()
    path = _config_path()
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get("fl_settings_dir")
            if isinstance(value, str) and value.strip():
                return Path(value).expanduser()
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
    return Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings"


def configured_scripts(settings_dir: Path) -> dict[str, Path]:
    hardware = settings_dir / "Hardware" / "DAWLoopMCP"
    current_controller = hardware / "device_DAWLoopController.py"
    transitional_controller = hardware / "device_DAWLoopMCP.py"
    if not current_controller.exists() and (
        _has_controller_name(transitional_controller, "DAWLoop MCP Controller")
        or _has_controller_name(transitional_controller, "DAWLoop Controller")
    ):
        current_controller = transitional_controller
    return {
        "controller": current_controller,
        "backend": hardware / "upstream_backend.py",
        "license": hardware / "UPSTREAM_LICENSE",
        "legacy_identity_controller": hardware / "device_DAWLoopMCP.py",
        "piano_roll": settings_dir / "Piano roll scripts" / "ComposeWithLLM.pyscript",
    }


def _has_controller_name(path: Path, name: str) -> bool:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[0] == f"# name={name}"
    except (OSError, IndexError):
        return False


def _same_text_bytes(left: bytes, right: bytes) -> bool:
    return left.replace(b"\r\n", b"\n") == right.replace(b"\r\n", b"\n")


def _controller_build_id(source: Path) -> str:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    repository_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=3,
        )
        commit = result.stdout.strip()
        if commit:
            return f"git:{commit}+controller:{digest}"
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        package_version = version("dawloop")
    except PackageNotFoundError:
        package_version = "unknown"
    return f"dawloop:{package_version}+controller:{digest}"


def install_user_scripts(settings_dir: Path) -> tuple[Path, ...]:
    source = _vendor_root()
    own_controller = Path(__file__).resolve().parent / "fl_scripts" / "device_DAWLoopController.py"
    controller_destination = configured_scripts(settings_dir)["controller"]
    installs = (
        (source / "fl_controller" / "device_FLStudioMCP.py", settings_dir / "Hardware" / "DAWLoopMCP" / "upstream_backend.py", "upstream"),
        (own_controller, controller_destination, "controller"),
        (source / "LICENSE", settings_dir / "Hardware" / "DAWLoopMCP" / "UPSTREAM_LICENSE", "upstream"),
        (source / "scripts" / "ComposeWithLLM.pyscript", settings_dir / "Piano roll scripts" / "ComposeWithLLM.pyscript", "upstream"),
    )
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    written = []
    for src, dst, kind in installs:
        if not src.is_file():
            raise FileNotFoundError("缺少随包 FL Studio MCP 文件")
        dst.parent.mkdir(parents=True, exist_ok=True)
        source_bytes = src.read_bytes()
        generated = None
        if kind == "controller":
            script = src.read_text(encoding="utf-8")
            script = script.replace(
                'CONTROLLER_BUILD_ID = "source-uninstalled"',
                f'CONTROLLER_BUILD_ID = "{_controller_build_id(src)}"',
                1,
            ).replace(
                "SETTINGS_DIR_OVERRIDE = None",
                f"SETTINGS_DIR_OVERRIDE = Path({str(settings_dir.resolve())!r})",
                1,
            ).replace(
                "UPSTREAM_SCRIPT_OVERRIDE = None",
                f"UPSTREAM_SCRIPT_OVERRIDE = Path({str((settings_dir / 'Hardware' / 'DAWLoopMCP' / 'upstream_backend.py').resolve())!r})",
                1,
            )
            generated = script.encode("utf-8")
        if dst.exists():
            current = dst.read_bytes()
            expected = generated if generated is not None else source_bytes
            if _same_text_bytes(current, expected):
                written.append(dst)
                continue
            managed = current.startswith(b"# name=DAWLoop Controller") or (
                kind == "controller" and current.startswith(b"# name=DAWLoop MCP Controller")
            )
            if kind != "controller" or not managed:
                raise FileExistsError(f"目标文件已存在且不属于 DAWLoop 管理：{dst.name}")
            backup = dst.with_name(f"{dst.name}.bak-{timestamp}")
            shutil.copy2(dst, backup)
        if generated is not None:
            dst.write_bytes(generated)
        else:
            shutil.copy2(src, dst)
        written.append(dst)
    save_settings_dir(settings_dir)
    return tuple(written)


def user_script_status(settings_dir: Path) -> dict[str, bool]:
    paths = configured_scripts(settings_dir)
    controller_name = "DAWLoop Controller"
    return {
        "controller": _has_controller_name(paths["controller"], controller_name),
        "backend": paths["backend"].is_file(),
        "license": paths["license"].is_file(),
        "identity_controller": _has_controller_name(
            paths["legacy_identity_controller"], "DAWLoop MCP Controller"
        ),
        "piano_roll": paths["piano_roll"].is_file(),
    }


def discover_project_controllers(settings_dir: Path) -> tuple[str, ...]:
    hardware = settings_dir / "Hardware"
    if not hardware.is_dir():
        return ()
    found = []
    for directory in hardware.iterdir():
        if not directory.is_dir():
            continue
        for script in directory.glob("device_*.py"):
            try:
                header = script.read_text(encoding="utf-8", errors="replace").splitlines()[:3]
            except OSError:
                continue
            name_line = next((line for line in header if line.startswith("# name=")), None)
            if name_line and any(token in name_line.casefold() for token in ("dawloop", "flskill mcp", "fl studio mcp")):
                found.append(name_line.partition("=")[2].strip())
    return tuple(sorted(set(found)))
