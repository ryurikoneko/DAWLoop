"""从旧现场证据生成独立耗时报告，禁止覆盖输出。"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
from preview_timing_report import build_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    names = ('result.json', 'local_observation.json', 'full_screen_observation.json', 'trace.json')
    raw = {name: (args.source/name).read_bytes() for name in names}
    report = build_report(*(json.loads(raw[name].decode('utf-8')) for name in names))
    report['source_hashes'] = {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps(report['metrics'], ensure_ascii=False))


if __name__ == '__main__':
    main()
