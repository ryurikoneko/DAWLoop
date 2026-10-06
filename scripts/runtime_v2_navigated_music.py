"""固定16音符整链；导航沿用冻结实现，接受动作由独立操作者提交回执。"""

from release_environment import fl_executable

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import runtime_v2_music_slice as legacy
from runtime_v2_navigation_live import RecordedNavigator
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from dawloop.adapters.gopher_native.transport import CDPTransport
from dawloop.runtime import FastMusicRuntime, NativeWriteJournal
from dawloop.runtime.human_reports import HumanReportStore, acceptance_receipt
from research.observation_handoff import FileMailbox, ObservationExchange
from research.practical_music_navigation import NavigatedMusicPreparation, CONTROLLER_FIELDS
from research.practical_music_slice import TARGET, evidence_bundle, operation_plan, guard_preparation


OPERATION = 'practical-kick-16-auto-navigation-session-1'
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'evidence/runtime_v2/practical_music_slice/auto_navigation/session_1'
LEDGER_ROOT = OUTPUT


class Interaction(legacy.LiveHumanInteraction):
    accept_observer = 'agent_visual_review'
    accept_window_seconds = None
    event_wait_seconds = 65

    def read_receipt(self, name):
        value = super().read_receipt(name)
        if name == 'accept' and value is not None and (value.get('accept_actor') != 'agent_computer_use'
                or value.get('preview_review_confirmed') is not True
                or value.get('click_completed') is not True
                or value.get('window') != self.bound_window):
            raise ValueError('AGENT_ACCEPT_RECEIPT_REQUIRED')
        return value

    async def confirm(self):
        self.preparation.check_native()
        value = await self.preparation.navigator.read_identity()
        before = self.backend.prepared['identity']
        keys = (*CONTROLLER_FIELDS, 'pattern_number','pattern_name','channel_index',
                'channel_name','selected_channels','ppq')
        if any(value.get(k) != before.get(k) for k in keys) or value.get('project_loading') is not False:
            raise ValueError('MUSIC_TARGET_CHANGED')
        self.preparation.check_native()


class FastHumanInteraction(legacy.LiveHumanInteraction):
    accept_window_seconds = None
    event_wait_seconds = 65
    confirm = Interaction.confirm

    def __init__(self, backend, preparation, *, report_store=None):
        self.report_store = report_store
        super().__init__(backend, preparation)
        self.application_timing = dict(clock_domain='application-python-'+uuid4().hex,
            coordinator_claimed_at=None, application_confirmed_at=None)
        if report_store is not None and report_store.snapshot()['operation_id'] != self.operation_id:
            raise ValueError('HUMAN_REPORT_OPERATION_MISMATCH')

    async def event(self, name, *, pending=False):
        if name != 'accept' or self.report_store is None:
            value = await super().event(name, pending=pending)
            if name == 'application':
                self.application_timing['coordinator_claimed_at'] = self.application_stamp()
            return value
        deadline = self.clock()+self.event_wait_seconds
        self.report_store.begin_accept()
        try:
            while self.clock() < deadline:
                if pending:
                    self.pending()
                record = self.report_store.claim_accept(deadline=deadline, clock=self.clock)
                if record is not None:
                    value = acceptance_receipt(record, self.operation_id)
                    self.events.append(dict(event=name, received_monotonic=self.clock(), receipt=value))
                    return value
                self.completed_response()
                await self.sleep(0.05)
            raise ValueError('HUMAN_EVENT_TIMEOUT')
        finally:
            self.report_store.end_accept()

    def application_stamp(self):
        return dict(clock_domain=self.application_timing['clock_domain'],
            monotonic_ms=self.clock()*1000, wall_unix_ms=time.time()*1000)

    async def wait_application(self, operation_id):
        value = await super().wait_application(operation_id)
        self.application_timing['application_confirmed_at'] = self.application_stamp()
        return value

    def timing(self):
        return dict(**super().timing(), application_delivery=dict(self.application_timing))

    def read_receipt(self, name):
        if name == 'accept' and self.report_store is not None:
            raise ValueError('HUMAN_REPORT_LIFECYCLE_REQUIRED')
        value = super().read_receipt(name)
        if name == 'preview' and value is not None and self.report_store is not None:
            self.report_store.bind_preview(self.bound_window)
        if name == 'accept' and value is not None and (
                value.get('accept_actor') != 'human'
                or value.get('observer') != 'human'
                or value.get('preview_review_confirmed') is not True
                or value.get('window') != self.bound_window):
            raise ValueError('HUMAN_ACCEPT_RECEIPT_REQUIRED')
        return value


