"""固定四音符的受限视觉接受；不认证精确音符集合。"""

import asyncio
import copy
import json
import time

from preview_phase_interaction import PreviewPhaseInteraction
from dawloop.runtime.accept_exchange import AcceptActionExchange
from dawloop.runtime.controlled_accept import ControlledAcceptGate
from dawloop.runtime.local_preview import FIXED_HASH
from dawloop.runtime.preview_pixels import RegionCapture, note_geometry
from dawloop.runtime.visual_accept import ReviewedAcceptLocator


def accepted_application(receipt, host_result, application, operation):
    response, error, _, _ = host_result
    if receipt.get('action_status') != 'ACTION_CONFIRMED' or error is not None:
        raise ValueError('VISUAL_ACCEPT_COMPLETION_UNPROVEN')
    payload = response.get('payload') if isinstance(response, dict) else None
    payload = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(payload, dict) or payload.get('result', {}).get('isError') is not False:
        raise ValueError('VISUAL_ACCEPT_COMPLETION_UNPROVEN')
    if (application.get('operation_id') != operation
            or any(application.get(k) is not True for k in
                ('preview_closed', 'target_unchanged', 'visible_four_note_geometry'))):
        raise ValueError('VISUAL_ACCEPT_APPLICATION_UNPROVEN')
    return dict(operation_id=operation, accepted=True,
        basis='REVIEWED_ACCEPT_ACTION_HOST_COMPLETION_AND_VISIBLE_APPLICATION',
        exact_set_verified=False)


