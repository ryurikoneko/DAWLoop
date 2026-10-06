import unittest
from datetime import datetime, timedelta, timezone

from dawloop.runtime import IdentityObservation, TargetIdentitySnapshot, compose_identity


class IdentitySnapshotTests(unittest.TestCase):
    def observation(self, value, backend='controller', binding='confirmed-session', basis=None, offset=0):
        return IdentityObservation(value, backend, 'read', datetime(2026, 9, 30, tzinfo=timezone.utc)+timedelta(seconds=offset),
                                   binding, basis)

    def test_unknown_fields_and_composite_provenance(self):
        unknown = TargetIdentitySnapshot()
        self.assertIsNone(unknown.pattern_index)
        controller = TargetIdentitySnapshot(pattern_index=self.observation(1, basis='pattern_1_based'))
        native = TargetIdentitySnapshot(plugin_name=self.observation('FLEX', backend='native'))
        combined = compose_identity(controller, native)
        self.assertEqual(combined.pattern_index.backend, 'controller')
        self.assertEqual(combined.plugin_name.backend, 'native')
        self.assertIsNone(combined.piano_roll_target)

    def test_mismatched_scope_conflicts_and_stale_data_are_rejected(self):
        first = TargetIdentitySnapshot(project=self.observation('display-title'))
        for second in (TargetIdentitySnapshot(plugin_name=self.observation('x', binding='another-session')),
                       TargetIdentitySnapshot(project=self.observation('different-title')),
                       TargetIdentitySnapshot(plugin_name=self.observation('x', offset=3))):
            with self.assertRaises(ValueError):
                compose_identity(first, second)

    def test_index_basis_and_timezone_are_required(self):
        with self.assertRaises(ValueError):
            TargetIdentitySnapshot(channel_index=self.observation(0))
        with self.assertRaises(ValueError):
            IdentityObservation(1, 'controller', 'read', datetime(2026, 9, 30), 'session')
