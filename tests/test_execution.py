import unittest

from dawproof.io import InMemoryEventStore
from dawproof.note_plan import NoteEvent, NotePlan
from dawproof.time import MusicalGrid
from dawproof.verification import write_read_verify


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        event = NoteEvent(0, 96, 60, 100)
        self.plan = NotePlan("pattern-test", MusicalGrid(96), 0, 1, (event,))

    def test_write_read_compare_returns_offline_result(self):
        store = InMemoryEventStore()
        result = write_read_verify(self.plan, store, store)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.scope, "offline")
        self.assertEqual(result.label, "Offline Algorithm Verified")

    def test_writer_success_without_matching_readback_stops(self):
        class WrongReadback:
            def write(self, target_id, events):
                return True

            def read(self, target_id):
                return (NoteEvent(1, 96, 60, 100),)

        result = write_read_verify(self.plan, WrongReadback(), WrongReadback())
        self.assertEqual(result.status, "STOP")
        self.assertEqual(result.mismatches[0].fields, ("start_tick",))

    def test_write_error_stops_even_when_readback_matches(self):
        class FailedWrite:
            def write(self, target_id, events):
                raise OSError("write failed")

            def read(self, target_id):
                return self.plan_events

            def __init__(self, events):
                self.plan_events = events

        result = write_read_verify(self.plan, FailedWrite(self.plan.events), FailedWrite(self.plan.events))
        self.assertEqual(result.status, "STOP")
        self.assertIsNotNone(result.write_error)

    def test_missing_reader_target_stops(self):
        store = InMemoryEventStore()
        result = write_read_verify(self.plan, store, object())
        self.assertEqual(result.status, "STOP")
        self.assertIsNotNone(result.read_error)


if __name__ == "__main__":
    unittest.main()