def fast_inputs():
    plan = operation_plan(OPERATION)
    return dict(pattern_index=plan.target['expected_pattern_index'],
        pattern_name=plan.target['expected_pattern_name'],
        channel_global_index=plan.target['expected_channel_index'],
        expected_channel_name=plan.target['expected_channel_name']), dict(
        ppq_context=dict(ppq=96, time_unit='ticks', velocity_unit='normalized_0_1'),
        notes=[dict(pitch=n['number'], start=n['time'], length=n['length'], velocity=n['velocity'])
               for n in plan.parameters['notes']])


async def execute_music_workflow(backend, *, on_event=None):
    target, musical_plan = fast_inputs()
    return await FastMusicRuntime(backend).execute_fast_music_plan(target, musical_plan,
        operation_id=OPERATION, experimental_authorized=True, on_event=on_event)


async def run(args):
    legacy.guard()
    if (OUTPUT/'run_intent.json').exists():
        raise ValueError('SINGLE_SESSION_REQUIRED')
    launch = legacy.read(OUTPUT/'launch.json')
    if launch['pid'] != args.pid:
        raise ValueError('HOST_PID_CHANGED')
    report_context = legacy.read(OUTPUT/'human_report_context.json')
    if report_context.get('operation_id') != OPERATION:
        raise ValueError('HUMAN_REPORT_OPERATION_MISMATCH')
    legacy.write(OUTPUT/'run_intent.json',dict(operation_id=OPERATION,max_dispatches=1,auto_accept=False))
    controller_output = OUTPUT/'runtime_controller_calls'
    controller_output.mkdir(exist_ok=False)
    navigator = RecordedNavigator('FLSkill MCP IN 2',settings_dir=args.settings_dir,output=controller_output)
    initial = await navigator.read_identity()
    if (initial.get('controller_build_id') != args.expected_build or initial.get('pattern_number') != 2
            or initial.get('channel_index') != 1 or initial.get('channel_name') != '808 Clap'
            or initial.get('selected_channels') != [1]):
        raise ValueError('EXISTING_CLAP_START_REQUIRED')
    context = {k:initial[k] for k in CONTROLLER_FIELDS}
    mailbox = FileMailbox(OUTPUT/'mailbox',ObservationExchange())
    backend = None
    stage_number = 0

    def native_guard(session):
        transport = backend.transport
        return (backend.session == session and transport.socket is not None
                and transport.epoch == session['bridge_epoch']
                and transport.host_generation == session['host_generation']
                and transport.target_id == session['target_id']
                and transport.poisoned_epoch != session['session'])

    async def observe(target, binding):
        nonlocal stage_number
        stage_number += 1
        if stage_number == 1:
            legacy.write(OUTPUT/'native_session.json',dict(session=backend.session,
                catalog_hash=backend.catalog_digest,controller_context=context))
        stage = 'TARGET_%d' % stage_number
        folder = OUTPUT/stage
        folder.mkdir()
        request = dict(request_id=uuid4().hex,operation_id=OPERATION,stage=stage,target=target,
            session=binding,output=str(folder),pid=args.pid,hwnd=args.hwnd)
        reply = await mailbox.request(dict(request=request))
        if reply.get('request') != request:
            raise ValueError('OBSERVATION_REQUEST_MISMATCH')
        ui = reply.get('ui',{})
        bracket = legacy.read(folder/'bracket_result.json')
        if (bracket.get('status') != 'BRACKET_PASSED_PENDING_VISUAL_REVIEW'
                or any(ui.get(k) != bracket.get(k) for k in ('image_hash','request_id','observer_generation'))):
            raise ValueError('IMAGE_REVIEW_BINDING_FAILED')
        region = legacy.read(folder/'region.json')
        if (region.get('image_hash') != bracket['image_hash']
                or region.get('request_id') != bracket['request_id']
                or region.get('observer_generation') != bracket['observer_generation']):
            raise ValueError('REGION_IMAGE_UNBOUND')
        guard_preparation(region,backend.session,operation_id=OPERATION)
        return ui

    preparation = NavigatedMusicPreparation(navigator,observe,controller_context=context,
        native_guard=native_guard,window_identity=dict(pid=args.pid,hwnd=args.hwnd))
    backend = GopherNativeWriteBackend(enabled=True,target_preparer=preparation,
        disposable_guard=legacy.guard,journal=NativeWriteJournal(LEDGER_ROOT/'dispatch_intents'),
        transport=CDPTransport(timeout=60))
    report_store = HumanReportStore.create(OUTPUT, **report_context)
    interaction = FastHumanInteraction(backend,preparation,report_store=report_store)
    backend.interaction = interaction
    started = time.monotonic()
    try:
        print('TARGET_PREPARATION_REQUESTED; 等待既有目标观察和空区域确认。',flush=True)
        def notify(event):
            legacy.write(OUTPUT/'fast_progress.json',event)
            print(event['state'],flush=True)
        result = await execute_music_workflow(backend,on_event=notify)
        legacy.write(OUTPUT/'fast_music_result.json',result.to_dict())
        report_store.finalize((OUTPUT/'fast_music_result.json').read_bytes())
        legacy.write(OUTPUT/'operation_result.json',result.evidence.get('operation_result',{}))
        legacy.write(OUTPUT/'human_timing.json',dict(**interaction.timing(),
            overall_workflow_ms=(time.monotonic()-started)*1000,
            navigation_transactions=navigator.transactions,navigation_primitives=navigator.primitives,
            performance_scope='HUMAN_WORKFLOW_NOT_PURE_NATIVE_LATENCY'))
        print(json.dumps(dict(status=result.state,error=result.error_code)),flush=True)
    finally:
        try:
            report_store.end_accept()
        finally:
            legacy.write(OUTPUT/'bridge_recovery.json',dict(callbacks_restored=backend.transport.callbacks_restored))


