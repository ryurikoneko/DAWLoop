"""新轮次保留旧失败，并要求就绪与顺序守卫。"""

import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import asyncio

import pytest
pytest.importorskip('numpy')

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import runtime_v2_local_preview_live as live


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')


@pytest.mark.parametrize('fault', [None, 'extra_session', 'not_recovered', 'bad_hash', 'wrong_summary'])
def test_visual_round_keeps_two_old_sessions_and_only_one_remaining(tmp_path, fault):
    write(tmp_path/'summary.json', {'status':'CLOSED_SETUP_FAILED_BEFORE_DISPATCH'})
    record = dict(status='CLOSED_ACCEPT_CONTROL_UNRESOLVED', cumulative_live_sessions=2,
        cumulative_dispatch_count=1, cumulative_accept_count=0)
    if fault == 'wrong_summary': record['cumulative_accept_count'] = 1
    write(tmp_path/'repaired_1/summary.json', record)
    for directory in (tmp_path/'session_1', tmp_path/'repaired_1/session_2'):
        write(directory/'launch.json', {'pid':1})
        write(directory/'recovery.json', dict(host_closed=True, debug_port_closed=True,
            baseline_sha256=live.BASELINE_HASH))
    if fault == 'extra_session': write(tmp_path/'other/session_3/launch.json', {'pid':2})
    if fault in ('not_recovered', 'bad_hash'):
        write(tmp_path/'session_1/recovery.json', dict(host_closed=fault != 'not_recovered',
            debug_port_closed=True, baseline_sha256='changed' if fault == 'bad_hash' else live.BASELINE_HASH))
    if fault:
        with pytest.raises(ValueError): live.visual_round_preflight(tmp_path)
    else:
        live.visual_round_preflight(tmp_path)


def complete(directory):
    write(directory/'result.json',dict(callbacks_restored=True,value=dict(
        preview_status='LOCAL_PREVIEW_READY',commit_status='ACCEPTED',application_status='APPLICATION_OBSERVED')))
    write(directory/'local_observation.json',dict(error=None,observer_stopped=True,observation={'confirmed':True}))
    write(directory/'recovery.json',dict(host_closed=True,debug_port_closed=True,baseline_sha256=live.BASELINE_HASH))


