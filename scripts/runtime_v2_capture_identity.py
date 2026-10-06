"""固定界面认证专用只读入口，不提供导航或脚本派发。"""

from release_environment import fl_executable

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from runtime_v2_throughput_live import baseline, process_state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('launch', 'identity', 'recovery'))
    parser.add_argument('output', nargs='?')
    parser.add_argument('--settings-dir', type=Path)
    args = parser.parse_args()
    action = args.action
    if action == 'launch':
        if not process_state()['host_closed']:
            raise ValueError('EXISTING_HOST_NOT_DISPOSABLE_CONFIRMED')
        environment = dict(os.environ)
        environment.pop('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', None)
        process = subprocess.Popen([fl_executable(), str(baseline())], env=environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        value = dict(pid=process.pid, launch_mode='NORMAL_NO_DEBUG', launched_unix=time.time())
    elif action == 'identity':
        if args.settings_dir is None:
            raise ValueError('EXPLICIT_CONTROLLER_SETTINGS_REQUIRED')
        raw = asyncio.run(ControllerIdentityBackend('FLSkill MCP IN 2', settings_dir=args.settings_dir).read_identity())
        fields = ('source','controller_build_id','controller_session_id','controller_version','controller_session','project_generation','project_loading','pattern_number',
                  'pattern_name','channel_index','channel_name','selected_channels','channel_index_type',
                  'ppq','fl_studio_version','observed_at')
        value = {key: raw.get(key) for key in fields}
    elif action == 'recovery':
        fixture = baseline()
        import hashlib
        value = dict(**process_state(), baseline_size=fixture.stat().st_size,
                     baseline_hash=hashlib.sha256(fixture.read_bytes()).hexdigest())
    else:
        raise ValueError('READ_ONLY_ACTION_REQUIRED')
    if args.output:
        with Path(args.output).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps(value, ensure_ascii=True))


if __name__ == '__main__':
    main()
