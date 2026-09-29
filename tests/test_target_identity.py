import asyncio
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from dawloop.adapters.fl_studio_mcp.identity import identity_from_response, read_current_target


PAYLOAD = {
    "source": "fl_studio_midi_scripting",
    "project_title": "DAWLoop_Live_Verification",
    "pattern_number": 1,
    "pattern_name": "DAWLoop Live Test",
    "channel_index": 0,
    "channel_name": "DAWLoop Test",
    "channel_index_type": "global",
    "ppq": 96,
    "safe_to_edit": True,
    "api_version": 38,
    "fl_studio_version": "FL Studio 26",
}


class TargetIdentityPayloadTests(unittest.TestCase):
    def test_complete_payload_has_explicit_global_index_and_observation_clock(self):
        target = identity_from_response({"success": True, "target": PAYLOAD})
        self.assertEqual((target.pattern_number, target.channel_index, target.ppq), (1, 0, 96))
        self.assertEqual(target.channel_index_type, "global")
        self.assertTrue(target.observed_at_utc)

    def test_missing_and_malformed_values_fail_closed(self):
        cases = (
            ("pattern_number", None), ("pattern_number", "1"),
            ("pattern_number", True), ("pattern_number", 0),
            ("pattern_name", None), ("channel_index", -1),
            ("channel_index", "0"), ("channel_index_type", "grouped"),
            ("ppq", 0), ("ppq", "96"), ("safe_to_edit", None),
            ("api_version", None), ("project_title", ""),
        )
        for key, value in cases:
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError):
                    identity_from_response({"success": True, "target": {**PAYLOAD, key: value}})

    def test_unavailable_or_malformed_responses_fail_closed(self):
        for response in (
            {"success": False, "error": "Timeout"},
            {"success": True, "error": "Unknown action: dawloop.getTargetIdentity"},
            {"success": True, "target": []},
        ):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    identity_from_response(response)

    def test_reader_uses_shared_rpc_and_explicit_settings_directory(self):
        calls = []

        class FakeConnection:
            def __init__(self):
                self._hardware_dir = None
                self._command_file = None
                self._response_file = None

            def send_command(self, action, params, timeout):
                calls.append((action, params.copy(), timeout, self._hardware_dir))
                return {"success": True, "target": PAYLOAD, "request_id": params["request_id"]}

            def disconnect(self):
                calls.append("disconnect")

        module = types.SimpleNamespace(MIDIConnection=FakeConnection)
        with tempfile.TemporaryDirectory() as directory:
            settings_dir = Path(directory)
            with patch.dict(sys.modules, {"fl_studio_mcp.utils.midi_connection": module}):
                target = asyncio.run(read_current_target("DAWLoop MCP IN 1", settings_dir=settings_dir))
        self.assertEqual(target.pattern_number, 1)
        self.assertEqual(calls[0][0], "dawloop.getTargetIdentity")
        self.assertEqual(calls[0][3], settings_dir / "Hardware" / "DAWLoopMCP")
        self.assertEqual(calls[-1], "disconnect")

    def test_reader_requires_port_and_correlated_response(self):
        with self.assertRaisesRegex(ValueError, "MIDI_PORT_REQUIRED"):
            asyncio.run(read_current_target(""))

        class FakeConnection:
            def __init__(self):
                self._hardware_dir = None
                self._command_file = None
                self._response_file = None

            def send_command(self, *args):
                return {"success": True, "target": PAYLOAD, "request_id": "wrong"}

            def disconnect(self):
                pass

        module = types.SimpleNamespace(MIDIConnection=FakeConnection)
        with patch.dict(sys.modules, {"fl_studio_mcp.utils.midi_connection": module}):
            with self.assertRaisesRegex(ValueError, "TARGET_IDENTITY_NOT_AVAILABLE"):
                asyncio.run(read_current_target("DAWLoop MCP IN 1"))


