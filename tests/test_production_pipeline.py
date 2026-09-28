import math
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

from flskill.production.mix import FaderCalibration, active_rms, plan_fader_db
from flskill.production.orchestration import (
    InstrumentRange,
    choose_instrument_for_phrase,
    find_register_gaps,
    source_note_coverage,
)
from flskill.production.smf import parse_smf, recommend_dense_window
from flskill.note_plan import NoteEvent


def vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


def make_midi(body: bytes, *, fmt: int = 0, division: int = 96) -> bytes:
    return (
        b"MThd" + struct.pack(">IHHH", 6, fmt, 1, division)
        + b"MTrk" + struct.pack(">I", len(body)) + body
    )


def write_wav(path: Path, samples: np.ndarray, *, channels: int = 1, width: int = 2) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(8000)
        if width == 2:
            samples = (np.clip(samples, -1, 1) * 32767).astype("<i2")
        handle.writeframes(samples.tobytes())


class ProductionPipelineTests(unittest.TestCase):
    def test_parse_smf_and_dense_window(self):
        body = bytearray()
        name = b"agent-test"
        body += vlq(0) + bytes([0xFF, 0x03, len(name)]) + name
        for delta, pitch in ((0, 60), (96, 62), (96, 64), (384, 67)):
            body += vlq(delta) + bytes([0x90, pitch, 100])
            body += vlq(24) + bytes([0x80, pitch, 0])
        body += vlq(0) + b"\xff\x2f\x00"
        midi = b"MThd" + struct.pack(">IHHH", 6, 1, 1, 96)
        midi += b"MTrk" + struct.pack(">I", len(body)) + body
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.mid"
            path.write_bytes(midi)
            summary = parse_smf(path)
        self.assertEqual(summary.division, 96)
        self.assertEqual(summary.tracks[0].name, "agent-test")
        self.assertEqual(len(summary.tracks[0].notes), 4)
        self.assertEqual(recommend_dense_window(
            summary.tracks[0], division=96, beats_per_bar=4, window_bars=1
        ), (1, 1))

    def test_active_rms_ignores_silence_for_active_measurement(self):
        sample_rate = 8000
        silence = np.zeros(sample_rate, dtype=np.float32)
        t = np.arange(sample_rate, dtype=np.float32) / sample_rate
        tone = 0.2 * np.sin(2 * math.pi * 440 * t)
        samples = np.concatenate([silence, tone])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(sample_rate)
                handle.writeframes((samples * 32767).astype("<i2").tobytes())
            result = active_rms(path)
        self.assertGreater(result.active_rms_dbfs, result.all_rms_dbfs)
        self.assertGreater(result.active_ratio, 0.4)
        self.assertLess(result.active_ratio, 0.6)

    def test_fader_plan_is_calibration_based(self):
        calibration = FaderCalibration(((0.0, -12.0), (0.5, 0.0), (1.0, 6.0)))
        value, expected_db = plan_fader_db(
            measured_active_dbfs=-40.0,
            target_active_dbfs=-37.0,
            current_fader_value=0.5,
            calibration=calibration,
        )
        self.assertAlmostEqual(expected_db, 3.0, places=6)
        self.assertAlmostEqual(value, 0.75, places=6)

    def test_orchestration_selects_comfortable_register(self):
        phrase = (
            NoteEvent(0, 96, 72, 90),
            NoteEvent(96, 96, 76, 90),
        )
        viola = InstrumentRange("viola", 48, 84, 55, 74)
        violin = InstrumentRange("violin", 55, 96, 67, 88)
        self.assertEqual(choose_instrument_for_phrase(phrase, (viola, violin)), violin)

    def test_register_gaps_and_source_coverage(self):
        source = (
            NoteEvent(0, 96, 60, 90),
            NoteEvent(96, 96, 64, 90),
        )
        arranged = ((NoteEvent(0, 96, 60, 80),),)
        self.assertEqual(find_register_gaps(
            arranged,
            start_tick=0,
            end_tick=192,
            step_ticks=96,
            low_pitch=60,
            high_pitch=72,
        ), (96,))
        self.assertEqual(source_note_coverage(source[:1], arranged), ())
        self.assertEqual(source_note_coverage(source, arranged), (source[1],))

    def test_smf_rejects_malformed_header_and_truncated_track(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.mid"
            path.write_bytes(b"NOPE" + struct.pack(">IHHH", 6, 0, 1, 96))
            with self.assertRaisesRegex(ValueError, "not a Standard MIDI File"):
                parse_smf(path)
            path.write_bytes(b"MThd" + struct.pack(">IHHH", 20, 0, 1, 96))
            with self.assertRaisesRegex(ValueError, "truncated MIDI header"):
                parse_smf(path)
            path.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 0, 1, 96) + b"MTrk\x00\x00\x00\x10x")
            with self.assertRaisesRegex(ValueError, "truncated MTrk data"):
                parse_smf(path)

    def test_smf_rejects_overlong_vlq_and_malformed_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.mid"
            path.write_bytes(make_midi(b"\x81\x80\x80\x80\x00\x90\x3c\x40"))
            with self.assertRaisesRegex(ValueError, "exceeds four bytes"):
                parse_smf(path)
            path.write_bytes(make_midi(b"\x00\x90\xff\x40"))
            with self.assertRaisesRegex(ValueError, "data byte"):
                parse_smf(path)

    def test_smf_supports_running_status_and_empty_track(self):
        body = b"\x00\x90\x3c\x64\x60\x3e\x64"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "running.mid"
            path.write_bytes(make_midi(body))
            self.assertEqual(len(parse_smf(path).tracks[0].notes), 2)
            path.write_bytes(make_midi(b""))
            self.assertEqual(parse_smf(path).tracks[0].notes, ())

    def test_rms_is_finite_for_silence_and_quiet_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            silence_path = Path(directory) / "silence.wav"
            write_wav(silence_path, np.zeros(8000, dtype=np.float32))
            silence = active_rms(silence_path)
            self.assertEqual(silence.active_ratio, 0.0)
            self.assertEqual(silence.active_rms_dbfs, float("-inf"))
            self.assertEqual(silence.peak_dbfs, float("-inf"))
            quiet_path = Path(directory) / "quiet.wav"
            write_wav(quiet_path, np.full(8000, 1e-5, dtype=np.float32))
            quiet = active_rms(quiet_path)
            self.assertEqual(quiet.active_ratio, 0.0)

    def test_rms_handles_stereo_and_rejects_unsupported_width(self):
        with tempfile.TemporaryDirectory() as directory:
            stereo_path = Path(directory) / "stereo.wav"
            tone = np.full((8000, 2), 0.2, dtype=np.float32)
            write_wav(stereo_path, tone, channels=2)
            self.assertGreater(active_rms(stereo_path).peak_dbfs, -15)
            width_path = Path(directory) / "width.wav"
            write_wav(width_path, np.zeros(8000, dtype=np.uint8), width=1)
            with self.assertRaisesRegex(ValueError, "unsupported PCM sample width"):
                active_rms(width_path)

    def test_rms_rejects_invalid_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.wav"
            path.write_bytes(b"not a wave")
            with self.assertRaises((EOFError, wave.Error)):
                active_rms(path)

    def test_silent_wav_cli_uses_json_null_for_non_finite_dbfs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "silence.wav"
            write_wav(path, np.zeros(8000, dtype=np.float32))
            root = Path(__file__).resolve().parents[1]
            env = dict(os.environ, PYTHONPATH=str(root / "src"))
            result = subprocess.run(
                [sys.executable, "-m", "flskill.cli", "measure-wav", str(path)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads(result.stdout)[0]
            self.assertIsNone(row["all_rms_dbfs"])
            self.assertIsNone(row["active_rms_dbfs"])
            self.assertEqual(row["active_ratio"], 0.0)

    def test_fader_calibration_clamps_out_of_range_targets(self):
        calibration = FaderCalibration(((0.0, -12.0), (0.5, 0.0), (1.0, 6.0)))
        self.assertEqual(calibration.db_for_value(0.0), -12.0)
        self.assertEqual(calibration.db_for_value(1.0), 6.0)
        self.assertEqual(calibration.db_for_value(-1.0), -12.0)
        self.assertEqual(calibration.db_for_value(2.0), 6.0)
        self.assertEqual(calibration.value_for_db(-100.0), 0.0)
        self.assertEqual(calibration.value_for_db(100.0), 1.0)
        self.assertEqual(plan_fader_db(
            measured_active_dbfs=-40.0,
            target_active_dbfs=100.0,
            current_fader_value=0.5,
            calibration=calibration,
        )[0], 1.0)
        self.assertEqual(plan_fader_db(
            measured_active_dbfs=100.0,
            target_active_dbfs=-100.0,
            current_fader_value=0.5,
            calibration=calibration,
        )[0], 0.0)

    def test_fader_calibration_rejects_invalid_points(self):
        with self.assertRaisesRegex(ValueError, "within 0..1"):
            FaderCalibration(((-0.1, -12.0), (1.0, 6.0)))
        with self.assertRaisesRegex(ValueError, "finite"):
            FaderCalibration(((0.0, float("nan")), (1.0, 6.0)))

    def test_orchestration_rejects_phrase_without_suitable_instrument(self):
        phrase = (NoteEvent(0, 96, 100, 90),)
        with self.assertRaisesRegex(ValueError, "no instrument"):
            choose_instrument_for_phrase(phrase, (InstrumentRange("low", 0, 60),))

    def test_source_coverage_preserves_duplicate_event_count(self):
        duplicate = NoteEvent(0, 96, 60, 90)
        self.assertEqual(source_note_coverage((duplicate, duplicate), ((duplicate,),)), (duplicate,))

    def test_sf2_rejects_invalid_truncated_and_missing_chunks(self):
        from flskill.production.sf2 import Sf2

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.sf2"
            path.write_bytes(b"not an sf2")
            with self.assertRaisesRegex(ValueError, "not an SF2"):
                Sf2(path)
            path.write_bytes(b"RIFF" + struct.pack("<I", 100) + b"sfbkLIST")
            with self.assertRaisesRegex(ValueError, "truncated SF2"):
                Sf2(path)
            body = b"RIFF" + struct.pack("<I", 4) + b"sfbk"
            path.write_bytes(body)
            with self.assertRaisesRegex(ValueError, "missing required chunks"):
                Sf2(path)

    def test_environment_profile_separates_reported_and_portable_status(self):
        from flskill.production.environment import EnvironmentProfile, EnvironmentStatus, inspect_environment

        profile = inspect_environment()
        self.assertIsInstance(profile, EnvironmentProfile)
        self.assertEqual(profile.original_developer_environment, "reported_working")
        self.assertIn("spectrum-peak", {check.name for check in profile.checks})
        self.assertIn("WASAPI", {check.name for check in profile.checks})
        self.assertIn("fugue-v4.py requires an output path in sys.argv[1]", profile.invocation_assumptions)
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing-fl64.exe"
            with patch.dict(os.environ, {"FL_STUDIO_PATH": str(missing)}):
                fl_check = next(item for item in inspect_environment().checks if item.name == "FL Studio")
            self.assertIs(fl_check.status, EnvironmentStatus.MISSING)
            self.assertNotIn(str(directory), fl_check.detail)

    def test_loopback_dependency_is_optional(self):
        from flskill.production.environment import EnvironmentStatus, inspect_environment

        check = next(item for item in inspect_environment().checks if item.name == "pyaudiowpatch")
        if check.status is EnvironmentStatus.OPTIONAL_MISSING:
            from flskill.production.loopback import list_loopback_devices
            with self.assertRaisesRegex(ImportError, "production-loopback"):
                list_loopback_devices()

    def test_smf_and_cli_work_without_numpy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.mid"
            path.write_bytes(make_midi(b"\x00\x90\x3c\x64"))
            root = Path(__file__).resolve().parents[1]
            env = dict(os.environ, PYTHONPATH=str(root / "src"))
            code = (
                "import builtins,sys; original=builtins.__import__; "
                "builtins.__import__=lambda name,*a,**k: (_ for _ in ()).throw(ImportError('blocked numpy')) "
                "if name == 'numpy' or name.startswith('numpy.') else original(name,*a,**k); "
                "sys.argv=['flskill','midi-inspect',r'" + str(path) + "','--window-bars','1']; "
                "import flskill.production; from flskill.cli import main; raise SystemExit(main())"
            )
            result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"note_count": 1', result.stdout)

    def test_measure_wav_shows_optional_numpy_install_hint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(__file__).resolve().parents[1]
            env = dict(os.environ, PYTHONPATH=str(root / "src"))
            code = (
                "import builtins,sys; original=builtins.__import__; "
                "builtins.__import__=lambda name,*a,**k: (_ for _ in ()).throw(ImportError('blocked numpy')) "
                "if name == 'numpy' or name.startswith('numpy.') else original(name,*a,**k); "
                "sys.argv=['flskill','measure-wav','unused.wav']; "
                "from flskill.cli import main; raise SystemExit(main())"
            )
            result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 2)
            self.assertIn('pip install "flskill[production]"', result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_doctor_reports_production_capabilities_independently_without_numpy(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        code = (
            "import builtins,sys,importlib.util; original=builtins.__import__; finder=importlib.util.find_spec; "
            "builtins.__import__=lambda name,*a,**k: (_ for _ in ()).throw(ImportError('blocked numpy')) "
            "if name == 'numpy' or name.startswith('numpy.') else original(name,*a,**k); "
            "importlib.util.find_spec=lambda name,*a,**k: None if name == 'numpy' else finder(name,*a,**k); "
            "sys.argv=['flskill','doctor']; from flskill.cli import main; raise SystemExit(main())"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("Production SMF analysis", result.stdout)
        self.assertIn("AVAILABLE", result.stdout.split("Production SMF analysis", 1)[1].splitlines()[0])
        self.assertIn("Production audio analysis", result.stdout)
        self.assertIn("OPTIONAL_MISSING", result.stdout.split("Production audio analysis", 1)[1].splitlines()[0])
        self.assertNotIn("Production Pipeline analysis helpers", result.stdout)


if __name__ == "__main__":
    unittest.main()
