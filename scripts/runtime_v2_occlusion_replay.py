"""离线回放遮挡证据；不连接宿主，不修改原始证据。"""

import argparse
import hashlib
import json
from pathlib import Path

from dawloop.runtime.preview_viewport import assess_occlusion_survey


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    record = json.loads(raw.decode('utf-8'))
    details = (record.get('invalidation') or {}).get('details') or {}
    assessment = assess_occlusion_survey(details.get('occlusion_evidence') or {}, details.get('hit_test'))
    result = dict(scope='OFFLINE_EVIDENCE_REPLAY', host_calls=0, writes_dispatched=0,
        source_sha256=hashlib.sha256(raw).hexdigest(), assessment=assessment)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(visual_coverage=assessment['visual_coverage'],
        candidates=len(assessment['candidates']), allow_dispatch=False)))


if __name__ == '__main__':
    main()
