from __future__ import annotations

import json
import math
import re

from dawloop.runtime import (BackendExecution, DataStatus, ExecutionStatus, ResponseStatus,
                            ScriptApplicationStatus, ScriptCompletionStatus, ScriptInvocationState)


class InvalidResponse(ValueError):
    def __init__(self, status):
        self.status = status


def _fail(status):
    raise InvalidResponse(status)


def _json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail(ResponseStatus.SCHEMA_ERROR)
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: _fail(ResponseStatus.SEMANTIC_ERROR))
    except json.JSONDecodeError:
        _fail(ResponseStatus.DECODE_ERROR)


def _unwrap(value):
    for _ in range(8):
        if isinstance(value, str):
            text = value.strip()
            if not text:
                _fail(ResponseStatus.SCHEMA_ERROR)
            if text[0] in '{["' or text in {'null', 'true', 'false'}:
                value = _json(text)
                continue
            return text
        if not isinstance(value, dict):
            return value
        if any(key in value for key in ('jsonrpc', 'id', 'result', 'error')):
            if value.get('jsonrpc') != '2.0' or type(value.get('id')) not in (int, str) or value['id'] not in (1, '1'):
                _fail(ResponseStatus.SCHEMA_ERROR)
            if ('result' in value) == ('error' in value):
                _fail(ResponseStatus.SCHEMA_ERROR)
            if 'error' in value:
                error = value['error']
                if not isinstance(error, dict) or type(error.get('code')) is not int or not isinstance(error.get('message'), str):
                    _fail(ResponseStatus.SCHEMA_ERROR)
                _fail(ResponseStatus.TOOL_ERROR)
            value = value['result']
            continue
        if 'content' in value or 'isError' in value:
            if 'isError' in value and type(value['isError']) is not bool:
                _fail(ResponseStatus.SCHEMA_ERROR)
            if value.get('isError') is True:
                _fail(ResponseStatus.TOOL_ERROR)
            content = value.get('content')
            if not isinstance(content, list) or not content:
                _fail(ResponseStatus.SCHEMA_ERROR)
            if any(not isinstance(item, dict) or item.get('type') != 'text'
                   or not isinstance(item.get('text'), str) for item in content):
                _fail(ResponseStatus.SCHEMA_ERROR)
            if 'structuredContent' in value:
                # 两套结果不能悄悄择一；未知双表示契约需要单独实现。
                _fail(ResponseStatus.SCHEMA_ERROR)
            value = '\n'.join(item['text'] for item in content)
            continue
        return value
    _fail(ResponseStatus.DECODE_ERROR)


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        _fail(ResponseStatus.SCHEMA_ERROR)
    return value


def _tempo(value):
    if isinstance(value, str):
        match = re.fullmatch(r'(?:Current tempo is )?(-?\d+(?:\.\d+)?)(?: BPM\.)?', value)
        if not match:
            _fail(ResponseStatus.DECODE_ERROR)
        value = float(match[1])
    elif isinstance(value, dict):
        if set(value) != {'tempo_bpm'}:
            _fail(ResponseStatus.SCHEMA_ERROR)
        value = value['tempo_bpm']
    value = _number(value)
    if value <= 0:
        _fail(ResponseStatus.SEMANTIC_ERROR)
    return {'tempo_bpm': value}


def _channels(value):
    if not isinstance(value, str):
        _fail(ResponseStatus.SCHEMA_ERROR)
    lines = value.splitlines()
    if not lines or lines[0] != 'Current Channel Rack Channels (1-based index):':
        _fail(ResponseStatus.DECODE_ERROR)
    channels = []
    for line in lines[1:]:
        match = re.fullmatch(r'(\d+): (.+)', line)
        if not match:
            _fail(ResponseStatus.DECODE_ERROR)
        index = int(match[1])
        if index != len(channels) + 1:
            _fail(ResponseStatus.SEMANTIC_ERROR)
        # 文本名称可能自己含方括号，保留原显示内容，不猜测插件字段。
        channels.append({'visual_index': index, 'display_name': match[2]})
    return {'channels': channels, 'index_basis': 'visual_1_based', 'selected_channel': None}


def _session(value):
    if isinstance(value, str):
        _fail(ResponseStatus.DECODE_ERROR)
    if not isinstance(value, dict) or not {'tempo_bpm', 'active_channels', 'active_mixer_tracks'} <= set(value):
        _fail(ResponseStatus.SCHEMA_ERROR)
    _tempo(value['tempo_bpm'])
    for key, minimum in (('active_channels', 1), ('active_mixer_tracks', 0)):
        items = value[key]
        if not isinstance(items, list):
            _fail(ResponseStatus.SCHEMA_ERROR)
        indices = set()
        for item in items:
            if not isinstance(item, dict) or type(item.get('index')) is not int or not isinstance(item.get('name'), str):
                _fail(ResponseStatus.SCHEMA_ERROR)
            if item['index'] < minimum or item['index'] in indices:
                _fail(ResponseStatus.SEMANTIC_ERROR)
            indices.add(item['index'])
            for field in ('volume_normalized', 'pan'):
                if field in item:
                    number = _number(item[field])
                    if not (0 <= number <= 1 if field == 'volume_normalized' else -1 <= number <= 1):
                        _fail(ResponseStatus.SEMANTIC_ERROR)
    return value


