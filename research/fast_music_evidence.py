"""汇总运行后证据；不恢复宿主操作或修改已经终止的结果。"""

import argparse
import hashlib
import json
from pathlib import Path


def collect(session):
    session = Path(session).resolve()
    raw = (session / 'fast_music_result.json').read_bytes()
    result = json.loads(raw)
    operation = result['operation_id']
    preview = result.get('evidence', {}).get('preview', {})
    inputs = {name: (session / name).read_bytes() for name in
        ('user_accept_report.json', 'application_observation.json')}
    human = json.loads(inputs['user_accept_report.json'])
    application = json.loads(inputs['application_observation.json'])
    # 自由文本不能替代结构化接受声明，旧报告需要保留其未绑定状态。
    human_bound = (human.get('operation_id') == operation
        and human.get('source') == 'direct_user_reply'
        and human.get('accept_actor') == 'human'
        and human.get('accepted') is True
        and human.get('preview_review_confirmed') is True
        and bool(preview.get('window'))
        and human.get('window') == preview['window'])
    target = result.get('evidence', {}).get('target', {})
    application_bound = (application.get('operation_id') == operation
        and application.get('preview_closed') is True
        and application.get('observer') == 'agent_visual_review'
        and application.get('observed') is True
        and application.get('phrase_visible') is True
        and application.get('visible_pattern') == target.get('pattern_index')
        and application.get('channel_name') == target.get('expected_channel_name')
        and bool(application.get('evidence_ref')))
    complete = (human_bound and application_bound
        and result.get('dispatch') == 'DISPATCHED'
        and result.get('completion') == 'CONFIRMED')
    report = dict(operation_id=operation,
        original_result_sha256=hashlib.sha256(raw).hexdigest(),
        original_state=result['state'], original_error=result.get('error_code'),
        host_completion=result.get('completion'),
        human_report='BOUND' if human_bound else 'UNBOUND',
        application_report='BOUND' if application_bound else 'UNBOUND',
        evidence_collection='COMPLETE' if complete else 'INCOMPLETE',
        runtime_resumed=False, dispatches_added=0,
        entrypoint_live_certification=False,
        producer_target_binding='NOT_VERIFIED', exact_set='NOT_VERIFIED',
        input_hashes={name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()})
    output = session / 'post_run_evidence.json'
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if output.exists():
        if output.read_bytes() != payload:
            raise ValueError('POST_RUN_EVIDENCE_CONFLICT')
    else:
        with output.open('xb') as stream:
            stream.write(payload)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.session_dir), ensure_ascii=False))


if __name__ == '__main__':
    main()
