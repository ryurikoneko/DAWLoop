"""接受契约拒绝错绑与重复动作，不用窗口关闭或回调冒充提交。"""

import asyncio
import copy

import pytest

from dawloop.runtime.controlled_accept import ControlledAcceptGate
from dawloop.runtime.local_preview import FIXED_HASH


def binding():
    return dict(operation_id='four-note-op', source_hash=FIXED_HASH, note_count=4,
        host_generation='host', bridge_epoch='epoch', process_id=101, main_hwnd=102,
        preview_hwnd=103, ready_at_ns=100, fingerprint={'viewport': 'fixed'},
        target=dict(controller_session='controller', project_generation='project',
            pattern_number=1, pattern_name='样式 1', channel_index=0, channel_name='808 Kick',
            selected_channels=[0], ppq=96))


def snapshot():
    b = binding()
    return dict(context={k: b[k] for k in ('operation_id', 'source_hash',
        'host_generation', 'bridge_epoch')}, target=b['target'], fingerprint=b['fingerprint'],
        pending=True, poisoned=False, local_preview_ready=True,
        target_source='INDEPENDENT_CONTROLLER_AND_LOCAL_WINDOW',
        read_started_ns=110, read_completed_ns=120,
        preview=dict(hwnd=103, parent=102, process_id=101, fixed_title=True,
            visible=True, enabled=True), accept_controls=[dict(control_id='accept-button',
                preview_hwnd=103, process_id=101, role='ACCEPT', identity_observed=True,
                visible=True, enabled=True)])


def run(coro):
    return asyncio.run(coro)


class Calls:
    def __init__(self, values=None, error=None):
        self.values = values or [snapshot()]
        self.reads, self.actions = 0, 0
        self.error = error

    async def read(self):
        value = self.values[min(self.reads, len(self.values)-1)]
        self.reads += 1
        return copy.deepcopy(value)

    async def action(self, context, control):
        self.actions += 1
        if self.error:
            raise self.error
        return dict(context=context, control_id=control['control_id'], acknowledged=True)


def gate(tmp_path, **kwargs):
    return ControlledAcceptGate(binding(), tmp_path/'accept-intent.json',
        max_age_ns=100, clock=lambda: 130, **kwargs)


def test_default_disabled_never_reads_or_acts(tmp_path):
    calls = Calls()
    with pytest.raises(ValueError, match='AUTO_ACCEPT_DISABLED'):
        run(gate(tmp_path).accept_once(calls.read, calls.action))
    assert calls.reads == calls.actions == 0
    assert not (tmp_path/'accept-intent.json').exists()


@pytest.mark.parametrize('field', ['operation_id', 'source_hash', 'host_generation', 'bridge_epoch'])
def test_changed_request_cannot_accept(tmp_path, field):
    value = snapshot()
    value['context'][field] = 'other'
    calls = Calls([value])
    with pytest.raises(ValueError, match='ACCEPT_BINDING_CHANGED'):
        run(gate(tmp_path, enabled=True).accept_once(calls.read, calls.action))
    assert calls.actions == 0
    assert not (tmp_path/'accept-intent.json').exists()


@pytest.mark.parametrize('fault', ['target', 'viewport', 'not_pending', 'poisoned', 'no_ready',
    'gopher_target', 'old_read', 'future_read', 'inverted_read', 'wrong_window', 'wrong_parent',
    'wrong_process', 'hidden', 'disabled', 'wrong_title', 'no_control', 'two_controls',
    'cancel_control', 'unproven_control', 'disabled_control', 'foreign_control'])
def test_unsafe_state_never_reaches_action(tmp_path, fault):
    value = snapshot()
    if fault == 'target': value['target']['channel_index'] = 1
    if fault == 'viewport': value['fingerprint']['viewport'] = 'other'
    if fault == 'not_pending': value['pending'] = False
    if fault == 'poisoned': value['poisoned'] = True
    if fault == 'no_ready': value['local_preview_ready'] = False
    if fault == 'gopher_target': value['target_source'] = 'GOPHER_SINGLE_FLIGHT'
    if fault == 'old_read': value['read_started_ns'] = 99
    if fault == 'future_read': value['read_completed_ns'] = 131
    if fault == 'inverted_read': value['read_completed_ns'] = 109
    if fault == 'wrong_window': value['preview']['hwnd'] = 999
    if fault == 'wrong_parent': value['preview']['parent'] = 999
    if fault == 'wrong_process': value['preview']['process_id'] = 999
    if fault == 'hidden': value['preview']['visible'] = False
    if fault == 'disabled': value['preview']['enabled'] = False
    if fault == 'wrong_title': value['preview']['fixed_title'] = False
    if fault == 'no_control': value['accept_controls'] = []
    if fault == 'two_controls': value['accept_controls'] *= 2
    if fault == 'cancel_control': value['accept_controls'][0]['role'] = 'CANCEL'
    if fault == 'unproven_control': value['accept_controls'][0]['identity_observed'] = False
    if fault == 'disabled_control': value['accept_controls'][0]['enabled'] = False
    if fault == 'foreign_control': value['accept_controls'][0]['preview_hwnd'] = 999
    calls = Calls([value])
    with pytest.raises(ValueError):
        run(gate(tmp_path, enabled=True).accept_once(calls.read, calls.action))
    assert calls.actions == 0


