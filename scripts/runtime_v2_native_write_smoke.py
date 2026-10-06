"""单次四音符运行时集成现场入口，界面证据通过本地事件文件提供。"""

from release_environment import fl_executable

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import time

from dawloop.runtime import BackendRouter, NativeWriteJournal, PianoRollBatchAddPlan, PianoRollScriptRenderer
from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from dawloop.adapters.gopher_native.write_backend import GopherNativeWriteBackend
from runtime_v2_throughput_live import baseline, process_state, BASELINE_HASH, BASELINE_SIZE


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/runtime_native_write'
EVENTS = Path(os.environ['TEMP']) / 'DAWLoop_RuntimeV2_3_1_events'
OPERATION_ID = 'runtime-native-add-3-1'


def write(name, value):
    with (OUTPUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fixture_guard():
    baseline()
    return True


class TargetPreparation:
    async def prepare(self, target, session):
        return await self.confirm(target, session)

    async def confirm(self, target, session):
        current = await ControllerIdentityBackend('FLSkill MCP IN 2').read_identity()
        identity = {k: current.get(k) for k in ('controller_session', 'project_generation',
            'project_loading', 'pattern_number', 'pattern_name', 'channel_index', 'channel_name',
            'selected_channels', 'ppq', 'fl_studio_version', 'observed_at')}
        ui = read(EVENTS/'target.json')
        return dict(identity=identity, ui=ui, session=session)


class ManualInteraction:
    async def event(self, name):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            path = EVENTS / (name + '.json')
            if path.exists():
                data = read(path)
                if data.get('operation_id') != OPERATION_ID:
                    raise ValueError('UI_EVENT_OPERATION_MISMATCH')
                return data
            await asyncio.sleep(0.05)
        raise ValueError('UI_OBSERVATION_TIMEOUT')

    async def wait_preview(self, operation_id):
        return await self.event('preview')

    async def wait_accept(self, operation_id):
        return await self.event('accept')

    async def wait_application(self, operation_id):
        return await self.event('application')

    async def guarded_auto_accept(self, *args):
        raise ValueError('AUTO_ACCEPT_DISABLED')


async def execute():
    fixture_guard()
    write('execution_start.json', dict(operation_id=OPERATION_ID, observed_unix=time.time()))
    musical = PianoRollBatchAddPlan(dict(expected_pattern_index=1, expected_pattern_name='样式 1',
        expected_channel_index=0, expected_channel_name='808 Kick'),
        tuple(dict(number=84+i, time=3072+i*48, length=24, velocity=0.5) for i in range(4)), OPERATION_ID)
    plan = musical.operation_plan()
    rendered = PianoRollScriptRenderer().render(plan.parameters['notes'])
    write('operation_plan.json', asdict(plan))
    (OUTPUT/'rendered_source.py').write_bytes(rendered.source)
    (OUTPUT/'source.sha256').write_text(rendered.sha256+'\n', encoding='utf-8')
    write('renderer.json', dict(source_hash=rendered.sha256, template_hash=rendered.template_hash,
        note_count=rendered.note_count, source_size=rendered.source_size))
    backend = GopherNativeWriteBackend(enabled=True, target_preparer=TargetPreparation(),
        interaction=ManualInteraction(), journal=NativeWriteJournal(OUTPUT/'dispatch_intents'),
        disposable_guard=fixture_guard)
    router = BackendRouter([backend])
    try:
        errors = await router.discover()
        if errors:
            raise ValueError('HOST_DISCOVERY_FAILED')
        write('catalog.json', dict(catalog_hash=backend.catalog_digest, raw_tool=backend.capabilities[0].raw_tool))
        result = await router.execute(plan)
        write('operation_result.json', result.to_dict())
        value = result.value or backend.last_execution or {}
        write('target_preparation.json', value.get('target_evidence', backend.prepared))
        write('execution_states.json', value.get('states', []))
        write('timings.json', value.get('timings', {}))
        print(json.dumps(dict(status=result.execution_status, error=result.error_code,
            completion=value.get('completion_status'), timeout=value.get('timeout_status'))))
    finally:
        await backend.close()
        write('bridge_recovery.json', dict(callbacks_restored=backend.transport.callbacks_restored))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('launch', 'run', 'recover'))
    args = parser.parse_args()
    if (OUTPUT/'summary.json').exists():
        raise ValueError('STAGE_CLOSED')
    if args.action == 'launch':
        if OUTPUT.exists() or EVENTS.exists() or not all(process_state().values()):
            raise ValueError('HOST_NOT_CLOSED_OR_TRIAL_EXISTS')
        fixture = baseline()
        OUTPUT.mkdir(parents=True)
        EVENTS.mkdir()
        write('launch_intent.json', dict(baseline_size=BASELINE_SIZE, baseline_sha256=BASELINE_HASH))
        env = dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222')
        process = subprocess.Popen([fl_executable(), str(fixture)], env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS)
        write('session_start.json', dict(pid=process.pid, debug_scope='CHILD_PROCESS_ENVIRONMENT_ONLY'))
        print(json.dumps(dict(pid=process.pid)))
    elif args.action == 'recover':
        state = process_state()
        if not all(state.values()):
            raise ValueError('HOST_OR_PORT_STILL_OPEN')
        baseline()
        write('baseline_integrity.json', dict(**state, baseline_size=BASELINE_SIZE,
            baseline_sha256_before=BASELINE_HASH, baseline_sha256_after=BASELINE_HASH,
            no_save_exit=True, observed_unix=time.time()))
        print(json.dumps(state))
    else:
        asyncio.run(execute())


if __name__ == '__main__':
    main()
