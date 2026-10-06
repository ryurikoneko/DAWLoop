"""独立全景观察的生命周期及采样区间，不向运行时发送就绪。"""

import hashlib
from pathlib import Path
import time

import numpy as np

from full_screen_preview_capture import FullScreenPreviewCapture
from preview_pixel_observer import PixelObserver
from dawloop.runtime.local_preview import LocalPreviewInteraction


class FullScreenDiagnosticInteraction(LocalPreviewInteraction):
    def __init__(self, *args, diagnostic, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostic = diagnostic

    def before_dispatch(self):
        super().before_dispatch()
        self.diagnostic.mark_dispatch(self.dispatch_at)


def onset_interval(onset, dispatch_at):
    if dispatch_at is None:
        return dict(status='NOT_DISPATCHED', interval_ms=None)
    if onset is None:
        return dict(status='NOT_OBSERVED', interval_ms=None)
    first = onset['first_capture_start_ns']
    absent = onset.get('last_absent_capture_start_ns')
    if first < dispatch_at:
        return dict(status='PRE_DISPATCH_SIGNAL', interval_ms=None)
    if absent is None:
        return dict(status='ABSENT_BOUND_UNAVAILABLE', interval_ms=None)
    lower = max(absent, dispatch_at)
    upper = onset['observed_at_ns']
    if lower > upper or onset['confirmed_at_ns'] < upper:
        return dict(status='INVALID_TIME_ORDER', interval_ms=None)
    return dict(status='DIAGNOSTIC_VISIBLE_CHANGE',
        interval_ms=[(lower-dispatch_at)/1e6, (upper-dispatch_at)/1e6],
        observed_to_confirmation_ms=(onset['confirmed_at_ns']-upper)/1e6,
        reference='LOCAL_PRE_HOST_DISPATCH_HOOK',
        meaning='SAMPLING_BOUND_ONLY_NOT_HOST_PIPELINE_LATENCY')


class FullScreenLiveDiagnostic:
    def __init__(self, private_directory, repository, roi, observer_factory=None):
        self.directory = Path(private_directory).resolve()
        if self.directory.is_relative_to(Path(repository).resolve()):
            raise ValueError('FULL_SCREEN_EVIDENCE_MUST_BE_PRIVATE')
        self.roi = tuple(roi)
        self.observer = (observer_factory or (lambda: PixelObserver(
            capture_factory=lambda: FullScreenPreviewCapture(self.roi))))()
        self.dispatch_at = None
        self.started_at = self.ready_at = None
        self.stop_confirmed = False

    def start(self):
        self.directory.mkdir(parents=True, exist_ok=False)
        self.started_at = time.perf_counter_ns()
        self.observer.start()
        self.ready_at = time.perf_counter_ns()

    def mark_dispatch(self, timestamp):
        if self.dispatch_at is not None:
            raise ValueError('DIAGNOSTIC_SINGLE_DISPATCH_ONLY')
        self.dispatch_at = timestamp

    def close(self):
        self.observer.stop()
        self.stop_confirmed = True

    def report(self):
        if not self.stop_confirmed:
            raise ValueError('FULL_SCREEN_STOP_NOT_CONFIRMED')
        result = self.observer.result()
        # 公开记录不传播底层异常文本中的路径或窗口名称。
        if result.get('error'):
            result['error'] = result['error'].split(':', 1)[0]
        result.update(scope='LIVE_FULL_SCREEN_DIAGNOSTIC_ONLY', roi=list(self.roi),
            diagnostic_only=True, runtime_state_emitted=False, exact_set_verified=False,
            observer_stopped=True, started_at_ns=self.started_at, ready_at_ns=self.ready_at,
            dispatch_hook_at_ns=self.dispatch_at,
            onset_interval=onset_interval(result.get('onset'), self.dispatch_at),
            full_frame_hashes={}, full_frames_in_repository=False)
        for name, frame in self.observer.full_frames.items():
            with (self.directory/(name+'.npy')).open('xb') as stream:
                np.save(stream, frame)
            result['full_frame_hashes'][name] = hashlib.sha256(frame.tobytes()).hexdigest()
        return result