def test_action_ack_is_not_commit_proof_and_cannot_repeat(tmp_path):
    calls, guarded = Calls(), gate(tmp_path, enabled=True)
    receipt = run(guarded.accept_once(calls.read, calls.action))
    assert receipt['action_status'] == 'ACTION_CONFIRMED'
    assert receipt['commit_status'] == 'UNKNOWN'
    assert receipt['exact_set_verified'] is False
    with pytest.raises(ValueError, match='ACCEPT_BUDGET_EXHAUSTED'):
        run(guarded.accept_once(calls.read, calls.action))
    with pytest.raises(FileExistsError):
        run(gate(tmp_path, enabled=True).accept_once(calls.read, calls.action))
    assert calls.actions == 1


@pytest.mark.parametrize('error', [TimeoutError('超时'), RuntimeError('断线')])
def test_unknown_action_consumes_persistent_budget(tmp_path, error):
    calls, guarded = Calls(error=error), gate(tmp_path, enabled=True)
    receipt = run(guarded.accept_once(calls.read, calls.action))
    assert receipt['action_status'] == receipt['commit_status'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='ACCEPT_BUDGET_EXHAUSTED'):
        run(guarded.accept_once(calls.read, calls.action))
    with pytest.raises(FileExistsError):
        run(gate(tmp_path, enabled=True).accept_once(calls.read, calls.action))
    assert calls.actions == 1


@pytest.mark.parametrize('fault', ['target', 'window', 'control', 'pending'])
def test_change_during_budget_reservation_rejects_without_action(tmp_path, fault):
    changed = snapshot()
    if fault == 'target': changed['target']['pattern_number'] = 2
    if fault == 'window': changed['preview']['hwnd'] = 999
    if fault == 'control': changed['accept_controls'][0]['control_id'] = 'replacement'
    if fault == 'pending': changed['pending'] = False
    calls, guarded = Calls([snapshot(), changed]), gate(tmp_path, enabled=True)
    with pytest.raises(ValueError):
        run(guarded.accept_once(calls.read, calls.action))
    assert calls.actions == 0
    assert (tmp_path/'accept-intent.json').exists()


def test_stale_ack_does_not_confirm_action(tmp_path):
    calls, guarded = Calls(), gate(tmp_path, enabled=True)
    async def wrong_ack(context, control):
        calls.actions += 1
        return dict(context=dict(context, operation_id='previous-op'),
            control_id=control['control_id'], acknowledged=True)
    receipt = run(guarded.accept_once(calls.read, wrong_ack))
    assert receipt['action_status'] == 'UNKNOWN'
    assert receipt['error_code'] == 'ACCEPT_ACTION_ACK_UNPROVEN'


def test_concurrent_accepts_only_one_action(tmp_path):
    async def experiment():
        calls, guarded = Calls(), gate(tmp_path, enabled=True)
        results = await asyncio.gather(guarded.accept_once(calls.read, calls.action),
            guarded.accept_once(calls.read, calls.action), return_exceptions=True)
        assert calls.actions == 1
        assert sum(isinstance(item, ValueError) for item in results) == 1
    run(experiment())


def test_cancelled_action_stays_unknown_and_cannot_repeat(tmp_path):
    calls, guarded = Calls(error=asyncio.CancelledError()), gate(tmp_path, enabled=True)
    with pytest.raises(asyncio.CancelledError):
        run(guarded.accept_once(calls.read, calls.action))
    assert guarded.receipt['action_status'] == 'UNKNOWN'
    assert guarded.receipt['action_returned_ns'] == 130
    with pytest.raises(ValueError, match='ACCEPT_BUDGET_EXHAUSTED'):
        run(guarded.accept_once(calls.read, calls.action))
    assert calls.actions == 1


def test_binding_is_detached_from_caller_mutation(tmp_path):
    value = binding()
    guarded = ControlledAcceptGate(value, tmp_path/'intent.json',
        max_age_ns=100, enabled=True, clock=lambda: 130)
    value['target']['channel_index'] = 99
    copy_of_binding = guarded.binding
    copy_of_binding['target']['channel_index'] = 98
    assert guarded.binding['target']['channel_index'] == 0
    calls = Calls()
    assert run(guarded.accept_once(calls.read, calls.action))['action_status'] == 'ACTION_CONFIRMED'


@pytest.mark.parametrize('field,value', [('note_count', 128), ('note_count', 4.0),
    ('source_hash', 'arbitrary-source'), ('preview_hwnd', True), ('ready_at_ns', None)])
