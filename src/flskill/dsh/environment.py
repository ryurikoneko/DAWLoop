"""Lightweight checks for optional DSH environment requirements."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import sys


class EnvironmentStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    OPTIONAL_MISSING = "OPTIONAL_MISSING"
    NOT_CHECKED = "NOT_CHECKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    status: EnvironmentStatus
    detail: str = ""


@dataclass(frozen=True)
class EnvironmentProfile:
    os_name: str
    python_version: str
    checks: tuple[EnvironmentCheck, ...]
    configured_environment_variables: tuple[str, ...]
    invocation_assumptions: tuple[str, ...]
    original_developer_environment: str = "reported_working"

    @property
    def portable_status(self) -> str:
        if any(check.status in {EnvironmentStatus.MISSING, EnvironmentStatus.UNSUPPORTED} for check in self.checks):
            return "BLOCKED"
        if any(check.status in {EnvironmentStatus.OPTIONAL_MISSING, EnvironmentStatus.NOT_CHECKED} for check in self.checks):
            return "PARTIAL"
        return "AVAILABLE"


def _module_check(name: str, modules: str | tuple[str, ...], *, optional: bool = True) -> EnvironmentCheck:
    candidates = (modules,) if isinstance(modules, str) else modules
    found = False
    for module in candidates:
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        if found:
            break
    return EnvironmentCheck(
        name,
        EnvironmentStatus.AVAILABLE if found else (
            EnvironmentStatus.OPTIONAL_MISSING if optional else EnvironmentStatus.MISSING
        ),
        "installed" if found else "not installed",
    )


def _executable_check(name: str, candidates: tuple[str, ...]) -> EnvironmentCheck:
    executable = next((shutil.which(candidate) for candidate in candidates if shutil.which(candidate)), None)
    return EnvironmentCheck(
        name,
        EnvironmentStatus.AVAILABLE if executable else EnvironmentStatus.OPTIONAL_MISSING,
        "available" if executable else "not found on PATH",
    )


def inspect_environment() -> EnvironmentProfile:
    checks = [
        _module_check("numpy", "numpy"),
        _module_check("pyaudiowpatch", "pyaudiowpatch"),
        _module_check("spectrum-peak", ("spectrum_peak", "spectrum-peak")),
        _executable_check("MuseScore", ("MuseScore4.exe", "MuseScore.exe", "musescore")),
        _executable_check("FluidSynth", ("fluidsynth.exe", "fluidsynth")),
    ]

    fl_path = os.environ.get("FL_STUDIO_PATH")
    if fl_path:
        fl_status = EnvironmentStatus.AVAILABLE if Path(fl_path).exists() else EnvironmentStatus.MISSING
        fl_detail = "configured path exists" if fl_status is EnvironmentStatus.AVAILABLE else "configured path not found"
    elif shutil.which("FL64.exe"):
        fl_status, fl_detail = EnvironmentStatus.AVAILABLE, "found on PATH"
    else:
        fl_status, fl_detail = EnvironmentStatus.NOT_CHECKED, "not probed; set FL_STUDIO_PATH to identify an installation"
    checks.append(EnvironmentCheck(
        "FL Studio",
        fl_status,
        fl_detail,
    ))
    checks.append(EnvironmentCheck(
        "WASAPI",
        EnvironmentStatus.NOT_APPLICABLE if os.name != "nt" else (
            EnvironmentStatus.NOT_CHECKED
            if importlib.util.find_spec("pyaudiowpatch") is not None
            else EnvironmentStatus.OPTIONAL_MISSING
        ),
        "endpoint enumeration not run" if os.name == "nt" and importlib.util.find_spec("pyaudiowpatch") is not None else (
            "Windows audio loopback API" if os.name == "nt" else "Windows-only capability"
        ),
    ))

    soundfont = os.environ.get("DSH_SOUNDFONT")
    checks.append(EnvironmentCheck(
        "SoundFont path",
        EnvironmentStatus.AVAILABLE if soundfont and Path(soundfont).is_file() else (
            EnvironmentStatus.OPTIONAL_MISSING if not soundfont else EnvironmentStatus.MISSING
        ),
        "configured file exists" if soundfont and Path(soundfont).is_file() else "not configured or file not found",
    ))

    relevant_env = ("FL_STUDIO_PATH", "DSH_SOUNDFONT", "PYTHONPATH")
    configured = tuple(name for name in relevant_env if os.environ.get(name))
    return EnvironmentProfile(
        os_name=platform.platform(),
        python_version=platform.python_version(),
        checks=tuple(checks),
        configured_environment_variables=configured,
        invocation_assumptions=(
            "track-scan.py requires the environment-specific spectrum-peak module",
            "fugue-v4.py requires an output path in sys.argv[1]",
        ),
    )