class PrimaryControllerTests(unittest.TestCase):
    def test_identity_uses_primary_controller_and_regular_commands_delegate(self):
        modules = {
            "channels": types.SimpleNamespace(
                selectedChannel=lambda *args: 0,
                getChannelName=lambda *args: "DAWLoop Test",
            ),
            "patterns": types.SimpleNamespace(
                patternNumber=lambda: 1,
                getPatternName=lambda number: "DAWLoop Live Test",
            ),
            "general": types.SimpleNamespace(
                getProjectTitle=lambda: "DAWLoop_Live_Verification",
                getRecPPQ=lambda: 96, safeToEdit=lambda: 1,
                getVersion=lambda: 38,
            ),
            "ui": types.SimpleNamespace(getVersion=lambda mode: "FL Studio 26"),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = root / "upstream_backend.py"
            upstream.write_text(
                "TRIGGER_NOTE=127\n"
                "def OnInit(): pass\n"
                "def OnDeInit(): pass\n"
                "def OnMidiMsg(event): event.forwarded = True\n",
                encoding="utf-8",
            )
            path = Path(__file__).resolve().parents[1] / "src" / "dawloop" / "fl_scripts" / "device_DAWLoopController.py"
            source = path.read_text(encoding="utf-8").replace(
                "UPSTREAM_SCRIPT_OVERRIDE = None",
                f"UPSTREAM_SCRIPT_OVERRIDE = Path({str(upstream)!r})",
            )
            wrapper = root / "device_DAWLoopController.py"
            wrapper.write_text(source, encoding="utf-8")
            spec = importlib.util.spec_from_file_location("dawloop_script_under_test", wrapper)
            script = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, modules):
                spec.loader.exec_module(script)
                script.SCRIPT_DIR = root
                script.COMMAND_FILE = root / "mcp_command.json"
                script.RESPONSE_FILE = root / "mcp_response.json"
                script.COMMAND_FILE.write_text(json.dumps({
                    "action": "dawloop.getTargetIdentity",
                    "params": {"request_id": "request-1"},
                }), encoding="utf-8")
                identity_event = types.SimpleNamespace(midiId=0x90, data1=127, data2=127, handled=False)
                script.OnMidiMsg(identity_event)
                identity_response = json.loads(script.RESPONSE_FILE.read_text(encoding="utf-8"))
                script.COMMAND_FILE.write_text(
                    '{"action":"transport.getStatus","params":{}}', encoding="utf-8"
                )
                regular_event = types.SimpleNamespace(midiId=0x90, data1=127, data2=127, handled=False)
                script.OnMidiMsg(regular_event)
        self.assertTrue(identity_event.handled)
        self.assertEqual(identity_response["target"]["pattern_number"], 1)
        self.assertEqual(identity_response["target"]["channel_index_type"], "global")
        self.assertEqual(identity_response["request_id"], "request-1")
        self.assertTrue(regular_event.forwarded)

    def test_identity_error_response_keeps_request_correlation(self):
        modules = {
            "channels": types.SimpleNamespace(selectedChannel=lambda *args: 0, getChannelName=lambda *args: "Test"),
            "patterns": types.SimpleNamespace(patternNumber=lambda: 1, getPatternName=lambda number: "Test"),
            "general": types.SimpleNamespace(getProjectTitle=lambda: "Test", getRecPPQ=lambda: 96, safeToEdit=lambda: 1, getVersion=lambda: 38),
            "ui": types.SimpleNamespace(getVersion=lambda mode: "FL Studio 26"),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = root / "upstream_backend.py"
            upstream.write_text("TRIGGER_NOTE=127\ndef OnInit(): pass\ndef OnDeInit(): pass\ndef OnMidiMsg(event): pass\n", encoding="utf-8")
            source_path = Path(__file__).resolve().parents[1] / "src" / "dawloop" / "fl_scripts" / "device_DAWLoopController.py"
            source = source_path.read_text(encoding="utf-8").replace("UPSTREAM_SCRIPT_OVERRIDE = None", f"UPSTREAM_SCRIPT_OVERRIDE = Path({str(upstream)!r})")
            wrapper = root / "controller.py"
            wrapper.write_text(source, encoding="utf-8")
            spec = importlib.util.spec_from_file_location("dawloop_identity_error_test", wrapper)
            script = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, modules):
                spec.loader.exec_module(script)
                script.COMMAND_FILE = root / "mcp_command.json"
                script.RESPONSE_FILE = root / "mcp_response.json"
                script.COMMAND_FILE.write_text(json.dumps({"action": "dawloop.getTargetIdentity", "params": {"request_id": "r-2"}}), encoding="utf-8")
                with patch.object(script, "_target_identity", side_effect=RuntimeError("unavailable")):
                    script._handle_identity_request()
                response = json.loads(script.RESPONSE_FILE.read_text(encoding="utf-8"))
        self.assertFalse(response["success"])
        self.assertEqual(response["request_id"], "r-2")


if __name__ == "__main__":
    unittest.main()
