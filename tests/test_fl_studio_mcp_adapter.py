import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dawloop.adapters.fl_studio_mcp import FLStudioMCPAdapter, TargetIdentity
from dawloop.adapters.fl_studio_mcp.identity import require_same_target
from dawloop.adapters.fl_studio_mcp.mapping import plan_to_mcp_notes, state_to_events
from dawloop.note_plan import NoteEvent, NotePlan
from dawloop.setup import configured_scripts, install_user_scripts, user_script_status
from dawloop.time import MusicalGrid


def sample_plan() -> NotePlan:
    return NotePlan(
        target_id="test-pattern",
        grid=MusicalGrid(ppq=480, beats_per_bar=4, beat_unit=4),
        section_start_tick=0,
        section_bars=1,
        events=(
            NoteEvent(0, 120, 60, 64),
            NoteEvent(120, 120, 64, 96),
            NoteEvent(240, 240, 67, 127),
            NoteEvent(0, 120, 60, 64),
        ),
    )


class FLStudioMCPAdapterTests(unittest.TestCase):
    def test_maps_plan_to_quarter_note_units_without_losing_duplicates(self):
        notes = plan_to_mcp_notes(sample_plan())
        self.assertEqual(len(notes), 4)
        self.assertEqual(notes[0], {"midi": 60, "time": 0.0, "duration": 0.25, "velocity": 64 / 127})
        self.assertEqual(notes[0], notes[3])

    def test_reads_exact_ticks_and_normalized_velocity(self):
        events = state_to_events({
            "ppq": 480,
            "notes": [
                {"midi": 60, "time_ticks": 0, "length_ticks": 120, "velocity": 64 / 127},
                {"midi": 60, "time_ticks": 0, "length_ticks": 120, "velocity": 64 / 127},
            ],
        }, 480)
        self.assertEqual(events, (NoteEvent(0, 120, 60, 64),) * 2)

    def test_stops_when_live_pattern_identity_is_not_available(self):
        plan = sample_plan()
        target = TargetIdentity("test-project", "test-pattern", 0, "Test", "unknown")
        report = asyncio.run(FLStudioMCPAdapter().execute(plan, target))
        self.assertEqual(report.status, "STOP")
        self.assertTrue(any("身份读取器" in error for error in report.errors))

    def test_rejects_channel_or_pattern_identity_change(self):
        expected = TargetIdentity("project", "pattern", 1, "Synth", "FL 2026", 1, 96, True, 38)
        actual = TargetIdentity("project", "other-pattern", 1, "Synth", "FL 2026", 1, 96, True, 38)
        with self.assertRaises(ValueError):
            require_same_target(expected, actual)

    def test_installer_creates_one_primary_controller_and_preserves_vendor_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "vendor"
            settings = root / "settings"
            config_path = root / "config.json"
            controller = vendor / "fl_controller" / "device_FLStudioMCP.py"
            piano_roll = vendor / "scripts" / "ComposeWithLLM.pyscript"
            controller.parent.mkdir(parents=True)
            piano_roll.parent.mkdir(parents=True)
            license_file = vendor / "LICENSE"
            license_file.parent.mkdir(parents=True, exist_ok=True)
            controller.write_text("upstream controller", encoding="utf-8")
            piano_roll.write_text("upstream piano roll", encoding="utf-8")
            license_file.write_text("upstream MIT notice", encoding="utf-8")
            paths = configured_scripts(settings)
            existing = paths["controller"]
            existing.parent.mkdir(parents=True)
            existing.write_text("# name=DAWLoop Controller\nold managed controller", encoding="utf-8")

            with patch("dawloop.setup._vendor_root", return_value=vendor), \
                    patch("dawloop.setup._config_path", return_value=config_path):
                installed = install_user_scripts(settings)

            self.assertEqual(len(installed), 4)
            self.assertIn(paths["controller"], installed)
            self.assertIn(
                "# name=DAWLoop Controller",
                paths["controller"].read_text(encoding="utf-8"),
            )
            self.assertIn("# supportedDevices=DAWLoop MCP IN,FLSkill MCP IN", paths["controller"].read_text(encoding="utf-8"))
            self.assertIn("SETTINGS_DIR_OVERRIDE = Path(", paths["controller"].read_text(encoding="utf-8"))
            self.assertEqual(paths["backend"].read_text(encoding="utf-8"), "upstream controller")
            self.assertEqual(paths["license"].read_text(encoding="utf-8"), "upstream MIT notice")
            self.assertFalse(paths["legacy_identity_controller"].exists())
            backups = list(existing.parent.glob("device_DAWLoopController.py.bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertIn("old managed controller", backups[0].read_text(encoding="utf-8"))
            self.assertEqual(user_script_status(settings), {
                "controller": True, "backend": True, "license": True,
                "identity_controller": False, "piano_roll": True,
            })

    def test_installer_replaces_transitional_identity_in_place_with_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "vendor"
            settings = root / "settings"
            (vendor / "fl_controller").mkdir(parents=True)
            (vendor / "scripts").mkdir()
            (vendor / "fl_controller" / "device_FLStudioMCP.py").write_text("upstream", encoding="utf-8")
            (vendor / "scripts" / "ComposeWithLLM.pyscript").write_text("piano", encoding="utf-8")
            (vendor / "LICENSE").write_text("license", encoding="utf-8")
            legacy_controller = settings / "Hardware" / "DAWLoopMCP" / "device_DAWLoopMCP.py"
            legacy_controller.parent.mkdir(parents=True)
            legacy_controller.write_text("# name=DAWLoop MCP Controller\nlegacy", encoding="utf-8")
            with patch("dawloop.setup._vendor_root", return_value=vendor), \
                    patch("dawloop.setup._config_path", return_value=root / "config.json"):
                install_user_scripts(settings)
            installed_path = legacy_controller
            self.assertTrue(installed_path.read_text(encoding="utf-8").startswith("# name=DAWLoop Controller"))
            self.assertEqual(len(list(installed_path.parent.glob("device_*.py"))), 1)
            self.assertEqual(user_script_status(settings)["identity_controller"], False)
            self.assertTrue(list(installed_path.parent.glob("device_DAWLoopMCP.py.bak-*")))

    def test_installer_stops_on_arbitrary_controller_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "vendor"
            settings = root / "settings"
            (vendor / "fl_controller").mkdir(parents=True)
            (vendor / "scripts").mkdir()
            (vendor / "fl_controller" / "device_FLStudioMCP.py").write_text("upstream", encoding="utf-8")
            (vendor / "scripts" / "ComposeWithLLM.pyscript").write_text("upstream", encoding="utf-8")
            (vendor / "LICENSE").write_text("license", encoding="utf-8")
            collision = configured_scripts(settings)["controller"]
            collision.parent.mkdir(parents=True)
            collision.write_text("# name=Personal Controller\n", encoding="utf-8")
            with patch("dawloop.setup._vendor_root", return_value=vendor), \
                    patch("dawloop.setup._config_path", return_value=root / "config.json"):
                with self.assertRaisesRegex(FileExistsError, "不属于 DAWLoop 管理"):
                    install_user_scripts(settings)
            self.assertEqual(collision.read_text(encoding="utf-8"), "# name=Personal Controller\n")


if __name__ == "__main__":
    unittest.main()
