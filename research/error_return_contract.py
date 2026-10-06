"""只在真实错误正文中识别标量，不扫描请求回显或整个响应包。"""

import json
import re


def assess_error_response(response, expected_count):
    result = dict(classification='C', error_channel_data_propagation='NOT_PROVEN',
                  error_channel_execution_contract='UNRESOLVED', returned_count=None,
                  producer_target_verified=False, freshness_verified=False)
    if type(expected_count) is not int or expected_count < 0:
        raise ValueError('EXPECTED_COUNT_REQUIRED')
    if not isinstance(response, dict) or response.get('ok') is not True:
        return dict(result, reason='NO_RAW_HOST_RESPONSE')
    try:
        payload = response.get('payload')
        raw = json.loads(payload) if isinstance(payload, str) else payload
    except (TypeError, ValueError):
        return dict(result, reason='RAW_FORMAT_UNRESOLVED')
    if (not isinstance(raw, dict) or raw.get('jsonrpc') != '2.0'
            or type(raw.get('id')) not in (str, int) or raw['id'] not in (1, '1')
            or ('result' in raw) == ('error' in raw)):
        return dict(result, reason='RAW_FORMAT_UNRESOLVED')
    if 'error' in raw:
        body = raw['error']
        if (not isinstance(body, dict) or type(body.get('code')) is not int
                or not isinstance(body.get('message'), str)):
            return dict(result, reason='RAW_ERROR_FORMAT_UNRESOLVED')
        texts = [body['message']]
        location = 'error.message'
    else:
        body = raw['result']
        if not isinstance(body, dict) or body.get('isError') is not True:
            return dict(result, reason='NO_RAW_ERROR_BODY')
        content = body.get('content')
        if (not isinstance(content, list) or not content or 'structuredContent' in body
                or any(not isinstance(item, dict) or item.get('type') != 'text'
                       or not isinstance(item.get('text'), str) for item in content)):
            return dict(result, reason='RAW_ERROR_FORMAT_UNRESOLVED')
        texts = [item['text'] for item in content]
        location = 'result.isError.content.text'
    # 仅独立异常行允许sentinel；源码/JSON/日志中的同名字符串不算传播。
    matches = []
    for text in texts:
        for line in text.splitlines():
            match = re.fullmatch(r'\s*(?:Exception:\s*)?DAWLOOP_ERROR_V1\|COUNT=(0|[1-9][0-9]*)\s*', line)
            if match:
                matches.append(int(match.group(1)))
    if len(matches) == 1 and matches[0] == expected_count:
        return dict(result, classification='A', returned_count=matches[0],
                    error_channel_data_propagation='LIVE_CANDIDATE_FOR_SMALL_SCALAR_DIAGNOSTIC',
                    error_channel_execution_contract='ERROR_RESPONSE_OBSERVED',
                    error_body_location=location, reason='ERROR_SENTINEL_COUNT_MATCH')
    if matches or any('DAWLOOP_ERROR_V1' in text for text in texts):
        return dict(result, reason='SENTINEL_AMBIGUOUS_OR_COUNT_DISAGREES')
    return dict(result, classification='B', error_body_location=location,
                error_channel_execution_contract='ERROR_RESPONSE_OBSERVED',
                reason='ERROR_BODY_WITHOUT_SCALAR',
                gopher_piano_roll_structured_readback='BLOCKED_WITH_CURRENT_DISCOVERED_INTERFACES')
