"""将既有实验后端收敛为结构化输入、人工接受及独立结果证据。"""

import asyncio
import copy
from dataclasses import asdict, dataclass, field
import inspect
import time

from .models import ExecutionStatus
from .native_write import AcceptPolicy, PianoRollBatchAddPlan, validate_plan
from .router import BackendRouter


@dataclass
class FastMusicResult:
    operation_id: str
    state: str = 'STOPPED_BEFORE_DISPATCH'
    mode: str = 'FAST'
    target_preparation: str = 'NOT_CONFIRMED'
    dispatch: str = 'NOT_DISPATCHED'
    application: str = 'NOT_OBSERVED'
    completion: str = 'NOT_DISPATCHED'
    human_accept: str = 'NOT_REQUESTED'
    producer_target_binding: str = 'NOT_VERIFIED'
    exact_set: str = 'NOT_VERIFIED'
    error_code: str | None = None
    evidence: dict = field(default_factory=dict)

    def to_dict(self):
        return copy.deepcopy(asdict(self))


def _plan(target, musical_plan, operation_id, policy):
    if not isinstance(target, dict) or set(target) != {
            'pattern_index', 'pattern_name', 'channel_global_index', 'expected_channel_name'}:
        raise ValueError('EXPLICIT_TARGET_REQUIRED')
    if not isinstance(musical_plan, dict) or set(musical_plan) != {'ppq_context', 'notes'}:
        raise ValueError('STRUCTURED_MUSICAL_PLAN_REQUIRED')
    context = musical_plan['ppq_context']
    if (not isinstance(context, dict) or set(context) != {'ppq', 'time_unit', 'velocity_unit'}
            or type(context['ppq']) is not int or context['ppq'] != 96
            or context['time_unit'] != 'ticks' or context['velocity_unit'] != 'normalized_0_1'):
        raise ValueError('CERTIFIED_PPQ_AND_UNITS_REQUIRED')
    if (not isinstance(policy, dict) or set(policy) != {
            'add_only', 'max_notes', 'retry', 'fallback_after_dispatch'}
            or policy['add_only'] is not True
            or any(type(policy[k]) is not int for k in ('max_notes', 'retry', 'fallback_after_dispatch'))
            or policy['max_notes'] != 16 or policy['retry'] != 0 or policy['fallback_after_dispatch'] != 0):
        raise ValueError('CERTIFIED_FAST_POLICY_REQUIRED')
    notes = musical_plan['notes']
    if not isinstance(notes, (list, tuple)) or len(notes) != 16:
        raise ValueError('CERTIFIED_16_NOTE_SCOPE_REQUIRED')
    converted = []
    for note in notes:
        if not isinstance(note, dict) or set(note) != {'pitch', 'start', 'length', 'velocity'}:
            raise ValueError('STRUCTURED_NOTE_REQUIRED')
        converted.append(dict(number=note['pitch'], time=note['start'],
                              length=note['length'], velocity=note['velocity']))
    plan = PianoRollBatchAddPlan(dict(
        expected_pattern_index=target['pattern_index'], expected_pattern_name=target['pattern_name'],
        expected_channel_index=target['channel_global_index'],
        expected_channel_name=target['expected_channel_name']), tuple(converted), operation_id).operation_plan()
    rendered = validate_plan(plan)
    if any(n['time'] + n['length'] > 96 * 4 * 8 for n in converted):
        raise ValueError('EIGHT_BAR_SCOPE_EXCEEDED')
    return plan, rendered


