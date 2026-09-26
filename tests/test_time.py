import unittest

from flskill.time import MusicalGrid, MusicalPosition, resolve_absolute_tick


class MusicalGridTests(unittest.TestCase):
    def test_resolves_position_on_nonzero_section(self):
        grid = MusicalGrid(ppq=96, beats_per_bar=4, beat_unit=4)
        self.assertEqual(resolve_absolute_tick(MusicalPosition(1, 1, 0), grid, 9216), 9216)
        self.assertEqual(resolve_absolute_tick(MusicalPosition(2, 1, 0), grid, 9216), 9600)
        self.assertEqual(resolve_absolute_tick(MusicalPosition(1, 2, 12), grid, 0), 108)

    def test_supports_non_quarter_denominator_without_rounding(self):
        grid = MusicalGrid(ppq=96, beats_per_bar=6, beat_unit=8)
        self.assertEqual(grid.ticks_per_beat, 48)
        self.assertEqual(grid.ticks_per_bar, 288)

    def test_rejects_invalid_grid_or_position(self):
        with self.assertRaises(ValueError):
            MusicalGrid(ppq=95, beat_unit=8)
        with self.assertRaises(ValueError):
            MusicalGrid(ppq=96, beat_unit=3)
        grid = MusicalGrid(ppq=96)
        with self.assertRaises(ValueError):
            resolve_absolute_tick(MusicalPosition(1, 5), grid)
        with self.assertRaises(ValueError):
            resolve_absolute_tick(MusicalPosition(1, 1, 96), grid)
        with self.assertRaises(ValueError):
            MusicalPosition(0, 1)


if __name__ == "__main__":
    unittest.main()
