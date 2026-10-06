import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_preview_observer', ROOT / 'research/native_preview_observer.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
analysis_spec = importlib.util.spec_from_file_location('analyze_native_preview', ROOT / 'research/analyze_native_preview.py')
analysis = importlib.util.module_from_spec(analysis_spec)
analysis_spec.loader.exec_module(analysis)


class NativeObserverTests(unittest.TestCase):
    def test_bounded_buffer_and_receipt_clock(self):
        counter = iter(range(100, 1000))
        buffer = observer.EventBuffer(limit=1, clock=lambda: next(counter))
        buffer.capture(0x8002, 123, 0, 0, 7, 999999)
        buffer.capture(0x8002, 124, 0, 0, 7, 888888)
        row = buffer.rows[0]
        self.assertEqual(row['callback_enter'], 100)
        self.assertEqual(row['callback_exit'], 101)
        self.assertEqual(row['dwmsEventTime'], 999999)
        self.assertEqual(buffer.dropped, 1)
        self.assertEqual(buffer.depth, 0)
        self.assertEqual(buffer.sequence, 2)

    def test_reentry_is_reported_without_resolving_window(self):
        buffer = observer.EventBuffer()
        buffer.depth = 1
        buffer.capture(0x8000, 123, -4, 0, 7, 5)
        self.assertTrue(buffer.rows[0]['reentrant'])
        self.assertNotIn('details', buffer.rows[0])

    def test_private_window_names_are_not_exported(self):
        self.assertEqual(observer.safe_name(observer.TITLE), observer.TITLE)
        self.assertEqual(observer.safe_name('私人作品'), '<已脱敏>')
        self.assertEqual(observer.safe_name(''), '')

    def test_zero_pid_rejected_before_loading_native_library(self):
        for pid in (0, -1, None, True):
            with self.assertRaisesRegex(ValueError, 'EXPLICIT_HOST_PID_REQUIRED'):
                observer.NativeEventObserver(pid, 'test')

    def test_draining_does_not_reset_total_budget(self):
        buffer = observer.EventBuffer(limit=1)
        buffer.capture(0x8002, 1, 0, 0, 7, 5)
        buffer.rows.popleft()
        buffer.capture(0x8002, 2, 0, 0, 7, 6)
        self.assertEqual(len(buffer.rows), 0)
        self.assertEqual(buffer.dropped, 1)

    def test_candidate_requires_identity_novelty_and_same_clock(self):
        before = dict(windows=[dict(hwnd=1)])
        after = dict(windows=[dict(hwnd=2, fixed_probe_title_match=True,
            class_name='TScriptDialog', visible=True)])
        row = dict(event='SHOW', idObject=0, idChild=0, clock_domain='python_perf_counter',
            timestamp_unit='ns', trace_id='t', callback_enter=100, hwnd=2,
            details=dict(process_id=7, fixed_probe_title_match=True,
                class_name='TScriptDialog', parent_hwnd=1))
        self.assertIsNotNone(analysis.select_candidate([row], before, after, 90, 7, 't'))
        for field, value in (('event', 'CREATE'), ('clock_domain', 'system_milliseconds'),
                             ('trace_id', 'old'), ('callback_enter', 80), ('hwnd', 1)):
            self.assertIsNone(analysis.select_candidate([dict(row, **{field: value})], before, after, 90, 7, 't'))
        self.assertIsNone(analysis.select_candidate([row], before, after, 90, 8, 't'))
        self.assertIsNone(analysis.select_candidate([row, row], before, after, 90, 7, 't'))
