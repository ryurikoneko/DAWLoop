# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""学习证据、去重、映射和反馈版本的离线边界测试。"""

from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest

from dawloop.learning import aggregate_features, build_profile, content_hash
from dawloop.learning import revise_profile, validate_bundle, validate_document, validate_profile, write_revision


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('learning_example',
    ROOT / 'learning/examples/generic_learning/run.py')
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.data = example.build_example()

    def test_complete_example_and_holdout(self):
        data = self.data
        self.assertEqual(validate_bundle(data['references'], data['analyses'], data['report']),
                         {'valid': True, 'independent_work_count': 2, 'generalization': 'NOT_CERTIFIED'})
        self.assertEqual(data['report']['excluded'], [{'source_id': 'sample-holdout', 'reason': 'holdout'}])
        self.assertEqual(len(data['plan']['notes']), 16)
        self.assertEqual(data['profile_v2']['feedback'][0]['context'], 'SYNTHETIC_EXAMPLE')
        self.assertEqual(data['profile_v2']['feedback'][0]['outcome'], 'VISUAL_REVIEW_ONLY')
        self.assertEqual(validate_profile(data['profile_v2'], report=data['report'],
                         parent=data['profile_v1']).rhythm_syncopation, 0.1)
        import json
        for name, value in data.items():
            self.assertEqual(value, json.loads((ROOT / 'learning/examples/generic_learning/expected'
                                                / f'{name}.json').read_text(encoding='utf-8')))

    def test_feature_rejections(self):
        changes = [({'unit': 'bars'}, 'FEATURE_UNIT_MISMATCH'),
                   ({'value': None}, 'UNKNOWN_FEATURE_INVALID'),
                   ({'value': 1, 'evidence_ref': None}, 'FEATURE_EVIDENCE_REQUIRED'),
                   ({'method': 'unknown'}, 'FEATURE_EVIDENCE_REQUIRED'),
                   ({'value': -1}, 'FEATURE_RANGE_INVALID'),
                   ({'name': 'artist'}, 'LEARNING_SCHEMA_INVALID'),
                   ({'value': float('nan')}, 'Out of range float'),
                   ({'value': True}, 'LEARNING_SCHEMA_INVALID'),
                   ({'definition_version': 'other'}, 'LEARNING_SCHEMA_INVALID'),
                   ({'extra': 'anything'}, 'LEARNING_SCHEMA_INVALID')]
        for change, error in changes:
            with self.subTest(change=change):
                analysis = deepcopy(self.data['analyses'][0])
                analysis['features'][0].update(change)
                with self.assertRaisesRegex(ValueError, error):
                    validate_document('extracted_features', analysis)

    def test_missing_is_not_zero_and_inferred_is_separate(self):
        analyses = deepcopy(self.data['analyses'])
        analyses[0]['features'][0].update(value=None, method='unknown', confidence=0,
                                         evidence_ref=None, missing_reason='Unavailable input')
        analyses[1]['features'][1]['method'] = 'inferred'
        report = aggregate_features(self.data['references'], analyses, group_id='generic-learning',
                                    holdout_source_ids=('sample-holdout',))
        density = next(d for d in report['distributions'] if d['name'] == 'note_density')
        self.assertEqual(density['coverage'], 0.5)
        self.assertEqual(density['count'], 1)
        intervals = [d for d in report['distributions'] if d['name'] == 'mean_abs_interval']
        self.assertEqual({d['method'] for d in intervals}, {'observed', 'inferred'})

    def test_hash_scope_duplicates_and_unknown_holdout(self):
        for kind in ('hash', 'scope', 'independent', 'content', 'source', 'holdout'):
            with self.subTest(kind=kind):
                refs, analyses = deepcopy(self.data['references']), deepcopy(self.data['analyses'])
                holdout = ('sample-holdout',)
                if kind == 'hash':
                    analyses[0]['source_hash'] = '0' * 64
                elif kind == 'scope':
                    analyses[1]['scope']['role'] = 'bass'
                elif kind == 'independent':
                    refs[1]['independent_work_id'] = refs[0]['independent_work_id']
                elif kind == 'content':
                    refs[1]['content_hash'] = refs[0]['content_hash']
                    analyses[1]['source_hash'] = refs[0]['content_hash']
                elif kind == 'source':
                    analyses.append(deepcopy(analyses[0]))
                else:
                    holdout = ('missing',)
                with self.assertRaises(ValueError):
                    aggregate_features(refs, analyses, group_id='generic-learning',
                                       holdout_source_ids=holdout)

    def test_unknown_rights_excluded(self):
        refs = deepcopy(self.data['references'])
        refs[1]['rights_status'] = 'unknown'
        report = aggregate_features(refs, self.data['analyses'], group_id='generic-learning',
                                    holdout_source_ids=('sample-holdout',))
        self.assertEqual(report['independent_work_count'], 1)
        self.assertIn({'source_id': 'sample-b', 'reason': 'rights_unknown'}, report['excluded'])

    def test_forged_report_statistics_rejected(self):
        for field, value in (('count', 20), ('mean', 99), ('coverage', 1), ('unit', 'bars')):
            with self.subTest(field=field):
                report = deepcopy(self.data['report'])
                report['distributions'][0][field] = value
                # 原覆盖本来为1，改成不同的数值才能验证拒绝。
                if field == 'coverage':
                    report['distributions'][0][field] = 0.9
                with self.assertRaises(ValueError):
                    validate_bundle(self.data['references'], self.data['analyses'], report)

    def test_profile_has_no_implicit_mapping_or_artist_fields(self):
        with self.assertRaisesRegex(ValueError, 'ALL_MAPPING_DECISIONS_REQUIRED'):
            build_profile(self.data['report'], profile_id='example', decisions={})
        profile = deepcopy(self.data['profile_v1'])
        profile['constraints']['artist'] = 'not-a-control'
        with self.assertRaisesRegex(ValueError, 'LEARNING_SCHEMA_INVALID'):
            validate_profile(profile)

    def test_profile_report_parent_feedback_binding(self):
        for kind in ('report', 'parent', 'feedback', 'changes', 'override', 'duplicate'):
            with self.subTest(kind=kind):
                profile = deepcopy(self.data['profile_v2'])
                if kind == 'report':
                    profile['report_hash'] = '0' * 64
                elif kind == 'parent':
                    profile['parent_hash'] = '0' * 64
                elif kind == 'feedback':
                    profile['feedback'][-1]['profile_hash'] = '0' * 64
                elif kind == 'changes':
                    profile['constraints']['rhythm_syncopation'] = 0.8
                elif kind == 'override':
                    profile['user_overrides'] = {}
                else:
                    profile['feedback'].append(deepcopy(profile['feedback'][0]))
                with self.assertRaises(ValueError):
                    validate_profile(profile, report=self.data['report'], parent=self.data['profile_v1'])

    def test_feedback_requires_actual_plan_hash(self):
        feedback = deepcopy(self.data['profile_v2']['feedback'][0])
        feedback['plan_hash'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'FEEDBACK_PLAN_MISMATCH'):
            revise_profile(self.data['profile_v1'], feedback=feedback, plan=self.data['plan'])

    def test_no_overwrite_or_unbound_revision_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'v1.json'
            write_revision(path, self.data['profile_v1'])
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_revision(path, self.data['profile_v1'])
            self.assertEqual(before, path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'PROFILE_PARENT_DOCUMENT_REQUIRED'):
                write_revision(Path(directory) / 'v2.json', self.data['profile_v2'])

    def test_local_reference_rejects_absolute_and_traversal(self):
        for path in ('C:/private/song.mid', '../song.mid', 'references/../song.mid', '/tmp/song.mid',
                     'references\\song.mid'):
            with self.subTest(path=path):
                reference = deepcopy(self.data['references'][0])
                reference['local_ref'] = path
                with self.assertRaises(ValueError):
                    validate_document('reference_track', reference)


if __name__ == '__main__':
    unittest.main()