def main():
    global OUTPUT, LEDGER_ROOT, OPERATION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','launch','run','recover'))
    parser.add_argument('--restart-after-reboot',action='store_true')
    parser.add_argument('--attempt',type=int,choices=(1,2),default=1)
    parser.add_argument('--session',type=int,choices=(1,2,3,4,5,6,7),default=1)
    parser.add_argument('--settings-dir',type=Path,required=True)
    parser.add_argument('--expected-build',required=True)
    parser.add_argument('--pid',type=int)
    parser.add_argument('--hwnd',type=int)
    args = parser.parse_args()
    if not args.settings_dir.is_absolute() or Path(sys.executable).resolve() != (ROOT/'.venv/Scripts/python.exe').resolve():
        raise ValueError('EXPLICIT_SETTINGS_AND_PROJECT_INTERPRETER_REQUIRED')
    if args.session in (2,3,4,5,6,7):
        if args.restart_after_reboot or args.attempt != 1:
            raise ValueError('NEW_SESSION_NOT_RESTART_REQUIRED')
        previous_path = ('session_1/restart_2' if args.session == 2 else 'session_%d' % (args.session-1))
        previous = legacy.read(ROOT/'evidence/runtime_v2/practical_music_slice/auto_navigation'/previous_path/'recovery.json')
        if previous.get('host_closed') is not True or previous.get('debug_port_closed') is not True:
            raise ValueError('PREVIOUS_RECOVERY_REQUIRED')
        OPERATION = 'practical-kick-16-auto-navigation-session-%d' % args.session
        OUTPUT = ROOT/('evidence/runtime_v2/practical_music_slice/auto_navigation/session_%d' % args.session)
        LEDGER_ROOT = OUTPUT
    if args.restart_after_reboot:
        if args.action != 'recover' and ((LEDGER_ROOT/'run_intent.json').exists()
                or any((LEDGER_ROOT/'dispatch_intents').glob('*'))):
            raise ValueError('OLD_DISPATCH_MAY_HAVE_OCCURRED')
        if args.attempt == 2:
            previous = legacy.read(LEDGER_ROOT/'restart_1/recovery.json')
            if previous.get('host_closed') is not True or previous.get('debug_port_closed') is not True:
                raise ValueError('PREVIOUS_RECOVERY_REQUIRED')
        OUTPUT = LEDGER_ROOT/('restart_%d' % args.attempt)
    elif args.attempt != 1:
        raise ValueError('EXPLICIT_RESTART_SCOPE_REQUIRED')
    legacy.OUTPUT = OUTPUT
    legacy.EVENTS = Path(legacy.os.environ['TEMP'])/(('DAWLoop_RuntimeV2_navigated_music_restart_%d' % args.attempt)
        if args.restart_after_reboot else ('DAWLoop_RuntimeV2_navigated_music_session_%d' % args.session))
    legacy.OPERATION_ID = OPERATION
    legacy.SESSION_NUMBER = 1
    if args.action == 'prepare':
        legacy.baseline()
        OUTPUT.mkdir(parents=True,exist_ok=False)
        legacy.write(OUTPUT/'human_report_context.json',dict(run_id=uuid4().hex,
            session_id=uuid4().hex,operation_id=OPERATION))
        bundle,rendered = evidence_bundle(OPERATION)
        legacy.write(OUTPUT/'plan.json',bundle)
        legacy.write(OUTPUT/'operation_plan.json',asdict(operation_plan(OPERATION)))
        (OUTPUT/'rendered_source.py').write_bytes(rendered.source)
        legacy.write(OUTPUT/'version.json',legacy.frozen())
        print(json.dumps(dict(notes=16,source_hash=rendered.sha256,live_dispatched=False)))
    elif args.action == 'launch':
        legacy.guard()
        if (OUTPUT/'launch_intent.json').exists() or not all(legacy.process_state().values()) or legacy.EVENTS.exists():
            raise ValueError('SINGLE_NEW_DISPOSABLE_SESSION_REQUIRED')
        legacy.write(OUTPUT/'launch_intent.json',dict(operation_id=OPERATION,max_dispatches=1,
            accept_actor='human',accept_window_seconds=None,callback_timeout_seconds=60,
            auto_accept_framework=False,observed_unix=time.time()))
        legacy.EVENTS.mkdir()
        env=dict(legacy.os.environ,WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222')
        p=legacy.subprocess.Popen([fl_executable(),str(legacy.baseline())],env=env,
            stdin=legacy.subprocess.DEVNULL,stdout=legacy.subprocess.DEVNULL,stderr=legacy.subprocess.DEVNULL,
            creationflags=legacy.subprocess.DETACHED_PROCESS)
        legacy.write(OUTPUT/'launch.json',dict(pid=p.pid,debug_scope='CHILD_PROCESS_ENVIRONMENT_ONLY'))
        print(json.dumps(dict(pid=p.pid)))
    elif args.action == 'recover':
        state=legacy.process_state()
        if not all(state.values()):
            raise ValueError('HOST_OR_DEBUG_PORT_OPEN')
        fixture=legacy.baseline()
        import hashlib
        legacy.write(OUTPUT/'recovery.json',dict(**state,baseline_size=fixture.stat().st_size,
            baseline_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest()))
        print(json.dumps(state))
    else:
        if not args.pid or not args.hwnd:
            raise ValueError('HOST_WINDOW_REQUIRED')
        asyncio.run(run(args))


if __name__ == '__main__':
    main()
