"""固定Clap一次显示请求，回执不认证可见卷帘目标。"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from uuid import uuid4

from runtime_v2_channel_selection_live import RecordingSelector, write
from runtime_v2_throughput_live import baseline


class RecordingOpener(RecordingSelector):
    expected_initial_index = 1
    expected_initial_name = '808 Clap'
    _allowed_actions = ('dawloop.getIdentitySnapshot', 'dawloop.openPianoRollOnce')
    _action = 'dawloop.openPianoRollOnce'
    _confirmation = 'PIANO_ROLL_OPEN_ACK_WITH_STABLE_IDENTITY'


async def run(args):
    baseline()
    root = Path(__file__).resolve().parents[1]
    if Path(sys.executable).resolve() != (root/'.venv/Scripts/python.exe').resolve():
        raise RuntimeError('PROJECT_INTERPRETER_REQUIRED')
    args.output.mkdir(parents=True,exist_ok=False)
    opener = RecordingOpener('FLSkill MCP IN 2',settings_dir=args.settings_dir,
                             output=args.output,expected_build=args.expected_build)
    result = dict(status='FAIL',operation_id=uuid4().hex,
                  producer_target_verified=False,exact_target_binding=False,
                  note_dispatches=0,script_dispatches=0,pattern_switches=0)
    try:
        value = await opener.select_once(result['operation_id'],1,'808 Clap')
        result.update(status=value['status'],execution=value['execution'])
    except Exception as error:
        result.update(error_type=type(error).__name__,error_code=str(error))
    result['open_request_attempts'] = opener.selection_requests
    write(args.output/'result.json',result)
    print(json.dumps(result,ensure_ascii=True))
    return 0 if result['status']=='PIANO_ROLL_OPEN_ACK_WITH_STABLE_IDENTITY' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--settings-dir',required=True,type=Path)
    parser.add_argument('--expected-build',required=True)
    parser.add_argument('--output',required=True,type=Path)
    sys.exit(asyncio.run(run(parser.parse_args())))
