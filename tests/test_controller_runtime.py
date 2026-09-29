from __future__ import annotations

import importlib.util
import json
import io
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout

from dawloop.controller_runtime import (
    inspect_runtime_status,
    installed_controller_identity,
    ping_preflight,
)


NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def runtime_payload(**overrides):
    value = {
        "controller": "DAWLoop Controller",
        "build_id": "git:test+controller:abc",
        "session_id": "session-a",
        "state": "READY",
        "initialized_at": NOW.isoformat(),
        "last_seen_at": NOW.isoformat(),
        "protocol_version": "dawloop-midi-json-v1",
        "controller_version": "phase0.7-runtime-status-v1",
        "source": "fl_studio_user_script",
    }
    value.update(overrides)
    return value


def load_live_controller(root: Path):
    upstream = root / "upstream_backend.py"
    upstream.write_text(
        "TRIGGER_NOTE=127\n"
        "def OnInit(): pass\n"
        "def OnDeInit(): pass\n"
        "def OnMidiMsg(event): pass\n",
        encoding="utf-8",
    )
    source_path = Path(__file__).resolve().parents[1] / "src" / "dawloop" / "fl_scripts" / "device_DAWLoopController.py"
    source = source_path.read_text(encoding="utf-8")
    source = source.replace("SETTINGS_DIR_OVERRIDE = None", f"SETTINGS_DIR_OVERRIDE = Path({str(root)!r})", 1)
    source = source.replace("UPSTREAM_SCRIPT_OVERRIDE = None", f"UPSTREAM_SCRIPT_OVERRIDE = Path({str(upstream)!r})", 1)
    wrapper = root / "device_DAWLoopController.py"
    wrapper.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"dawloop_controller_test_{id(root)}", wrapper)
    module = importlib.util.module_from_spec(spec)
    fake_api = {
        "channels": types.SimpleNamespace(selectedChannel=lambda *args: (_ for _ in ()).throw(AssertionError("不应读取 Channel")), getChannelName=lambda *args: None),
        "general": types.SimpleNamespace(safeToEdit=lambda: (_ for _ in ()).throw(AssertionError("不应读取工程"))),
        "patterns": types.SimpleNamespace(patternNumber=lambda: (_ for _ in ()).throw(AssertionError("不应读取 Pattern"))),
        "ui": types.SimpleNamespace(),
    }
    with patch.dict(sys.modules, fake_api):
        spec.loader.exec_module(module)
    return module


