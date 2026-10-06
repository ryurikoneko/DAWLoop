"""独立全屏诊断不参与派发授权，检测区域来自同一张全景。"""

from dawloop.runtime.preview_pixels import ROI, RegionCapture


class FullScreenPreviewCapture:
    def __init__(self, roi=ROI, capture_factory=RegionCapture, bounds=None):
        if bounds is None:
            import win32api
            bounds = (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))
        self.bounds, self.roi = tuple(bounds), tuple(roi)
        left, top, right, bottom = self.bounds
        x1, y1, x2, y2 = self.roi
        if not (left <= x1 < x2 <= right and top <= y1 < y2 <= bottom):
            raise ValueError('DIAGNOSTIC_ROI_OUTSIDE_DISPLAY')
        self.capture = capture_factory(self.bounds)
        self.scale = self.capture.scale
        self.physical_roi = self.capture.physical_roi
        self.full_frame = None

    def grab(self):
        full, start, end = self.capture.grab()
        left, top, right, bottom = self.bounds
        if full.shape != (bottom-top, right-left, 4):
            raise ValueError('DIAGNOSTIC_DISPLAY_GEOMETRY_CHANGED')
        self.full_frame = full
        x1, y1, x2, y2 = self.roi
        return full[y1-top:y2-top, x1-left:x2-left].copy(), start, end

    def close(self):
        self.capture.close()
