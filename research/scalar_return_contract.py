"""只判定正常原始结果中的标量；不把日志、完成文字或缓存当作读取结果。"""

import json
import re


def assess_scalar_response(response, expected_count):
    result = dict(classification='D', scalar_return_propagation='NOT_PROVEN',
                  direct_return_contract='UNRESOLVED', returned_count=None,
                  producer_target_verified=False, freshness_verified=False)
    if type(expected_count) is not int or expected_count < 0:
        raise ValueError('EXPECTED_COUNT_REQUIRED')
    if not isinstance(response, dict) or response.get('ok') is not True:
        return dict(result, reason='EXECUTION_OR_RESPONSE_UNRESOLVED')
    raw = response.get('payload')
    try:
        envelope = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return dict(result, reason='RAW_RESPONSE_FORMAT_UNRESOLVED')
    if not isinstance(envelope, dict) or envelope.get('jsonrpc') != '2.0':
        return dict(result, reason='RAW_RESPONSE_FORMAT_UNRESOLVED')
    if envelope.get('id') not in (1, '1') or ('result' in envelope) == ('error' in envelope):
        return dict(result, reason='RAW_RESPONSE_FORMAT_UNRESOLVED')
    body = envelope.get('result')
    if not isinstance(body, dict) or body.get('isError') is True:
        return dict(result, reason='TOOL_ERROR_OR_UNKNOWN_RESULT')
    content = body.get('content')
    if not isinstance(content, list) or any(not isinstance(item, dict)
            or item.get('type') != 'text' or not isinstance(item.get('text'), str)
            for item in content):
        return dict(result, reason='UNSUPPORTED_NORMAL_RETURN_FORMAT')
    texts = [item['text'] for item in content]
    # 不扫描整包寻找sentinel；错误、metadata或日志里的同名文字不证明return传播。
    scalars = [text for text in texts if re.fullmatch(r'DAWLOOP_RETURN_V1\|(?:0|[1-9][0-9]*)', text)]
    if len(texts) == 1 and len(scalars) == 1 and 'structuredContent' not in body:
        count = int(scalars[0].split('|')[1])
        if count == expected_count:
            return dict(result, classification='A', scalar_return_propagation='LIVE_CANDIDATE',
                        returned_count=count, reason='NORMAL_RETURN_SENTINEL_AND_COUNT_MATCH')
        return dict(result, returned_count=count, reason='RETURNED_COUNT_DISAGREES')
    if texts == ['Script executed without errors'] and 'structuredContent' not in body:
        return dict(result, classification='B', reason='COMPLETION_ONLY_NO_SCALAR_RETURN')
    return dict(result, reason='UNSUPPORTED_OR_AMBIGUOUS_NORMAL_RETURN')
