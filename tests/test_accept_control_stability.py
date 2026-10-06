"""预览音符就绪后，只读等待按钮栏；不重试任何输入。"""

import asyncio
import copy
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from controlled_visual_interaction import ControlledVisualInteraction


@pytest.mark.parametrize('fault',[None,'window','viewport','title','never_stable','callback'])
def test_control_wait_uses_live_metadata_and_requires_two_consecutive_matches(fault):
    calls = []
    preview = dict(hwnd=103,parent=102,rectangle=[778,470,1271,635],fixed_title=True,
        enabled=True,native_title='DAWLoop Native Add',window_class='TScriptDialog')
    fingerprint = {'viewport':'fixed'}
    state = dict(preview=preview,preview_confirmed=True,fingerprint=fingerprint)
    if fault == 'window': preview['hwnd'] = 104
    if fault == 'viewport': state['fingerprint'] = {'viewport':'changed'}
    interaction = ControlledVisualInteraction.__new__(ControlledVisualInteraction)
    interaction.control_stability = None
    interaction.transition_ns = 80_000_000
    interaction.host_task = SimpleNamespace(done=lambda:fault == 'callback')
    interaction.backend = SimpleNamespace(transport=SimpleNamespace(poisoned_epoch=None))
    interaction.session = {'session':'epoch'}
    interaction.accept_binding = {'preview_hwnd':103}
    interaction.baseline_fingerprint = copy.deepcopy(fingerprint)
    interaction.preview_rectangle = [778,470,1271,635]
    interaction.viewport = SimpleNamespace(pid=101,top=102,preview_snapshot=lambda:state,
        user=SimpleNamespace(GetDpiForWindow=lambda hwnd:120),
        gui=SimpleNamespace(GetForegroundWindow=lambda:103))
    def capture(**facts):
        assert facts['preview']['process_id'] == 101
        assert facts['preview']['visible'] is True
        calls.append(facts)
        if fault == 'title': raise ValueError('VISUAL_ACCEPT_WINDOW_UNPROVEN')
        if fault == 'never_stable' or len(calls) == 1:
            raise ValueError('VISUAL_ACCEPT_TEMPLATE_MISMATCH')
        return {'control':{'control_id':'fixed'}}
    interaction.locator = SimpleNamespace(capture=capture)
    if fault:
        with pytest.raises(ValueError): asyncio.run(interaction._wait_for_control())
        assert interaction.control_stability is None
    else:
        asyncio.run(interaction._wait_for_control())
        assert len(calls) == 3
        assert interaction.control_stability['matched_samples'] == 2
    if fault in ('window','viewport','callback'): assert not calls
