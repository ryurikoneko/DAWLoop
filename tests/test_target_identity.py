import asyncio
import importlib.util
import sys
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

    def test_timeout_and_unrecognized_controller_responses_fail_closed(self):
        for response in (
            {"success": False, "error": "Timeout"},
            {"success": True, "error": "Unknown action: dawloop.getTargetIdentity"},
            {"success": True, "target": []},
        ):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    identity_from_response(response)

    def test_reader_uses_existing_midi_json_transport(self):
        calls = []

        def send_command(action, *, timeout):
            calls.append((action, timeout))
            return {"success": True, "target": PAYLOAD}

        connection = types.SimpleNamespace(send_command=send_command)
        with patch("fl_studio_mcp.utils.connection.get_connection", return_value=connection):
            target = asyncio.run(read_current_target())
        self.assertEqual(calls, [("dawloop.getTargetIdentity", 3.0)])
        self.assertEqual(target.pattern_number, 1)


class ReadOnlyUserScriptTests(unittest.TestCase):
    def test_identity_request_does_not_delegate_or_mutate(self):
        calls = []
        action = ["dawloop.getTargetIdentity"]
        command = types.SimpleNamespace(read_text=lambda **_: '{"action":"' + action[0] + '"}')
        upstream = types.SimpleNamespace(
            TRIGGER_NOTE=127, COMMAND_FILE=command,
            write_response=lambda response: calls.append(("response", response)),
            OnMidiMsg=lambda event: calls.append(("delegated", event)),
        )
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
            "device_FLStudioMCP": upstream,
        }
        path = Path(__file__).resolve().parents[1] / "src" / "dawloop" / "fl_scripts" / "device_DAWLoopMCP.py"
        spec = importlib.util.spec_from_file_location("dawloop_script_under_test", path)
        script = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(script)
            event = types.SimpleNamespace(midiId=0x90, data1=127, data2=127, handled=False)
            script.OnMidiMsg(event)
            action[0] = "transport.getStatus"
            script.OnMidiMsg(event)
        self.assertTrue(event.handled)
        self.assertEqual([name for name, _ in calls], ["response", "delegated"])
        self.assertEqual(calls[0][1]["target"]["pattern_number"], 1)
        self.assertEqual(calls[0][1]["target"]["channel_index_type"], "global")


if __name__ == "__main__":
    unittest.main()
