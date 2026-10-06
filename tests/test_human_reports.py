from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from dawloop.runtime.human_reports import HumanReport, HumanReportStore, acceptance_receipt


class HumanReportsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.store = HumanReportStore.create(self.root, run_id='run-1', session_id='session-1',
                                             operation_id='operation-1')
        self.window = dict(hwnd=20, title='测试预览')
        self.store.bind_preview(self.window)

    def report(self, **changes):
        return dict(run_id='run-1', session_id='session-1', report_id='report-1',
                    reported_at='2026-10-05T12:00:00+08:00', event_type='ACCEPTED', source='HUMAN',
                    evidence_ref='direct-user-reply-1', preview_window=self.window,
                    preview_review_confirmed=True) | changes

    def terminal(self):
        raw = json.dumps(dict(operation_id='operation-1', state='STOPPED_AFTER_DISPATCH_UNKNOWN',
            error_code='HUMAN_EVENT_TIMEOUT', completion='UNKNOWN', application='NOT_OBSERVED')).encode()
        (self.root/'fast_music_result.json').write_bytes(raw)
        self.store.finalize(raw)
        return raw

    def test_realtime_claim_and_common_schema(self):
        value = self.report()
        self.assertEqual(self.store.submit(value)['delivery'], 'PENDING')
        self.store.begin_accept()
        receipt = acceptance_receipt(self.store.claim_accept(), 'operation-1')
        self.assertEqual(receipt['human_report'], value)
        self.assertEqual(receipt['accept_actor'], 'human')
        self.assertIsNone(self.store.claim_accept())

    def test_wrong_run_session_and_window_are_quarantined(self):
        self.store.begin_accept()
        for index, change in enumerate((dict(run_id='run-2'), dict(session_id='session-2'),
                                       dict(preview_window={'hwnd': 21}))):
            record = self.store.submit(self.report(report_id=f'wrong-{index}', **change))
            self.assertFalse(record['linked'])
            self.assertEqual(record['delivery'], 'UNLINKED')
        self.assertIsNone(self.store.claim_accept())

    def test_duplicate_is_idempotent_and_conflict_rejected(self):
        first = self.store.submit(self.report())
        self.assertEqual(first, self.store.submit(self.report()))
        with self.assertRaisesRegex(ValueError, 'ID_CONFLICT'):
            self.store.submit(self.report(evidence_ref='other-user-reply'))
        self.assertEqual(len(self.store.snapshot()['human_reports']), 1)

    def test_pending_and_new_reports_become_late_after_timeout(self):
        self.store.begin_accept()
        self.store.submit(self.report())
        self.store.end_accept()
        raw = self.terminal()
        # 用户声称的历史时间不能把晚到回执伪装成实时交付。
        self.store.submit(self.report(report_id='late', reported_at='2000-01-01T00:00:00+00:00'))
        snapshot = self.store.snapshot()
        self.assertTrue(all(r['delivery'] == 'LATE' for r in snapshot['human_reports']))
        self.assertEqual(snapshot['run_result']['error_code'], 'HUMAN_EVENT_TIMEOUT')
        self.assertFalse(snapshot['runtime_resumed'])
        self.assertEqual(snapshot['dispatches_added'], 0)
        self.assertEqual((self.root/'fast_music_result.json').read_bytes(), raw)

    def test_reopened_store_keeps_binding_and_idempotency(self):
        self.store.submit(self.report())
        raw = self.terminal()
        reopened = HumanReportStore(self.root)
        self.assertEqual(reopened.submit(self.report())['delivery'], 'LATE')
        reopened.finalize(raw)
        self.assertEqual(len(reopened.snapshot()['human_reports']), 1)

    def test_original_result_cannot_be_rewritten(self):
        raw = self.terminal()
        with self.assertRaisesRegex(ValueError, 'IMMUTABLE'):
            self.store.finalize(raw.replace(b'UNKNOWN', b'OTHER'))
        (self.root/'fast_music_result.json').write_bytes(raw+b' ')
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_RUN_RESULT_CHANGED'):
            self.store.submit(self.report())

    def test_terminal_requires_exact_file_and_operation(self):
        with self.assertRaisesRegex(ValueError, 'OPERATION_MISMATCH'):
            self.store.finalize(b'{"operation_id":"another"}')
        with self.assertRaisesRegex(ValueError, 'FILE_REQUIRED'):
            self.store.finalize(b'{"operation_id":"operation-1"}')

    def test_missing_and_invalid_fields(self):
        for key in self.report():
            with self.subTest(missing=key):
                value = self.report()
                del value[key]
                with self.assertRaises(ValueError):
                    HumanReport.parse(value)
        for changes in (dict(run_id=''), dict(session_id=12), dict(report_id='../other'),
                        dict(source='AGENT'), dict(event_type='OTHER'), dict(reported_at=3),
                        dict(reported_at='2026-10-05T12:00:00'), dict(evidence_ref=''),
                        dict(preview_review_confirmed=1), dict(preview_review_confirmed=False),
                        dict(preview_window={'hwnd': True}), dict(extra='field')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.store.submit(self.report(**changes))

    def test_listening_reports_cannot_accept(self):
        self.store.begin_accept()
        for index, event in enumerate(('LISTENED_OK', 'LISTENED_BAD')):
            record = self.store.submit(self.report(report_id=f'listen-{index}', event_type=event,
                preview_window=None, preview_review_confirmed=False))
            self.assertEqual(record['delivery'], 'LATE')
        self.assertIsNone(self.store.claim_accept())

    def test_rejection_stops_acceptance(self):
        self.store.begin_accept()
        self.store.submit(self.report(event_type='REJECTED', preview_review_confirmed=False))
        with self.assertRaisesRegex(ValueError, 'HUMAN_ACCEPT_REJECTED'):
            acceptance_receipt(self.store.claim_accept(), 'operation-1')

    def test_conflicting_pending_decisions_stop(self):
        self.store.begin_accept()
        self.store.submit(self.report())
        self.store.submit(self.report(report_id='reject', event_type='REJECTED'))
        with self.assertRaisesRegex(ValueError, 'CONFLICTING_HUMAN_DECISIONS'):
            self.store.claim_accept()
        self.store.end_accept()
        self.assertTrue(all(r['delivery'] == 'LATE' for r in self.store.snapshot()['human_reports']))

    def test_same_report_concurrent_submissions_are_one_record(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: HumanReportStore(self.root).submit(self.report()), range(8)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(len(self.store.snapshot()['human_reports']), 1)

    def test_finalize_and_submit_are_serialized(self):
        raw = json.dumps(dict(operation_id='operation-1', state='HUMAN_EVENT_TIMEOUT')).encode()
        (self.root/'fast_music_result.json').write_bytes(raw)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.store.finalize, raw), pool.submit(self.store.submit, self.report())]
            for future in futures:
                future.result()
        self.assertEqual(self.store.snapshot()['human_reports'][0]['delivery'], 'LATE')

    def test_deadline_checked_inside_claim(self):
        self.store.begin_accept()
        self.store.submit(self.report())
        self.assertIsNone(self.store.claim_accept(deadline=55, clock=lambda: 55))
        self.store.end_accept()
        self.assertEqual(self.store.snapshot()['human_reports'][0]['delivery'], 'LATE')

    def test_preview_and_payload_cannot_be_replaced(self):
        report = self.report()
        self.store.submit(report)
        report['preview_window']['hwnd'] = 99
        self.assertEqual(self.store.snapshot()['human_reports'][0]['report']['preview_window']['hwnd'], 20)
        with self.assertRaisesRegex(ValueError, 'PREVIEW_CHANGED'):
            self.store.bind_preview({'hwnd': 99})

    def test_explicit_cli_submits_across_processes_without_host(self):
        path = self.root/'user_report.json'
        path.write_text(json.dumps(self.report(), ensure_ascii=False), encoding='utf-8')
        script = Path(__file__).resolve().parents[1]/'scripts/runtime_v2_human_report.py'
        result = subprocess.run([sys.executable, str(script), 'submit', '--session-dir', str(self.root),
            '--report', str(path)], capture_output=True, encoding='utf-8', timeout=5,
            env=dict(__import__('os').environ, PYTHONIOENCODING='utf-8'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['delivery'], 'PENDING')
        self.store.begin_accept()
        self.assertEqual(self.store.claim_accept()['report'], self.report())


if __name__ == '__main__':
    unittest.main()