class ControllerRuntimeTests(unittest.TestCase):
    def test_runtime_status_missing_and_malformed_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller_status.json"
            missing = inspect_runtime_status(path, "build", now=NOW)
            self.assertEqual(missing.code, "CONTROLLER_RUNTIME_STATUS_MISSING")
            path.write_text("{", encoding="utf-8")
            malformed = inspect_runtime_status(path, "build", now=NOW)
            self.assertEqual(malformed.code, "CONTROLLER_RUNTIME_STATUS_MALFORMED")

    def test_matching_fresh_ready_runtime_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller_status.json"
            path.write_text(json.dumps(runtime_payload()), encoding="utf-8")
            observed = inspect_runtime_status(path, "git:test+controller:abc", now=NOW)
        self.assertEqual(observed.code, "CONTROLLER_RUNTIME_READY")
        self.assertTrue(observed.ready)
        self.assertEqual(observed.age_seconds, 0)

    def test_stale_runtime_requires_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller_status.json"
            old = NOW - timedelta(seconds=11)
            path.write_text(json.dumps(runtime_payload(last_seen_at=old.isoformat())), encoding="utf-8")
            observed = inspect_runtime_status(path, "git:test+controller:abc", now=NOW)
        self.assertEqual(observed.code, "CONTROLLER_RUNTIME_STALE")
        self.assertEqual(observed.status, "RELOAD_REQUIRED")

    def test_build_mismatch_requires_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller_status.json"
            path.write_text(json.dumps(runtime_payload()), encoding="utf-8")
            observed = inspect_runtime_status(path, "new-build", now=NOW)
        self.assertEqual(observed.code, "CONTROLLER_RUNTIME_BUILD_MISMATCH")

    def test_non_ready_state_does_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller_status.json"
            path.write_text(json.dumps(runtime_payload(state="STOPPED")), encoding="utf-8")
            observed = inspect_runtime_status(path, "git:test+controller:abc", now=NOW)
        self.assertEqual(observed.code, "CONTROLLER_RUNTIME_NOT_READY")

    def test_disk_sha_is_separate_from_embedded_runtime_build(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "device.py"
            script.write_text('CONTROLLER_BUILD_ID = "git:expected+controller:abc"\n', encoding="utf-8")
            build_id, disk_sha = installed_controller_identity(script)
        self.assertEqual(build_id, "git:expected+controller:abc")
        self.assertEqual(len(disk_sha), 64)
        self.assertNotEqual(build_id, disk_sha)

    def test_ping_preflight_blocks_missing_stale_and_mismatched_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory)
            controller = settings / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            controller.write_text('CONTROLLER_BUILD_ID = "expected"\n', encoding="utf-8")
            missing = ping_preflight(settings, now=NOW)
            self.assertFalse(missing.ready)
            self.assertEqual(missing.code, "CONTROLLER_RUNTIME_STATUS_MISSING")
            status = controller.with_name("controller_status.json")
            status.write_text(json.dumps(runtime_payload(build_id="older")), encoding="utf-8")
            mismatch = ping_preflight(settings, now=NOW)
            self.assertFalse(mismatch.ready)
            self.assertEqual(mismatch.code, "CONTROLLER_RUNTIME_BUILD_MISMATCH")
            old = NOW - timedelta(seconds=11)
            status.write_text(json.dumps(runtime_payload(build_id="expected", last_seen_at=old.isoformat())), encoding="utf-8")
            stale = ping_preflight(settings, now=NOW)
            self.assertFalse(stale.ready)
            self.assertEqual(stale.code, "CONTROLLER_RUNTIME_STALE")

    def test_ping_preflight_allows_only_fresh_matching_ready_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory)
            controller = settings / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            controller.write_text('CONTROLLER_BUILD_ID = "expected"\n', encoding="utf-8")
            controller.with_name("controller_status.json").write_text(
                json.dumps(runtime_payload(build_id="expected")), encoding="utf-8"
            )
            self.assertTrue(ping_preflight(settings, now=NOW).ready)

    def test_controller_oninit_writes_atomic_runtime_status_and_changes_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = load_live_controller(root)
            module.CONTROLLER_BUILD_ID = "expected-build"
            module.OnInit()
            path = root / "Hardware" / "DAWLoopMCP" / "controller_status.json"
            first = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(first["build_id"], "expected-build")
            self.assertEqual(first["state"], "READY")
            self.assertEqual(first["source"], "fl_studio_user_script")
            self.assertTrue(first["session_id"])
            self.assertFalse(path.with_name(".controller_status.json.tmp").exists())
            module.OnInit()
            second = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotEqual(first["session_id"], second["session_id"])

    def test_status_write_failure_does_not_crash_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = load_live_controller(root)
            blocked_parent = root / "not-a-directory"
            blocked_parent.write_text("占位", encoding="utf-8")
            module.STATUS_FILE = blocked_parent / "controller_status.json"
            module.OnInit()
            self.assertFalse(module.STATUS_FILE.exists())

    def test_runtime_status_callbacks_do_not_call_daw_mutation_apis(self):
        with tempfile.TemporaryDirectory() as directory:
            module = load_live_controller(Path(directory))
            module.OnInit()
            module.OnIdle()
            self.assertTrue((Path(directory) / "Hardware" / "DAWLoopMCP" / "controller_status.json").is_file())

    def test_trace_script_stops_before_loading_midi_transport_without_runtime_pass(self):
        path = Path(__file__).parent / "live_fl" / "trace_midi.py"
        spec = importlib.util.spec_from_file_location("dawloop_trace_gate_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(sys, "argv", [str(path), "--midi-port", "unused", "--settings-dir", directory]), \
                    patch.dict(sys.modules, {"fl_studio_mcp.utils.midi_connection": None}), \
                    redirect_stdout(output):
                result = module.main()
        self.assertEqual(result, 1)
        self.assertIn("CONTROLLER_BUILD_ID_MISSING", output.getvalue())


if __name__ == "__main__":
    unittest.main()