def test_ready_refresh_appends_without_overwriting_and_uses_latest(tmp_path, monkeypatch):
    old = dict(ready=True, checked_unix=1)
    write(tmp_path/'ready.json', old)
    original = (tmp_path/'ready.json').read_bytes()
    class Transport:
        callbacks_restored = True
        def __init__(self, **kwargs): pass
    class Backend:
        session = {'host_generation':'new'}
        catalog_digest = live.CERTIFIED_CATALOG
        def __init__(self, **kwargs): pass
        async def discover(self): pass
        async def close(self): pass
    monkeypatch.setattr(live, 'CDPTransport', Transport)
    monkeypatch.setattr(live, 'GopherNativeWriteBackend', Backend)
    monkeypatch.setattr(live, 'checked_catalog', lambda transport: [])
    asyncio.run(live.readiness(tmp_path))
    asyncio.run(live.readiness(tmp_path))
    assert (tmp_path/'ready.json').read_bytes() == original
    assert (tmp_path/'ready-000001.json').is_file()
    assert live.read_ready(tmp_path) == json.loads((tmp_path/'ready-000002.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('fault', ['failed', 'malformed', 'gap'])
def test_ready_refresh_never_falls_back_to_old_success(tmp_path, fault):
    write(tmp_path/'ready.json', dict(ready=True))
    if fault == 'failed':
        write(tmp_path/'ready-000001.json', dict(ready=False))
        assert live.read_ready(tmp_path)['ready'] is False
    else:
        if fault == 'malformed': (tmp_path/'ready-000001.json').write_text('{', encoding='utf-8')
        if fault == 'gap': write(tmp_path/'ready-000002.json', dict(ready=True))
        with pytest.raises(ValueError): live.read_ready(tmp_path)


def test_ready_refresh_after_execution_refused_before_connection(tmp_path, monkeypatch):
    write(tmp_path/'execution_intent.json', {'dispatch_budget':1})
    def forbidden(**kwargs): raise AssertionError('不得建立连接')
    monkeypatch.setattr(live, 'CDPTransport', forbidden)
    with pytest.raises(ValueError, match='READY_REFRESH_AFTER_EXECUTION_FORBIDDEN'):
        asyncio.run(live.readiness(tmp_path))


@pytest.mark.parametrize('fault', [None,'extra','not_closed','hash','summary'])
def test_new_authorization_allows_exactly_one_after_three_recovered_sessions(tmp_path, fault):
    summary = dict(status='CLOSED_READY_EXPIRED_BEFORE_DISPATCH', cumulative_live_sessions=3,
        cumulative_dispatch_count=1,cumulative_accept_count=0)
    if fault == 'summary': summary['cumulative_live_sessions'] = 2
    write(tmp_path/'visual_1/summary.json',summary)
    for name in ('session_1','repaired_1/session_2','visual_1/session_3'):
        write(tmp_path/name/'launch.json',{'pid':1})
        write(tmp_path/name/'recovery.json',dict(host_closed=fault != 'not_closed',
            debug_port_closed=True,baseline_sha256='changed' if fault == 'hash' else live.BASELINE_HASH))
    if fault == 'extra': write(tmp_path/'visual_2/session_4/launch.json',{'pid':1})
    if fault:
        with pytest.raises(ValueError): live.extended_visual_preflight(tmp_path)
    else: live.extended_visual_preflight(tmp_path)


@pytest.mark.parametrize('session',['session_1','session_2','session_3','session_5'])
def test_extended_visual_round_cannot_expand_new_budget(monkeypatch,session):
    monkeypatch.setattr(sys,'argv',['entry','launch','--round','controlled_accept_visual_2','--trial',session])
    with pytest.raises(ValueError,match='EXTENDED_VISUAL_SINGLE_NEW_SESSION_ONLY'): live.main()


def test_previous_failure_blocks_next_session(tmp_path):
    complete(tmp_path)
    assert live.previous_passed(tmp_path)
    value=json.loads((tmp_path/'result.json').read_text(encoding='utf-8'))
    value['value']['preview_status']='NOT_OBSERVED'
    write(tmp_path/'result.json',value)
    assert not live.previous_passed(tmp_path)


def test_new_round_preserves_original_closed_record(tmp_path,monkeypatch):
    root=tmp_path/'evidence'; original={'status':'STOPPED_NOT_READY'}
    write(root/'summary.json',original)
    monkeypatch.setattr(live,'EVIDENCE_ROOT',root)
    monkeypatch.setattr(live,'baseline',lambda:tmp_path/'fixture.flp')
    monkeypatch.setattr(live,'process_state',lambda:{'host_closed':True,'debug_port_closed':True})
    monkeypatch.setenv('TEMP',str(tmp_path/'temp')); (tmp_path/'temp').mkdir()
    calls=[]
    monkeypatch.setattr(live, 'fl_executable', lambda: str(tmp_path/'synthetic-FL.exe'))
    monkeypatch.setattr(live.subprocess,'Popen',lambda *a,**k: calls.append(a) or SimpleNamespace(pid=1))
    monkeypatch.setattr(live.subprocess, 'DETACHED_PROCESS', 0x00000008, raising=False)
    monkeypatch.setattr(sys,'argv',['entry','launch','--round','validation_1','--trial','session_1'])
    live.main()
    assert len(calls)==1 and (root/'validation_1/session_1/launch.json').exists()
    assert json.loads((root/'summary.json').read_text(encoding='utf-8'))==original
    monkeypatch.setattr(sys,'argv',['entry','launch','--round','validation_1','--trial','session_3'])
    with pytest.raises(ValueError,match='PREVIOUS_SESSION_NOT_RECOVERED'):
        live.main()
    assert len(calls)==1


def test_readiness_is_readonly_and_restores_callbacks(tmp_path,monkeypatch):
    class Transport:
        callbacks_restored=True
    class Backend:
        def __init__(self,**kwargs):
            self.session={'host_generation':'test-generation'}; self.catalog_digest='digest'
        async def discover(self):
            pass
        async def close(self):
            pass
        async def execute(self,*args):
            raise AssertionError('只读就绪门不得派发')
    monkeypatch.setattr(live,'CDPTransport',lambda **kwargs:Transport())
    monkeypatch.setattr(live,'GopherNativeWriteBackend',Backend)
    monkeypatch.setattr(live,'checked_catalog',lambda transport:[{'name':'get_tempo'}])
    asyncio.run(live.readiness(tmp_path))
    value=json.loads((tmp_path/'ready.json').read_text(encoding='utf-8'))
    assert value['ready'] and value['writes_dispatched']==0 and value['callbacks_restored']


@pytest.mark.parametrize('fault', ['missing', 'malformed', 'stale', 'pattern', 'channel',
    'unconfirmed', 'no_reference', 'no_launch', 'no_ready'])
def test_controlled_preflight_refuses_before_intent_or_connection(tmp_path, monkeypatch, fault):
    import time
    directory, events = tmp_path/'session', tmp_path/'events'
    directory.mkdir(); events.mkdir()
    ui = dict(visible=True, confirmed=True, pattern_number=1, channel_name='808 Kick',
        observed_unix=time.time(), evidence_ref='fixture-target-observation')
    if fault == 'stale': ui['observed_unix'] -= 61
    if fault == 'pattern': ui['pattern_number'] = 2
    if fault == 'channel': ui['channel_name'] = 'other'
    if fault == 'unconfirmed': ui['confirmed'] = False
    if fault == 'no_reference': ui.pop('evidence_ref')
    if fault != 'missing': write(events/'target.json', ui)
    if fault == 'malformed': (events/'target.json').write_text('{', encoding='utf-8')
    if fault != 'no_launch': write(directory/'launch.json', {'pid':1})
    if fault != 'no_ready': write(directory/'ready.json', {'ready':True})
    monkeypatch.setattr(live, 'ROUND_ID', 'controlled_accept_1')
    monkeypatch.setattr(live, 'baseline', lambda: None)
    def forbidden(*args, **kwargs):
        raise AssertionError('材料失败不应建立宿主连接')
    monkeypatch.setattr(live, 'CDPTransport', forbidden)
    with pytest.raises(ValueError, match='CONTROLLED_'):
        asyncio.run(live.run(directory, events))
    assert not (directory/'execution_intent.json').exists()


@pytest.mark.parametrize('session', ['session_4', 'session_5'])
def test_controlled_round_uses_total_three_session_budget(monkeypatch, session):
    monkeypatch.setattr(sys, 'argv', ['entry', 'launch', '--round', 'controlled_accept_1',
        '--trial', session])
    with pytest.raises(ValueError, match='STABILITY_THREE_SESSION_LIMIT'):
        live.main()


@pytest.mark.parametrize('fault', ['none', 'stale', 'catalog', 'callback', 'pid', 'malformed'])
def test_controlled_preflight_checks_ready_material_without_reserving_budget(tmp_path, fault):
    import time
    events = tmp_path/'events'; events.mkdir()
    write(events/'target.json', dict(visible=True, confirmed=True, pattern_number=1,
        channel_name='808 Kick', observed_unix=time.time(), evidence_ref='target'))
    launch = dict(pid=1)
    ready = dict(ready=True, callbacks_restored=True, catalog_hash=live.CERTIFIED_CATALOG,
        checked_unix=time.time())
    if fault == 'stale': ready['checked_unix'] -= 181
    if fault == 'catalog': ready['catalog_hash'] = 'other'
    if fault == 'callback': ready['callbacks_restored'] = False
    if fault == 'pid': launch['pid'] = True
    write(tmp_path/'launch.json', launch); write(tmp_path/'ready.json', ready)
    if fault == 'malformed': (tmp_path/'ready.json').write_text('{', encoding='utf-8')
    if fault == 'none':
        live.controlled_preflight(tmp_path, events)
    else:
        with pytest.raises(ValueError, match='CONTROLLED_'):
            live.controlled_preflight(tmp_path, events)
    assert not (tmp_path/'execution_intent.json').exists()


@pytest.mark.parametrize('session', ['session_1', 'session_4', 'session_5'])
def test_controlled_repair_only_remaining_sessions(monkeypatch, session):
    monkeypatch.setattr(sys, 'argv', ['entry', 'launch', '--round', 'controlled_accept_repaired_1',
        '--trial', session])
    with pytest.raises(ValueError, match='CONTROLLED_REMAINING_TWO_SESSION_LIMIT'):
        live.main()


def test_controlled_repair_does_not_bypass_total_session_budget(tmp_path, monkeypatch):
    project = tmp_path/'project'
    root = project/'evidence/runtime_v2/controlled_accept'
    write(root/'summary.json', dict(status='CLOSED_SETUP_FAILED_BEFORE_DISPATCH',
        live_session_count=1, writes_dispatched=0, accept_actions=0))
    for name in ('session_1', 'another/session_2', 'other/session_3'):
        write(root/name/'launch.json', dict(pid=1))
    monkeypatch.setattr(live, 'ROOT', project)
    monkeypatch.setattr(live, 'baseline', lambda: None)
    monkeypatch.setattr(sys, 'argv', ['entry', 'launch', '--round', 'controlled_accept_repaired_1',
        '--trial', 'session_2'])
    with pytest.raises(ValueError, match='CONTROLLED_TOTAL_SESSION_BUDGET_EXHAUSTED'):
        live.main()


@pytest.mark.parametrize('round_id', ['diagnostic_1','diagnostic_2','diagnostic_3','diagnostic_4','preview_phase_1'])
def test_diagnostic_round_rejects_additional_session(monkeypatch,round_id):
    monkeypatch.setattr(sys,'argv',['entry','launch','--round',round_id,'--trial','session_2'])
    with pytest.raises(ValueError,match='DIAGNOSTIC_SINGLE_SESSION_ONLY'):
        live.main()


@pytest.mark.parametrize('fault', ['local', 'local_evidence', 'observer', 'backend'])
def test_cleanup_failure_does_not_skip_other_resources(tmp_path, monkeypatch, fault):
    from types import SimpleNamespace
    closed = []
    records = {}
    async def local_close():
        closed.append('local')
        if fault == 'local':
            raise ValueError('故障')
    def observer_stop():
        closed.append('observer')
        if fault == 'observer':
            raise ValueError('故障')
    async def backend_close():
        closed.append('backend')
        if fault == 'backend':
            raise ValueError('故障')
    def record(path, value):
        if path.name == 'local_observation.json' and fault == 'local_evidence':
            raise OSError('故障')
        records[path.name] = value
    monkeypatch.setattr(live, 'write', record)
    with pytest.raises(ValueError, match='RUNTIME_CLEANUP_UNCONFIRMED'):
        asyncio.run(live.close_runtime_resources(
            SimpleNamespace(close=local_close, metrics=lambda: {}, frames={}),
            SimpleNamespace(stop=observer_stop, result=lambda: {}),
            SimpleNamespace(close=backend_close), SimpleNamespace(callbacks_restored=fault != 'backend'),
            tmp_path, {}, SimpleNamespace(events=[])))
    assert closed == ['local', 'observer', 'backend']
    assert records['result.json']['resource_cleanup_status'] == 'FAILED'
    assert len(records['result.json']['cleanup_errors']) == 1


def test_frozen_version_blocks_changed_code_but_keeps_manifest(tmp_path, monkeypatch):
    code = tmp_path/'research/entry.py'
    code.parent.mkdir()
    code.write_text('value = 1\n', encoding='utf-8')
    monkeypatch.setattr(live, 'ROOT', tmp_path)
    directory = tmp_path/'round'
    live.stability_version(directory, create=True)
    original = (directory/'version.json').read_bytes()
    live.stability_version(directory)
    code.write_text('value = 2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='STABILITY_VERSION_CHANGED'):
        live.stability_version(directory, create=True)
    assert (directory/'version.json').read_bytes() == original


def test_stability_round_refuses_fourth_session(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['entry', 'launch', '--round', 'stability_1', '--trial', 'session_4'])
    with pytest.raises(ValueError, match='STABILITY_THREE_SESSION_LIMIT'):
        live.main()


@pytest.mark.parametrize('fault', ['cleanup', 'callback', 'full_screen', 'listener'])
def test_stability_requires_complete_execution_and_all_cleanup(tmp_path, fault):
    complete(tmp_path)
    result = json.loads((tmp_path/'result.json').read_text(encoding='utf-8'))
    result.update(execution_status='SUCCESS', resource_cleanup_status='COMPLETE', cleanup_errors=[])
    result['value']['completion_status'] = 'COMPLETION_CONFIRMED'
    write(tmp_path/'full_screen_observation.json', dict(observer_stopped=True, error=None))
    write(tmp_path/'winevents.json', dict(unhooked=True, error=None))
    write(tmp_path/'result.json', result)
    assert live.previous_passed(tmp_path, strict=True)
    if fault == 'cleanup':
        result['resource_cleanup_status'] = 'FAILED'
    elif fault == 'callback':
        result['value']['completion_status'] = 'UNKNOWN'
    elif fault == 'full_screen':
        write(tmp_path/'full_screen_observation.json', dict(observer_stopped=False, error=None))
    else:
        write(tmp_path/'winevents.json', dict(unhooked=False, error=None))
    write(tmp_path/'result.json', result)
    assert not live.previous_passed(tmp_path, strict=True)