class ControlledVisualInteraction(PreviewPhaseInteraction):
    def __init__(self, *args, backend, directory, sky_window_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.backend, self.directory = backend, directory
        self.sky_window_id = sky_window_id
        self.locator = ReviewedAcceptLocator(enabled=True)
        self.accept_receipt = None
        self.application_evidence = None
        self.control_stability = None

    def bind_dispatch_task(self, task):
        self.host_task = task

    async def prepare_preview(self, plan, session, evidence):
        self.plan = copy.deepcopy(plan)
        await super().prepare_preview(plan, session, evidence)

    def _pending(self):
        return (not self.host_task.done()
            and self.backend.transport.poisoned_epoch != self.session['session'])

    async def _snapshot(self):
        start = time.perf_counter_ns()
        evidence = await self.backend.target_preparer.confirm(self.plan.target, self.session)
        self.backend.check_target(self.plan, evidence)
        state = self.viewport.preview_snapshot()
        preview = copy.deepcopy(state['preview'])
        if not preview or state['preview_confirmed'] is not True:
            raise ValueError('VISUAL_ACCEPT_PREVIEW_MISSING')
        preview.update(process_id=self.viewport.pid, visible=True)
        captured = await asyncio.to_thread(self.locator.capture, preview=preview,
            expected_rectangle=self.preview_rectangle,
            dpi=self.viewport.user.GetDpiForWindow(preview['hwnd']),
            foreground_hwnd=self.viewport.gui.GetForegroundWindow())
        return dict(context={k:self.accept_binding[k] for k in
            ('operation_id','source_hash','host_generation','bridge_epoch')},
            target=self.identity(evidence), fingerprint=state['fingerprint'],
            pending=self._pending(), poisoned=self.backend.transport.poisoned_epoch == self.session['session'],
            local_preview_ready=self.observation is not None,
            target_source='INDEPENDENT_CONTROLLER_AND_LOCAL_WINDOW',
            read_started_ns=start, read_completed_ns=time.perf_counter_ns(),
            preview=preview, accept_controls=[captured['control']])

    async def guarded_auto_accept(self, operation, source_hash):
        if source_hash != FIXED_HASH or operation != self.operation_id or not self._pending():
            raise ValueError('VISUAL_ACCEPT_CONTEXT_UNPROVEN')
        state = self.viewport.preview_snapshot()
        preview = state.get('preview')
        if not preview or not state['preview_confirmed']:
            raise ValueError('VISUAL_ACCEPT_PREVIEW_MISSING')
        self.preview_rectangle = list(preview['rectangle'])
        self.accept_binding = dict(operation_id=operation, source_hash=source_hash, note_count=4,
            host_generation=self.session['host_generation'], bridge_epoch=self.session['bridge_epoch'],
            process_id=self.viewport.pid, main_hwnd=self.viewport.top, preview_hwnd=preview['hwnd'],
            ready_at_ns=self.runtime_ready_at, target=copy.deepcopy(self.target),
            fingerprint=copy.deepcopy(self.baseline_fingerprint))
        await self._wait_for_control()
        gate = ControlledAcceptGate(self.accept_binding, self.directory/'accept_intent.json',
            max_age_ns=100_000_000, enabled=True)
        main_origin = list(self.viewport.gui.GetWindowRect(self.viewport.top)[:2])
        exchange = AcceptActionExchange(self.directory, main_origin=main_origin,
            sky_window_id=self.sky_window_id, timeout=10)

        async def revalidate():
            snapshot = await self._snapshot()
            control = gate._check(snapshot, time.perf_counter_ns())
            return dict(control=control, pending=snapshot['pending'],
                main_origin=list(self.viewport.gui.GetWindowRect(self.viewport.top)[:2]),
                sky_window_id=self.sky_window_id)

        async def action(context, control):
            return await exchange.action(context, control, revalidate)
        self.accept_receipt = await gate.accept_once(self._snapshot, action)
        if self.accept_receipt['action_status'] != 'ACTION_CONFIRMED':
            raise ValueError('VISUAL_ACCEPT_ACTION_UNKNOWN')

    async def _wait_for_control(self):
        start = time.perf_counter_ns()
        previous = None
        samples = 0
        while time.perf_counter_ns()-start < self.transition_ns:
            if not self._pending():
                raise ValueError('VISUAL_ACCEPT_CONTEXT_UNPROVEN')
            state = self.viewport.preview_snapshot()
            preview = copy.deepcopy(state.get('preview'))
            if (not preview or not state['preview_confirmed']
                    or preview['hwnd'] != self.accept_binding['preview_hwnd']
                    or preview['parent'] != self.viewport.top
                    or state['fingerprint'] != self.baseline_fingerprint):
                raise ValueError('VISUAL_ACCEPT_BINDING_CHANGED')
            preview.update(process_id=self.viewport.pid,visible=True)
            try:
                captured = await asyncio.to_thread(self.locator.capture,preview=preview,
                    expected_rectangle=self.preview_rectangle,
                    dpi=self.viewport.user.GetDpiForWindow(preview['hwnd']),
                    foreground_hwnd=self.viewport.gui.GetForegroundWindow())
            except ValueError as error:
                if str(error) != 'VISUAL_ACCEPT_TEMPLATE_MISMATCH': raise
                previous = None
            else:
                samples += 1
                current = captured['control']
                if previous == current and time.perf_counter_ns()-start < self.transition_ns:
                    self.control_stability = dict(started_ns=start,confirmed_ns=time.perf_counter_ns(),
                        matched_samples=samples,clock_domain='python_perf_counter',
                        criterion='TWO_CONSECUTIVE_EXACT_BUTTON_BAR_MATCHES')
                    return
                previous = current
            await asyncio.sleep(0.016)
        raise ValueError('VISUAL_ACCEPT_CONTROL_NOT_STABLE')

    async def wait_accept(self, operation):
        host_result = await asyncio.shield(self.host_task)
        evidence = await self.backend.target_preparer.confirm(self.plan.target, self.session)
        self.backend.check_target(self.plan, evidence)
        state = self.viewport.preview_snapshot()
        capture = RegionCapture(tuple(self.baseline_fingerprint['roi']))
        try:
            frame, start, end = capture.grab()
        finally:
            capture.close()
        matches, boxes = note_geometry(frame, self.detector.chroma_floor)
        self.application_evidence = dict(operation_id=operation,
            preview_closed=state['preview_confirmed'] is False,
            target_unchanged=self.identity(evidence) == self.target
                and state['fingerprint'] == self.baseline_fingerprint,
            visible_four_note_geometry=matches, boxes=boxes,
            capture_started_ns=start, capture_completed_ns=end, exact_set_verified=False)
        return accepted_application(self.accept_receipt or {}, host_result, self.application_evidence, operation)

    async def wait_application(self, operation):
        if not self.application_evidence or self.application_evidence['operation_id'] != operation:
            raise ValueError('VISUAL_ACCEPT_APPLICATION_UNPROVEN')
        return dict(operation_id=operation, observed=True, evidence=self.application_evidence,
            exact_set_verified=False)

    def metrics(self):
        return dict(super().metrics(), accept_receipt=self.accept_receipt,
            application_evidence=self.application_evidence, control_stability=self.control_stability,
            automatic_accept_certified=False)
