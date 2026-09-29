import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from dawloop.adapters.fl_studio_mcp import FLStudioMCPAdapter, TargetIdentity
from dawloop.adapters.fl_studio_mcp import adapter as adapter_module
from dawloop.note_plan import NoteEvent


CAPTURE_PATH = Path(__file__).parent / "live_fl" / "capture_note_roundtrip.py"
SPEC = importlib.util.spec_from_file_location("capture_note_roundtrip_for_tests", CAPTURE_PATH)
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)
TARGET = TargetIdentity(
    capture.PROJECT_NAME, capture.PATTERN_NAME, 0, capture.CHANNEL_NAME, "FL Studio 26"
)
EVIDENCE_NAMES = {
    "environment.json", "target_identity.json", "plan.json", "pre_state.json",
    "execution.json", "readback.json", "verification.json", "README.md",
}


async def connected():
    return True, "connected"


def clean_git(arguments, **_kwargs):
    if arguments[1] == "status":
        value = ""
    elif arguments[1] == "branch":
        value = "feature/live-note-evidence-capture\n"
    else:
        value = "a" * 40 + "\n"
    return subprocess.CompletedProcess(arguments, 0, value, "")


class SimulatedAdapter:
    def __init__(self, mode="pass"):
        self.mode = mode
        self.calls = 0

    async def execute(self, plan, target, identity_reader, evidence_observer):
        self.calls += 1
        evidence_observer("target_before", target.to_dict())
        evidence_observer("pre_state", {
            "ppq": plan.grid.ppq,
            "note_count": 1 if self.mode == "nonblank" else 0,
            "state_mtime_before_ns": 10,
            "state_mtime_after_ns": 11,
        })
        if self.mode == "nonblank":
            return adapter_module._report(plan, target, errors=("unsafe",))
        evidence_observer("write_attempt", {"requested_count": len(plan.events)})
        if self.mode == "write_fail":
            return adapter_module._report(plan, target, errors=("C:\\Users\\ExampleUser\\error",))
        evidence_observer("write_queued", {"accepted": True})
        evidence_observer("target_before_trigger", target.to_dict())
        if self.mode == "read_fail":
            return adapter_module._report(plan, target, errors=("read failed",))
        if self.mode == "backend_only":
            return replace(adapter_module._report(plan, target), status="PASS")

        actual = list(plan.events)
        if self.mode == "missing":
            actual.pop()
        elif self.mode == "unexpected":
            actual.append(NoteEvent(300, 12, 55, 70))
        elif self.mode == "duplicate":
            actual.append(plan.events[0])
        evidence_observer("target_after", target.to_dict())
        evidence_observer("readback", {
            "events": [event.to_dict() for event in actual],
            "state_mtime_before_ns": 20,
            "state_mtime_after_ns": 21,
        })
        report = adapter_module._report(plan, target, tuple(actual))
        return replace(report, status="PASS") if self.mode == "pass" else report


