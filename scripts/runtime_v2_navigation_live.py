"""A→B→A冻结事务，外部观察沿用已认证采样器与有界邮箱。"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dawloop.adapters.fl_target_navigation import ControllerTargetNavigator
from dawloop.adapters.fl_target_preparation import ControllerTargetPreparer
from research.observation_handoff import FileMailbox, ObservationExchange
from runtime_v2_throughput_live import baseline
from runtime_v2_channel_selection_live import FIELDS, write

TARGETS = {
    'A': dict(expected_pattern_index=1, expected_pattern_name='样式 1',
              expected_channel_index=0, expected_channel_name='808 Kick'),
    'B': dict(expected_pattern_index=2, expected_pattern_name='样式 2',
              expected_channel_index=1, expected_channel_name='808 Clap'),
}


class RecordedNavigator(ControllerTargetNavigator):
    def __init__(self, *args, output, **kwargs):
        super().__init__(*args, **kwargs)
        self.output, self.calls, self.transactions, self.primitives = output, [], 0, 0

    def _read(self, action='dawloop.getIdentitySnapshot', extra=None):
        record = dict(action=action, started_monotonic=time.monotonic(), clock_domain='navigation_python')
        if action == 'dawloop.navigateTargetOnce':
            self.transactions += 1
            record['params'] = extra
        try:
            value = super()._read(action, extra)
            record['result'] = {k: value[k] for k in (*FIELDS, 'existing_patterns', 'visible_channels',
                'pattern_index', 'primitives', 'navigation_transactions') if k in value}
            return value
        except Exception as error:
            record['error_code'] = str(error) if isinstance(error,(ValueError,RuntimeError,TimeoutError)) else type(error).__name__
            raise
        finally:
            path = self.settings_dir/'Hardware/DAWLoopMCP/mcp_response.json'
            if path.exists():
                raw = path.read_bytes()
                envelope = json.loads(raw.decode('utf-8'))
                record['raw_response_sha256'] = hashlib.sha256(raw).hexdigest()
                record['response_request_id'] = envelope.get('request_id')
                if action == 'dawloop.navigateTargetOnce':
                    nav = envelope.get('selection') or envelope.get('navigation')
                    if isinstance(nav, dict) and nav.get('operation_id') == extra['operation_id']:
                        record['host_navigation'] = nav
                        self.primitives += len(nav.get('primitives', []))
            record['completed_monotonic'] = time.monotonic()
            record['total_ms'] = (record['completed_monotonic']-record['started_monotonic'])*1000
            self.calls.append(record)
            write(self.output/('call_%d.json'%len(self.calls)),record)


async def run(args):
    root = Path(__file__).resolve().parents[1]
    args.output = args.output.resolve()
    if Path(sys.executable).resolve() != (root/'.venv/Scripts/python.exe').resolve():
        raise RuntimeError('PROJECT_INTERPRETER_REQUIRED')
    import mido
    import rtmidi
    fixture = baseline()
    args.output.mkdir(parents=True,exist_ok=False)
    sources = ('src/dawloop/fl_scripts/device_DAWLoopController.py',
        'src/dawloop/adapters/fl_target_navigation.py','src/dawloop/adapters/fl_target_preparation.py',
        'src/dawloop/adapters/fl_controller_identity.py','research/piano_roll_binding_live.mjs',
        'research/capture_interval_observer.mjs','research/navigation_observer_live.mjs',
        'scripts/runtime_v2_navigation_live.py')
    write(args.output/'version.json',dict(source_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in sources},baseline_size=fixture.stat().st_size,
        baseline_hash=hashlib.sha256(fixture.read_bytes()).hexdigest(),
        sequence=['select_pattern','select_channel_global','targeted_open_piano_roll'],targets=TARGETS,
        launch_mode='NORMAL_NO_DEBUG',handoff_seconds=55,state_age_seconds=60))
    navigator = RecordedNavigator('FLSkill MCP IN 2',settings_dir=args.settings_dir,output=args.output)
    summary = dict(result='FAIL_BEFORE_NAVIGATION',note_dispatches=0,script_dispatches=0,
        repair_retries=0,fallback_navigation=0,auto_accept=False,
        producer_target_verified=False,exact_target_binding=False,automation_production_ready=False)
    mailbox = FileMailbox(args.output/'mailbox', ObservationExchange())
    stage = 'PREFLIGHT'
    session = None
    try:
        initial = await navigator.read_identity()
        if initial['controller_build_id'] != args.expected_build:
            raise RuntimeError('CONTROLLER_BUILD_CONTEXT_MISMATCH')
        for target in TARGETS.values():
            if sum(row.get('index')==target['expected_pattern_index'] and row.get('name')==target['expected_pattern_name']
                   and row.get('is_default') in (0,False) for row in initial.get('existing_patterns') or []) != 1:
                raise RuntimeError('A_B_EXISTING_PATTERN_UNCONFIRMED')
            if sum(row.get('global_index')==target['expected_channel_index'] and row.get('name')==target['expected_channel_name']
                   for row in initial.get('visible_channels') or []) != 1:
                raise RuntimeError('A_B_EXISTING_CHANNEL_UNCONFIRMED')
        session = dict(binding_kind='CONTROLLER_ONLY',controller_build_id=initial['controller_build_id'],
            controller_session_id=initial['controller_session_id'],project_generation=initial['project_generation'])
        write(args.output/'session.json',session)
        async def navigate(target,binding):
            ack = await navigator.navigate_once(target,binding,uuid4().hex)
            write(args.output/(stage+'_transaction.json'),ack)
        async def observe(target,binding):
            observation = args.output/stage
            observation.mkdir()
            request = dict(request_id=uuid4().hex,operation_id=uuid4().hex,stage=stage,
                target=target,session=binding,output=str(observation),pid=args.pid,hwnd=args.hwnd)
            start = time.monotonic()
            reply = await mailbox.request(dict(request=request))
            if reply.get('request') != request:
                raise RuntimeError('OBSERVATION_REQUEST_MISMATCH')
            ui = reply.get('ui',{})
            bracket = json.loads((observation/'bracket_result.json').read_text(encoding='utf-8'))
            packet = json.loads((observation/'observation.json').read_text(encoding='utf-8'))
            if (bracket.get('status')!='BRACKET_PASSED_PENDING_VISUAL_REVIEW' or
                    ui.get('image_hash')!=bracket['image_hash'] or ui.get('request_id')!=bracket['request_id'] or
                    ui.get('observer_generation')!=bracket['observer_generation'] or
                    bracket['host_pid']!=args.pid or bracket['window_id']!=args.hwnd):
                raise RuntimeError('IMAGE_REVIEW_BINDING_FAILED')
            result = packet['result']
            if ui.get('observed_unix') != result['capture_completed_at']['wall_unix_ms']/1000:
                raise RuntimeError('CAPTURE_TIMESTAMP_UNBOUND')
            if time.time()-result['capture_started_at']['wall_unix_ms']/1000 > 60:
                raise RuntimeError('TARGET_EVIDENCE_STALE')
            write(observation/'handoff.json',dict(total_ms=(time.monotonic()-start)*1000,
                clock_domain='navigation_python',transport_age_separate=True))
            return ui
        preparer = ControllerTargetPreparer(navigator,navigate,observe,
            window_identity=dict(pid=args.pid,hwnd=args.hwnd))
        preparer.validate_request(TARGETS['A'],session)
        context = preparer.identity(initial,TARGETS['A'])
        if initial.get('ppq') != 96:
            raise RuntimeError('PPQ_MISMATCH')
        stage='A_INITIAL'
        evidence = await preparer.observe(TARGETS['A'],session,context)
        write(args.output/'A_initial_confirmation.json',evidence)
        for stage,target in [('A_TO_B',TARGETS['B']),('B_TO_A',TARGETS['A'])]:
            started = time.monotonic()
            evidence = await preparer.prepare(target,session)
            write(args.output/(stage+'_confirmation.json'),dict(evidence=evidence,
                full_prepare_ms=(time.monotonic()-started)*1000,clock_domain='navigation_python'))
        summary.update(result='PASS',target_preparation='LIVE_PROVEN_OBSERVATIONAL_IN_TEST_SCOPE')
    except Exception as error:
        summary.update(result='FAIL_DURING_OR_AFTER_NAVIGATION' if navigator.transactions else 'FAIL_BEFORE_NAVIGATION',
            error_code=('HANDOFF_DELIVERY_TIMEOUT' if isinstance(error,TimeoutError) else
                (str(error) or type(error).__name__) if isinstance(error,(RuntimeError,ValueError)) else type(error).__name__))
    finally:
        summary.update(stage=stage,navigation_transactions=navigator.transactions,
            navigation_primitives=navigator.primitives,poisoned=navigator.poisoned,session=session,
            recovery_pending=True,native_bridge_attached=False)
        write(args.output/'navigation_result.json',summary)
        print(json.dumps(summary,ensure_ascii=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--settings-dir',type=Path,required=True)
    parser.add_argument('--expected-build',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--hwnd',type=int,required=True)
    asyncio.run(run(parser.parse_args()))
