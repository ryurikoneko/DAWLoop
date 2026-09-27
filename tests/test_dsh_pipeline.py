import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

import numpy as np

from flskill.dsh.mix import FaderCalibration, active_rms, plan_fader_db
from flskill.dsh.orchestration import (
    InstrumentRange,
    choose_instrument_for_phrase,
    find_register_gaps,
    source_note_coverage,
)
from flskill.dsh.smf import parse_smf, recommend_dense_window
from flskill.note_plan import NoteEvent


def vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


class DshPipelineTests(unittest.TestCase):
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
        self.assertEqual(source_note_coverage(source, arranged), (source[1],))


if __name__ == "__main__":
    unittest.main()