class CaptureEvidenceTests(unittest.TestCase):
    def run_capture(self, reader=lambda: TARGET, ppq=96, mode="pass"):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        backend = SimulatedAdapter(mode)
        with patch.object(capture.subprocess, "run", side_effect=clean_git):
            run_dir = asyncio.run(capture.capture_note_roundtrip(
                reader, ppq, Path(directory.name) / "evidence", adapter=backend,
                connection_probe=connected,
            ))
        artifacts = {
            name: json.loads((run_dir / name).read_text(encoding="utf-8"))
            for name in EVIDENCE_NAMES if name.endswith(".json")
        }
        return backend, run_dir, artifacts

    def test_requires_identity_reader_before_write(self):
        def unavailable():
            raise RuntimeError("identity unavailable")

        backend, _, files = self.run_capture(reader=unavailable)
        self.assertEqual(backend.calls, 0)
        self.assertEqual(files["verification.json"]["status"], "STOP")
        self.assertEqual(files["verification.json"]["error_code"], "PATTERN_IDENTITY_READER_MISSING")
        self.assertIsNone(files["verification.json"]["actual_count"])

    def test_rejects_wrong_pattern_and_channel_before_write(self):
        for wrong in (
            TargetIdentity(TARGET.project_id, "Other Pattern", 0, TARGET.channel_name, TARGET.fl_studio_version),
            TargetIdentity(TARGET.project_id, TARGET.pattern_id, 0, "Other Channel", TARGET.fl_studio_version),
        ):
            with self.subTest(wrong=wrong):
                backend, _, files = self.run_capture(reader=lambda: wrong)
                self.assertEqual(backend.calls, 0)
                self.assertEqual(files["verification.json"]["status"], "STOP")

    def test_rejects_invalid_ppq_with_null_comparison(self):
        backend, _, files = self.run_capture(ppq=3)
        result = files["verification.json"]
        self.assertEqual(backend.calls, 0)
        self.assertEqual(result["status"], "STOP")
        self.assertEqual(result["failure_stage"], "plan")
        self.assertIsNone(result["planned_count"])
        self.assertIsNone(result["actual_count"])

    def test_dirty_worktree_stops_before_live_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = SimulatedAdapter()

            def dirty_git(arguments, **kwargs):
                if arguments[1] == "status":
                    return subprocess.CompletedProcess(arguments, 0, " M src/dawloop/example.py\n", "")
                return clean_git(arguments, **kwargs)

            with patch.object(capture.subprocess, "run", side_effect=dirty_git):
                run_dir = asyncio.run(capture.capture_note_roundtrip(
                    lambda: TARGET, 96, Path(directory) / "evidence", adapter=backend,
                    connection_probe=connected,
                ))
            result = json.loads((run_dir / "verification.json").read_text(encoding="utf-8"))
            environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
            self.assertEqual(backend.calls, 0)
            self.assertEqual(result["error_code"], "DIRTY_OR_UNAVAILABLE_GIT_WORKTREE")
            self.assertTrue(environment["dirty_worktree"])

    def test_source_change_during_attempt_invalidates_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            status_calls = 0

            def changing_git(arguments, **kwargs):
                nonlocal status_calls
                if arguments[1] == "status":
                    status_calls += 1
                    if status_calls > 1:
                        return subprocess.CompletedProcess(arguments, 0, " M README.md\n", "")
                return clean_git(arguments, **kwargs)

            with patch.object(capture.subprocess, "run", side_effect=changing_git):
                run_dir = asyncio.run(capture.capture_note_roundtrip(
                    lambda: TARGET, 96, Path(directory) / "evidence",
                    adapter=SimulatedAdapter(), connection_probe=connected,
                ))
            result = json.loads((run_dir / "verification.json").read_text(encoding="utf-8"))
            environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "STOP")
            self.assertEqual(result["error_code"], "SOURCE_CHANGED_DURING_RUN")
            self.assertEqual(result["actual_count"], 4)
            self.assertTrue(result["comparison_performed"])
            self.assertTrue(environment["dirty_worktree"])

    def test_rejects_nonblank_target(self):
        _, _, files = self.run_capture(mode="nonblank")
        self.assertEqual(files["verification.json"]["failure_stage"], "pre_state_nonempty")
        self.assertFalse(files["execution.json"]["write_attempted"])

    def test_write_and_fresh_readback_failures_do_not_fake_empty_differences(self):
        for mode in ("write_fail", "read_fail", "backend_only"):
            with self.subTest(mode=mode):
                _, _, files = self.run_capture(mode=mode)
                result = files["verification.json"]
                self.assertEqual(result["status"], "STOP")
                self.assertIsNone(result["actual_count"])
                for field in ("missing", "extra", "unexpected", "duplicate_mismatches", "mismatches"):
                    self.assertIsNone(result[field])
                self.assertFalse(result["comparison_performed"])

    def test_exact_match_passes_and_writes_eight_files(self):
        _, run_dir, files = self.run_capture()
        self.assertEqual({item.name for item in run_dir.iterdir()}, EVIDENCE_NAMES)
        result = files["verification.json"]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual((result["planned_count"], result["actual_count"]), (4, 4))
        self.assertEqual((result["missing"], result["unexpected"]), ([], []))
        self.assertTrue(result["comparison_performed"])
        self.assertEqual(files["environment.json"]["commit_sha"], "a" * 40)
        self.assertFalse(files["environment.json"]["dirty_worktree"])
        self.assertTrue(files["readback.json"]["observed"])

    def test_missing_unexpected_and_duplicate_counts_stop(self):
        for mode, field in (("missing", "missing"), ("unexpected", "unexpected"), ("duplicate", "duplicate_mismatches")):
            with self.subTest(mode=mode):
                _, _, files = self.run_capture(mode=mode)
                result = files["verification.json"]
                self.assertEqual(result["status"], "STOP")
                self.assertTrue(result["comparison_performed"])
                self.assertTrue(result[field])

    def test_error_text_and_local_path_are_not_archived(self):
        _, run_dir, _ = self.run_capture(mode="write_fail")
        text = "\n".join(path.read_text(encoding="utf-8") for path in run_dir.iterdir())
        self.assertNotIn("C:\\Users\\ExampleUser", text)
        self.assertNotIn(str(run_dir.parent), text)


