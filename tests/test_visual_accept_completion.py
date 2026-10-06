"""接受动作、宿主完成和可见效果必须分别证明，缺一不可。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
from controlled_visual_interaction import accepted_application


@pytest.mark.parametrize('fault', ['action_unknown', 'callback_error', 'callback_missing',
    'callback_is_error', 'preview_open', 'target_changed', 'no_notes', 'other_operation'])
def test_incomplete_accept_chain_is_rejected(fault):
    receipt = dict(action_status='ACTION_CONFIRMED')
    response, error = {'payload':{'result':{'isError':False}}}, None
    application = dict(operation_id='fixed', preview_closed=True, target_unchanged=True,
        visible_four_note_geometry=True)
    if fault == 'action_unknown': receipt['action_status'] = 'UNKNOWN'
    if fault == 'callback_error': error = TimeoutError()
    if fault == 'callback_missing': response = None
    if fault == 'callback_is_error': response['payload']['result']['isError'] = True
    if fault == 'preview_open': application['preview_closed'] = False
    if fault == 'target_changed': application['target_unchanged'] = False
    if fault == 'no_notes': application['visible_four_note_geometry'] = False
    if fault == 'other_operation': application['operation_id'] = 'previous'
    with pytest.raises(ValueError):
        accepted_application(receipt, (response,error,0,0), application, 'fixed')


def test_full_chain_remains_visual_not_exact_verification():
    result = accepted_application({'action_status':'ACTION_CONFIRMED'},
        ({'payload':{'result':{'isError':False}}},None,0,0),
        dict(operation_id='fixed', preview_closed=True, target_unchanged=True,
            visible_four_note_geometry=True), 'fixed')
    assert result['accepted'] is True
    assert result['exact_set_verified'] is False
