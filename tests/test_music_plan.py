import copy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from dawloop.music_plan import (
    ChordRegion, HarmonyContext, MusicalPlan, PlanningRequest, SectionBrief, StyleConstraints,
    VariationConstraints, VoiceConstraints, compile_musical_plan, eligible_pitches,
    generate_reference_plan, validate_musical_plan,
)
from dawloop.note_plan import NoteEvent
from dawloop.time import MusicalGrid


def example_request():
    return PlanningRequest(
        '8小节拨弦句，前半克制，后半提高力度与音域；沿用动机',
        MusicalGrid(96, 4, 4), SectionBrief('pre', 8, 0.4, 0.8, 2, 0.3, 0.25, 'pluck'),
        HarmonyContext(2, 'natural_minor', (
            ChordRegion('h1', 1, 2, 2, 'minor'), ChordRegion('h2', 3, 4, 10, 'major'),
            ChordRegion('h3', 5, 6, 5, 'major'), ChordRegion('h4', 7, 8, 0, 'major'),
        ), 2, (2, 5, 9)), VoiceConstraints(60, 72, 65, 7, 1, 'forbid'),
        VariationConstraints(2, 4, 1.0, True, False, 'stop_at_boundary'),
    )


class MusicalPlanTests(unittest.TestCase):
    def setUp(self):
        self.request = example_request()
        self.plan = generate_reference_plan(self.request)

    def test_deterministic_roundtrip_with_semantic_maps(self):
        encoded = json.dumps(self.plan.to_dict(), ensure_ascii=False, sort_keys=True)
        self.assertEqual(encoded, json.dumps(generate_reference_plan(self.request).to_dict(),
                                            ensure_ascii=False, sort_keys=True))
        self.assertEqual(PlanningRequest.from_dict(self.request.to_dict()), self.request)
        self.assertEqual(MusicalPlan.from_dict(json.loads(encoded)), self.plan)
        self.assertEqual(len(self.plan.phrase_map), 4)
        self.assertEqual(self.plan.phrase_map[1].derived_from, 'phrase-1')
        self.assertEqual(self.plan.motif_map[0].note_ids, self.plan.phrase_map[0].note_ids)
        self.assertGreater(self.plan.notes[-1].velocity, self.plan.notes[0].velocity)
        self.assertEqual(validate_musical_plan(self.plan)['live_certification'], 'NONE')

    def test_unknown_fields_and_arbitrary_source_rejected_at_all_boundaries(self):
        for path in ((), ('grid',), ('section',), ('harmony',), ('voice',), ('variation',)):
            with self.subTest(path=path):
                value = self.request.to_dict()
                obj = value if not path else value[path[0]]
                obj['source'] = 'arbitrary code'
                with self.assertRaises(ValueError):
                    PlanningRequest.from_dict(value)
        for field in ('notes', 'phrase_map', 'motif_map'):
            with self.subTest(field=field):
                value = self.plan.to_dict()
                value[field][0]['source'] = 'arbitrary code'
                with self.assertRaises(ValueError):
                    MusicalPlan.from_dict(value)

    def test_invalid_numbers_and_types_rejected(self):
        mutations = (
            ('section', 'energy_start', float('nan')),
            ('section', 'energy_end', float('inf')),
            ('section', 'motion', True), ('section', 'bars', True),
            ('section', 'tension', -0.1), ('section', 'density', 3),
            ('voice', 'max_pitch', 59), ('voice', 'max_leap', 1.5),
            ('variation', 'preserve_rhythm', 'true'), ('variation', 'repeat_count', 3),
            ('harmony', 'key', 'D'), ('harmony', 'allowed_tensions', [1]),
            ('voice', 'polyphony_limit', 2),
        )
        for section, field, bad in mutations:
            with self.subTest(section=section, field=field):
                value = self.request.to_dict()
                value[section][field] = bad
                with self.assertRaises(ValueError):
                    PlanningRequest.from_dict(value)

    def test_harmony_must_cover_every_bar_without_gaps_or_overlap(self):
        for field, value in (('start_bar', 4), ('start_bar', 2), ('end_bar', 5),
                             ('chord_id', 'h1'), ('quality', 'minor')):
            with self.subTest(field=field, value=value):
                data = self.request.to_dict()
                data['harmony']['progression'][1][field] = value
                with self.assertRaises(ValueError):
                    PlanningRequest.from_dict(data)

    def test_chord_eligibility_changes_on_exact_boundary(self):
        before = eligible_pitches(self.request, 767)
        after = eligible_pitches(self.request, 768)
        self.assertNotIn(70, before)
        self.assertIn(70, after)
        self.assertTrue(all(60 <= pitch <= 72 for pitch in after))

    def test_note_pitch_time_velocity_and_context_rejected(self):
        for field, value in (('pitch', 73), ('pitch', 61), ('length', 0),
                             ('start', -1), ('start', 3072), ('velocity', 0),
                             ('velocity', 0.8), ('pitch', True), ('chord_id', 'h4'),
                             ('harmonic_function', 'tension')):
            with self.subTest(field=field, value=value):
                data = self.plan.to_dict()
                data['notes'][0][field] = value
                with self.assertRaises(ValueError):
                    MusicalPlan.from_dict(data)
        for field, value in (('ppq', 480), ('bars', 4), ('target_role', 'bass')):
            data = self.plan.to_dict()
            data[field] = value
            with self.assertRaises(ValueError):
                MusicalPlan.from_dict(data)

    def test_density_and_note_multiplicity_are_not_deduplicated(self):
        data = self.plan.to_dict()
        data['notes'][1].update(start=data['notes'][0]['start'], pitch=data['notes'][0]['pitch'])
        with self.assertRaisesRegex(ValueError, 'POLYPHONY_EXCEEDED'):
            MusicalPlan.from_dict(data)
        data = self.plan.to_dict()
        data['notes'][1]['note_id'] = data['notes'][0]['note_id']
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_NOTE_ID'):
            MusicalPlan.from_dict(data)
        data = self.plan.to_dict()
        data['notes'][1]['start'] = 500
        data['notes'].sort(key=lambda n: (n['start'], n['note_id']))
        with self.assertRaisesRegex(ValueError, 'DENSITY_MISMATCH'):
            MusicalPlan.from_dict(data)

    def test_explanation_cannot_lie_about_notes_or_motif(self):
        for field in ('phrase_map', 'motif_map'):
            data = self.plan.to_dict()
            data[field][0]['note_ids'][0] = 'missing-note'
            with self.assertRaisesRegex(ValueError, 'MUSIC_EXPLANATION_MISMATCH'):
                MusicalPlan.from_dict(data)
        data = self.plan.to_dict()
        data['phrase_map'][1]['mean_register_shift'] += 12
        with self.assertRaisesRegex(ValueError, 'MUSIC_EXPLANATION_MISMATCH'):
            MusicalPlan.from_dict(data)

    def test_rhythm_contour_and_variation_caps_enforced(self):
        events = tuple(NoteEvent(n.start, n.length, n.pitch, n.velocity) for n in self.plan.notes)
        changed = list(events)
        changed[4] = replace(events[4], start_tick=events[4].start_tick + 24)
        with self.assertRaisesRegex(ValueError, 'RHYTHM_PRESERVATION_FAILED'):
            compile_musical_plan(self.request, tuple(changed))
        monotone = tuple(NoteEvent(index * 192, 48, 65, 90) for index in range(16))
        request = replace(self.request, harmony=replace(self.request.harmony, allowed_tensions=(2, 5, 9, 7)),
                          variation=replace(self.request.variation, preserve_contour=True))
        changed = list(monotone)
        changed[5] = replace(monotone[5], pitch=67)
        with self.assertRaisesRegex(ValueError, 'CONTOUR_PRESERVATION_FAILED'):
            compile_musical_plan(request, tuple(changed))
        request = replace(request, variation=replace(request.variation,
            preserve_contour=False, variation_strength=0))
        with self.assertRaisesRegex(ValueError, 'VARIATION_BUDGET_EXCEEDED'):
            compile_musical_plan(request, tuple(changed))

    def test_no_feasible_reference_continuation_does_not_relax_constraints(self):
        request = replace(self.request, voice=VoiceConstraints(60, 60, 60, 0, 1, 'forbid'))
        with self.assertRaisesRegex(ValueError, 'REFERENCE_SEARCH_NO_FEASIBLE_CONTINUATION'):
            generate_reference_plan(request)

    def test_leap_and_phrase_boundary_enforced(self):
        request = replace(self.request, voice=replace(self.request.voice, max_leap=0))
        events = tuple(NoteEvent(n.start, n.length, n.pitch, n.velocity) for n in self.plan.notes)
        with self.assertRaisesRegex(ValueError, 'MAX_LEAP_EXCEEDED'):
            compile_musical_plan(request, events)
        changed = list(events)
        changed[3] = replace(changed[3], duration=200)
        with self.assertRaisesRegex(ValueError, 'NOTE_CROSSES_PHRASE_BOUNDARY'):
            compile_musical_plan(self.request, tuple(changed))

    def test_provenance_hash_is_bound_to_current_constraints(self):
        data = self.plan.to_dict()
        data['constraints_snapshot']['section']['motion'] = 0.5
        with self.assertRaisesRegex(ValueError, 'PROVENANCE_INVALID'):
            MusicalPlan.from_dict(data)
        snapshot = self.plan.to_dict()
        snapshot['notes'][0]['pitch'] = 0
        self.assertNotEqual(snapshot, self.plan.to_dict())
        corrupted = copy.deepcopy(self.plan)
        corrupted.provenance['input_hash'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'PROVENANCE_INVALID'):
            corrupted.to_dict()

    def test_public_profiles_are_data_and_profile_name_never_controls_music(self):
        root = Path(__file__).resolve().parents[1] / 'profiles' / 'examples'
        paths = sorted(root.glob('*.json'))
        self.assertEqual(len(paths), 5)
        for path in paths:
            style = StyleConstraints.from_dict(json.loads(path.read_text(encoding='utf-8')))
            request = replace(self.request, style_constraints=style)
            a = generate_reference_plan(request)
            b = generate_reference_plan(replace(request, style_constraints=replace(style,
                profile_id='arbitrary-local-name')))
            self.assertEqual(a.notes, b.notes)
            self.assertEqual(a.phrase_map, b.phrase_map)
            self.assertEqual(validate_musical_plan(a)['note_count'], 16)

    def test_profile_cannot_expand_hard_constraints_or_add_unknown_rules(self):
        style = StyleConstraints('generic', 0.7, 0.3, 0.4, 1)
        request = replace(self.request, style_constraints=style)
        plan = generate_reference_plan(request)
        self.assertTrue(all(request.voice.min_pitch <= n.pitch <= request.voice.max_pitch for n in plan.notes))
        self.assertNotEqual(tuple(n.start for n in plan.notes), tuple(n.start for n in self.plan.notes))
        value = {'profile_id': 'generic', 'rhythm_syncopation': 0.7, 'melody_leap_tendency': 0.3,
                 'harmony_tension_usage': 0.4, 'motif_variation_strength': 1,
                 'artist_rule': 'special-case'}
        with self.assertRaises(ValueError):
            StyleConstraints.from_dict(value)


if __name__ == '__main__':
    unittest.main()
