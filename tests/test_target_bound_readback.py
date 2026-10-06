from dataclasses import fields, replace
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from dawloop.runtime.identity import IdentityObservation, TargetIdentitySnapshot
from dawloop.runtime.readback import ReadbackFreshness, READ_ONLY_NOTE_EXPRESSION, assess_readback, validate_read_only_expression


class TargetBoundReadbackTests(unittest.TestCase):
    def target(self):
        now = datetime.now(timezone.utc)
        def field(value, basis=None):
            return IdentityObservation(value, 'controller', 'read', now, 'session:project', basis)
        return TargetIdentitySnapshot(pattern_index=field(1, 'pattern_1_based'), pattern_name=field('片段甲'),
                                      channel_index=field(0, 'global_0_based'), channel_name=field('通道甲'), ppq=field(96))

    def proof(self):
        return dict(request_generation='read-1', export_generation='read-1', request_started=10.0,
                    export_started=10.5, export_completed=11.0, same_monotonic_clock=True,
                    producer_target=self.target(), producer_binding_verified=True)

    def test_cache_without_generation_is_unknown_even_with_matching_identity(self):
        target = self.target()
        result = assess_readback(target, target, target)
        self.assertEqual(result.freshness, ReadbackFreshness.UNKNOWN)
        self.assertFalse(result.target_bound)

    def test_export_generation_and_monotonic_order_are_required(self):
        target = self.target()
        for change, status in (({'export_generation': 'old'}, 'STALE'),
                               ({'export_completed': 9.0}, 'STALE'),
                               ({'export_started': 9.0}, 'STALE'),
                               ({'export_started': None}, 'UNKNOWN'),
                               ({'same_monotonic_clock': False}, 'UNKNOWN'),
                               ({'export_completed': float('nan')}, 'UNKNOWN')):
            proof = dict(self.proof(), **change)
            result = assess_readback(target, target, target, **proof)
            self.assertEqual(result.freshness, status)
            self.assertFalse(result.target_bound)

    def test_race_rejects_pattern_channel_and_context_change(self):
        target = self.target()
        other_context = replace(target, **{
            field.name: replace(getattr(target, field.name), context_binding='other-session')
            for field in fields(target) if getattr(target, field.name) is not None
        })
        for changed in (replace(target, pattern_index=replace(target.pattern_index, value=2)),
                        replace(target, channel_index=replace(target.channel_index, value=1)),
                        other_context):
            result = assess_readback(target, target, changed, **self.proof())
            self.assertEqual(result.error_code, 'TARGET_CHANGED')
            self.assertFalse(result.target_bound)

    def test_round_trip_switch_cannot_be_hidden_by_equal_endpoint_identity(self):
        target = self.target()
        other = replace(target, pattern_index=replace(target.pattern_index, value=2))
        result = assess_readback(target, target, target, **dict(self.proof(), producer_target=other))
        self.assertEqual(result.error_code, 'TARGET_CHANGED')
        result = assess_readback(target, target, target, **dict(self.proof(), producer_binding_verified=False))
        self.assertEqual(result.error_code, 'PRODUCER_TARGET_UNPROVEN')
        self.assertFalse(result.target_bound)

    def test_verified_producer_and_generation_allow_bound_readback(self):
        target = self.target()
        result = assess_readback(target, target, target, **self.proof())
        self.assertEqual(result.freshness, ReadbackFreshness.FRESH)
        self.assertTrue(result.target_bound)

    def test_script_validator_rejects_mutation_io_dynamic_calls_and_altered_template(self):
        self.assertTrue(validate_read_only_expression(READ_ONLY_NOTE_EXPRESSION))
        forbidden = ['score.clearNotes()', 'score.addNote(note)', 'open("file")', '__import__("os")',
                     'exec("pass")', 'eval("1")', 'score.PPQ = 96', 'import os',
                     READ_ONLY_NOTE_EXPRESSION.replace('note.number', 'note.clone()'),
                     READ_ONLY_NOTE_EXPRESSION.replace('range(score.noteCount)', 'range(1)')]
        for source in forbidden:
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_read_only_expression(source)

    def test_mock_score_returns_minimal_note_structure_without_mutation(self):
        class Score:
            PPQ = 96
            noteCount = 3
            def getNote(self, index):
                return SimpleNamespace(number=60+index, time=index*96, length=48, velocity=.8)
        validate_read_only_expression(READ_ONLY_NOTE_EXPRESSION)
        result = eval(compile(READ_ONLY_NOTE_EXPRESSION, '<只读模板模拟>', 'eval'),
                      {'__builtins__': {'range': range}, 'score': Score()})
        self.assertEqual((result['ppq'], result['note_count'], len(result['notes'])), (96, 3, 3))
        self.assertEqual(result['notes'][1], {'pitch':61, 'start':96, 'length':48, 'velocity':.8})
