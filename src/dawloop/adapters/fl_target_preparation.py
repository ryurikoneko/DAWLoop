"""现有目标导航与独立界面观察的受限准备契约。"""

import asyncio
import copy
import math
import time

from dawloop.runtime.identity import IdentityFieldStatus
from dawloop.runtime.native_write import TARGET_FIELDS
from .fl_controller_identity import controller_snapshot


class ControllerTargetPreparer:
    def __init__(self, identity_backend, navigate, observe_ui, *, window_identity,
                 clock=time.time, max_age_seconds=60):
        if (not isinstance(window_identity, dict)
                or set(window_identity) != {'pid', 'hwnd'}
                or any(type(v) is not int or v <= 0 for v in window_identity.values())
                or type(max_age_seconds) not in (int, float)
                or not math.isfinite(max_age_seconds) or not 0 < max_age_seconds <= 60):
            raise ValueError('TARGET_PREPARATION_CONFIGURATION_INVALID')
        self.identity_backend = identity_backend
        self.navigate = navigate
        self.observe_ui = observe_ui
        self.window_identity = dict(window_identity)
        self.clock = clock
        self.max_age_seconds = max_age_seconds
        self.prepared = None
        self.lock = asyncio.Lock()

    def validate_request(self, target, session):
        if (not isinstance(target, dict) or set(target) != set(TARGET_FIELDS)
                or type(target['expected_pattern_index']) is not int
                or target['expected_pattern_index'] < 1
                or type(target['expected_channel_index']) is not int
                or target['expected_channel_index'] < 0
                or any(not isinstance(target[k], str) or not target[k].strip()
                       for k in ('expected_pattern_name', 'expected_channel_name'))):
            raise ValueError('EXPLICIT_TARGET_REQUIRED')
        keys = (('controller_build_id', 'controller_session_id', 'project_generation')
                if isinstance(session, dict) and session.get('binding_kind') == 'CONTROLLER_ONLY'
                else ('session', 'bridge_epoch', 'host_generation', 'target_id'))
        if (not isinstance(session, dict)
                or any(not isinstance(session.get(k), str) or not session[k].strip() for k in keys)):
            raise ValueError('HOST_BINDING_REQUIRED')

    def fresh(self, timestamp):
        now = self.clock()
        if (type(timestamp) not in (int, float) or not math.isfinite(timestamp)
                or type(now) not in (int, float) or not math.isfinite(now)
                or not 0 <= now-timestamp <= self.max_age_seconds):
            raise ValueError('TARGET_EVIDENCE_STALE')

    def identity(self, value, target=None):
        snapshot, status = controller_snapshot(value)
        names = ('pattern_index', 'pattern_name', 'channel_index', 'channel_name', 'ppq')
        if any(status[k] != IdentityFieldStatus.AVAILABLE for k in names):
            raise ValueError('TARGET_IDENTITY_AMBIGUOUS')
        self.fresh(snapshot.pattern_index.observed_at.timestamp())
        if target is not None:
            for field, observed in zip(TARGET_FIELDS, names):
                if getattr(snapshot, observed).value != target[field]:
                    raise ValueError('TARGET_IDENTITY_MISMATCH')
        return value['controller_session'], value['project_generation']

    def check_ui(self, ui, target, session):
        if (not isinstance(ui, dict) or ui.get('visible') is not True
                or ui.get('confirmed') is not True
                or ui.get('observer') not in ('agent_visual_review', 'human')
                or not isinstance(ui.get('evidence_ref'), str) or not ui['evidence_ref'].strip()
                or type(ui.get('pattern_number')) is not int
                or ui['pattern_number'] != target['expected_pattern_index']
                or ui.get('channel_name') != target['expected_channel_name']
                or type(ui.get('window_pid')) is not int
                or type(ui.get('window_hwnd')) is not int
                or ui['window_pid'] != self.window_identity['pid']
                or ui['window_hwnd'] != self.window_identity['hwnd']
                or ui.get('session') != session):
            raise ValueError('PIANO_ROLL_TARGET_UNCONFIRMED')
        self.fresh(ui.get('observed_unix'))

    async def observe(self, target, session, context):
        before = await self.identity_backend.read_identity()
        if session.get('binding_kind') == 'CONTROLLER_ONLY' and any(
                before.get(k) != session[k] for k in ('controller_build_id', 'controller_session_id', 'project_generation')):
            raise ValueError('CONTROLLER_BUILD_CONTEXT_MISMATCH')
        if self.identity(before, target) != context:
            raise ValueError('TARGET_CONTEXT_CHANGED')
        ui = copy.deepcopy(await self.observe_ui(copy.deepcopy(target), copy.deepcopy(session)))
        self.check_ui(ui, target, session)
        after = await self.identity_backend.read_identity()
        if session.get('binding_kind') == 'CONTROLLER_ONLY' and any(
                after.get(k) != session[k] for k in ('controller_build_id', 'controller_session_id', 'project_generation')):
            raise ValueError('CONTROLLER_BUILD_CONTEXT_MISMATCH')
        if self.identity(after, target) != context or before['ppq'] != after['ppq']:
            raise ValueError('TARGET_CONTEXT_CHANGED')
        first = controller_snapshot(before)[0].pattern_index.observed_at.timestamp()
        last = controller_snapshot(after)[0].pattern_index.observed_at.timestamp()
        if not first <= ui['observed_unix'] <= last:
            raise ValueError('TARGET_OBSERVATION_ORDER_UNPROVEN')
        # 首尾一致只证明本次观察边界，不能排除中途切换又切回。
        self.identity(before, target)
        self.check_ui(ui, target, session)
        return dict(identity=copy.deepcopy(after), ui=ui, session=copy.deepcopy(session),
                    binding=dict(level='OBSERVATIONAL', controller_session=context[0],
                                 project_generation=context[1], identity_before=copy.deepcopy(before),
                                 identity_after=copy.deepcopy(after), producer_target_verified=False,
                                 automation_live_certified=False))

    async def prepare(self, target, session):
        async with self.lock:
            self.prepared = None
            self.validate_request(target, session)
            target, session = copy.deepcopy(target), copy.deepcopy(session)
            initial = await self.identity_backend.read_identity()
            context = self.identity(initial)
            await self.navigate(copy.deepcopy(target), copy.deepcopy(session))
            evidence = await self.observe(target, session, context)
            self.prepared = (target, session, context)
            return evidence

    async def confirm(self, target, session):
        async with self.lock:
            try:
                self.validate_request(target, session)
                if self.prepared is None or (target, session) != self.prepared[:2]:
                    raise ValueError('TARGET_PREPARATION_REQUIRED')
                return await self.observe(copy.deepcopy(target), copy.deepcopy(session), self.prepared[2])
            except BaseException:
                self.prepared = None
                raise