class _HumanEvidence:
    def __init__(self, interaction, operation_id, result, on_event):
        self.interaction = interaction
        self.operation_id = operation_id
        self.result = result
        self.on_event = on_event

    def __getattr__(self, name):
        return getattr(self.interaction, name)

    async def wait_preview(self, operation_id):
        receipt = await self.interaction.wait_preview(operation_id)
        if (not isinstance(receipt, dict) or receipt.get('operation_id') != self.operation_id
                or receipt.get('observed') is not True or receipt.get('host_preview_present') is not True
                or not receipt.get('evidence_ref')):
            raise ValueError('HOST_PREVIEW_EVIDENCE_REQUIRED')
        self.result.evidence['preview'] = copy.deepcopy(receipt)
        event = dict(state='READY_FOR_HUMAN_ACCEPT', operation_id=self.operation_id,
                     clock_domain='runtime_monotonic', emitted_at=time.monotonic(),
                     preview_basis='HOST_PREVIEW_PRESENT_HUMAN_REVIEW_REQUIRED',
                     exact_set='NOT_VERIFIED')
        self.result.evidence.setdefault('events', []).append(event)
        if self.on_event is not None:
            try:
                self.on_event(copy.deepcopy(event))
            except Exception as error:
                # 通知失败不能改变已经派发的宿主调用或虚构其执行状态。
                self.result.evidence['notification_error'] = type(error).__name__
        return receipt

    async def wait_accept(self, operation_id):
        self.result.human_accept = 'UNKNOWN'
        try:
            receipt = await self.interaction.wait_accept(operation_id)
        except Exception as error:
            self.result.human_accept = ('TIMEOUT' if isinstance(error, TimeoutError)
                or str(error) == 'HUMAN_EVENT_TIMEOUT' else 'UNKNOWN')
            raise
        if (not isinstance(receipt, dict) or receipt.get('operation_id') != self.operation_id
                or receipt.get('accepted') is not True or receipt.get('accept_actor') != 'human'
                or not receipt.get('evidence_ref')):
            self.result.human_accept = 'REJECTED'
            raise ValueError('HUMAN_ACCEPT_RECEIPT_REQUIRED')
        self.result.human_accept = 'REPORTED'
        self.result.evidence['human_accept'] = copy.deepcopy(receipt)
        return receipt

    async def wait_application(self, operation_id):
        receipt = await self.interaction.wait_application(operation_id)
        if (not isinstance(receipt, dict) or receipt.get('operation_id') != self.operation_id
                or receipt.get('observed') is not True or not receipt.get('evidence_ref')):
            raise ValueError('APPLICATION_EVIDENCE_REQUIRED')
        self.result.evidence['application'] = copy.deepcopy(receipt)
        return receipt


