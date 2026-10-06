"""单次通道选择验收；仅复用受限入口，不提供导航修复。"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

from dawloop.adapters.fl_channel_selection import ControllerChannelSelector
from dawloop.controller_runtime import installed_controller_identity
from dawloop.setup import configured_scripts
from runtime_v2_throughput_live import baseline


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


FIELDS = ('source', 'controller_build_id', 'controller_session_id', 'controller_session',
          'controller_version', 'project_generation', 'project_loading', 'pattern_number',
          'pattern_name', 'channel_index', 'channel_name', 'channel_index_type',
          'selected_channels', 'ppq', 'fl_studio_version', 'observed_at',
          'status', 'operation_id', 'request_id', 'global_index')


class RecordingSelector(ControllerChannelSelector):
    expected_initial_index = 0
    expected_initial_name = '808 Kick'
    def __init__(self, *args, output, expected_build, **kwargs):
        super().__init__(*args, **kwargs)
        self.output = output
        self.expected_build = expected_build
        self.calls = []
        self.selection_requests = 0

    def _read(self, action='dawloop.getIdentitySnapshot', extra=None):
        started = time.monotonic()
        if action in ('dawloop.selectOneChannelOnce', 'dawloop.openPianoRollOnce'):
            self.selection_requests += 1
            if self.selection_requests != 1:
                raise RuntimeError('LIVE_SELECTION_BUDGET_EXHAUSTED')
        record = dict(action=action, started_monotonic=started,
                      clock_domain='selection_harness_monotonic')
        if extra is not None:
            record['parameters'] = extra
        try:
            value = super()._read(action, extra)
            record['result'] = {key: value.get(key) for key in FIELDS if key in value}
            response = self.settings_dir / 'Hardware' / 'DAWLoopMCP' / 'mcp_response.json'
            raw = response.read_bytes()
            envelope = json.loads(raw.decode('utf-8'))
            record['response_sha256'] = hashlib.sha256(raw).hexdigest()
            record['response_request_id'] = envelope.get('request_id')
            record['response_success'] = envelope.get('success')
            if action == 'dawloop.getIdentitySnapshot' and not self.calls:
                if (value.get('controller_build_id') != self.expected_build or
                        value.get('pattern_number') != 1 or value.get('channel_index') != self.expected_initial_index or
                        value.get('channel_name') != self.expected_initial_name or
                        value.get('selected_channels') != [self.expected_initial_index] or
                        value.get('ppq') != 96):
                    raise RuntimeError('INITIAL_A_OR_BUILD_UNCONFIRMED')
            return value
        except BaseException as error:
            record['error_type'] = type(error).__name__
            record['error_code'] = str(error) if isinstance(error, (ValueError, RuntimeError, TimeoutError)) else type(error).__name__
            raise
        finally:
            record['completed_monotonic'] = time.monotonic()
            record['total_ms'] = (record['completed_monotonic'] - started) * 1000
            self.calls.append(record)
            write(self.output / ('call_%d.json' % len(self.calls)), record)


async def run(args):
    fixture = baseline()
    root = Path(__file__).resolve().parents[1]
    if Path(sys.executable).resolve() != (root / '.venv/Scripts/python.exe').resolve():
        raise RuntimeError('PROJECT_INTERPRETER_REQUIRED')
    import mido
    import rtmidi
    args.output.mkdir(parents=True, exist_ok=False)
    sources = ('scripts/runtime_v2_channel_selection_live.py',
               'src/dawloop/adapters/fl_channel_selection.py',
               'src/dawloop/adapters/fl_controller_identity.py',
               'src/dawloop/fl_scripts/device_DAWLoopController.py')
    write(args.output / 'version.json', dict(
        source_sha256={name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources},
        baseline_size=fixture.stat().st_size,
        baseline_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
        project_interpreter=True, explicit_controller_config=True,
        launch_mode='NORMAL_NO_DEBUG',
        frozen_sequence=['identity_A', 'select_global_1_once', 'independent_identity_B']))
    expected, _ = installed_controller_identity(configured_scripts(args.settings_dir)['controller'])
    if expected != args.expected_build:
        raise RuntimeError('EXPECTED_INSTALLED_BUILD_MISMATCH')
    selector = RecordingSelector('FLSkill MCP IN 2', settings_dir=args.settings_dir,
                                 output=args.output, expected_build=expected)
    summary = dict(scope='LIVE_CONTROLLER_SINGLE_CHANNEL_SELECTION', result='FAIL',
                   operation_id=uuid4().hex, expected_build=expected,
                   target_global_index=1, target_channel_name='808 Clap',
                   pattern_switches=0, piano_roll_open_actions=0, note_dispatches=0,
                   script_dispatches=0, repair_retries=0, fallback_navigation=0,
                   auto_accept=False, producer_target_verified=False, exact_target_binding=False)
    started = time.monotonic()
    try:
        value = await selector.select_once(summary['operation_id'], 1, '808 Clap')
        summary.update(result='PASS', confirmation=value['status'],
                       controller_build_id=value['identity_after']['controller_build_id'],
                       controller_session_id=value['identity_after']['controller_session_id'],
                       project_generation=value['identity_after']['project_generation'])
    except Exception as error:
        summary.update(error_type=type(error).__name__,
                       error_code=str(error) if isinstance(error, (ValueError, RuntimeError, TimeoutError)) else type(error).__name__)
    finally:
        summary.update(total_ms=(time.monotonic() - started)*1000,
                       selection_request_attempts=selector.selection_requests,
                       identity_calls=sum(c['action']=='dawloop.getIdentitySnapshot' for c in selector.calls),
                       poisoned=selector.poisoned)
        write(args.output / 'selection_result.json', summary)
        print(json.dumps(summary, ensure_ascii=True))
    return 0 if summary['result']=='PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings-dir', required=True, type=Path)
    parser.add_argument('--expected-build', required=True)
    parser.add_argument('--output', required=True, type=Path)
    sys.exit(asyncio.run(run(parser.parse_args())))
