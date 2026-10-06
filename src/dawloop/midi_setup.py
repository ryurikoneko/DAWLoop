from __future__ import annotations

import os
import re
import subprocess
import sys
import csv
import ctypes
from ctypes import wintypes
from pathlib import Path


CANONICAL_MIDI_IN = "DAWLoop MCP IN"
CANONICAL_MIDI_OUT = "DAWLoop MCP OUT"
LEGACY_MIDI_IN = "FLSkill MCP IN"
LEGACY_MIDI_OUT = "FLSkill MCP OUT"
DAWLOOP_CONTROLLER_NAME = "DAWLoop Controller"


def logical_port_name(name: str) -> str:
    return re.sub(r"\s+\d+$", "", name.strip())


def inspect_midi_ports(input_names: list[str], output_names: list[str]) -> dict[str, object]:
    inputs = {logical_port_name(name) for name in input_names}
    outputs = {logical_port_name(name) for name in output_names}
    canonical_in = CANONICAL_MIDI_IN in outputs
    canonical_out = CANONICAL_MIDI_OUT in inputs
    legacy_in = LEGACY_MIDI_IN in outputs
    legacy_out = LEGACY_MIDI_OUT in inputs
    canonical_complete = canonical_in and canonical_out
    legacy_complete = legacy_in and legacy_out
    if canonical_complete and legacy_complete:
        names_status = "BOTH_PRESENT"
    elif canonical_complete:
        names_status = "PASS"
    elif legacy_complete:
        names_status = "LEGACY_MIDI_PORT_NAMES"
    elif any((canonical_in, canonical_out, legacy_in, legacy_out)):
        names_status = "PARTIAL_MIDI_PORTS"
    else:
        names_status = "DAWLOOP_MIDI_PORT_MISSING"
    return {
        "canonical_input_available": canonical_in,
        "canonical_output_available": canonical_out,
        "legacy_input_available": legacy_in,
        "legacy_output_available": legacy_out,
        "names_status": names_status,
        "selected_python_output": select_midi_output(output_names),
    }


def _select_port(names: list[str], preferred: tuple[str, ...]) -> str | None:
    by_logical: dict[str, list[str]] = {}
    for name in names:
        by_logical.setdefault(logical_port_name(name), []).append(name)
    for candidate in preferred:
        matches = by_logical.get(candidate, [])
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
    return None


def select_midi_output(names: list[str]) -> str | None:
    return _select_port(names, (CANONICAL_MIDI_IN, LEGACY_MIDI_IN))


def locate_loopmidi_executable() -> Path | None:
    candidates = []
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidates.append(Path(base) / "Tobias Erichsen" / "loopMIDI" / "loopMIDI.exe")
    if sys.platform == "win32":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for key_path in (
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\loopMIDI.exe",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\loopMIDI.exe",
                ):
                    try:
                        with winreg.OpenKey(hive, key_path) as key:
                            candidates.append(Path(winreg.QueryValue(key, None)))
                    except OSError:
                        continue
        except ImportError:
            pass
    return next((path for path in candidates if path.is_file()), None)


def loopmidi_process_running() -> bool:
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq loopMIDI.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and '"loopmidi.exe"' in result.stdout.casefold()


def loopmidi_autostart_status() -> str:
    if sys.platform != "win32":
        return "NOT_APPLICABLE"
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        ) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                _, command, _ = winreg.EnumValue(key, index)
                if "loopmidi.exe" in str(command).casefold():
                    return "ENABLED"
    except (ImportError, OSError):
        pass
    return "LOOPMIDI_AUTOSTART_NOT_CONFIRMED"


def locate_fl_studio_executable() -> Path | None:
    candidates = []
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            root = Path(base) / "Image-Line"
            if root.is_dir():
                candidates.extend(root.glob("FL Studio*/FL64.exe"))
    if sys.platform == "win32":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for key_path in (
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FL64.exe",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\FL64.exe",
                ):
                    try:
                        with winreg.OpenKey(hive, key_path) as key:
                            candidates.append(Path(winreg.QueryValue(key, None)))
                    except OSError:
                        continue
        except ImportError:
            pass
    process_path = _running_process_path("FL64.exe")
    if process_path:
        candidates.insert(0, process_path)
    return next((path for path in candidates if path.is_file()), None)


def _running_process_path(image_name: str) -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
            check=False,
        )
        rows = list(csv.reader(result.stdout.splitlines()))
        pid = next((int(row[1]) for row in rows if len(row) > 1 and row[0].casefold() == image_name.casefold()), None)
        if result.returncode != 0 or pid is None:
            return None
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            length = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(length.value)
            if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                return None
            return Path(buffer.value)
        finally:
            kernel.CloseHandle(handle)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def fl_studio_running() -> bool:
    return _running_process_path("FL64.exe") is not None


def inspect_loopmidi(input_names: list[str], output_names: list[str]) -> dict[str, object]:
    executable = locate_loopmidi_executable()
    ports = inspect_midi_ports(input_names, output_names)
    return {
        "installed": executable is not None,
        "running": loopmidi_process_running(),
        "autostart": loopmidi_autostart_status(),
        "ports": ports,
    }
