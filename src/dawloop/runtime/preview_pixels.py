"""固定音符区域的只读采样；像素区间不是绘制完成时刻。"""

import threading
import time
import numpy as np

ROI = (620, 300, 850, 450)


def note_geometry(frame, chroma_floor):
    pixels = frame[:, :, :3].astype(np.int16)
    blue, green, red = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    mask = (green-red > chroma_floor[0]) & (green-blue > chroma_floor[1])
    columns = np.flatnonzero(mask.sum(axis=0) >= 4)
    groups = np.split(columns, np.flatnonzero(np.diff(columns) > 1)+1) if len(columns) else []
    boxes = []
    for group in groups:
        if 8 <= len(group) <= 32:
            ys = np.flatnonzero(mask[:, group].sum(axis=1) >= 4)
            if len(ys) and 6 <= ys[-1]-ys[0]+1 <= 24:
                boxes.append([int(group[0]), int(ys[0]), int(group[-1]+1), int(ys[-1]+1)])
    if len(boxes) != 4:
        return False, boxes
    centers = [(float((a+c)/2), float((b+d)/2)) for a,b,c,d in boxes]
    valid = all(25 <= centers[i+1][0]-centers[i][0] <= 55 and
        8 <= centers[i][1]-centers[i+1][1] <= 28 for i in range(3))
    return valid, boxes


class PixelDetector:
    def __init__(self, baseline, persist=3, stable=5):
        samples = np.stack(baseline).astype(np.float32)
        self.mean = samples.mean(axis=0)
        self.noise = float(np.max(np.mean(np.abs(samples-self.mean), axis=(1,2,3))))
        self.threshold = self.noise + max(0.5, self.noise*4)
        pixels = samples[:, :, :, :3]
        self.chroma_floor = [float(np.max(pixels[:,:,:,1]-pixels[:,:,:,2]))+8,
            float(np.max(pixels[:,:,:,1]-pixels[:,:,:,0]))+8]
        self.stable_threshold = max(0.25, self.noise*2)
        self.persist, self.stable = persist, stable
        self.pending = []
        self.onset = None
        self.stable_at = None
        self.streak = 0
        self.previous = baseline[-1]
        self.previous_end = None
        self.last_absent_start = None

    def feed(self, frame, start, end):
        value = frame.astype(np.float32)
        mad = float(np.mean(np.abs(value-self.mean)))
        change = float(np.mean(np.abs(value-self.previous)))
        ratio = float(np.mean(np.max(np.abs(value-self.mean), axis=2) > max(2,self.noise*4)))
        matches, boxes = note_geometry(frame, self.chroma_floor)
        eligible = mad > self.threshold and matches
        row = dict(capture_start_ns=start, capture_end_ns=end, mad=mad,
            changed_pixel_ratio=ratio, frame_change=change, four_note_geometry=matches,
            boxes=boxes, candidate=eligible)
        if self.onset is None:
            if eligible:
                self.pending.append(row)
                if len(self.pending) >= self.persist:
                    self.onset = dict(first_capture_start_ns=self.pending[0]['capture_start_ns'],
                        observed_at_ns=self.pending[0]['capture_end_ns'], confirmed_at_ns=end,
                        last_absent_capture_start_ns=self.last_absent_start,
                        clock_domain='python_perf_counter')
            else:
                self.pending.clear()
                self.last_absent_start = start
        if self.onset:
            self.streak = self.streak+1 if eligible and change <= self.stable_threshold else 0
            if self.streak >= self.stable and self.stable_at is None:
                self.stable_at = end
        self.previous = frame.copy()
        self.previous_end = end
        return row


class RegionCapture:
    def __init__(self, roi=ROI):
        import win32gui, win32ui, win32con
        self.gui, self.ui, self.con = win32gui, win32ui, win32con
        self.roi = roi
        self.width, self.height = roi[2]-roi[0], roi[3]-roi[1]
        self.screen_handle = win32gui.GetDC(0)
        self.screen = win32ui.CreateDCFromHandle(self.screen_handle)
        self.scale = (self.screen.GetDeviceCaps(118)/self.screen.GetDeviceCaps(8),
            self.screen.GetDeviceCaps(117)/self.screen.GetDeviceCaps(10))
        self.physical_roi = tuple(round(v*self.scale[i%2]) for i,v in enumerate(roi))
        self.physical_width = self.physical_roi[2]-self.physical_roi[0]
        self.physical_height = self.physical_roi[3]-self.physical_roi[1]
        self.memory = self.screen.CreateCompatibleDC()
        self.bitmap = win32ui.CreateBitmap()
        self.bitmap.CreateCompatibleBitmap(self.screen, self.physical_width, self.physical_height)
        self.original = self.memory.SelectObject(self.bitmap)

    def grab(self):
        start = time.perf_counter_ns()
        self.memory.BitBlt((0,0),(self.physical_width,self.physical_height),self.screen,self.physical_roi[:2],
            self.con.SRCCOPY | 0x40000000)
        frame = np.frombuffer(self.bitmap.GetBitmapBits(True), dtype=np.uint8).reshape(
            self.physical_height,self.physical_width,4)
        ys = np.linspace(0,self.physical_height-1,self.height).astype(int)
        xs = np.linspace(0,self.physical_width-1,self.width).astype(int)
        frame = frame[ys[:,None],xs].copy()
        return frame, start, time.perf_counter_ns()

    def close(self):
        self.memory.SelectObject(self.original)
        self.gui.DeleteObject(self.bitmap.GetHandle())
        self.memory.DeleteDC()
        self.screen.DeleteDC()
        self.gui.ReleaseDC(0,self.screen_handle)


