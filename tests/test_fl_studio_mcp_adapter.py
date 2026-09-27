import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flskill.adapters.fl_studio_mcp import FLStudioMCPAdapter, TargetIdentity
from flskill.adapters.fl_studio_mcp.identity import require_same_target
from flskill.adapters.fl_studio_mcp.mapping import plan_to_mcp_notes, state_to_events
from flskill.note_plan import NoteEvent, NotePlan
from flskill.setup import install_user_scripts, user_script_status
from flskill.time import MusicalGrid


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
        expected = TargetIdentity("project", "pattern", 1, "Synth", "FL 2026")
        actual = TargetIdentity("project", "other-pattern", 1, "Synth", "FL 2026")
        with self.assertRaises(ValueError):
            require_same_target(expected, actual)

    def test_installer_backs_up_existing_upstream_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "vendor"
            settings = root / "settings"
            controller = vendor / "fl_controller" / "device_FLStudioMCP.py"
            piano_roll = vendor / "scripts" / "ComposeWithLLM.pyscript"
            controller.parent.mkdir(parents=True)
            piano_roll.parent.mkdir(parents=True)
            controller.write_text("upstream controller", encoding="utf-8")
            piano_roll.write_text("upstream piano roll", encoding="utf-8")
            existing = settings / "Hardware" / "FLStudioMCP" / controller.name
            existing.parent.mkdir(parents=True)
            existing.write_text("user customized", encoding="utf-8")

            with patch("flskill.setup._vendor_root", return_value=vendor):
                installed = install_user_scripts(settings)

            self.assertEqual(len(installed), 2)
            self.assertEqual(existing.read_text(encoding="utf-8"), "upstream controller")
            backups = list(existing.parent.glob("device_FLStudioMCP.py.bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "user customized")
            self.assertEqual(user_script_status(settings), {"controller": True, "piano_roll": True})


if __name__ == "__main__":
    unittest.main()