class SimulatedMCP:
    def __init__(self, state_file: Path, mode: str):
        self.state_file = state_file
        self.mode = mode
        self.calls = []
        self.queued = False
        self.written = False
        self.clock = state_file.stat().st_mtime_ns

    async def call(self, _client, name, arguments=None):
        self.calls.append(name)
        if name == "fl_get_selected_channel":
            return {"index": 0, "name": "Wrong Channel" if self.mode == "channel_mismatch" else capture.CHANNEL_NAME}
        if name == "fl_get_piano_roll_info":
            return {"state_file": str(self.state_file), "request_file_exists": False}
        if name == "fl_trigger_script":
            if self.mode == "backend_only" and self.queued:
                return "Failed to trigger FL Studio"
            self.clock += 1_000_000_000
            os.utime(self.state_file, ns=(self.clock, self.clock))
            if self.queued:
                self.written = True
            return "FL Studio triggered successfully"
        if name == "fl_get_piano_roll_state":
            if self.mode == "read_fail" and self.written:
                raise RuntimeError("read failed")
            notes = []
            if self.mode == "nonblank" or self.written:
                notes = [{"midi": 60, "time_ticks": 0, "length_ticks": 48, "velocity": 64 / 127}]
            return {"ppq": 97 if self.mode == "ppq_mismatch" else 96, "notes": notes}
        if name == "fl_send_notes":
            if self.mode == "write_fail":
                raise RuntimeError("write failed")
            self.queued = True
            return "Queued 4 note(s)"
        if name == "fl_clear_request_queue":
            self.queued = False
            return "Request queue cleared."
        raise AssertionError(name)


class LiveAdapterGateTests(unittest.TestCase):
    def execute_simulated(self, mode="pass", reader=lambda: TARGET):
        with tempfile.TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            state_file.write_text("{}", encoding="utf-8")
            simulated = SimulatedMCP(state_file, mode)

            class Client:
                def __init__(self, *_args, **_kwargs):
                    pass

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *_args):
                    return False

            with patch.dict(sys.modules, {"fastmcp": types.SimpleNamespace(Client=Client)}), \
                    patch.object(adapter_module, "_server_script", return_value=Path("unused")), \
                    patch.object(adapter_module, "_call", side_effect=simulated.call):
                report = asyncio.run(FLStudioMCPAdapter().execute(
                    capture.synthetic_plan(96), TARGET, reader,
                ))
            return report, simulated.calls

    def test_pattern_and_channel_identity_mismatch_stop_before_write(self):
        wrong_pattern = TargetIdentity(
            TARGET.project_id, "Other Pattern", 0, TARGET.channel_name, TARGET.fl_studio_version
        )
        for mode, reader in (("pass", lambda: wrong_pattern), ("channel_mismatch", lambda: TARGET)):
            with self.subTest(mode=mode):
                report, calls = self.execute_simulated(mode, reader)
                self.assertEqual(report.status, "STOP")
                self.assertNotIn("fl_send_notes", calls)

    def test_ppq_and_nonblank_state_stop_before_write(self):
        for mode in ("ppq_mismatch", "nonblank"):
            with self.subTest(mode=mode):
                report, calls = self.execute_simulated(mode)
                self.assertEqual(report.status, "STOP")
                self.assertNotIn("fl_send_notes", calls)

    def test_backend_write_and_readback_failures_stop(self):
        for mode in ("write_fail", "read_fail", "backend_only"):
            with self.subTest(mode=mode):
                report, calls = self.execute_simulated(mode)
                self.assertEqual(report.status, "STOP")
                self.assertIn("fl_send_notes", calls)

    def test_adapter_requests_independent_post_write_readback(self):
        report, calls = self.execute_simulated()
        self.assertEqual(calls.count("fl_trigger_script"), 2)
        self.assertEqual(calls.count("fl_get_piano_roll_state"), 2)
        write_at = calls.index("fl_send_notes")
        trigger_after_write = calls.index("fl_trigger_script", write_at)
        read_after_write = calls.index("fl_get_piano_roll_state", write_at)
        self.assertLess(write_at, trigger_after_write)
        self.assertLess(trigger_after_write, read_after_write)
        self.assertEqual(report.status, "STOP")
        self.assertTrue(report.missing)

    def test_target_change_after_queue_clears_queue_without_triggering_write(self):
        wrong_pattern = TargetIdentity(
            TARGET.project_id, "Other Pattern", 0, TARGET.channel_name, TARGET.fl_studio_version
        )
        reads = 0

        def changing_reader():
            nonlocal reads
            reads += 1
            return wrong_pattern if reads == 3 else TARGET

        report, calls = self.execute_simulated(reader=changing_reader)
        self.assertEqual(report.status, "STOP")
        self.assertIn("fl_clear_request_queue", calls)
        self.assertEqual(calls.count("fl_trigger_script"), 1)


if __name__ == "__main__":
    unittest.main()
