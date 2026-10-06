"""固定音乐片段的结构化输入与人工观察边界。"""

import asyncio
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import time

from dawloop.note_plan.model import NoteEvent, NotePlan
from dawloop.time import MusicalGrid
from dawloop.runtime.native_write import PianoRollBatchAddPlan, PianoRollScriptRenderer


OPERATION_ID = 'practical-kick-16-session-1'
OPERATION_IDS = (OPERATION_ID, 'practical-kick-16-session-2',
                 'practical-kick-16-auto-navigation-session-1',
                 'practical-kick-16-auto-navigation-session-2',
                 'practical-kick-16-auto-navigation-session-3',
                 'practical-kick-16-auto-navigation-session-4',
                 'practical-kick-16-auto-navigation-session-5',
                 'practical-kick-16-auto-navigation-session-6',
                 'practical-kick-16-auto-navigation-session-7')
TARGET = dict(expected_pattern_index=1, expected_pattern_name='样式 1',
              expected_channel_index=0, expected_channel_name='808 Kick')
POSITIONS = ((1536,1680,1728,1872), (1920,1992,2112,2232),
             (2304,2448,2496,2568), (2688,2856,2880,3024))
VELOCITIES = ((108,70,101,76), (110,62,103,72), (108,70,101,66), (110,64,103,80))


def musical_plan():
    return NotePlan('pattern-1-channel-0', MusicalGrid(96,4,4), 1536, 4,
        tuple(NoteEvent(t,12,60,v) for ts,vs in zip(POSITIONS,VELOCITIES)
              for t,v in zip(ts,vs)))


def operation_plan(operation_id=OPERATION_ID):
    if operation_id not in OPERATION_IDS:
        raise ValueError('MUSIC_SLICE_SESSION_NOT_APPROVED')
    events = musical_plan().events
    notes = tuple(dict(number=e.pitch, time=e.start_tick, length=e.duration,
        velocity=float((Decimal(e.velocity)/127).quantize(
            Decimal('0.000001'), rounding=ROUND_HALF_UP))) for e in events)
    return PianoRollBatchAddPlan(dict(TARGET), notes, operation_id).operation_plan()


def validate_slice(plan, operation_id=OPERATION_ID):
    expected = operation_plan(operation_id)
    if (plan.operation != expected.operation or plan.mode != expected.mode
            or plan.target != expected.target or plan.parameters != expected.parameters
            or plan.metadata != expected.metadata or plan.note_plan is not None):
        raise ValueError('MUSIC_SLICE_SCOPE_MISMATCH')
    return PianoRollScriptRenderer().render(plan.parameters['notes'])


def guard_preparation(receipt, session, now=None, operation_id=OPERATION_ID):
    operation_plan(operation_id)
    now = time.time() if now is None else now
    if (receipt.get('operation_id') != operation_id or receipt.get('session') != session
            or receipt.get('target') != TARGET or receipt.get('region') != [1536,3072]
            or receipt.get('active_region_empty') is not True
            or receipt.get('human_available') is not True
            or receipt.get('preview_absent') is not True
            or receipt.get('observer') != 'agent_visual_review'
            or not receipt.get('evidence_ref')
            or type(receipt.get('observed_unix')) not in (int,float)
            or not 0 <= now-receipt['observed_unix'] <= 60):
        raise ValueError('MUSIC_SLICE_PREPARATION_REQUIRED')


def evidence_bundle(operation_id=OPERATION_ID):
    plan = musical_plan()
    rendered = validate_slice(operation_plan(operation_id), operation_id)
    body = plan.to_dict()
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',',':'),
        ensure_ascii=False).encode('utf-8')).hexdigest()
    return dict(musical_plan=body, plan_sha256=digest,
        source_sha256=rendered.sha256, template_sha256=rendered.template_hash,
        source_size=rendered.source_size, note_count=rendered.note_count,
        role='切分底鼓句', target=TARGET, exact_set_verified=False,
        useful_musical_output=None, scope='OFFLINE_PREPARATION'), rendered


