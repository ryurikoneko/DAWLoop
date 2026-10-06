"""单会话音乐片段入口；人工接受，未提供自动点击。"""

from release_environment import fl_executable

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from dawloop.runtime import BackendRouter, NativeWriteJournal
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from research.practical_music_slice import (HumanSliceInteraction, OPERATION_ID, TARGET,
    evidence_bundle, guard_preparation, operation_plan, validate_slice)
from runtime_v2_throughput_live import baseline, process_state, write


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'evidence/runtime_v2/practical_music_slice/session_1'
EVENTS = Path(os.environ['TEMP'])/'DAWLoop_RuntimeV2_music_slice_session_1'
SESSION_NUMBER = 1


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def frozen():
    paths = [p for folder in ('src/dawloop/runtime','src/dawloop/adapters','research','scripts')
        for p in (ROOT/folder).rglob('*') if p.suffix in ('.py','.js','.mjs','.json','.npz')]
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def guard():
    baseline()
    previous_closed()
    if read(OUTPUT/'version.json') != frozen():
        raise ValueError('MUSIC_SLICE_VERSION_CHANGED')
    if (OUTPUT/'recovery.json').exists():
        raise ValueError('SESSION_CLOSED')
    return True


def previous_closed():
    if SESSION_NUMBER == 1:
        return
    previous = ROOT/'evidence/runtime_v2/practical_music_slice/session_1'
    recovery = read(previous/'recovery.json')
    summary = read(previous/'summary.json')
    path = baseline()
    if (summary.get('status') != 'CLOSED_NOT_ACCEPTED_RECOVERY_VERIFIED'
            or recovery.get('host_closed') is not True
            or recovery.get('debug_port_closed') is not True
            or recovery.get('baseline_size') != path.stat().st_size
            or recovery.get('baseline_sha256') != hashlib.sha256(path.read_bytes()).hexdigest()):
        raise ValueError('PREVIOUS_SESSION_RECOVERY_REQUIRED')


class Preparation:
    async def prepare(self, target, session):
        return await self.confirm(target,session)

    async def confirm(self, target, session):
        identity = await ControllerIdentityBackend('FLSkill MCP IN 2').read_identity()
        receipt = read(EVENTS/'region.json')
        guard_preparation(receipt,session,operation_id=OPERATION_ID)
        return dict(identity=identity,ui=read(EVENTS/'target.json'),session=session)


class LiveHumanInteraction(HumanSliceInteraction):
    def __init__(self, backend, preparation):
        self.backend = backend
        self.preparation = preparation
        self.bound_window = None
        super().__init__(self.read_receipt,self.confirm,operation_id=OPERATION_ID)

    async def confirm(self):
        identity = await ControllerIdentityBackend('FLSkill MCP IN 2').read_identity()
        initial = self.backend.prepared['identity']
        keys = ('controller_session','project_generation','pattern_number','pattern_name',
                'channel_index','channel_name','selected_channels','ppq')
        if (any(identity.get(k)!=initial.get(k) for k in keys)
                or identity.get('project_loading') is not False
                or self.backend.transport.poisoned_epoch == self.backend.session['session']):
            raise ValueError('MUSIC_TARGET_CHANGED')

    def preview_window(self):
        import win32gui
        import win32process
        pid = read(OUTPUT/'launch.json')['pid']
        candidates=[]
        def inspect(hwnd,_):
            if (win32process.GetWindowThreadProcessId(hwnd)[1]==pid
                    and win32gui.IsWindowVisible(hwnd)
                    and win32gui.IsWindowEnabled(hwnd)
                    and win32gui.GetClassName(hwnd)=='TScriptDialog'
                    and win32gui.GetWindowText(hwnd)=='DAWLoop Native Add'):
                candidates.append(dict(hwnd=hwnd,parent=win32gui.GetParent(hwnd),
                    class_name='TScriptDialog',title='DAWLoop Native Add'))
        def top(hwnd,_):
            inspect(hwnd,None)
            if win32process.GetWindowThreadProcessId(hwnd)[1]==pid:
                win32gui.EnumChildWindows(hwnd,inspect,None)
        win32gui.EnumWindows(top,None)
        unique={item['hwnd']:item for item in candidates}
        if len(unique)>1:
            raise ValueError('PREVIEW_WINDOW_AMBIGUOUS')
        return next(iter(unique.values()),None)

    def read_receipt(self,name):
        if name=='preview':
            window=self.preview_window()
            if window is None:
                return None
            self.bound_window=window
            value=dict(operation_id=OPERATION_ID,observer='agent_visual_review',
                evidence_ref='host_preview.json',observed=True,host_preview_present=True,
                content_review='HUMAN_REVIEW_REQUIRED',window=window,
                observed_monotonic=time.monotonic())
            write(OUTPUT/'host_preview.json',value)
            print('宿主预览窗口已出现，请直接审阅并接受一次。',flush=True)
            return value
        path=EVENTS/(name+'.json')
        value=read(path) if path.exists() else None
        if name=='application' and value is not None and self.preview_window() is not None:
            raise ValueError('PREVIEW_STILL_OPEN')
        return value


