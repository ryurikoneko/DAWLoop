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
    controller_runtime_paths,
    inspect_controller_lifecycle,
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

    def test_runtime_paths_are_absolute_and_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root = Path(directory) / "Hardware" / "DAWLoopMCP"
            controller = root / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            previous = Path.cwd()
            try:
                import os
                os.chdir(other)
                paths = controller_runtime_paths(controller)
            finally:
                os.chdir(previous)
        self.assertTrue(paths["root"].is_absolute())
        self.assertEqual(paths["root"], root.resolve())
        self.assertEqual(paths["ready"], root.resolve() / "controller_status.json")

    def test_module_and_init_markers_are_separate_and_bound_to_one_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = load_live_controller(root)
            paths = controller_runtime_paths(root / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py")
            loaded = json.loads(paths["module"].read_text(encoding="utf-8"))
            self.assertEqual(loaded["event"], "MODULE_LOADED")
            self.assertEqual(loaded["build_id"], "source-uninstalled")
            self.assertTrue(loaded["module_instance_id"])
            self.assertFalse(paths["init"].exists())
            module.CONTROLLER_BUILD_ID = "expected-build"
            module.OnInit()
            initialized = json.loads(paths["init"].read_text(encoding="utf-8"))
            ready = json.loads(paths["ready"].read_text(encoding="utf-8"))
            self.assertEqual(initialized["event"], "ON_INIT_ENTERED")
            self.assertEqual(initialized["module_instance_id"], loaded["module_instance_id"])
            self.assertEqual(initialized["session_id"], ready["session_id"])

    def test_simulated_reload_changes_module_instance_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = controller_runtime_paths(root / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py")
            first = load_live_controller(root)
            first_id = json.loads(paths["module"].read_text(encoding="utf-8"))["module_instance_id"]
            second = load_live_controller(root)
            second_id = json.loads(paths["module"].read_text(encoding="utf-8"))["module_instance_id"]
        self.assertNotEqual(first_id, second_id)
        self.assertNotEqual(first.MODULE_INSTANCE_ID, second.MODULE_INSTANCE_ID)

    def test_lifecycle_reports_module_without_init_as_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            controller.write_text('CONTROLLER_BUILD_ID = "expected"\n', encoding="utf-8")
            paths = controller_runtime_paths(controller)
            paths["module"].write_text(json.dumps({
                "event": "MODULE_LOADED", "build_id": "expected",
                "module_instance_id": "instance-a", "runtime_root": str(paths["root"]),
            }), encoding="utf-8")
            result = inspect_controller_lifecycle(controller, "expected", now=NOW)
        self.assertEqual(result["verification"], "STOP")
        self.assertIsNone(result["init"])

    def test_lifecycle_reports_init_without_ready_as_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            controller.write_text('CONTROLLER_BUILD_ID = "expected"\n', encoding="utf-8")
            paths = controller_runtime_paths(controller)
            module_instance = "instance-a"
            paths["module"].write_text(json.dumps({
                "event": "MODULE_LOADED", "build_id": "expected",
                "module_instance_id": module_instance, "runtime_root": str(paths["root"]),
            }), encoding="utf-8")
            paths["init"].write_text(json.dumps({
                "event": "ON_INIT_ENTERED", "build_id": "expected",
                "module_instance_id": module_instance, "session_id": "session-a",
            }), encoding="utf-8")
            result = inspect_controller_lifecycle(controller, "expected", now=NOW)
        self.assertEqual(result["verification"], "STOP")

    def test_lifecycle_requires_fresh_matching_ready_heartbeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            controller.write_text('CONTROLLER_BUILD_ID = "expected"\n', encoding="utf-8")
            paths = controller_runtime_paths(controller)
            module_instance = "instance-a"
            paths["module"].write_text(json.dumps({
                "event": "MODULE_LOADED", "build_id": "expected",
                "module_instance_id": module_instance, "runtime_root": str(paths["root"]),
            }), encoding="utf-8")
            paths["init"].write_text(json.dumps({
                "event": "ON_INIT_ENTERED", "build_id": "expected",
                "module_instance_id": module_instance, "session_id": "session-a",
            }), encoding="utf-8")
            old = NOW - timedelta(seconds=11)
            paths["ready"].write_text(json.dumps(runtime_payload(
                build_id="expected", session_id="session-a", last_seen_at=old.isoformat(),
            )), encoding="utf-8")
            stale = inspect_controller_lifecycle(controller, "expected", now=NOW)
            paths["ready"].write_text(json.dumps(runtime_payload(
                build_id="expected", session_id="session-a", last_seen_at=NOW.isoformat(),
            )), encoding="utf-8")
            fresh = inspect_controller_lifecycle(controller, "expected", now=NOW)
        self.assertEqual(stale["verification"], "RELOAD_REQUIRED")
        self.assertEqual(fresh["verification"], "PASS")

    def test_stale_build_markers_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            controller.write_text('CONTROLLER_BUILD_ID = "current"\n', encoding="utf-8")
            paths = controller_runtime_paths(controller)
            paths["module"].write_text(json.dumps({
                "event": "MODULE_LOADED", "build_id": "old", "module_instance_id": "old-instance",
            }), encoding="utf-8")
            result = inspect_controller_lifecycle(controller, "current", now=NOW)
        self.assertIsNone(result["module"])
        self.assertEqual(result["verification"], "RELOAD_REQUIRED")

    def test_bootstrap_error_from_previous_module_instance_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            controller.write_text('CONTROLLER_BUILD_ID = "expected"\n', encoding="utf-8")
            paths = controller_runtime_paths(controller)
            paths["module"].write_text(json.dumps({
                "event": "MODULE_LOADED", "build_id": "expected",
                "module_instance_id": "new-instance", "runtime_root": str(paths["root"]),
            }), encoding="utf-8")
            paths["error"].write_text(json.dumps({
                "build_id": "expected", "module_instance_id": "old-instance",
                "stage": "PROJECT_IMPORT",
            }), encoding="utf-8")
            paths["error_marker"].write_text(
                "expected\nold-instance\nPROJECT_IMPORT\nImportError\n", encoding="utf-8"
            )
            result = inspect_controller_lifecycle(controller, "expected", now=NOW)
        self.assertIsNone(result["error"])
        self.assertIsNone(result["fallback_error"])
        self.assertEqual(result["verification"], "STOP")

    def test_bootstrap_error_from_current_module_instance_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / "Hardware" / "DAWLoopMCP" / "device_DAWLoopController.py"
            controller.parent.mkdir(parents=True)
            controller.write_text('CONTROLLER_BUILD_ID = "expected"\n', encoding="utf-8")
            paths = controller_runtime_paths(controller)
            paths["module"].write_text(json.dumps({
                "event": "MODULE_LOADED", "build_id": "expected",
                "module_instance_id": "current-instance", "runtime_root": str(paths["root"]),
            }), encoding="utf-8")
            paths["error"].write_text(json.dumps({
                "build_id": "expected", "module_instance_id": "current-instance",
                "stage": "PROJECT_IMPORT",
            }), encoding="utf-8")
            result = inspect_controller_lifecycle(controller, "expected", now=NOW)
        self.assertEqual(result["verification"], "STOP")

    def test_bootstrap_error_is_serialized_without_daW_api_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            module = load_live_controller(Path(directory))
            module.CONTROLLER_BUILD_ID = "expected-build"
            module._record_bootstrap_error("PROJECT_IMPORT", RuntimeError("safe diagnostic"))
            payload = json.loads(module.BOOTSTRAP_ERROR_FILE.read_text(encoding="utf-8"))
        self.assertEqual(payload["build_id"], "expected-build")
        self.assertEqual(payload["stage"], "PROJECT_IMPORT")
        self.assertEqual(payload["exception_type"], "RuntimeError")
        self.assertNotIn("private", payload["safe_message"].lower())

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
            error = json.loads(module.BOOTSTRAP_ERROR_FILE.read_text(encoding="utf-8"))
            self.assertTrue(error["stage"].startswith("ON_INIT_STATUS_WRITE"))

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
