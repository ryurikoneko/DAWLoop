import json
from pathlib import Path
import tempfile
import unittest

from research.fast_music_evidence import collect


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.result = dict(operation_id='op-1', state='STOPPED_AFTER_DISPATCH_UNKNOWN',
            error_code='HUMAN_EVENT_TIMEOUT', dispatch='DISPATCHED', completion='CONFIRMED',
            evidence=dict(preview=dict(window=dict(hwnd=10)),
                target=dict(pattern_index=1, expected_channel_name='808 Kick')))
        self.human = dict(operation_id='op-1', source='direct_user_reply', accept_actor='human',
            accepted=True, preview_review_confirmed=True, window=dict(hwnd=10))
        self.application = dict(operation_id='op-1', preview_closed=True,
            observer='agent_visual_review', observed=True, phrase_visible=True,
            visible_pattern=1, channel_name='808 Kick', evidence_ref='frame-1')

    def write_inputs(self):
        for name, value in [('fast_music_result', self.result),
                ('user_accept_report', self.human), ('application_observation', self.application)]:
            (self.root / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')

    def test_late_evidence_does_not_rewrite_timeout_or_certify(self):
        self.write_inputs()
        original = (self.root / 'fast_music_result.json').read_bytes()
        report = collect(self.root)
        self.assertEqual(report['evidence_collection'], 'COMPLETE')
        self.assertEqual(report['original_error'], 'HUMAN_EVENT_TIMEOUT')
        self.assertFalse(report['entrypoint_live_certification'])
        self.assertFalse(report['runtime_resumed'])
        self.assertEqual(report['dispatches_added'], 0)
        self.assertEqual(original, (self.root / 'fast_music_result.json').read_bytes())
        self.assertEqual(report, collect(self.root))

    def test_wrong_request_actor_window_and_missing_fields_stay_unbound(self):
        for change in ({'operation_id': 'old'}, {'accept_actor': 'agent'},
                {'window': {'hwnd': 11}}, {'accepted': None}, {'source': 'inferred'}):
            with self.subTest(change=change):
                original = dict(self.human)
                self.human.update(change)
                self.write_inputs()
                self.assertEqual(collect(self.root)['human_report'], 'UNBOUND')
                (self.root / 'post_run_evidence.json').unlink()
                self.human = original

    def test_wrong_target_does_not_complete(self):
        self.application['channel_name'] = '808 Clap'
        self.write_inputs()
        self.assertEqual(collect(self.root)['evidence_collection'], 'INCOMPLETE')

    def test_unknown_completion_does_not_complete(self):
        self.result['completion'] = 'UNKNOWN'
        self.write_inputs()
        self.assertEqual(collect(self.root)['evidence_collection'], 'INCOMPLETE')

    def test_changed_evidence_cannot_overwrite_existing_report(self):
        self.write_inputs()
        collect(self.root)
        before = (self.root / 'post_run_evidence.json').read_bytes()
        self.human['report'] = 'changed'
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, 'POST_RUN_EVIDENCE_CONFLICT'):
            collect(self.root)
        self.assertEqual(before, (self.root / 'post_run_evidence.json').read_bytes())

    def test_missing_file_does_not_create_report(self):
        self.write_inputs()
        (self.root / 'user_accept_report.json').unlink()
        with self.assertRaises(FileNotFoundError):
            collect(self.root)
        self.assertFalse((self.root / 'post_run_evidence.json').exists())
