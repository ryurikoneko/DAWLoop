import unittest

from flskill.note_plan import NoteEvent
from flskill.verification import compare_events


class ExactSetTests(unittest.TestCase):
    def test_exact_match_preserves_duplicate_count(self):
        event = NoteEvent(0, 96, 60, 100)
        missing, extra, mismatches = compare_events((event, event), (event, event))
        self.assertEqual((missing, extra, mismatches), ((), (), ()))

    def test_missing_and_extra_are_reported(self):
        planned = (NoteEvent(0, 96, 60, 100),)
        actual = (NoteEvent(96, 96, 62, 90),)
        missing, extra, mismatches = compare_events(planned, actual)
        self.assertEqual(missing, planned)
        self.assertEqual(extra, actual)
        self.assertEqual(set(mismatches[0].fields), {"start_tick", "pitch", "velocity"})

    def test_reports_each_single_field_mismatch(self):
        expected = NoteEvent(96, 48, 64, 80)
        cases = (
            (NoteEvent(97, 48, 64, 80), "start_tick"),
            (NoteEvent(96, 49, 64, 80), "duration"),
            (NoteEvent(96, 48, 65, 80), "pitch"),
            (NoteEvent(96, 48, 64, 81), "velocity"),
        )
        for observed, field in cases:
            with self.subTest(field=field):
                _, _, mismatches = compare_events((expected,), (observed,))
                self.assertEqual(mismatches[0].fields, (field,))


if __name__ == "__main__":
    unittest.main()
