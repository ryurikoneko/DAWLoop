"""仅导航的交接协调；宿主和界面输入由既有适配回调提供。"""

import copy
from datetime import datetime
import json
import time
from types import MappingProxyType

from dawloop.adapters.fl_target_preparation import ControllerTargetPreparer


class NavigationHandoff:
    def __init__(self, backend, identity, read_session, primitive, observe_ui, recover,
                 *, targets, steps, window_identity, expected_catalog_hash, scope,
                 clock=time.time, monotonic=time.perf_counter):
        self.backend, self.reader = backend, identity
        self.read_session, self.primitive = read_session, primitive
        self.observe_ui, self.recover = observe_ui, recover
        self.targets = copy.deepcopy(targets)
        self.steps = MappingProxyType({direction: tuple(values) for direction, values in steps.items()})
        if (set(self.steps) != {'A_TO_B', 'B_TO_A'} or any(
                not values or len(values) > 8 or len(set(values)) != len(values)
                or any(value not in {'select_pattern', 'select_channel', 'open_piano_roll',
                                     'focus_channel_rack'} for value in values)
                for values in self.steps.values())):
            raise ValueError('PREDEFINED_PRIMITIVES_REQUIRED')
        self.expected_catalog_hash = expected_catalog_hash
        self.clock, self.monotonic = clock, monotonic
        self.session = self.context = None
        self.phase = 'NOT_STARTED'
        self.used = False
        self.last_identity_complete = None
        self.awaiting_identity_2 = False
        self.observation_exchange = None
        self.report = dict(scope=scope, events=[], evidence={}, timing={},
                           navigation_transactions=0, navigation_primitives=0,
                           directions={}, repair_retries=0, fallback_navigation=0,
                           note_dispatches=0, run_piano_roll_script_calls=0,
                           auto_accept='OFF', producer_target_verified=False,
                           exact_target_binding=False, automation_production_ready=False,
                           live_certified=False)
        self.preparer = ControllerTargetPreparer(self, self.navigate, self.ui,
                                                 window_identity=window_identity, clock=clock)

    def event(self, name, **metadata):
        self.report['events'].append(dict(event=name, timestamp=self.clock(), **metadata))

    async def check_session(self):
        if await self.read_session() != self.session:
            raise ValueError('HOST_BINDING_CHANGED')

    async def read_identity(self):
        await self.check_session()
        if self.awaiting_identity_2 and self.observation_exchange is not None:
            self.observation_exchange.confirm_started()
        started = self.monotonic()
        value = await self.reader.read_identity()
        await self.check_session()
        context = self.preparer.identity(value)
        if self.context is not None and context != self.context:
            raise ValueError('TARGET_CONTEXT_CHANGED')
        if value.get('ppq') != 96:
            raise ValueError('PPQ_MISMATCH')
        self.event('IDENTITY_READ', phase=self.phase, duration_ms=(self.monotonic()-started)*1000)
        from research.observation_handoff import stamp
        if self.observation_exchange is not None:
            self.last_identity_complete = stamp(self.observation_exchange.domain)
            if self.awaiting_identity_2:
                self.observation_exchange.confirm_complete()
                self.report.setdefault('handoff_timing', []).append(dict(
                    trace=copy.deepcopy(self.observation_exchange.trace),
                    durations=self.observation_exchange.durations()))
        self.awaiting_identity_2 = False
        return value

    async def navigate(self, target, session):
        direction = self.phase
        expected = self.targets['B' if direction == 'A_TO_B' else 'A']
        if (direction not in self.steps or direction in self.report['directions']
                or target != expected or session != self.session):
            raise ValueError('NAVIGATION_TRANSACTION_FORBIDDEN')
        await self.check_session()
        row = dict(navigation_transactions=1, navigation_primitives=0,
                   predefined_primitives=list(self.steps[direction]), outcome='UNKNOWN')
        self.report['directions'][direction] = row
        self.report['navigation_transactions'] += 1
        self.event('NAVIGATION_BEGIN', direction=direction)
        started = self.monotonic()
        for step in self.steps[direction]:
            await self.check_session()
            # 计数包含结果未知的尝试，失败后绝不重新认领动作预算。
            row['navigation_primitives'] += 1
            self.report['navigation_primitives'] += 1
            self.event('NAVIGATION_PRIMITIVE', direction=direction, primitive=step)
            outcome = await self.primitive(step, copy.deepcopy(target), copy.deepcopy(session))
            if outcome != 'SUCCESS':
                raise ValueError('NAVIGATION_RESULT_UNKNOWN' if outcome == 'UNKNOWN' else 'NAVIGATION_PRIMITIVE_FAILED')
            await self.check_session()
        row.update(outcome='SUCCESS', navigation_action_duration_ms=(self.monotonic()-started)*1000)
        self.phase = direction + '_CONFIRM'
        self.event('NO_MORE_NAVIGATION', direction=direction)

    async def ui(self, target, session):
        await self.check_session()
        started = self.monotonic()
        value = await self.observe_ui(copy.deepcopy(target), copy.deepcopy(session))
        self.awaiting_identity_2 = True
        await self.check_session()
        self.event('UI_OBSERVATION', phase=self.phase, duration_ms=(self.monotonic()-started)*1000)
        return value

    def store_evidence(self, name, evidence):
        ui = evidence['ui']
        before = datetime.fromisoformat(evidence['binding']['identity_before']['observed_at']).timestamp()
        after = datetime.fromisoformat(evidence['binding']['identity_after']['observed_at']).timestamp()
        if not before < ui['capture_started_unix'] <= ui['observed_unix'] <= ui['capture_completed_unix'] < after:
            raise ValueError('STRICT_UI_BRACKET_FAILED')
        # 日志往返使用真实证据结构，同时验证序列化没有偷偷丢弃绑定字段。
        self.report['evidence'][name] = json.loads(json.dumps(evidence, ensure_ascii=False, allow_nan=False))
        rows = [row for row in self.report['events'] if row.get('phase') == self.phase]
        reads = [row['duration_ms'] for row in rows if row['event'] == 'IDENTITY_READ'][-2:]
        observations = [row['duration_ms'] for row in rows if row['event'] == 'UI_OBSERVATION']
        self.report['timing'][name] = dict(identity_read_1_duration_ms=reads[0],
            ui_observation_duration_ms=observations[-1], identity_read_2_duration_ms=reads[1],
            latency_scope='含适配器与界面交接，不是纯原生接口延迟')
        self.event(name)

    async def run(self):
        if self.used:
            raise ValueError('HANDOFF_ALREADY_CONSUMED')
        self.used = True
        self.report['status'] = 'STOPPED'
        try:
            self.session = await self.backend.connect()
            self.event('CATALOG_READINESS')
            await self.backend.discover()
            if self.backend.catalog_digest != self.expected_catalog_hash:
                raise ValueError('CATALOG_CHANGED')
            self.report['catalog_hash'] = self.backend.catalog_digest
            self.phase = 'INITIAL_A'
            initial = await self.read_identity()
            self.context = self.preparer.identity(initial, self.targets['A'])
            evidence = await self.preparer.observe(self.targets['A'], self.session, self.context)
            self.store_evidence('A_CONFIRMED', evidence)
            for direction, target, name in (('A_TO_B', 'B', 'B_CONFIRMED'),
                                             ('B_TO_A', 'A', 'A_RECONFIRMED')):
                self.phase = direction
                started = self.monotonic()
                evidence = await self.preparer.prepare(self.targets[target], self.session)
                self.store_evidence(name, evidence)
                self.report['timing'][direction] = dict(full_prepare_duration_ms=(self.monotonic()-started)*1000,
                                                        latency_scope='含界面回调交接，非原生接口延迟')
            self.report['status'] = 'HANDOFF_PASSED'
        except Exception as error:
            self.report.update(error_code=str(error), failed_phase=self.phase,
                               failure_category='TARGET_CONFIRMATION_FAILED' if self.phase.endswith('_CONFIRM') else 'HANDOFF_STOPPED')
        finally:
            self.phase = 'RECOVERY'
            if self.observation_exchange is not None:
                self.observation_exchange.terminate('STOPPED')
            cleanup_errors = []
            try:
                await self.backend.close()
                self.report['callbacks_restored'] = self.backend.transport.callbacks_restored
            except Exception as error:
                self.report['callbacks_restored'] = False
                cleanup_errors.append(str(error) or type(error).__name__)
            try:
                recovery = await self.recover()
                self.report['recovery'] = copy.deepcopy(recovery)
                if self.report['callbacks_restored'] is not True or any(
                        recovery.get(key) is not True for key in ('no_save_exit', 'baseline_unchanged', 'host_closed', 'debug_port_closed')):
                    raise ValueError('RECOVERY_NOT_CONFIRMED')
            except Exception as error:
                cleanup_errors.append(str(error) or type(error).__name__)
            if cleanup_errors:
                self.report.update(status='STOPPED', recovery_error=';'.join(cleanup_errors))
            self.event('RECOVERY_COMPLETED')
            self.phase = 'CLOSED'
        return json.loads(json.dumps(self.report, ensure_ascii=False, allow_nan=False))
