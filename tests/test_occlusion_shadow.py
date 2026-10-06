"""窗口排除依据不能升级为完整视觉证明或派发许可。"""

import copy

import pytest

from dawloop.runtime.preview_viewport import assess_occlusion_survey


def survey(facts):
    return dict(piano_roll_chain=dict(windows=[dict(hwnd=1,enabled=False)],complete=True),
        preceding_scan_complete=True,atomic_snapshot=False,
        preceding_overlaps=[dict(hwnd=2,level_hwnd=1,visual_facts=facts)])


@pytest.mark.parametrize('facts', [{}, {'cloaked':None}, {'region_type':None},
    {'transparent_style':True}, {'layered':True}, {'cloaked':False,'region_type':'COMPLEX'}])
def test_uncertain_or_transparent_candidate_never_excluded(facts):
    result = assess_occlusion_survey(survey(facts))
    assert len(result['candidates'])==1 and result['excluded']==[]
    assert result['visual_coverage']=='UNKNOWN' and not result['allow_dispatch']


@pytest.mark.parametrize('facts,basis', [({'cloaked':True},'COMPOSITION_CLOAKED'),
    ({'region_type':'EMPTY'},'EMPTY_WINDOW_REGION')])
def test_excluding_all_observed_candidates_does_not_certify_clear(facts,basis):
    result = assess_occlusion_survey(survey(facts))
    assert result['excluded'][0]['basis']==basis and result['candidates']==[]
    assert result['visual_coverage']=='UNKNOWN' and not result['allow_dispatch']
    assert result['guard_action']=='KEEP_ORIGINAL_GUARD' and not result['exact_set_verified']


def test_missing_legacy_evidence_remains_unknown_without_mutation():
    record = survey({})
    record['preceding_scan_complete']=False
    old = copy.deepcopy(record)
    result = assess_occlusion_survey(record)
    assert record==old and result['disabled_chain_hwnds']==[1]
    assert 'SURVEY_INCOMPLETE' in result['missing_evidence']
    assert not result['allow_dispatch']


@pytest.mark.parametrize('before,after,changed', [(True,False,True),(False,False,False),
    (None,False,False),('unknown',False,False)])
def test_enable_transition_requires_two_explicit_boolean_observations(before,after,changed):
    result = assess_occlusion_survey({},dict(main_enabled_before=before,main_enabled_after=after))
    assert result['main_enabled_transition'] is changed
    assert result['visual_coverage']=='UNKNOWN' and not result['allow_dispatch']


@pytest.mark.parametrize('region_result,cloaked_result,region_type', [(0,1,None),(1,0,'EMPTY'),(3,0,'COMPLEX')])
def test_native_read_failure_is_unknown_and_region_handle_always_released(monkeypatch,region_result,cloaked_result,region_type):
    import ctypes
    from types import SimpleNamespace
    gui = pytest.importorskip('win32gui')
    from dawloop.runtime.preview_viewport import window_visual_facts
    released = []
    def create(*args):
        return 123
    def delete(handle):
        released.append(handle)
        return True
    def get_region(*args):
        return region_result
    def get_attribute(*args):
        return cloaked_result
    libraries = dict(gdi32=SimpleNamespace(CreateRectRgn=create,DeleteObject=delete),
        user32=SimpleNamespace(GetWindowRgn=get_region),
        dwmapi=SimpleNamespace(DwmGetWindowAttribute=get_attribute))
    monkeypatch.setattr(ctypes,'WinDLL',lambda name:libraries[name])
    monkeypatch.setattr(gui,'GetWindowLong',lambda h,index:0x80020)
    facts = window_visual_facts(999)
    assert released==[123] and facts['region_type']==region_type
    assert facts['layered'] and facts['transparent_style']
    if region_result==0:
        assert facts['errors']['region']=='NO_REGION_OR_ERROR'
    if cloaked_result!=0:
        assert facts['cloaked'] is None
