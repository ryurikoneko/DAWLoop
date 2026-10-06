"""全景与区域必须同帧，诊断采集不能认证运行时。"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
from full_screen_preview_capture import FullScreenPreviewCapture
from preview_pixel_observer import PixelObserver


class Capture:
    def __init__(self, bounds):
        self.scale = (1.25, 1.25)
        self.physical_roi = bounds
        self.calls = 0
        self.closed = False
        self.frame = np.arange(20*30*4, dtype=np.uint8).reshape(20, 30, 4)

    def grab(self):
        self.calls += 1
        return self.frame, 10, 20

    def close(self):
        self.closed = True


def test_full_and_roi_share_one_capture_and_timestamps():
    capture = FullScreenPreviewCapture((5, 3, 15, 13), Capture, (0, 0, 30, 20))
    roi, start, end = capture.grab()
    assert (start, end) == (10, 20) and capture.capture.calls == 1
    np.testing.assert_array_equal(roi, capture.full_frame[3:13, 5:15])
    roi[:] = 0
    assert capture.full_frame[3:13, 5:15].any()
    capture.close()
    assert capture.capture.closed


def test_invalid_region_never_opens_capture():
    with pytest.raises(ValueError, match='OUTSIDE_DISPLAY'):
        FullScreenPreviewCapture((5, 3, 35, 13), Capture, (0, 0, 30, 20))


def test_changed_display_shape_is_rejected():
    capture = FullScreenPreviewCapture((5, 3, 15, 13), Capture, (0, 0, 30, 20))
    capture.capture.frame = np.zeros((10, 30, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match='GEOMETRY_CHANGED'):
        capture.grab()
    capture.close()


def test_diagnostic_observer_has_no_runtime_authority():
    observer = PixelObserver(capture_factory=FullScreenPreviewCapture)
    result = observer.result()
    assert result['diagnostic_only'] is True
    assert result['runtime_state_emitted'] is False
    assert result['exact_set_verified'] is False
    assert len(observer.full_frames) == 0


def test_observer_retains_bounded_same_frame_snapshots_and_closes_capture():
    instances = []

    class Desktop(Capture):
        def __init__(self, bounds):
            super().__init__(bounds)
            self.frame = np.full((170, 250, 4), 50, dtype=np.uint8)
            instances.append(self)

    observer = PixelObserver(capture_factory=lambda: FullScreenPreviewCapture(
        (0, 0, 230, 150), Desktop, (0, 0, 250, 170)))
    try:
        observer.start()
        assert observer.baseline_ready.is_set()
    finally:
        observer.stop()
    assert instances[0].closed and not observer.thread.is_alive()
    assert 1 <= len(observer.full_frames) <= 5
    for name, frame in observer.full_frames.items():
        np.testing.assert_array_equal(observer.frames[name], frame[:150, :230])