class FastMusicRuntime:
    """独占一个已配置后端；不启动宿主，不创建目标，不替调用方保存或关闭工程。"""

    def __init__(self, backend):
        from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
        if not isinstance(backend, GopherNativeWriteBackend):
            raise TypeError('NATIVE_FAST_BACKEND_REQUIRED')
        self.backend = backend
        self.lock = asyncio.Lock()
        self.operations = set()
        self.last_result = None

    async def execute_fast_music_plan(self, target, musical_plan, acceptance_mode='human', *,
            operation_id, experimental_authorized=False, policy=None, on_event=None):
        async with self.lock:
            result = FastMusicResult(operation_id)
            self.last_result = result
            interaction = self.backend.interaction
            discovered = False
            try:
                if experimental_authorized is not True:
                    raise ValueError('EXPERIMENTAL_AUTHORIZATION_REQUIRED')
                if acceptance_mode != 'human' or self.backend.accept_policy != AcceptPolicy.MANUAL_ACCEPT:
                    raise ValueError('HUMAN_ACCEPT_ONLY')
                if interaction is None or getattr(interaction, 'local_preview', False) is True:
                    raise ValueError('HUMAN_PREVIEW_INTERACTION_REQUIRED')
                if on_event is not None and (not callable(on_event) or inspect.iscoroutinefunction(on_event)
                        or inspect.iscoroutinefunction(getattr(on_event, '__call__', None))):
                    raise ValueError('SYNCHRONOUS_EVENT_CALLBACK_REQUIRED')
                if type(operation_id) is not str:
                    raise ValueError('OPERATION_ID_REQUIRED')
                plan, rendered = _plan(copy.deepcopy(target), copy.deepcopy(musical_plan), operation_id,
                    copy.deepcopy(policy) if policy is not None else dict(
                        add_only=True, max_notes=16, retry=0, fallback_after_dispatch=0))
                if operation_id in self.operations:
                    raise ValueError('OPERATION_ALREADY_ATTEMPTED')
                # 未知结果也不能用同一operation重新导航或派发；持久派发预算仍由旧journal负责。
                self.operations.add(operation_id)
                self.backend.last_execution = None
                self.backend.prepared = None
                result.evidence.update(target=copy.deepcopy(target), source_hash=rendered.sha256,
                    template_hash=rendered.template_hash, note_count=16,
                    ppq_context=dict(
                        ppq=96, time_unit='ticks', velocity_unit='normalized_0_1'))
                self.backend.interaction = _HumanEvidence(interaction, operation_id, result, on_event)
                router = BackendRouter([self.backend])
                discovered = True
                errors = await router.discover()
                if errors:
                    raise ValueError('HOST_DISCOVERY_FAILED')
                raw_result = await router.execute(plan)
                result.evidence['operation_result'] = raw_result.to_dict()
                result.error_code = raw_result.error_code or raw_result.message
                record = copy.deepcopy(self.backend.last_execution or {})
                result.evidence['backend_execution'] = record
                if self.backend.prepared is not None:
                    result.target_preparation = 'CONFIRMED_OBSERVATIONAL'
                    result.evidence['target_preparation'] = copy.deepcopy(self.backend.prepared)
                dispatched = (record.get('dispatch_status') == 'DISPATCHED'
                    or bool(raw_result.script_invocation and raw_result.script_invocation.dispatched))
                dispatch_unknown = not dispatched and raw_result.execution_status == ExecutionStatus.UNKNOWN
                if dispatched or dispatch_unknown:
                    result.dispatch = 'DISPATCHED' if dispatched else 'UNKNOWN'
                    result.state = 'STOPPED_AFTER_DISPATCH_UNKNOWN'
                    result.completion = 'UNKNOWN'
                    from dawloop.adapters.gopher_native.response import decode_script_acceptance
                    decoded = decode_script_acceptance(record.get('raw_bridge_response'))
                    if decoded.status == ExecutionStatus.SUCCESS:
                        result.completion = 'CONFIRMED'
                    elif result.error_code is None:
                        result.error_code = decoded.error_code or 'HOST_COMPLETION_UNPROVEN'
                    if record.get('application_status') == 'APPLICATION_OBSERVED':
                        result.application = 'OBSERVED'
                    if (result.completion == 'CONFIRMED' and result.application == 'OBSERVED'
                            and result.human_accept == 'REPORTED' and not result.error_code):
                        result.state = 'COMPLETED_UNVERIFIED'
            except asyncio.CancelledError:
                self._capture_stop(result, 'CANCELLED')
                raise
            except Exception as error:
                self._capture_stop(result, str(error) if isinstance(error, ValueError) else type(error).__name__)
            finally:
                if discovered:
                    try:
                        await self.backend.close()
                        result.evidence['bridge_cleanup'] = dict(
                            callbacks_restored=getattr(self.backend.transport, 'callbacks_restored', None))
                    except Exception as error:
                        result.evidence['bridge_cleanup'] = dict(error=type(error).__name__)
                        result.error_code = result.error_code or 'BRIDGE_CLEANUP_FAILED'
                        if result.dispatch != 'NOT_DISPATCHED':
                            result.state = 'STOPPED_AFTER_DISPATCH_UNKNOWN'
                self.backend.interaction = interaction
            return result

    def _capture_stop(self, result, error):
        result.error_code = error
        record = copy.deepcopy(self.backend.last_execution or {})
        if result.evidence.get('source_hash') and record.get('operation_id') == result.operation_id:
            result.evidence['backend_execution'] = record
            if record.get('dispatch_status') == 'DISPATCHED':
                result.dispatch = 'DISPATCHED'
                result.completion = 'UNKNOWN'
                result.state = 'STOPPED_AFTER_DISPATCH_UNKNOWN'