async def run():
    guard()
    if not (OUTPUT/'launch.json').exists() or (OUTPUT/'run_intent.json').exists():
        raise ValueError('SINGLE_SESSION_REQUIRED')
    write(OUTPUT/'run_intent.json',dict(operation_id=OPERATION_ID,observed_unix=time.time()))
    plan=operation_plan(OPERATION_ID)
    validate_slice(plan,OPERATION_ID)
    prep=Preparation()
    backend=GopherNativeWriteBackend(enabled=True,target_preparer=prep,
        disposable_guard=guard,journal=NativeWriteJournal(OUTPUT/'dispatch_intents'))
    interaction=LiveHumanInteraction(backend,prep)
    backend.interaction=interaction
    router=BackendRouter([backend])
    started=time.monotonic()
    try:
        errors=await router.discover()
        if errors:
            raise ValueError('HOST_DISCOVERY_FAILED')
        if backend.session!=read(OUTPUT/'ready.json')['session']:
            raise ValueError('HOST_GENERATION_CHANGED')
        result=await router.execute(plan)
        write(OUTPUT/'operation_result.json',result.to_dict())
        write(OUTPUT/'human_timing.json',dict(**interaction.timing(),
            overall_workflow_ms=(time.monotonic()-started)*1000,
            scope='LIVE_NATIVE_HUMAN_WORKFLOW',
            backend_timing_interpretation='接受字段是通知时刻，不能作为点击时刻或纯宿主性能'))
        print(json.dumps(dict(status=result.execution_status,error=result.error_code)),flush=True)
    except Exception as error:
        write(OUTPUT/'run_error.json',dict(error=type(error).__name__,message=str(error)))
        raise
    finally:
        await backend.close()
        write(OUTPUT/'bridge_recovery.json',dict(callbacks_restored=backend.transport.callbacks_restored))


async def ready():
    guard()
    backend=GopherNativeWriteBackend(enabled=True)
    try:
        await backend.discover()
        write(OUTPUT/'ready.json',dict(session=backend.session,catalog_hash=backend.catalog_digest,
            identity=await ControllerIdentityBackend('FLSkill MCP IN 2').read_identity(),
            writes_dispatched=0,checked_unix=time.time()))
    finally:
        await backend.close()


def main():
    global OUTPUT, EVENTS, OPERATION_ID, SESSION_NUMBER
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','launch','ready','run','recover'))
    parser.add_argument('--session',type=int,choices=(1,2),default=1)
    args=parser.parse_args()
    action=args.action
    SESSION_NUMBER=args.session
    OPERATION_ID='practical-kick-16-session-%d' % SESSION_NUMBER
    OUTPUT=ROOT/('evidence/runtime_v2/practical_music_slice/session_%d' % SESSION_NUMBER)
    EVENTS=Path(os.environ['TEMP'])/('DAWLoop_RuntimeV2_music_slice_session_%d' % SESSION_NUMBER)
    if action=='prepare':
        previous_closed()
        bundle,rendered=evidence_bundle(OPERATION_ID)
        OUTPUT.mkdir(parents=True,exist_ok=True)
        write(OUTPUT/'plan.json',bundle)
        write(OUTPUT/'operation_plan.json',asdict(operation_plan(OPERATION_ID)))
        with (OUTPUT/'rendered_source.py').open('xb') as stream:
            stream.write(rendered.source)
        write(OUTPUT/'version.json',frozen())
        print(json.dumps(dict(note_count=16,source_hash=rendered.sha256,scope='OFFLINE_PREPARATION')))
    elif action=='launch':
        guard()
        if (OUTPUT/'launch_intent.json').exists() or not all(process_state().values()) or EVENTS.exists():
            raise ValueError('SINGLE_NEW_DISPOSABLE_SESSION_REQUIRED')
        write(OUTPUT/'launch_intent.json',dict(operation_id=OPERATION_ID,max_dispatches=1,
            auto_accept=False,observed_unix=time.time()))
        EVENTS.mkdir()
        env=dict(os.environ,WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222')
        p=subprocess.Popen([fl_executable(),str(baseline())],env=env,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS)
        write(OUTPUT/'launch.json',dict(pid=p.pid,debug_scope='CHILD_PROCESS_ENVIRONMENT_ONLY'))
    elif action=='ready':
        asyncio.run(ready())
    elif action=='run':
        asyncio.run(run())
    else:
        state=process_state()
        if not all(state.values()):
            raise ValueError('HOST_OR_DEBUG_PORT_OPEN')
        path=baseline()
        write(OUTPUT/'recovery.json',dict(**state,baseline_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            baseline_size=path.stat().st_size,no_save_exit_report='REQUIRES_UI_EVIDENCE'))


if __name__=='__main__':
    main()
