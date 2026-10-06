"""显式启用的实验新增后端，目标与界面观察由调用方提供。"""

import asyncio
import copy
import json
import time

from dawloop.runtime import (BackendError, BackendExecution, Capability, ExecutionMode,
    ExecutionStatus, ResponseStatus, ScriptApplicationStatus, ScriptCompletionStatus,
    ScriptInvocationState, ToolSafetyClassification)
from dawloop.runtime.native_write import (AcceptPolicy, NATIVE_BATCH_ADD,
    NativeWriteState, validate_plan)
from .backend import GopherNativeBackend
from .catalog import known_catalog, catalog_hash
from dawloop.runtime.diagnostics import observe, diagnostic_span


CERTIFIED_CATALOG = '514d035244b0aea4d94fbb5ce8cad79415878e76dca6c85d94e1ebf692f4234e'
CERTIFIED_VERSION = 'Producer Edition v26.1.6 [build 5639]'


class GopherNativeWriteBackend(GopherNativeBackend):
    name = 'gopher_native_experimental'

    def __init__(self, *, enabled=False, target_preparer=None, interaction=None,
                 journal=None, disposable_guard=None, accept_policy=AcceptPolicy.MANUAL_ACCEPT,
                 auto_accept_enabled=False, **kwargs):
        super().__init__(**kwargs)
        self.enabled = enabled
        self.target_preparer = target_preparer
        self.interaction = interaction
        self.journal = journal
        self.disposable_guard = disposable_guard
        self.accept_policy = AcceptPolicy(accept_policy)
        self.auto_accept_enabled = auto_accept_enabled
        self.prepared = None
        self.last_execution = None

    async def discover(self):
        if not self.enabled:
            return []
        async with self.lock:
            self.session = await self._run(self.transport.connect)
            raw = await self._run(self.transport.invoke, 'catalog')
            payload = raw['payload']
            payload = json.loads(payload) if isinstance(payload, str) else payload
            tools = payload if isinstance(payload, list) else payload['tools']
            self.catalog_digest = catalog_hash(tools)
            reference = known_catalog()['tools']['run_piano_roll_script']
            tool = next((t for t in tools if t['name'] == 'run_piano_roll_script'), {})
            if (self.catalog_digest != CERTIFIED_CATALOG
                    or tool.get('inputSchema') != reference['input_schema']
                    or tool.get('description') != reference['description']):
                raise BackendError('NATIVE_WRITE_CONTRACT_CHANGED')
            self.capabilities = [Capability(NATIVE_BATCH_ADD, self.name, tool,
                safety=ToolSafetyClassification.TARGETED_WRITE, writable=True, verifiable=False,
                evidence='LIVE_PROVEN_IN_TEST_SCOPE', experimental=True,
                allowed_modes=(ExecutionMode.FAST,), version_constraints={'fl_version': CERTIFIED_VERSION})]
            return copy.deepcopy(self.capabilities)

    async def validate(self, plan, capability):
        if not self.enabled or capability not in self.capabilities:
            raise ValueError('EXPERIMENTAL_BACKEND_DISABLED_OR_STALE')
        if plan.mode != ExecutionMode.FAST or plan.metadata.get('experimental_authorized') is not True:
            raise ValueError('EXPERIMENTAL_FAST_REQUIRED')
        if any(v is None for v in (self.target_preparer, self.interaction, self.journal, self.disposable_guard)):
            raise ValueError('EXPERIMENTAL_BOUNDARY_REQUIRED')
        if self.accept_policy == AcceptPolicy.GUARDED_AUTO_ACCEPT and not self.auto_accept_enabled:
            raise ValueError('AUTO_ACCEPT_DISABLED')
        if self.disposable_guard() is not True:
            raise ValueError('DISPOSABLE_SESSION_REQUIRED')
        notes = plan.parameters.get('notes')
        if isinstance(notes, (list, tuple)) and not 1 <= len(notes) <= 128:
            raise BackendError('CAPABILITY_LIMIT_EXCEEDED')
        validate_plan(plan, getattr(self, 'diagnostics', None))

    def check_target(self, plan, evidence):
        identity, ui = evidence['identity'], evidence['ui']
        mapping = {'expected_pattern_index': 'pattern_number', 'expected_pattern_name': 'pattern_name',
                   'expected_channel_index': 'channel_index', 'expected_channel_name': 'channel_name'}
        if (any(identity.get(v) != plan.target[k] for k, v in mapping.items())
                or identity.get('selected_channels') != [plan.target['expected_channel_index']]
                or identity.get('project_loading') is not False or identity.get('ppq') != 96
                or identity.get('fl_studio_version') != CERTIFIED_VERSION
                or ui.get('visible') is not True or ui.get('channel_name') != plan.target['expected_channel_name']
                or ui.get('pattern_number') != plan.target['expected_pattern_index']
                or ui.get('confirmed') is not True or not ui.get('evidence_ref')
                or not 0 <= time.time() - ui.get('observed_unix', 0) <= 60
                or evidence.get('session') != self.session):
            raise ValueError('TARGET_PREPARATION_FAILED')
        return copy.deepcopy(evidence)

    async def resolve_target(self, plan):
        if self.session is None or self.transport.poisoned_epoch == self.session['session']:
            raise BackendError('SESSION_UNAVAILABLE')
        with diagnostic_span(getattr(self, 'diagnostics', None), 'target_prepare'):
            evidence = await self.target_preparer.prepare(plan.target, copy.deepcopy(self.session))
        self.prepared = self.check_target(plan, evidence)
        return dict(plan.target)

    async def execute(self, plan, capability):
        async with self.lock:
            plan = copy.deepcopy(plan)
            await self.validate(plan, capability)
            diagnostics = getattr(self, 'diagnostics', None)
            rendered = validate_plan(plan, diagnostics)
            with diagnostic_span(diagnostics, 'target_reconfirm'):
                evidence = self.check_target(plan, await self.target_preparer.confirm(
                    plan.target, copy.deepcopy(self.session)))
            local_preview = getattr(self.interaction, 'local_preview', False) is True
            if local_preview:
                try:
                    await self.interaction.prepare_preview(plan, self.session, evidence)
                    refreshed = await self.target_preparer.confirm(plan.target, copy.deepcopy(self.session))
                    self.interaction.reconfirm_preview(refreshed)
                    evidence = self.check_target(plan, refreshed)
                except asyncio.CancelledError:
                    await self.interaction.close()
                    raise
                except Exception as error:
                    await self.interaction.close()
                    raise BackendError(str(error), dispatched=False) from error
            observe(diagnostics, 'source_validation_complete')
            operation_id = plan.metadata['operation_id']
            try:
                self.journal.reserve(operation_id, self.session, rendered.sha256)
            except BaseException:
                if local_preview:
                    await self.interaction.close()
                raise
            record = dict(backend=self.name, capability=NATIVE_BATCH_ADD, operation_id=operation_id,
                source_hash=rendered.sha256, template_hash=rendered.template_hash,
                source_size=rendered.source_size, note_count=rendered.note_count,
                host_generation=self.session['host_generation'], target_evidence=evidence,
                target_status='TARGET_PREPARED', dispatch_status='NOT_DISPATCHED',
                preview_status='NOT_OBSERVED', commit_status='NOT_ACCEPTED',
                application_status='NOT_OBSERVED', completion_status='NOT_DISPATCHED',
                user_message='尚未派发', timings=dict(dispatch_at=None, preview_observed_at=None,
                    accept_at=None, callback_at=None, timeout_at=None, actual_apply_latency=None), states=[])
            self.last_execution = record
            def state(value):
                record['states'].append(dict(state=value.value, observed_at=time.time()))
            state(NativeWriteState.PLANNED)
            state(NativeWriteState.TARGET_PREPARED)
            state(NativeWriteState.SOURCE_VALIDATED)
            record['timings']['dispatch_at'] = time.time()
            start = time.monotonic()
            state(NativeWriteState.DISPATCHED)
            record['dispatch_status'] = 'DISPATCHED'
            record['user_message'] = '等待执行状态确认'
            record['completion_status'] = 'PENDING'
            accept_monotonic = None
            async def dispatch():
                def call():
                    try:
                        if local_preview:
                            try:
                                self.interaction.before_dispatch()
                            except Exception as error:
                                raise BackendError(str(error), dispatched=False) from error
                        observe(diagnostics, 'native_dispatch_begin')
                        response = self.transport.invoke_batch(plan.parameters['notes'], rendered, operation_id)
                        return response, None, time.time(), time.monotonic()
                    except BackendError as error:
                        return None, error, time.time(), time.monotonic()
                    except Exception:
                        return None, BackendError('DISPATCH_UNKNOWN', dispatched=True), time.time(), time.monotonic()
                return await self._run(call)
            task = asyncio.create_task(dispatch())
            ui_error = None
            try:
                if hasattr(self.interaction, 'bind_dispatch_task'):
                    self.interaction.bind_dispatch_task(task)
                preview = await self.interaction.wait_preview(operation_id)
                observe(diagnostics, 'runtime_preview_notification')
                if preview.get('observed') is not True or preview.get('operation_id') != operation_id:
                    raise ValueError('PREVIEW_EVIDENCE_REQUIRED')
                record['preview_status'] = 'LOCAL_PREVIEW_READY' if local_preview else 'PREVIEW_EFFECT_OBSERVED'
                record['timings']['preview_observed_at'] = time.time()
                if local_preview:
                    record['local_preview_observation'] = preview['observation']
                    record['timings']['local_preview_ready_ns'] = time.perf_counter_ns()
                    state(NativeWriteState.LOCAL_PREVIEW_READY)
                    observe(diagnostics, 'runtime_local_preview_ready')
                    state(NativeWriteState.WAITING_FOR_ACCEPT)
                    self.interaction.runtime_ready(record['timings']['local_preview_ready_ns'])
                else:
                    state(NativeWriteState.PREVIEW_OBSERVED)
                record['user_message'] = '预览已就绪'
                if self.accept_policy == AcceptPolicy.GUARDED_AUTO_ACCEPT:
                    if task.done() or self.transport.poisoned_epoch == self.session['session']:
                        raise ValueError('AUTO_ACCEPT_SESSION_NOT_READY')
                    self.check_target(plan, await self.target_preparer.confirm(plan.target, self.session))
                    validate_plan(plan)
                    if task.done() or self.transport.poisoned_epoch == self.session['session']:
                        raise ValueError('AUTO_ACCEPT_SESSION_NOT_READY')
                    await self.interaction.guarded_auto_accept(operation_id, rendered.sha256)
                accepted = await self.interaction.wait_accept(operation_id)
                observe(diagnostics, 'runtime_accept_notification')
                if accepted.get('accepted') is not True or accepted.get('operation_id') != operation_id:
                    raise ValueError('ACCEPT_EVIDENCE_REQUIRED')
                record['commit_status'] = 'ACCEPTED'
                record['timings']['accept_at'] = time.time()
                accept_monotonic = time.monotonic()
                state(NativeWriteState.ACCEPTED)
                application = await self.interaction.wait_application(operation_id)
                if application.get('observed') is not True or application.get('operation_id') != operation_id:
                    raise ValueError('APPLICATION_EVIDENCE_REQUIRED')
                record['application_status'] = 'APPLICATION_OBSERVED'
                record['user_message'] = '已执行'
                state(NativeWriteState.APPLICATION_OBSERVED)
            except asyncio.CancelledError:
                self.transport.poisoned_epoch = self.transport.epoch
                await task
                raise
            except Exception as error:
                ui_error = str(error)
                record['interaction_error'] = ui_error
                state(NativeWriteState.ABORTED)
            finally:
                if local_preview:
                    try:
                        await self.interaction.close()
                    except Exception as cleanup_error:
                        # 停止观察器失败仍须收束已派发任务，不能遗留后台宿主调用。
                        record['interaction_cleanup_error'] = str(cleanup_error)
                        ui_error = ui_error or 'INTERACTION_CLEANUP_FAILED'
                        state(NativeWriteState.ABORTED)
            response, error, finished, finished_monotonic = await task
            observe(diagnostics, 'dispatch_task_joined')
            if error is not None and not error.dispatched:
                record['dispatch_status'] = 'NOT_DISPATCHED'
                record['completion_status'] = 'NOT_DISPATCHED'
                record['timings']['dispatch_at'] = None
                record['user_message'] = '派发已拒绝'
                record['states'] = [s for s in record['states'] if s['state'] != NativeWriteState.DISPATCHED]
                state(NativeWriteState.ABORTED)
                return BackendExecution(ExecutionStatus.NOT_DISPATCHED, value=copy.deepcopy(record),
                    error_code=error.code, script_invocation=ScriptInvocationState())
            record['timings']['whole_interaction_ms'] = (time.monotonic() - start) * 1000
            record['raw_bridge_response'] = response
            if error is None:
                try:
                    payload = response['payload']
                    decoded = json.loads(payload) if isinstance(payload, str) else payload
                    if decoded.get('result', {}).get('isError') is not False:
                        raise ValueError('SCRIPT_COMPLETION_NOT_CONFIRMED')
                except (ValueError, TypeError, KeyError):
                    error = BackendError('SCRIPT_RESULT_UNKNOWN', dispatched=True)
            completed = error is None
            record['completion_status'] = 'COMPLETION_CONFIRMED' if completed else 'COMPLETION_UNKNOWN'
            timing_key = 'callback_at' if completed else 'timeout_at' if error.code == 'EXECUTION_TIMEOUT' else 'result_unknown_at'
            record['timings'][timing_key] = finished
            accept = record['timings']['accept_at']
            record['timeout_status'] = (None if completed or error.code != 'EXECUTION_TIMEOUT' else
                'TIMEOUT_BEFORE_ACCEPT' if accept_monotonic is None or finished_monotonic <= accept_monotonic
                else 'TIMEOUT_AFTER_ACCEPT')
            times = record['timings']
            for key, first, last in (('dispatch_to_preview_ms', 'dispatch_at', 'preview_observed_at'),
                    ('preview_to_accept_ms', 'preview_observed_at', 'accept_at'),
                    ('accept_to_callback_ms', 'accept_at', 'callback_at')):
                times[key] = ((times[last] - times[first]) * 1000
                    if times.get(first) is not None and times.get(last) is not None and times[last] >= times[first] else None)
            state(NativeWriteState.COMPLETION_CONFIRMED if completed else NativeWriteState.COMPLETION_UNKNOWN)
            application_observed = record['application_status'] == 'APPLICATION_OBSERVED'
            return BackendExecution(ExecutionStatus.SUCCESS if completed and not ui_error else ExecutionStatus.UNKNOWN,
                value=copy.deepcopy(record), error_code=error.code if error else ui_error,
                response_status=ResponseStatus.SUCCESS if completed else ResponseStatus.TIMEOUT
                    if error.code == 'EXECUTION_TIMEOUT' else ResponseStatus.RESULT_UNKNOWN,
                script_application_status=ScriptApplicationStatus.SCRIPT_EFFECT_CONFIRMED
                    if application_observed else ScriptApplicationStatus.UNKNOWN,
                script_invocation=ScriptInvocationState(True, application_observed,
                    ScriptCompletionStatus.CONFIRMED if completed else ScriptCompletionStatus.UNKNOWN))

    async def readback(self, plan, capability):
        raise BackendError('VERIFICATION_UNSUPPORTED')
