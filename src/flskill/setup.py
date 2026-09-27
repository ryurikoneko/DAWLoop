from __future__ import annotations

import os
import shutil
import sysconfig
from datetime import datetime
from pathlib import Path


def _vendor_root() -> Path:
    checkout = Path(__file__).resolve().parents[2] / "third_party" / "fl-studio-mcp"
    if checkout.is_dir():
        return checkout
    return Path(sysconfig.get_path("data")) / "share" / "flskill" / "third_party" / "fl-studio-mcp"


def install_user_scripts(settings_dir: Path) -> tuple[Path, ...]:
    source = _vendor_root()
    installs = (
        (source / "fl_controller" / "device_FLStudioMCP.py", settings_dir / "Hardware" / "FLStudioMCP" / "device_FLStudioMCP.py"),
        (source / "scripts" / "ComposeWithLLM.pyscript", settings_dir / "Piano roll scripts" / "ComposeWithLLM.pyscript"),
    )
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    written = []
    for src, dst in installs:
        if not src.is_file():
            raise FileNotFoundError(f"缺少随包上游脚本：{src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            backup = dst.with_name(f"{dst.name}.bak-{timestamp}")
            shutil.copy2(dst, backup)
        shutil.copy2(src, dst)
        written.append(dst)
    return tuple(written)


def user_script_status(settings_dir: Path) -> dict[str, bool]:
    return {
        "controller": (settings_dir / "Hardware" / "FLStudioMCP" / "device_FLStudioMCP.py").is_file(),
        "piano_roll": (settings_dir / "Piano roll scripts" / "ComposeWithLLM.pyscript").is_file(),
    }


def default_settings_dir() -> Path:
    override = os.environ.get("FLSKILL_FL_SETTINGS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings"
