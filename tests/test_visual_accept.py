"""固定视觉模板的拒绝边界，以及一次性接受契约的结合。"""

import asyncio
from pathlib import Path

import numpy as np
import pytest

from dawloop.runtime.visual_accept import ReviewedAcceptLocator, DIALOG_SIZE
from dawloop.runtime.controlled_accept import ControlledAcceptGate
from test_controlled_accept import binding, snapshot, Calls


def frame():
    from dawloop.runtime import visual_accept
    with np.load(Path(visual_accept.__file__).with_name('fixtures') /
            'reviewed_accept_four_note.npz', allow_pickle=False) as sample:
        value = np.zeros((165, 493, 4), dtype=np.uint8)
        value[3:25, 4:285, :3] = sample['title']
        value[118:158, 6:486, :3] = sample['footer']
    return value


def facts():
    return dict(preview=dict(hwnd=103, parent=102, process_id=101,
            native_title='DAWLoop Native Add',window_class='TScriptDialog',
        rectangle=[778, 470, 1271, 635], fixed_title=True, visible=True, enabled=True),
        expected_rectangle=[778, 470, 1271, 635], dpi=120, foreground_hwnd=103)


def test_disabled_locator_never_returns_control():
    with pytest.raises(ValueError, match='VISUAL_ACCEPT_DISABLED'):
        ReviewedAcceptLocator().locate(frame(), **facts())


def test_reviewed_bar_produces_scoped_point_not_commit():
    control = ReviewedAcceptLocator(enabled=True).locate(frame(), **facts())
    assert control['click_point_relative'] == [451, 136]
    assert control['commit_status'] == 'UNKNOWN'
    assert control['exact_set_verified'] is False


@pytest.mark.parametrize('fault', ['native_title', 'missing_title', 'window_class', 'accept', 'reset', 'regenerate',
    'moved', 'size', 'dpi', 'foreground', 'hidden', 'disabled', 'other_title',
    'pid_type', 'rgb', 'scaled', 'float'])
def test_changed_or_ambiguous_visual_identity_is_rejected(fault):
    value, metadata = frame(), facts()
    if fault == 'native_title': metadata['preview']['native_title'] = 'Other'
    if fault == 'missing_title': metadata['preview'].pop('native_title')
    if fault == 'window_class': metadata['preview']['window_class'] = 'Other'
    if fault == 'accept': value[135, 450, 0] ^= 1
    if fault == 'reset': value[135, 30, 0] ^= 1
    if fault == 'regenerate': value[135, 130, 0] ^= 1
    if fault == 'moved': metadata['preview']['rectangle'][0] += 1
    if fault == 'size': metadata['preview']['rectangle'][2] += 1
    if fault == 'dpi': metadata['dpi'] = 120.0
    if fault == 'foreground': metadata['foreground_hwnd'] = 999
    if fault == 'hidden': metadata['preview']['visible'] = False
    if fault == 'disabled': metadata['preview']['enabled'] = False
    if fault == 'other_title': metadata['preview']['fixed_title'] = False
    if fault == 'pid_type': metadata['preview']['process_id'] = 101.0
    if fault == 'rgb': value = value[:, :, :3]
    if fault == 'scaled': value = value[:164]
    if fault == 'float': value = value.astype(float)
    with pytest.raises(ValueError):
        ReviewedAcceptLocator(enabled=True).locate(value, **metadata)


@pytest.mark.parametrize('fault',['blank_title','blank_frame','background_change'])
def test_native_title_is_required_even_when_image_bright_mask_is_empty(fault):
    original = frame()
    assert not (original[3:25,4:285,:3] > 220).any()
    changed = original.copy()
    if fault == 'blank_title': changed[3:25,4:285,:3] = 0
    if fault == 'blank_frame': changed[:] = 0
    if fault == 'background_change': changed[3:25,4:285,:3] = 120
    assert not (changed[3:25,4:285,:3] > 220).any()
    metadata = facts()
    metadata['preview'].pop('native_title')
    with pytest.raises(ValueError,match='WINDOW_UNPROVEN'):
        ReviewedAcceptLocator(enabled=True).locate(changed,**metadata)


@pytest.mark.parametrize('fault',['blank_title','colored_title'])
def test_title_pixels_are_not_substituted_for_native_identity(fault):
    value = frame()
    value[3:25,4:285,:3] = 0 if fault == 'blank_title' else 120
    result = ReviewedAcceptLocator(enabled=True).locate(value,**facts())
    assert result['identity_method'] == 'NATIVE_TITLE_AND_CLASS_WITH_EXACT_REVIEWED_BUTTON_BAR'
    assert result['exact_set_verified'] is False


def test_capture_failure_still_releases_resources():
    class Capture:
        scale = (1.25, 1.25)
        closed = False
        def grab(self): raise RuntimeError('采样失败')
        def close(self): self.closed = True
    capture = Capture()
    with pytest.raises(RuntimeError):
        ReviewedAcceptLocator(enabled=True).capture(**facts(), capture_factory=lambda _: capture,
            display_bounds=(0, 0, 2048, 1152))
    assert capture.closed


@pytest.mark.parametrize('fault',[None,'display_geometry','template','outside'])
def test_capture_uses_template_full_display_grid_and_closes(tmp_path,fault):
    metadata = facts()
    full = np.zeros((1152,2048,4),dtype=np.uint8)
    full[470:635,778:1271] = frame()
    if fault == 'display_geometry': full = full[:1151]
    if fault == 'template': full[605,800,0] ^= 1
    if fault == 'outside': metadata['preview']['rectangle'][2] = 3000
    captures = []
    class Capture:
        scale = (1.25,1.25)
        closed = False
        def __init__(self,bounds):
            assert bounds == (0,0,2048,1152)
            captures.append(self)
        def grab(self): return full,1,2
        def close(self): self.closed = True
    locator = ReviewedAcceptLocator(enabled=True)
    if fault:
        with pytest.raises(ValueError):
            locator.capture(**metadata,capture_factory=Capture,display_bounds=(0,0,2048,1152))
    else:
        result = locator.capture(**metadata,capture_factory=Capture,display_bounds=(0,0,2048,1152))
        assert result['control']['template_hash'] == 'e340115a21ca6bde8cdf6b9ce2cbd04f74137414f5a27e2bcbdc9e2a95df97f4'
    assert all(capture.closed for capture in captures)
    assert len(captures) == (0 if fault == 'outside' else 1)


def test_visual_control_uses_existing_persistent_one_action_budget(tmp_path):
    control = ReviewedAcceptLocator(enabled=True).locate(frame(), **facts())
    value = snapshot()
    value['accept_controls'] = [control]
    calls = Calls([value])
    gate = ControlledAcceptGate(binding(), tmp_path/'intent.json', max_age_ns=100,
        enabled=True, clock=lambda: 130)
    receipt = asyncio.run(gate.accept_once(calls.read, calls.action))
    assert calls.actions == 1
    assert receipt['action_status'] == 'ACTION_CONFIRMED'
    assert receipt['commit_status'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='ACCEPT_BUDGET_EXHAUSTED'):
        asyncio.run(gate.accept_once(calls.read, calls.action))