def test_other_scope_cannot_construct_gate(tmp_path, field, value):
    changed = binding()
    changed[field] = value
    with pytest.raises(ValueError, match='CONTROLLED_ACCEPT_SCOPE_UNSUPPORTED'):
        ControlledAcceptGate(changed, tmp_path/'intent.json', max_age_ns=100)


def test_read_duration_included_in_freshness_bound(tmp_path):
    calls = Calls()
    guarded = ControlledAcceptGate(binding(), tmp_path/'intent.json',
        max_age_ns=19, enabled=True, clock=lambda: 130)
    with pytest.raises(ValueError, match='ACCEPT_EVIDENCE_STALE'):
        run(guarded.accept_once(calls.read, calls.action))
    assert calls.actions == 0


@pytest.mark.parametrize('ack', [{'preview_closed': True}, {'callback_success': True},
    {'accepted': True}, {'application_observed': True}])
def test_indirect_signals_cannot_confirm_action(tmp_path, ack):
    calls, guarded = Calls(), gate(tmp_path, enabled=True)
    async def indirect(context, control):
        calls.actions += 1
        return dict(context=context, control_id=control['control_id'], **ack)
    receipt = run(guarded.accept_once(calls.read, indirect))
    assert receipt['action_status'] == receipt['commit_status'] == 'UNKNOWN'


def test_intent_write_failure_never_reaches_action(tmp_path):
    calls = Calls()
    guarded = ControlledAcceptGate(binding(), tmp_path/'missing'/'intent.json',
        max_age_ns=100, enabled=True, clock=lambda: 130)
    with pytest.raises(FileNotFoundError):
        run(guarded.accept_once(calls.read, calls.action))
    assert calls.actions == 0
    with pytest.raises(ValueError, match='ACCEPT_BUDGET_EXHAUSTED'):
        run(guarded.accept_once(calls.read, calls.action))


@pytest.mark.parametrize('field,value', [('selected_channels', [False]),
    ('selected_channels', [0.0]), ('ppq', 96.0), ('controller_session', ''),
    ('project_generation', True)])
def test_identity_type_alias_cannot_construct_gate(tmp_path, field, value):
    changed = binding()
    changed['target'][field] = value
    with pytest.raises(ValueError, match='CONTROLLED_ACCEPT_SCOPE_UNSUPPORTED'):
        ControlledAcceptGate(changed, tmp_path/'intent.json', max_age_ns=100)


@pytest.mark.parametrize('location,field,value', [('target', 'pattern_number', True),
    ('target', 'channel_index', False), ('target', 'selected_channels', [0.0]),
    ('target', 'ppq', 96.0), ('preview', 'hwnd', 103.0),
    ('preview', 'parent', 102.0), ('preview', 'process_id', 101.0),
    ('control', 'preview_hwnd', 103.0), ('control', 'process_id', 101.0)])
@pytest.mark.parametrize('changed_read', [0, 1])
def test_numeric_alias_rejected_before_action(tmp_path, location, field, value, changed_read):
    changed = snapshot()
    if location == 'control':
        changed['accept_controls'][0][field] = value
    else:
        changed[location][field] = value
    values = [changed] if changed_read == 0 else [snapshot(), changed]
    calls = Calls(values)
    with pytest.raises(ValueError):
        run(gate(tmp_path, enabled=True).accept_once(calls.read, calls.action))
    assert calls.actions == 0
    assert (tmp_path/'accept-intent.json').exists() is bool(changed_read)


def test_cleanup_failure_still_joins_dispatched_host_task(tmp_path):
    import threading
    from dawloop.runtime import BackendRouter, ExecutionStatus, NativeWriteJournal
    from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
    from test_native_write_runtime import Interaction, Target, Transport, plan

    async def experiment():
        finished = threading.Event()
        class Host(Transport):
            def invoke_batch(self, *args):
                finished.wait(2)
                return super().invoke_batch(*args)
        class FailedCleanup(Interaction):
            local_preview = True
            async def prepare_preview(self, *args): pass
            def reconfirm_preview(self, *args): pass
            def before_dispatch(self): pass
            def runtime_ready(self, *args): pass
            async def wait_preview(self, operation):
                await asyncio.sleep(0.01)
                return dict(operation_id=operation, observed=True, observation={'verification_status':'NOT_VERIFIED'})
            async def close(self):
                finished.set()
                raise RuntimeError('采样线程停止未确认')
        host = Host()
        backend = GopherNativeWriteBackend(enabled=True, transport=host,
            target_preparer=Target(), interaction=FailedCleanup(),
            journal=NativeWriteJournal(tmp_path/'journal'), disposable_guard=lambda: True)
        router = BackendRouter([backend])
        await router.discover()
        result = await router.execute(plan())
        assert result.execution_status == ExecutionStatus.UNKNOWN
        assert result.value['completion_status'] == 'COMPLETION_CONFIRMED'
        assert result.error_code == 'INTERACTION_CLEANUP_FAILED'
        assert result.value['interaction_cleanup_error'] == '采样线程停止未确认'
        assert host.calls == 1
    run(experiment())
