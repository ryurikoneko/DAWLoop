import unittest
import importlib
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
from io import StringIO

from dawloop.cli import _setup_fl
from dawloop.midi_setup import (
    inspect_loopmidi, inspect_midi_ports, logical_port_name, select_midi_output,
)


class MidiPortInspectionTests(unittest.TestCase):
    def test_normalizes_backend_port_index_suffix(self):
        self.assertEqual(logical_port_name("DAWLoop MCP IN 2"), "DAWLoop MCP IN")

    def test_detects_canonical_ports(self):
        result = inspect_midi_ports(
            ["DAWLoop MCP OUT 1"], ["DAWLoop MCP IN 2"]
        )
        self.assertEqual(result["names_status"], "PASS")
        self.assertEqual(result["selected_python_output"], "DAWLoop MCP IN 2")

    def test_detects_legacy_names_and_canonical_names_together(self):
        legacy = inspect_midi_ports(
            ["FLSkill MCP OUT 1"], ["FLSkill MCP IN 2"]
        )
        both = inspect_midi_ports(
            ["DAWLoop MCP OUT 1", "FLSkill MCP OUT 2"],
            ["DAWLoop MCP IN 3", "FLSkill MCP IN 4"],
        )
        self.assertEqual(legacy["names_status"], "LEGACY_MIDI_PORT_NAMES")
        self.assertEqual(legacy["selected_python_output"], "FLSkill MCP IN 2")
        self.assertEqual(both["names_status"], "BOTH_PRESENT")

    def test_partial_or_missing_ports_fail_closed(self):
        self.assertEqual(inspect_midi_ports([], ["DAWLoop MCP IN 1"])["names_status"], "PARTIAL_MIDI_PORTS")
        self.assertEqual(inspect_midi_ports([], [])["names_status"], "DAWLOOP_MIDI_PORT_MISSING")
        self.assertIsNone(select_midi_output(["loopMIDI Port 1", "Microsoft GS Wavetable Synth 2"]))

    def test_loopmidi_missing_and_stopped_are_distinct(self):
        with patch("dawloop.midi_setup.locate_loopmidi_executable", return_value=None), \
                patch("dawloop.midi_setup.loopmidi_process_running", return_value=False), \
                patch("dawloop.midi_setup.loopmidi_autostart_status", return_value="LOOPMIDI_AUTOSTART_NOT_CONFIRMED"):
            result = inspect_loopmidi([], [])
        self.assertFalse(result["installed"])
        self.assertFalse(result["running"])
        self.assertEqual(result["autostart"], "LOOPMIDI_AUTOSTART_NOT_CONFIRMED")

    def test_process_detection_is_case_insensitive(self):
        result = type("Result", (), {"returncode": 0, "stdout": '"loopMIDI.exe","123"'})()
        with patch("dawloop.midi_setup.subprocess.run", return_value=result):
            from dawloop.midi_setup import loopmidi_process_running
            self.assertTrue(loopmidi_process_running())


class SetupSafetyTests(unittest.TestCase):
    def test_dry_run_does_not_install_or_create_files(self):
        with TemporaryDirectory() as directory:
            settings = Path(directory) / "not-created"
            report = {"dry_run": True, "would_install": ["controller"]}
            output = StringIO()
            with patch("dawloop.cli._fl_setup_report", return_value=report), \
                    patch("dawloop.setup.install_user_scripts", side_effect=AssertionError("install called")), \
                    redirect_stdout(output):
                result = _setup_fl(settings, True)
            self.assertEqual(result, 0)
            self.assertFalse(settings.exists())
            self.assertIn('"files_changed": false', output.getvalue())

    def test_setup_modules_do_not_call_daw_write_apis(self):
        root = Path(__file__).resolve().parents[1] / "src" / "dawloop"
        sources = (root / "setup.py").read_text(encoding="utf-8") + \
            (root / "midi_setup.py").read_text(encoding="utf-8") + \
            (root / "fl_mcp_server.py").read_text(encoding="utf-8")
        for token in ("mixer.setTrack", "plugins.setParam", "pianoRoll", "patterns.createPattern", "channels.setChannel"):
            with self.subTest(token=token):
                self.assertNotIn(token, sources)

    def test_controller_declares_canonical_and_legacy_binding(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "dawloop" / "fl_scripts" / "device_DAWLoopController.py").read_text(encoding="utf-8")
        self.assertIn("# name=DAWLoop Controller", source)
        self.assertIn("# supportedDevices=DAWLoop MCP IN,FLSkill MCP IN", source)

    def test_bundled_backend_selects_only_dawloop_or_legacy_input_port(self):
        module = importlib.import_module("fl_studio_mcp.utils.midi_connection")
        original_hardware_dir = module._get_fl_hardware_dir
        opened = []

        class FakeConnection:
            def __init__(self):
                self._connected = False
                self._port = None
                self._error = None
                self._port_name = None

            @property
            def is_connected(self):
                return self._connected

        midi = type("Mido", (), {
            "get_output_names": staticmethod(lambda: ["Microsoft Synth 0", "FLSkill MCP IN 2"]),
            "open_output": staticmethod(lambda name: opened.append(name) or object()),
        })
        with patch.object(module, "MIDIConnection", FakeConnection), \
                patch.dict("sys.modules", {"mido": midi}):
            from dawloop.fl_mcp_server import _configure_bundled_transport
            try:
                _configure_bundled_transport()
                connection = FakeConnection()
                self.assertTrue(connection.connect())
            finally:
                module._get_fl_hardware_dir = original_hardware_dir
        self.assertEqual(opened, ["FLSkill MCP IN 2"])
        self.assertEqual(connection._port_name, "FLSkill MCP IN 2")


if __name__ == "__main__":
    unittest.main()
