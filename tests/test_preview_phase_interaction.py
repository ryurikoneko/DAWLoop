"""预览阶段不能解除派发前守卫，也不能仅凭像素发出就绪。"""

import asyncio
from types import SimpleNamespace
import sys
from pathlib import Path
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
from preview_phase_interaction import PreviewPhaseInteraction
from dawloop.runtime.preview_viewport import NativePianoRollViewport, ViewportInvalidated
from dawloop.runtime import BackendRouter, NativeWriteJournal, ExecutionStatus
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from test_local_preview import Viewport, Capture, fixed_plan, run_async
from test_native_write_runtime import Interaction, Transport, Target


class PhaseViewport(Viewport):
    active = False
    def preview_snapshot(self):
        return dict(fingerprint=self.fingerprint(), preview_confirmed=self.active, preview={'hwnd': 3})


class Diagnostic:
    def mark_dispatch(self, value):
        self.value = value


@pytest.mark.parametrize('limit', [True, 0, -1, 1001, float('nan'), float('inf'), '1000'])
def test_invalid_transition_limit_is_rejected_before_preparation(limit):
    with pytest.raises(ValueError, match='INVALID_PREVIEW_TRANSITION_LIMIT'):
        PreviewPhaseInteraction(PhaseViewport(), Interaction(), trace_id='t',
            diagnostic=Diagnostic(), transition_ms=limit)


def phase_sample(viewport, now):
    interaction = PreviewPhaseInteraction(viewport, Interaction(), trace_id='t',
        diagnostic=Diagnostic(), clock=lambda: now[0])
    interaction.baseline_fingerprint = viewport.fingerprint()
    interaction.dispatch_at = 0
    return interaction


def test_first_preview_after_deadline_cannot_emit_ready():
    viewport = PhaseViewport()
    viewport.active = True
    interaction = phase_sample(viewport, [1_000_000_001])
    with pytest.raises(ValueError, match='FIXED_PREVIEW_NOT_CONFIRMED'):
        interaction._fingerprint('POST_DISPATCH_SAMPLE')
    assert not interaction._preview_confirmation_allowed()


@pytest.mark.parametrize('fault', ['replacement', 'disappearance', 'missing_identity'])
def test_confirmed_preview_cannot_transfer_to_another_window(fault):
    viewport = PhaseViewport()
    viewport.active = True
    now = [1_000_000_000]
    interaction = phase_sample(viewport, now)
    interaction._fingerprint('POST_DISPATCH_SAMPLE')
    now[0] += 1
    interaction._fingerprint('POST_DISPATCH_SAMPLE')
    viewport.preview_snapshot = lambda: dict(fingerprint=viewport.fingerprint(),
        preview_confirmed=fault != 'disappearance',
        preview={'hwnd': 4} if fault == 'replacement' else {})
    with pytest.raises(ValueError):
        interaction._fingerprint('POST_DISPATCH_SAMPLE')
    assert interaction.metrics()['observation'] is None
    assert not interaction._preview_confirmation_allowed()


@run_async
async def test_phase_reaches_local_ready_without_external_notice_or_verification():
    Capture.notes = Capture.preexisting = False
    viewport = PhaseViewport()
    class Host(Transport):
        def invoke_batch(self, *args):
            viewport.active = True
            Capture.notes = True
            return super().invoke_batch(*args)
    diagnostic = Diagnostic()
    interaction = PreviewPhaseInteraction(viewport, Interaction(), trace_id='t', diagnostic=diagnostic,
        capture_factory=Capture)
    with tempfile.TemporaryDirectory() as directory:
        backend = GopherNativeWriteBackend(enabled=True, transport=Host(), target_preparer=Target(),
            interaction=interaction, journal=NativeWriteJournal(directory), disposable_guard=lambda: True)
        router = BackendRouter([backend])
        await router.discover()
        result = await router.execute(fixed_plan())
    assert result.execution_status == ExecutionStatus.SUCCESS
    assert result.value['preview_status'] == 'LOCAL_PREVIEW_READY'
    assert result.value['local_preview_observation']['verification_status'] == 'NOT_VERIFIED'
    assert interaction.phase_rows and interaction.metrics()['observer_stopped']


@run_async
async def test_pixel_signal_without_owned_preview_times_out_without_ready():
    Capture.notes = Capture.preexisting = False
    viewport = PhaseViewport()
    interaction = PreviewPhaseInteraction(viewport, Interaction(), trace_id='t', diagnostic=Diagnostic(),
        transition_ms=100, capture_factory=Capture)
    session = Transport().connect()
    await interaction.prepare_preview(fixed_plan(), session, await Target().confirm(fixed_plan().target, session))
    interaction.before_dispatch()
    Capture.notes = True
    with pytest.raises(ValueError, match='FIXED_PREVIEW_NOT_CONFIRMED'):
        await interaction.wait_preview('smoke-1')
    await interaction.close()
    assert interaction.metrics()['observation'] is None


@run_async
async def test_pre_dispatch_change_still_refuses_marker_and_post_change_refuses_ready():
    Capture.notes = Capture.preexisting = False
    viewport = PhaseViewport()
    diagnostic = Diagnostic()
    interaction = PreviewPhaseInteraction(viewport, Interaction(), trace_id='t', diagnostic=diagnostic,
        capture_factory=Capture)
    session = Transport().connect()
    await interaction.prepare_preview(fixed_plan(), session, await Target().confirm(fixed_plan().target, session))
    viewport.value = 2
    with pytest.raises(ValueError, match='VIEWPORT_INVALIDATED'):
        interaction.before_dispatch()
    await interaction.close()
    assert not hasattr(diagnostic, 'value')
    interaction = PreviewPhaseInteraction(viewport, Interaction(), trace_id='t', diagnostic=Diagnostic())
    interaction.baseline_fingerprint = viewport.fingerprint()
    interaction.dispatch_at = interaction.clock()
    viewport.value = 3
    with pytest.raises(ValueError, match='VIEWPORT_INVALIDATED'):
        interaction._fingerprint('POST_DISPATCH_SAMPLE')


@pytest.mark.parametrize('fault', ['duplicate', 'title', 'parent', 'disabled', 'overlap'])
def test_preview_window_contract_rejects_ambiguity_and_cover(fault):
    viewport = object.__new__(NativePianoRollViewport)
    viewport.pid, viewport.top = 42, 1
    viewport.fingerprint = lambda **kwargs: dict(roi=[620, 300, 850, 450])
    viewport.process = SimpleNamespace(GetWindowThreadProcessId=lambda h: (0, 42))
    viewport.gui = SimpleNamespace(GetClassName=lambda h: 'TScriptDialog', IsWindowVisible=lambda h: True,
        GetParent=lambda h: 9 if fault == 'parent' else 1,
        GetWindowText=lambda h: 'OTHER' if fault == 'title' else 'DAWLoop Native Add',
        IsWindowEnabled=lambda h: fault != 'disabled',
        GetWindowRect=lambda h: (630, 310, 800, 440) if fault == 'overlap' else (900, 500, 1200, 700),
        EnumWindows=lambda callback, arg: callback(3, arg),
        EnumChildWindows=lambda h, callback, arg: callback(4 if fault == 'duplicate' else 3, arg))
    with pytest.raises(ViewportInvalidated):
        viewport.preview_snapshot()