def _plugin_list(value):
    if not isinstance(value, str):
        _fail(ResponseStatus.SCHEMA_ERROR)
    lines = value.splitlines()
    if not lines or not re.fullmatch(r"Parameters for '(.+)':", lines[0]):
        _fail(ResponseStatus.DECODE_ERROR)
    parameters = []
    for line in lines[1:]:
        match = re.fullmatch(r'\s*Index (\d+): (.+)', line)
        if not match:
            _fail(ResponseStatus.DECODE_ERROR)
        if int(match[1]) != len(parameters) + 1:
            _fail(ResponseStatus.SEMANTIC_ERROR)
        parameters.append({'visual_index': int(match[1]), 'name': match[2]})
    return {'plugin_name': re.fullmatch(r"Parameters for '(.+)':", lines[0])[1], 'parameters': parameters}


def _plugin_value(value):
    if not isinstance(value, str):
        _fail(ResponseStatus.SCHEMA_ERROR)
    match = re.fullmatch(r"Value for '(.+)' \(Visual Index (\d+)\): Normalized Value: (-?\d+(?:\.\d+)?), String Value: '(.*)'", value)
    if not match:
        _fail(ResponseStatus.DECODE_ERROR)
    index, number = int(match[2]), float(match[3])
    if index < 1 or not 0 <= number <= 1:
        _fail(ResponseStatus.SEMANTIC_ERROR)
    return {'parameter_name': match[1], 'visual_index': index, 'normalized_value': number, 'display_value': match[4]}


DECODERS = {'get_tempo': _tempo, 'list_channel_names': _channels, 'get_session_context': _session,
            'get_plugin_parameter_list': _plugin_list, 'get_plugin_parameter_value': _plugin_value}


def decode_script_acceptance(response):
    if isinstance(response, dict) and response.get('ok') is False and response.get('code') == 'EXECUTION_TIMEOUT':
        # 超时不能转换为格式错误，更不能否定已经发生的宿主效果。
        return BackendExecution(ExecutionStatus.UNKNOWN, error_code='EXECUTION_TIMEOUT',
                                response_status=ResponseStatus.TIMEOUT,
                                script_application_status=ScriptApplicationStatus.UNKNOWN,
                                script_invocation=ScriptInvocationState(True, False, ScriptCompletionStatus.UNKNOWN)
                                if response.get('dispatched') is True else None)
    try:
        if not isinstance(response, dict) or response.get('ok') is not True or 'payload' not in response:
            _fail(ResponseStatus.SCHEMA_ERROR)
        if _unwrap(response['payload']) != 'Script executed without errors':
            _fail(ResponseStatus.SEMANTIC_ERROR)
        # 无错误确认只证明源码接受，不能由响应文字推导函数调用或音符效果。
        return BackendExecution(ExecutionStatus.SUCCESS, response_status=ResponseStatus.TRANSPORT_SUCCESS,
                                script_application_status=ScriptApplicationStatus.SOURCE_ACCEPTED,
                                script_invocation=ScriptInvocationState(True, False, ScriptCompletionStatus.CONFIRMED))
    except InvalidResponse as error:
        return BackendExecution(ExecutionStatus.FAILED if error.status == ResponseStatus.TOOL_ERROR else ExecutionStatus.UNKNOWN,
                                error_code=error.status.value, response_status=error.status,
                                script_application_status=ScriptApplicationStatus.UNKNOWN)


def decode_response(tool_name, response, arguments=None):
    try:
        if not isinstance(response, dict) or response.get('ok') is not True or 'payload' not in response:
            _fail(ResponseStatus.SCHEMA_ERROR)
        if tool_name not in DECODERS:
            _fail(ResponseStatus.SCHEMA_ERROR)
        value = DECODERS[tool_name](_unwrap(response['payload']))
        if tool_name == 'get_plugin_parameter_value' and arguments:
            identifier = arguments['param_identifier']
            if (identifier.isdecimal() and int(identifier) != value['visual_index']) or (
                    not identifier.isdecimal() and identifier != value['parameter_name']):
                _fail(ResponseStatus.SEMANTIC_ERROR)
        return BackendExecution(ExecutionStatus.SUCCESS, value, data_status=DataStatus.VALID,
                                response_status=ResponseStatus.SUCCESS)
    except InvalidResponse as error:
        tool_error = error.status == ResponseStatus.TOOL_ERROR
        return BackendExecution(ExecutionStatus.FAILED if tool_error else ExecutionStatus.SUCCESS,
                                error_code=error.status.value,
                                data_status=DataStatus.TOOL_ERROR if tool_error else DataStatus.INVALID,
                                response_status=error.status)
