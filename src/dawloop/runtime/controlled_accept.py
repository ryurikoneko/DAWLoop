"""固定四音符的接受契约；不包含界面动作驱动，也不证明工程提交。"""

import asyncio
import copy
import json
import os
from pathlib import Path
import time

from .local_preview import FIXED_HASH, TARGET_KEYS


def _same_identity(left, right):
    # 布尔值与浮点数能在普通相等比较中冒充整数身份。
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_identity(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_identity(a, b) for a, b in zip(left, right))
    return left == right


class ControlledAcceptGate:
    def __init__(self, binding, intent_path, *, max_age_ns, enabled=False,
                 clock=time.perf_counter_ns):
        self._binding = copy.deepcopy(binding)
        self.intent_path = Path(intent_path)
        self.max_age_ns, self.enabled, self.clock = max_age_ns, enabled, clock
        self.lock = asyncio.Lock()
        self.attempted = False
        self.receipt = None
        b = self._binding
        if (b.get('source_hash') != FIXED_HASH or type(b.get('note_count')) is not int
                or b['note_count'] != 4
                or any(not isinstance(b.get(k), str) or not b[k]
                    for k in ('operation_id', 'host_generation', 'bridge_epoch'))
                or any(type(b.get(k)) is not int or b[k] <= 0
                    for k in ('process_id', 'main_hwnd', 'preview_hwnd', 'ready_at_ns'))
                or not isinstance(b.get('fingerprint'), dict) or not b['fingerprint']
                or not isinstance(b.get('target'), dict)
                or any(b['target'].get(k) is None for k in TARGET_KEYS)
                or type(b['target'].get('pattern_number')) is not int
                or b['target']['pattern_number'] != 1
                or b['target'].get('pattern_name') != '样式 1'
                or type(b['target'].get('channel_index')) is not int
                or b['target']['channel_index'] != 0
                or b['target'].get('channel_name') != '808 Kick'
                or any(not isinstance(b['target'].get(k), str) or not b['target'][k]
                    for k in ('controller_session', 'project_generation'))
                or not _same_identity(b['target'].get('selected_channels'), [0])
                or type(b['target'].get('ppq')) is not int
                or b['target'].get('ppq') != 96):
            raise ValueError('CONTROLLED_ACCEPT_SCOPE_UNSUPPORTED')
        if type(max_age_ns) is not int or max_age_ns <= 0:
            raise ValueError('ACCEPT_FRESHNESS_BOUND_REQUIRED')

    @property
    def binding(self):
        return copy.deepcopy(self._binding)

    def _check(self, snapshot, now):
        b = self._binding
        if (snapshot.get('context') != {k: b[k] for k in
                ('operation_id', 'source_hash', 'host_generation', 'bridge_epoch')}
                or not _same_identity(snapshot.get('target'), b['target'])
                or not _same_identity(snapshot.get('fingerprint'), b['fingerprint'])):
            raise ValueError('ACCEPT_BINDING_CHANGED')
        if (snapshot.get('pending') is not True or snapshot.get('poisoned') is not False
                or snapshot.get('local_preview_ready') is not True):
            raise ValueError('ACCEPT_SESSION_NOT_READY')
        if snapshot.get('target_source') != 'INDEPENDENT_CONTROLLER_AND_LOCAL_WINDOW':
            raise ValueError('ACCEPT_INDEPENDENT_TARGET_EVIDENCE_REQUIRED')
        start, end = snapshot.get('read_started_ns'), snapshot.get('read_completed_ns')
        if (type(start) is not int or type(end) is not int
                or not b['ready_at_ns'] <= start <= end <= now
                or now-start > self.max_age_ns):
            raise ValueError('ACCEPT_EVIDENCE_STALE')
        preview = snapshot.get('preview') or {}
        if (any(type(preview.get(k)) is not int for k in ('hwnd', 'parent', 'process_id'))
                or preview.get('hwnd') != b['preview_hwnd']
                or preview.get('parent') != b['main_hwnd']
                or preview.get('process_id') != b['process_id']
                or preview.get('fixed_title') is not True
                or preview.get('visible') is not True or preview.get('enabled') is not True):
            raise ValueError('ACCEPT_PREVIEW_CHANGED')
        controls = snapshot.get('accept_controls')
        if not isinstance(controls, list) or len(controls) != 1:
            raise ValueError('ACCEPT_CONTROL_AMBIGUOUS_OR_MISSING')
        control = controls[0]
        if (not isinstance(control, dict)
                or not isinstance(control.get('control_id'), str) or not control['control_id']
                or any(type(control.get(k)) is not int for k in ('preview_hwnd', 'process_id'))
                or control.get('preview_hwnd') != b['preview_hwnd']
                or control.get('process_id') != b['process_id']
                or control.get('role') != 'ACCEPT'
                or control.get('identity_observed') is not True
                or control.get('visible') is not True or control.get('enabled') is not True):
            raise ValueError('ACCEPT_CONTROL_UNPROVEN')
        return copy.deepcopy(control)

    async def accept_once(self, snapshot_reader, action):
        async with self.lock:
            if self.enabled is not True:
                raise ValueError('AUTO_ACCEPT_DISABLED')
            if self.attempted:
                raise ValueError('ACCEPT_BUDGET_EXHAUSTED')
            started = self.clock()
            control = self._check(await snapshot_reader(), self.clock())
            self.attempted = True
            self.receipt = dict(action_status='NOT_DISPATCHED', commit_status='UNKNOWN',
                context={k: self.binding[k] for k in
                    ('operation_id', 'source_hash', 'host_generation', 'bridge_epoch')},
                control_id=control['control_id'], clock_domain='python_perf_counter',
                check_started_ns=started, action_started_ns=None, action_returned_ns=None,
                check_to_action_ms=None, error_code=None, exact_set_verified=False)
            # 先持久化预算；动作抛错或进程退出后不能重新实例化并再次点击。
            with self.intent_path.open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(self.receipt, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                latest = self._check(await snapshot_reader(), self.clock())
                if latest != control:
                    raise ValueError('ACCEPT_CONTROL_REPLACED')
            except Exception as error:
                self.receipt['error_code'] = str(error)
                raise
            self.receipt['action_started_ns'] = self.clock()
            self.receipt['check_to_action_ms'] = (
                self.receipt['action_started_ns'] - started) / 1e6
            self.receipt['action_status'] = 'UNKNOWN'
            try:
                answer = await action(copy.deepcopy(self.receipt['context']), latest)
                if (not isinstance(answer, dict) or answer.get('context') != self.receipt['context']
                        or answer.get('control_id') != latest['control_id']
                        or answer.get('acknowledged') is not True):
                    raise ValueError('ACCEPT_ACTION_ACK_UNPROVEN')
                self.receipt['action_status'] = 'ACTION_CONFIRMED'
            except asyncio.CancelledError:
                self.receipt['error_code'] = 'ACCEPT_ACTION_CANCELLED_UNKNOWN'
                raise
            except Exception as error:
                self.receipt['error_code'] = str(error)
            finally:
                self.receipt['action_returned_ns'] = self.clock()
            return copy.deepcopy(self.receipt)
