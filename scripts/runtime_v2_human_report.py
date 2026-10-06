"""提交或检查显式会话的人工报告；不启动宿主、不执行接受动作。"""

import argparse
import json
from pathlib import Path

from dawloop.runtime.human_reports import HumanReportStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('submit', 'inspect', 'finalize'))
    parser.add_argument('--session-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not args.session_dir.is_absolute():
        raise ValueError('EXPLICIT_ABSOLUTE_SESSION_REQUIRED')
    store = HumanReportStore(args.session_dir)
    if args.action == 'submit':
        if args.report is None:
            raise ValueError('HUMAN_REPORT_FILE_REQUIRED')
        value = store.submit(json.loads(args.report.read_text(encoding='utf-8')))
    else:
        if args.report is not None:
            raise ValueError('INSPECT_REPORT_NOT_ALLOWED')
        if args.action == 'finalize':
            store.finalize((args.session_dir/'fast_music_result.json').read_bytes())
        value = store.snapshot()
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
