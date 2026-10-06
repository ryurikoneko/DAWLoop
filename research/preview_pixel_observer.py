import threading
import time
import numpy as np
from dawloop.runtime.preview_pixels import ROI, PixelDetector, RegionCapture, note_geometry


class PixelObserver:
    def __init__(self, capture_factory=RegionCapture):
        self.capture_factory = capture_factory
        self.full_frames = {}
        self.stop_event = threading.Event()
        self.baseline_ready = threading.Event()
        self.rows, self.frames = [], {}
        self.error = None
        self.detector = None
        self.missed = 0

    def start(self):
        def sample():
            capture = None
            baseline = []
            period = 1_000_000_000//60
            deadline = time.perf_counter_ns()
            try:
                capture = self.capture_factory()
                self.capture_geometry = dict(scale=list(capture.scale),
                    physical_roi=list(capture.physical_roi), normalization='NEAREST_LOGICAL_GRID')
                while not self.stop_event.is_set() and len(self.rows) < 7200:
                    frame, start, end = capture.grab()
                    if self.detector is None:
                        baseline.append(frame)
                        row = dict(capture_start_ns=start, capture_end_ns=end, baseline=True)
                        if len(baseline) == 40:
                            self.detector = PixelDetector(baseline)
                            self.frames['baseline'] = frame
                            self.baseline_ready.set()
                    else:
                        row = self.detector.feed(frame,start,end)
                        if row['candidate'] and 'candidate' not in self.frames:
                            self.frames['candidate'] = frame
                        if self.detector.onset and 'onset_confirmed' not in self.frames:
                            self.frames['onset_confirmed'] = frame
                        if self.detector.stable_at and 'stable' not in self.frames:
                            self.frames['stable'] = frame
                        if not row['candidate'] and self.detector.onset is None:
                            self.frames['pre_onset'] = frame
                    if getattr(capture, 'full_frame', None) is not None:
                        for name, image in self.frames.items():
                            if getattr(self, '_frame_refs', {}).get(name) is not image:
                                self.full_frames[name] = capture.full_frame.copy()
                        self._frame_refs = dict(self.frames)
                    self.rows.append(row)
                    deadline += period
                    now = time.perf_counter_ns()
                    if now > deadline:
                        missed = (now-deadline)//period+1
                        self.missed += missed
                        deadline += missed*period
                    self.stop_event.wait(max(0,(deadline-now)/1e9))
            except Exception as error:
                self.error = type(error).__name__ + ': ' + str(error)
                self.baseline_ready.set()
            finally:
                if capture:
                    capture.close()
        self.thread = threading.Thread(target=sample,daemon=True)
        self.thread.start()
        if not self.baseline_ready.wait(5) or self.error:
            self.stop()
            raise ValueError('PIXEL_BASELINE_UNAVAILABLE')

    def stop(self):
        self.stop_event.set()
        if hasattr(self,'thread'):
            self.thread.join(5)
            if self.thread.is_alive():
                raise ValueError('PIXEL_OBSERVER_STOP_UNCONFIRMED')

    def result(self):
        durations = [(r['capture_end_ns']-r['capture_start_ns'])/1e6 for r in self.rows]
        ends = [r['capture_end_ns'] for r in self.rows]
        return dict(diagnostic_only=True, runtime_state_emitted=False, exact_set_verified=False, clock_domain='python_perf_counter', roi=list(ROI), target_fps=60,
            capture_geometry=getattr(self,'capture_geometry',None),
            actual_fps=(len(ends)-1)*1e9/(ends[-1]-ends[0]) if len(ends)>1 else None,
            average_capture_ms=float(np.mean(durations)) if durations else None,
            max_capture_ms=max(durations) if durations else None,
            max_frame_gap_ms=max(np.diff(ends))/1e6 if len(ends)>1 else None,
            missed_scheduled_slots=self.missed, dropped_frames=None,
            dropped_frames_semantics='NO_GPU_FRAME_COUNTER_AVAILABLE',error=self.error,
            baseline_noise=self.detector.noise if self.detector else None,
            threshold=self.detector.threshold if self.detector else None,
            chroma_floor=self.detector.chroma_floor if self.detector else None,
            onset=self.detector.onset if self.detector else None,
            stable_ns=self.detector.stable_at if self.detector else None,frames=self.rows)
