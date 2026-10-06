"""审核过的固定预览按钮栏识别；像素匹配不证明工程提交。"""

import hashlib
from pathlib import Path

import numpy as np

TEMPLATE_HASH = 'e340115a21ca6bde8cdf6b9ce2cbd04f74137414f5a27e2bcbdc9e2a95df97f4'
DIALOG_SIZE = (493, 165)
TITLE_CROP = (4, 3, 285, 25)
FOOTER_CROP = (6, 118, 486, 158)
CLICK_POINT = (451, 136)


def _crop(frame, rectangle):
    left, top, right, bottom = rectangle
    return frame[top:bottom, left:right, :3]


class ReviewedAcceptLocator:
    def __init__(self, *, enabled=False):
        self.enabled = enabled
        path = Path(__file__).with_name('fixtures') / 'reviewed_accept_four_note.npz'
        if hashlib.sha256(path.read_bytes()).hexdigest() != TEMPLATE_HASH:
            raise ValueError('VISUAL_ACCEPT_TEMPLATE_CHANGED')
        with np.load(path, allow_pickle=False) as data:
            self.title, self.footer = data['title'].copy(), data['footer'].copy()

    def locate(self, frame, *, preview, expected_rectangle, dpi, foreground_hwnd):
        if self.enabled is not True:
            raise ValueError('VISUAL_ACCEPT_DISABLED')
        rect = preview.get('rectangle')
        if (not isinstance(rect, list) or len(rect) != 4
                or any(type(v) is not int for v in rect)
                or rect != expected_rectangle
                or (rect[2]-rect[0], rect[3]-rect[1]) != DIALOG_SIZE
                or type(dpi) is not int or dpi != 120):
            raise ValueError('VISUAL_ACCEPT_GEOMETRY_CHANGED')
        if (any(type(preview.get(k)) is not int or preview[k] <= 0
                    for k in ('hwnd', 'parent', 'process_id'))
                or type(foreground_hwnd) is not int or foreground_hwnd != preview['hwnd']
                or preview.get('native_title') != 'DAWLoop Native Add'
                or preview.get('window_class') != 'TScriptDialog'
                or any(preview.get(k) is not True for k in ('fixed_title', 'visible', 'enabled'))):
            raise ValueError('VISUAL_ACCEPT_WINDOW_UNPROVEN')
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                or frame.shape != (DIALOG_SIZE[1], DIALOG_SIZE[0], 4)):
            raise ValueError('VISUAL_ACCEPT_FRAME_UNSUPPORTED')
        # 标题由原生窗口信息确认；完整按钮栏仍拒绝任何近似匹配。
        if not np.array_equal(_crop(frame, FOOTER_CROP), self.footer):
            raise ValueError('VISUAL_ACCEPT_TEMPLATE_MISMATCH')
        return dict(control_id='reviewed-accept:' + TEMPLATE_HASH,
            preview_hwnd=preview['hwnd'], process_id=preview['process_id'], role='ACCEPT',
            identity_observed=True, visible=True, enabled=True,
            identity_method='NATIVE_TITLE_AND_CLASS_WITH_EXACT_REVIEWED_BUTTON_BAR',
            native_title=preview['native_title'], window_class=preview['window_class'],
            template_hash=TEMPLATE_HASH, window_rectangle=list(rect), dpi=dpi,
            click_point_relative=list(CLICK_POINT), coordinate_space='CAPTURE_LOGICAL_PIXELS',
            commit_status='UNKNOWN', exact_set_verified=False)

    def capture(self, *, preview, expected_rectangle, dpi, foreground_hwnd,
                capture_factory=None, display_bounds=None):
        from .preview_pixels import RegionCapture
        if self.enabled is not True:
            raise ValueError('VISUAL_ACCEPT_DISABLED')
        if display_bounds is None:
            import win32api
            display_bounds = (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))
        left, top, right, bottom = display_bounds
        x1, y1, x2, y2 = preview['rectangle']
        if not left <= x1 < x2 <= right or not top <= y1 < y2 <= bottom:
            raise ValueError('VISUAL_ACCEPT_OUTSIDE_DISPLAY')
        # 模板来自全屏归一化；先截局部会改变非整数DPI下的采样相位。
        capture = (capture_factory or RegionCapture)(tuple(display_bounds))
        try:
            if tuple(capture.scale) != (1.25, 1.25):
                raise ValueError('VISUAL_ACCEPT_CAPTURE_SCALE_CHANGED')
            full, start, end = capture.grab()
            if full.shape != (bottom-top, right-left, 4):
                raise ValueError('VISUAL_ACCEPT_DISPLAY_GEOMETRY_CHANGED')
            frame = full[y1-top:y2-top, x1-left:x2-left].copy()
            control = self.locate(frame, preview=preview, expected_rectangle=expected_rectangle,
                dpi=dpi, foreground_hwnd=foreground_hwnd)
            return dict(control=control, capture_started_ns=start, capture_completed_ns=end,
                pixel_sha256=hashlib.sha256(frame[:, :, :3].tobytes()).hexdigest())
        finally:
            capture.close()
