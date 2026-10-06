"""固定四音符的实验本地预览观察；不提供写入验证。"""

import asyncio
import copy
import hashlib
from dataclasses import dataclass, asdict
import threading
import time

from .native_write import PianoRollScriptRenderer

FIXED_HASH = 'ac68744417a7b98f7c2a7c2293ba255b73e6d99ecd3609618af0f501f786da75'
TARGET_KEYS = ('controller_session', 'project_generation', 'pattern_number', 'pattern_name',
    'channel_index', 'channel_name', 'selected_channels', 'ppq')


@dataclass(frozen=True)
class PreviewObservation:
    trace_id: str
    operation_id: str
    host_generation: str
    bridge_epoch: str
    capture_started_at: int
    baseline_completed_at: int
    dispatch_at: int
    preview_detected_at: int
    confirmation_at: int
    last_absent_capture_started_at: int
    roi: tuple
    frame_interval_ms: float | None
    detection_method: str = 'FIXED_FOUR_NOTE_THREE_FRAME_CONFIRMATION'
    confidence: str = 'RULE_MATCH_IN_FIXED_TEST_SCOPE'
    clock_domain: str = 'python_perf_counter'
    verification_status: str = 'NOT_VERIFIED'


class LocalPreviewInteraction:
    local_preview = True

    def __init__(self, viewport, manual, *, trace_id, clock=time.perf_counter_ns,
                 capture_factory=None, detector_factory=None, ready_callback=None):
        self.viewport, self.manual, self.trace_id = viewport, manual, trace_id
        self.clock = clock
        self.ready_callback = ready_callback
        self.capture_factory, self.detector_factory = capture_factory, detector_factory
        self.stop_event = threading.Event()
        self.baseline_ready = threading.Event()
        self.lock = threading.Lock()
        self.dispatch_at = None
        self.error = None
        self.frames, self.rows = {}, []
        self.observation = None
        self.baseline_fingerprint = None
        self.missed_slots = 0
        self.invalidation = None

    @staticmethod
    def _safe_evidence(value):
        result = copy.deepcopy(value)
        for key in ('pattern_name', 'channel_name'):
            if key in result:
                raw = result.pop(key)
                result[key + '_hash'] = hashlib.sha256(str(raw).encode('utf-8')).hexdigest()
        return result

    def _record_invalidation(self, stage, reason, before=None, after=None, details=None):
        if self.invalidation is not None:
            return
        after_available = after is not None
        before, after = before or {}, after or {}
        keys = sorted(set(before) | set(after))
        self.invalidation = dict(stage=stage, reason=reason, observed_at=self.clock(),
            clock_domain='python_perf_counter', dispatched=self.dispatch_at is not None,
            changed_fields=[k for k in keys if before.get(k) != after.get(k)] if after_available else [],
            after_available=after_available,
            before=self._safe_evidence(before), after=self._safe_evidence(after),
            details=copy.deepcopy(details or {}))

    def _fingerprint(self, stage):
        try:
            current = self.viewport.fingerprint()
        except Exception as error:
            self._record_invalidation(stage, getattr(error, 'reason', 'FINGERPRINT_READ_ERROR'),
                self.baseline_fingerprint, details=getattr(error, 'details', {}))
            self._invalidate(str(error))
            raise
        if self.baseline_fingerprint is not None and current != self.baseline_fingerprint:
            self._record_invalidation(stage, 'FINGERPRINT_CHANGED', self.baseline_fingerprint,
                current, getattr(self.viewport, 'last_inspection', {}))
            self._invalidate('VIEWPORT_INVALIDATED')
            raise ValueError('VIEWPORT_INVALIDATED')
        return current

    @staticmethod
    def identity(evidence):
        return {k: copy.deepcopy(evidence['identity'].get(k)) for k in TARGET_KEYS}

    async def prepare_preview(self, plan, session, evidence):
        self.prepare_started_at = self.clock()
        if PianoRollScriptRenderer().render(plan.parameters['notes']).sha256 != FIXED_HASH:
            raise ValueError('LOCAL_PREVIEW_SCOPE_UNSUPPORTED')
        if hasattr(self, 'thread'):
            raise ValueError('LOCAL_PREVIEW_SINGLE_USE')
        self.operation_id = plan.metadata['operation_id']
        self.session = copy.deepcopy(session)
        self.target = self.identity(evidence)
        self.loop = asyncio.get_running_loop()
        self.future = self.loop.create_future()
        self.baseline_fingerprint = self._fingerprint('INITIAL_BASELINE')
        self.capture_started_at = self.clock()
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()
        if not await asyncio.to_thread(self.baseline_ready.wait, 5):
            await self.close()
            raise ValueError('LOCAL_PREVIEW_BASELINE_TIMEOUT')
        if self.error:
            await self.close()
            raise ValueError(self.error)
        self.prepare_ready_at = self.clock()

    def _invalidate(self, code):
        self.error = code
        self.baseline_ready.set()
        if hasattr(self, 'future'):
            self.loop.call_soon_threadsafe(self._deliver_error, code)

    def _deliver_error(self, code):
        if not self.future.done():
            self.future.set_exception(ValueError(code))

    def reconfirm_preview(self, evidence):
        with self.lock:
            if self.error or self.identity(evidence) != self.target:
                self._record_invalidation('TARGET_RECONFIRM', 'TARGET_CHANGED', self.target,
                    self.identity(evidence))
                self._invalidate('VIEWPORT_INVALIDATED')
                raise ValueError('VIEWPORT_INVALIDATED')
            self._fingerprint('BASELINE_RECONFIRM')

    def before_dispatch(self):
        with self.lock:
            if self.error:
                self._invalidate('VIEWPORT_INVALIDATED')
                raise ValueError('VIEWPORT_INVALIDATED')
            self._fingerprint('FINAL_PRE_DISPATCH')
            self.dispatch_at = self.clock()

    def _preview_confirmation_allowed(self):
        return True

    def _deliver(self, observation):
        if self.stop_event.is_set() or self.error or self.future.done():
            return
        if (observation.operation_id != self.operation_id
                or observation.host_generation != self.session['host_generation']
                or observation.bridge_epoch != self.session['bridge_epoch']):
            self._deliver_error('LOCAL_PREVIEW_CONTEXT_MISMATCH')
            return
        self.observation = observation
        self.future.set_result(dict(observed=True, operation_id=self.operation_id,
            local_preview=True, observation=asdict(observation)))

    def _sample(self):
        from .preview_pixels import RegionCapture, PixelDetector, note_geometry
        factory = self.capture_factory or RegionCapture
        detector_factory = self.detector_factory or PixelDetector
        capture = None
        baseline = []
        try:
            capture = factory(tuple(self.baseline_fingerprint['roi']))
            period = 1_000_000_000 // 60
            deadline = self.clock()
            previous_end = None
            while not self.stop_event.is_set():
                with self.lock:
                    cycle_start = self.clock()
                    stage = ('POST_DISPATCH_SAMPLE' if self.dispatch_at is not None
                        else 'BASELINE_SAMPLE' if len(baseline) < 40 else 'ARMED_SAMPLE')
                    try:
                        self._fingerprint(stage)
                    except Exception:
                        rejected_at = self.clock()
                        self.rows.append(dict(cycle_start_ns=cycle_start, cycle_end_ns=rejected_at,
                            fingerprint_completed_ns=rejected_at, capture_start_ns=None,
                            capture_end_ns=None, detection_completed_ns=None, outcome='GUARD_REJECTED'))
                        raise
                    fingerprint_end = self.clock()
                    frame, start, end = capture.grab()
                    cycle = dict(cycle_start_ns=cycle_start, fingerprint_completed_ns=fingerprint_end,
                        capture_start_ns=start, capture_end_ns=end, detection_completed_ns=None,
                        cycle_end_ns=None, outcome='CAPTURED')
                    self.rows.append(cycle)
                    if len(self.rows) > 7200:
                        raise ValueError('LOCAL_PREVIEW_OBSERVATION_LIMIT')
                    if len(baseline) < 40:
                        baseline.append(frame)
                        if len(baseline) == 40:
                            self.detector = detector_factory(baseline)
                            if any(note_geometry(f, (8, 8))[0] for f in baseline):
                                raise ValueError('PREVIEW_ALREADY_EXISTS')
                            self.baseline_completed_at = end
                            self.detector.last_absent_start = start
                            self.frames['baseline'] = frame
                            self.baseline_ready.set()
                    elif self.dispatch_at is None:
                        # 基线完成至派发期间不得把已经出现的候选认作本次结果。
                        row = self.detector.feed(frame, start, end)
                        if row['candidate']:
                            self._record_invalidation('ARMED_SAMPLE', 'PRE_DISPATCH_CANDIDATE')
                            raise ValueError('VIEWPORT_INVALIDATED')
                    else:
                        row = self.detector.feed(frame, start, end)
                        onset = self.detector.onset
                        if onset and self._preview_confirmation_allowed():
                            if onset['first_capture_start_ns'] < self.dispatch_at:
                                raise ValueError('LOCAL_PREVIEW_PRE_DISPATCH_CANDIDATE')
                            self.frames['confirmed'] = frame
                            observation = PreviewObservation(self.trace_id, self.operation_id,
                                self.session['host_generation'], self.session['bridge_epoch'],
                                self.capture_started_at, self.baseline_completed_at, self.dispatch_at,
                                onset['observed_at_ns'], onset['confirmed_at_ns'],
                                max(self.dispatch_at, onset['last_absent_capture_start_ns']),
                                tuple(self.baseline_fingerprint['roi']),
                                (end-previous_end)/1e6 if previous_end else None)
                            self.loop.call_soon_threadsafe(self._deliver, observation)
                            cycle.update(detection_completed_ns=self.clock(), cycle_end_ns=self.clock(),
                                outcome='CONFIRMED')
                            break
                    cycle.update(detection_completed_ns=self.clock(), cycle_end_ns=self.clock(),
                        outcome='COMPLETE')
                previous_end = end
                deadline += period
                now = self.clock()
                if now > deadline:
                    count = (now-deadline)//period+1
                    self.missed_slots += count
                    deadline += count*period
                self.stop_event.wait(max(0, (deadline-now)/1e9))
        except Exception as error:
            if self.rows and self.rows[-1].get('cycle_end_ns') is None:
                self.rows[-1].update(cycle_end_ns=self.clock(), outcome='ABORTED')
            self._invalidate(str(error))
        finally:
            if capture:
                capture.close()

    async def wait_preview(self, operation_id):
        if operation_id != self.operation_id:
            raise ValueError('LOCAL_PREVIEW_CONTEXT_MISMATCH')
        return await asyncio.wait_for(asyncio.shield(self.future), 90)

    async def wait_accept(self, operation_id):
        return await self.manual.wait_accept(operation_id)

    def runtime_ready(self, timestamp):
        self.runtime_ready_at = timestamp
        if self.ready_callback:
            self.ready_callback(self.operation_id, timestamp)

    async def wait_application(self, operation_id):
        return await self.manual.wait_application(operation_id)

    async def guarded_auto_accept(self, *args):
        raise ValueError('AUTO_ACCEPT_DISABLED')

    async def close(self):
        self.stop_event.set()
        if hasattr(self, 'thread'):
            await asyncio.to_thread(self.thread.join, 5)
            if self.thread.is_alive():
                raise ValueError('LOCAL_PREVIEW_STOP_UNCONFIRMED')
        if hasattr(self, 'future'):
            if self.future.done() and not self.future.cancelled():
                self.future.exception()
            else:
                self.future.cancel()

    def metrics(self):
        durations = [(r['capture_end_ns']-r['capture_start_ns'])/1e6 for r in self.rows
            if r['capture_start_ns'] is not None]
        def elapsed(start, end):
            values = [(r[end]-r[start])/1e6 for r in self.rows
                if r.get(start) is not None and r.get(end) is not None]
            return dict(samples=len(values), average_ms=sum(values)/len(values) if values else None,
                max_ms=max(values) if values else None)
        return dict(observation=asdict(self.observation) if self.observation else None,
            fingerprint=dict(self.baseline_fingerprint or {}, target=getattr(self, 'target', None)), error=self.error,
            rows=self.rows, missed_scheduled_slots=self.missed_slots, dropped_gpu_frames=None,
            average_capture_ms=sum(durations)/len(durations) if durations else None,
            max_capture_ms=max(durations) if durations else None,
            invalidation=self.invalidation,
            prepare_started_at=getattr(self, 'prepare_started_at', None),
            prepare_ready_at=getattr(self, 'prepare_ready_at', None),
            fingerprint_timing=elapsed('cycle_start_ns', 'fingerprint_completed_ns'),
            detection_timing=elapsed('capture_end_ns', 'detection_completed_ns'),
            cycle_timing=elapsed('cycle_start_ns', 'cycle_end_ns'),
            capture_started_at=getattr(self, 'capture_started_at', None),
            baseline_completed_at=getattr(self, 'baseline_completed_at', None),
            runtime_ready_at=getattr(self, 'runtime_ready_at', None),
            observer_stopped=not hasattr(self, 'thread') or not self.thread.is_alive(),
            external_preview_notification_required=False)
