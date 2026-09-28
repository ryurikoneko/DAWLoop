import unittest

from dawproof.note_plan import NoteEvent, NotePlan
from dawproof.time import MusicalGrid


class NotePlanTests(unittest.TestCase):
    def setUp(self):
        self.grid = MusicalGrid(96, 4, 4)
        self.event = NoteEvent(384, 96, 60, 100)
        self.plan = NotePlan("pattern-a", self.grid, 384, 2, (self.event,))

    def test_serialization_round_trip(self):
        self.assertEqual(NotePlan.from_dict(self.plan.to_dict()), self.plan)

    def test_rejects_invalid_event_values(self):
        for values in (
            (0, 0, 60, 100),
            (0, 1, 128, 100),
            (0, 1, 60, 0),
            (-1, 1, 60, 100),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                NoteEvent(*values)

    def test_rejects_event_outside_section(self):
        with self.assertRaises(ValueError):
            NotePlan("pattern-a", self.grid, 384, 1, (NoteEvent(768, 1, 60, 100),))

    def test_rejects_unknown_plan_fields(self):
        value = self.plan.to_dict()
        value["source"] = "unexpected"
        with self.assertRaises(ValueError):
            NotePlan.from_dict(value)


if __name__ == "__main__":
    unittest.main()
