"""失效证据必须可解释，新增观测不能削弱拒绝边界。"""

from types import SimpleNamespace

import pytest

from dawloop.runtime.preview_viewport import NativePianoRollViewport, ViewportInvalidated
from dawloop.runtime.local_preview import LocalPreviewInteraction
from test_local_preview import Viewport, Capture, fixed_plan, run_async
from test_native_write_runtime import Interaction, Transport, Target


@pytest.mark.parametrize('fault,reason', [
    ('gone', 'WINDOW_GONE'), ('hidden', 'WINDOW_HIDDEN'),
    ('process', 'WINDOW_PROCESS_CHANGED'), ('foreground', 'FOREGROUND_NOT_ALLOWED'),
    ('layout', 'UNCALIBRATED_LAYOUT'), ('occluded', 'ROI_OCCLUDED')])
def test_native_failure_reasons_preserve_rejection(monkeypatch, fault, reason):
    pixels = pytest.importorskip('dawloop.runtime.preview_pixels')
    class Anchor(Capture):
        scale = [1.25, 1.25]
    monkeypatch.setattr(pixels, 'RegionCapture', Anchor)
    viewport = object.__new__(NativePianoRollViewport)
    viewport.pid, viewport.hwnd, viewport.top = 42, 2, 1
    viewport.process = SimpleNamespace(GetWindowThreadProcessId=lambda h: (1, 43 if fault=='process' else 42))
    viewport.user = SimpleNamespace(GetDpiForWindow=lambda h: 120)
    viewport.gui = SimpleNamespace(
        IsWindow=lambda h: fault!='gone', IsWindowVisible=lambda h: fault!='hidden',
        IsWindowEnabled=lambda h: True,
        GetForegroundWindow=lambda: 3 if fault=='foreground' else 1,
        GetClassName=lambda h: 'OTHER', GetWindowText=lambda h: '不应输出的私人标题',
        GetParent=lambda h: 0, GetWindowRect=lambda h: (373,87,2043,1104),
        GetClientRect=lambda h: (0,0,1600 if fault=='layout' else 1669,1016),
        ClientToScreen=lambda h,p: (373,87), WindowFromPoint=lambda p: 3 if fault=='occluded' else 2)
    with pytest.raises(ViewportInvalidated) as raised:
        viewport.fingerprint()
    assert raised.value.reason == reason
    assert str(raised.value) in ('VIEWPORT_INVALIDATED', 'VIEWPORT_LAYOUT_UNSUPPORTED')
    assert '私人标题' not in str(raised.value.details)


@run_async
async def test_changed_fingerprint_records_field_and_blocks_dispatch():
    Capture.notes = Capture.preexisting = False
    viewport = Viewport()
    interaction = LocalPreviewInteraction(viewport, Interaction(), trace_id='trace', capture_factory=Capture)
    session = Transport().connect()
    evidence = await Target().confirm(fixed_plan().target, session)
    await interaction.prepare_preview(fixed_plan(), session, evidence)
    viewport.value = 2
    with pytest.raises(ValueError, match='VIEWPORT_INVALIDATED'):
        interaction.before_dispatch()
    await interaction.close()
    diagnostic = interaction.metrics()['invalidation']
    assert diagnostic['reason'] == 'FINGERPRINT_CHANGED'
    assert diagnostic['changed_fields'] == ['dpi']
    assert diagnostic['before']['dpi'] == 1 and diagnostic['after']['dpi'] == 2
    assert interaction.dispatch_at is None


@run_async
async def test_target_diff_hashes_names_and_retains_first_failure():
    Capture.notes = Capture.preexisting = False
    interaction = LocalPreviewInteraction(Viewport(), Interaction(), trace_id='trace', capture_factory=Capture)
    session = Transport().connect()
    evidence = await Target().confirm(fixed_plan().target, session)
    await interaction.prepare_preview(fixed_plan(), session, evidence)
    evidence['identity']['pattern_name'] = '私人片段甲'
    with pytest.raises(ValueError, match='VIEWPORT_INVALIDATED'):
        interaction.reconfirm_preview(evidence)
    interaction._record_invalidation('LATER', 'OTHER')
    await interaction.close()
    diagnostic = interaction.metrics()['invalidation']
    assert diagnostic['reason'] == 'TARGET_CHANGED'
    assert 'pattern_name' in diagnostic['changed_fields']
    assert '私人片段甲' not in str(diagnostic)
    assert len(diagnostic['after']['pattern_name_hash']) == 64