class HumanSliceInteraction:
    local_preview = False
    accept_observer = 'human'
    accept_window_seconds = 30
    event_wait_seconds = 45

    def __init__(self, read_event, verify_target, *, clock=time.monotonic, sleep=asyncio.sleep,
                 operation_id=OPERATION_ID):
        operation_plan(operation_id)
        self.operation_id = operation_id
        self.read_event = read_event
        self.verify_target = verify_target
        self.clock = clock
        self.sleep = sleep
        self.task = None
        self.started = None
        self.preview = None
        self.accept_receipt = None
        self.events = []

    def bind_dispatch_task(self, task):
        self.task = task
        self.started = self.clock()

    def pending(self):
        if (self.task is None or self.task.done() or (self.accept_window_seconds is not None
                and self.clock()-self.started >= self.accept_window_seconds)):
            raise ValueError('HUMAN_ACCEPT_WINDOW_CLOSED')

    def completed_response(self):
        if self.task is None:
            raise ValueError('DISPATCH_TASK_REQUIRED')
        if not self.task.done():
            return None
        if self.task.cancelled() or self.task.exception() is not None:
            raise ValueError('CALL_COMPLETION_UNKNOWN')
        response, error, *_ = self.task.result()
        if error is not None or not response:
            raise ValueError('CALL_COMPLETION_UNKNOWN')
        return response

    async def event(self, name, *, pending=False):
        deadline = self.clock()+self.event_wait_seconds
        while self.clock()<deadline:
            if pending:
                self.pending()
            value = self.read_event(name)
            if value is not None:
                if (value.get('operation_id') != self.operation_id or not value.get('evidence_ref')
                        or value.get('observer') not in ('human','agent_visual_review')):
                    raise ValueError('HUMAN_EVENT_INVALID')
                self.events.append(dict(event=name, received_monotonic=self.clock(), receipt=value))
                return value
            # 失败回调不能靠继续等待人工消息恢复；成功回调允许稍后补交回执。
            if name in ('accept','application'):
                self.completed_response()
            await self.sleep(0.05)
        raise ValueError('HUMAN_EVENT_TIMEOUT')

    async def wait_preview(self, operation_id):
        if operation_id != self.operation_id:
            raise ValueError('OPERATION_MISMATCH')
        value = await self.event('preview', pending=True)
        if value.get('observed') is not True or value.get('host_preview_present') is not True:
            raise ValueError('HUMAN_PREVIEW_REQUIRED')
        await self.verify_target()
        self.pending()
        self.preview = value
        return value

    async def wait_accept(self, operation_id):
        if operation_id != self.operation_id or self.preview is None:
            raise ValueError('HUMAN_PREVIEW_REQUIRED')
        # 人工回执可能晚于成功回调到达，不能把通知时刻冒充点击时刻。
        value = await self.event('accept')
        if (value.get('accepted') is not True or value.get('observer') != self.accept_observer
                or (self.accept_window_seconds is not None
                    and value.get('accepted_within_window') is not True)):
            raise ValueError('HUMAN_ACCEPT_REQUIRED')
        response = self.completed_response()
        if (response is None and self.accept_window_seconds is not None
                and self.clock()-self.started >= self.accept_window_seconds):
            raise ValueError('HUMAN_ACCEPT_WINDOW_CLOSED')
        await self.verify_target()
        self.accept_receipt = value
        return value

    async def wait_application(self, operation_id):
        if operation_id != self.operation_id or self.accept_receipt is None:
            raise ValueError('HUMAN_ACCEPT_REQUIRED')
        value = await self.event('application')
        if (value.get('observed') is not True or value.get('preview_closed') is not True
                or value.get('phrase_visible') is not True):
            raise ValueError('APPLICATION_REVIEW_REQUIRED')
        await self.verify_target()
        return value

    async def guarded_auto_accept(self, *args):
        raise ValueError('AUTO_ACCEPT_DEFERRED')

    def timing(self):
        return dict(clock_domain='python_monotonic', events=self.events,
            accept_window_seconds=self.accept_window_seconds,
            human_accept_timestamp=None, human_review_accept_wait_ms=None,
            accept_to_callback_ms=None, exact_set_verified=False,
            preview_certification=('HOST_PREVIEW_PRESENT' if self.preview is not None else 'NOT_OBSERVED'),
            human_accept_reported=self.accept_receipt is not None and self.accept_observer == 'human',
            agent_accept_reported=self.accept_receipt is not None and self.accept_observer == 'agent_visual_review',
            human_content_review='NOT_CERTIFIED')
