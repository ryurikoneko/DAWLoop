"""诊断不接管运行时，失败与成功结果必须分开。"""

from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
from full_screen_live_diagnostic import FullScreenLiveDiagnostic, FullScreenDiagnosticInteraction, onset_interval
from dawloop.runtime.local_preview import LocalPreviewInteraction


def test_pre_dispatch_and_unknown_bounds_are_not_certified():
    onset = dict(first_capture_start_ns=50, observed_at_ns=70,
                 confirmed_at_ns=100, last_absent_capture_start_ns=20)
    assert onset_interval(onset, 60)['status'] == 'PRE_DISPATCH_SIGNAL'
    assert onset_interval(onset, None)['status'] == 'NOT_DISPATCHED'
    assert onset_interval(None, 60)['status'] == 'NOT_OBSERVED'
    onset['last_absent_capture_start_ns'] = None
    assert onset_interval(onset, 10)['status'] == 'ABSENT_BOUND_UNAVAILABLE'


def test_interval_uses_same_local_clock_and_labels_dispatch_proxy():
    onset = dict(first_capture_start_ns=4_000_000, observed_at_ns=5_000_000,
        confirmed_at_ns=8_000_000, last_absent_capture_start_ns=2_000_000)
    result = onset_interval(onset, 1_000_000)
    assert result['interval_ms'] == [1, 4]
    assert result['observed_to_confirmation_ms'] == 3
    assert result['reference'] == 'LOCAL_PRE_HOST_DISPATCH_HOOK'


class Observer:
    def __init__(self):
        self.started = self.stopped = False
        self.full_frames = {'baseline': np.zeros((5, 5, 4), dtype=np.uint8)}

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def result(self):
        return dict(onset=None, error='ValueError: private/path')


def test_diagnostic_survives_runtime_rejection_and_saves_only_private_frames(tmp_path):
    observer = Observer()
    repository = tmp_path/'repo'
    private = tmp_path/'private'
    diagnostic = FullScreenLiveDiagnostic(private, repository, (0, 0, 5, 5), lambda: observer)
    diagnostic.start()
    diagnostic.mark_dispatch(10)
    runtime_result = {'status': 'UNKNOWN', 'reason': 'ROI_OCCLUDED'}
    assert not observer.stopped
    diagnostic.close()
    report = diagnostic.report()
    assert observer.stopped and report['observer_stopped']
    assert report['error'] == 'ValueError'
    assert not report['runtime_state_emitted'] and not report['exact_set_verified']
    assert runtime_result == {'status': 'UNKNOWN', 'reason': 'ROI_OCCLUDED'}
    assert (private/'baseline.npy').exists() and not repository.exists()
    with pytest.raises(ValueError, match='SINGLE_DISPATCH'):
        diagnostic.mark_dispatch(20)


def test_repository_output_and_unconfirmed_stop_are_rejected(tmp_path):
    with pytest.raises(ValueError, match='MUST_BE_PRIVATE'):
        FullScreenLiveDiagnostic(tmp_path/'repo/images', tmp_path/'repo', (0, 0, 5, 5))
    diagnostic = FullScreenLiveDiagnostic(tmp_path/'private', tmp_path/'repo', (0, 0, 5, 5), Observer)
    with pytest.raises(ValueError, match='STOP_NOT_CONFIRMED'):
        diagnostic.report()


def test_baseline_failure_can_be_closed_without_dispatch(tmp_path):
    class Broken(Observer):
        def start(self):
            raise ValueError('BASELINE_FAILURE')
    diagnostic = FullScreenLiveDiagnostic(tmp_path/'private', tmp_path/'repo', (0, 0, 5, 5), Broken)
    with pytest.raises(ValueError, match='BASELINE_FAILURE'):
        diagnostic.start()
    diagnostic.close()
    assert diagnostic.report()['onset_interval']['status'] == 'NOT_DISPATCHED'


def test_original_pre_dispatch_rejection_does_not_mark_diagnostic(monkeypatch):
    calls = []
    class Diagnostic:
        def mark_dispatch(self, timestamp):
            calls.append(timestamp)
    def reject(self):
        raise ValueError('VIEWPORT_INVALIDATED')
    monkeypatch.setattr(LocalPreviewInteraction, 'before_dispatch', reject)
    interaction = FullScreenDiagnosticInteraction(None, None, trace_id='t', diagnostic=Diagnostic())
    with pytest.raises(ValueError, match='VIEWPORT_INVALIDATED'):
        interaction.before_dispatch()
    assert not calls


def test_local_close_does_not_stop_independent_diagnostic(monkeypatch):
    import asyncio
    class Diagnostic:
        stopped = False
        def mark_dispatch(self, timestamp):
            self.timestamp = timestamp
    diagnostic = Diagnostic()
    monkeypatch.setattr(LocalPreviewInteraction, 'before_dispatch', lambda self: setattr(self, 'dispatch_at', 100))
    interaction = FullScreenDiagnosticInteraction(None, None, trace_id='t', diagnostic=diagnostic)
    interaction.before_dispatch()
    asyncio.run(interaction.close())
    assert diagnostic.timestamp == 100 and not diagnostic.stopped