@run_async
async def test_post_dispatch_guard_evidence_prevents_ready_delivery():
    Capture.notes = Capture.preexisting = False
    viewport = Viewport()
    interaction = LocalPreviewInteraction(viewport, Interaction(), trace_id='trace', capture_factory=Capture)
    session = Transport().connect()
    await interaction.prepare_preview(fixed_plan(), session, await Target().confirm(fixed_plan().target, session))
    with interaction.lock:
        interaction.dispatch_at = interaction.clock()
        viewport.value = 2
    with pytest.raises(ValueError, match='VIEWPORT_INVALIDATED'):
        await interaction.wait_preview('smoke-1')
    await interaction.close()
    metrics = interaction.metrics()
    assert metrics['invalidation']['stage'] == 'POST_DISPATCH_SAMPLE'
    assert metrics['invalidation']['dispatched']
    assert metrics['observation'] is None and metrics['runtime_ready_at'] is None
    rejected = metrics['rows'][-1]
    assert rejected['capture_start_ns'] is None and rejected['outcome'] == 'GUARD_REJECTED'
    assert rejected['cycle_end_ns'] >= rejected['fingerprint_completed_ns']


@run_async
async def test_preparation_and_cycle_timings_use_same_clock():
    Capture.notes = Capture.preexisting = False
    interaction = LocalPreviewInteraction(Viewport(), Interaction(), trace_id='trace', capture_factory=Capture)
    session = Transport().connect()
    await interaction.prepare_preview(fixed_plan(), session, await Target().confirm(fixed_plan().target, session))
    interaction.before_dispatch()
    Capture.notes = True
    await interaction.wait_preview('smoke-1')
    await interaction.close()
    metrics = interaction.metrics()
    assert metrics['prepare_started_at'] <= metrics['capture_started_at']
    assert metrics['baseline_completed_at'] <= metrics['prepare_ready_at']
    for row in metrics['rows']:
        assert (row['cycle_start_ns'] <= row['fingerprint_completed_ns'] <= row['capture_start_ns']
            <= row['capture_end_ns'] <= row['detection_completed_ns'] <= row['cycle_end_ns'])
    assert metrics['cycle_timing']['samples'] == len(metrics['rows'])
    assert metrics['cycle_timing']['average_ms'] >= metrics['average_capture_ms']


@run_async
async def test_initial_failure_is_reportable_without_sampler():
    class Invalid(Viewport):
        def fingerprint(self):
            raise ViewportInvalidated('VIEWPORT_INVALIDATED', 'WINDOW_HIDDEN', {'window_visible':False})
    interaction = LocalPreviewInteraction(Invalid(), Interaction(), trace_id='trace')
    session = Transport().connect()
    with pytest.raises(ValueError, match='VIEWPORT_INVALIDATED'):
        await interaction.prepare_preview(fixed_plan(), session, await Target().confirm(fixed_plan().target, session))
    await interaction.close()
    metrics = interaction.metrics()
    assert metrics['invalidation']['stage'] == 'INITIAL_BASELINE'
    assert metrics['invalidation']['reason'] == 'WINDOW_HIDDEN'
    assert metrics['capture_started_at'] is None and metrics['observer_stopped']


@pytest.mark.parametrize('enabled', [True, False])
def test_occlusion_survey_records_disabled_chain_and_overlap_without_titles(enabled, monkeypatch):
    monkeypatch.setattr('dawloop.runtime.preview_viewport.window_visual_facts', lambda h: {})
    viewport = object.__new__(NativePianoRollViewport)
    viewport.pid, viewport.hwnd, viewport.top = 42, 2, 1
    rectangles = {1:(0,0,100,100),2:(10,10,90,90),3:(20,20,40,40),4:(70,70,80,80)}
    viewport.process = SimpleNamespace(GetWindowThreadProcessId=lambda h:(1,42))
    viewport.gui = SimpleNamespace(IsWindowEnabled=lambda h:enabled if h==2 else True,
        IsWindowVisible=lambda h:True, GetWindowRect=lambda h:rectangles[h],
        GetParent=lambda h:1 if h==2 else 0, GetWindow=lambda h,flag:3 if h==2 else 0,
        GetClassName=lambda h:'TScriptDialog', GetWindowText=lambda h:'DAWLoop Native Add',
        EnumChildWindows=lambda h,callback,arg:callback(4,arg),
        EnumWindows=lambda callback,arg:None)
    value = viewport._occlusion_evidence((15,15,50,50),1)
    assert value['piano_roll_chain']['windows'][0]['enabled'] is enabled
    assert value['piano_roll_chain']['complete'] and value['preceding_scan_complete']
    assert value['preceding_overlaps'][0]['hwnd']==3
    assert not value['fixed_preview_windows'][0]['intersects_roi']
    assert value['geometry_does_not_prove_pixel_occlusion'] and not value['atomic_snapshot']
    assert 'DAWLoop Native Add' not in str(value)
