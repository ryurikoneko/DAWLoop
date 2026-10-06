import asyncio
import json
import unittest
from pathlib import Path

from dawloop.adapters.gopher_native.response import decode_response
from dawloop.runtime import DataStatus, ExecutionStatus, ResponseStatus


FIXTURES = Path(__file__).with_name('native_fixtures')


def decode(name, payload):
    return decode_response(name, {'ok': True, 'payload': payload})


class NativeResponseTests(unittest.TestCase):
    def test_live_fixtures_and_invalid_session_are_not_valid_data(self):
        for path in FIXTURES.glob('*.json'):
            with self.subTest(fixture=path.name):
                fixture = json.loads(path.read_text(encoding='utf-8'))
                result = decode(fixture['tool'], fixture['payload'])
                self.assertEqual(result.status, ExecutionStatus.SUCCESS)
                if fixture['tool'] == 'get_session_context':
                    self.assertEqual(result.data_status, DataStatus.INVALID)
                    self.assertEqual(result.response_status, ResponseStatus.DECODE_ERROR)
                    self.assertIsNone(result.value)
                else:
                    self.assertEqual(result.data_status, DataStatus.VALID)
                    self.assertEqual(result.response_status, ResponseStatus.SUCCESS)
        tempo = json.loads((FIXTURES/'get_tempo.json').read_text(encoding='utf-8'))
        self.assertEqual(decode('get_tempo', tempo['payload']).value['tempo_bpm'], 130)

    def test_json_rpc_mcp_and_nested_json_text(self):
        session = {'tempo_bpm': 130, 'active_channels': [], 'active_mixer_tracks': []}
        payload = {'jsonrpc': '2.0', 'id': '1', 'result': {'content': [
            {'type': 'text', 'text': json.dumps(json.dumps(session))}], 'isError': False}}
        self.assertEqual(decode('get_session_context', json.dumps(payload)).value, session)
        self.assertEqual(decode('get_tempo', 'Current tempo is 130.0 BPM.').data_status, DataStatus.VALID)

    def test_empty_unknown_partial_mixed_and_invalid_nested_payloads(self):
        cases = [({'content': []}, ResponseStatus.SCHEMA_ERROR),
                 ({'content': [{'type': 'image', 'data': 'x'}]}, ResponseStatus.SCHEMA_ERROR),
                 ({'content': [{'type': 'text'}]}, ResponseStatus.SCHEMA_ERROR),
                 ('{"jsonrpc":"2.0","id":1,"result":', ResponseStatus.DECODE_ERROR),
                 ('prefix {"tempo_bpm":130}', ResponseStatus.DECODE_ERROR),
                 ('"unterminated', ResponseStatus.DECODE_ERROR),
                 ({'tempo_bpm': 130}, ResponseStatus.SCHEMA_ERROR)]
        for payload, expected in cases:
            with self.subTest(payload=payload):
                result = decode('get_session_context', payload)
                self.assertEqual(result.data_status, DataStatus.INVALID)
                self.assertEqual(result.response_status, expected)
                self.assertIsNone(result.value)

    def test_rpc_and_mcp_errors_are_tool_errors(self):
        for payload in ({'isError': True, 'content': []},
                        {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32603, 'message': '失败'}}):
            result = decode('get_tempo', payload)
            self.assertEqual(result.status, ExecutionStatus.FAILED)
            self.assertEqual(result.data_status, DataStatus.TOOL_ERROR)
            self.assertEqual(result.response_status, ResponseStatus.TOOL_ERROR)

    def test_late_wrong_id_bad_envelopes_and_duplicate_keys(self):
        for payload in ({'jsonrpc': '2.0', 'id': 2, 'result': 130},
                        {'jsonrpc': '1.0', 'id': 1, 'result': 130},
                        {'jsonrpc': '2.0', 'id': True, 'result': 130},
                        {'jsonrpc': '2.0', 'id': 1}, {'result': 130},
                        {'jsonrpc': '2.0', 'id': 1, 'result': 130, 'error': {}},
                        '{"tempo_bpm":130,"tempo_bpm":140}'):
            self.assertEqual(decode('get_tempo', payload).response_status, ResponseStatus.SCHEMA_ERROR)
        self.assertEqual(decode_response('get_tempo', {'ok': True}).response_status, ResponseStatus.SCHEMA_ERROR)

    def test_schema_and_semantic_errors_are_distinct(self):
        self.assertEqual(decode('get_tempo', True).response_status, ResponseStatus.SCHEMA_ERROR)
        self.assertEqual(decode('get_tempo', -1).response_status, ResponseStatus.SEMANTIC_ERROR)
        self.assertEqual(decode('get_tempo', 'NaN').response_status, ResponseStatus.DECODE_ERROR)
        session = {'tempo_bpm': 130, 'active_channels': [{'index': 0, 'name': 'x'}], 'active_mixer_tracks': []}
        self.assertEqual(decode('get_session_context', session).response_status, ResponseStatus.SEMANTIC_ERROR)
        fixture = json.loads((FIXTURES/'get_plugin_parameter_value.json').read_text(encoding='utf-8'))
        result = decode_response('get_plugin_parameter_value', {'ok': True, 'payload': fixture['payload']},
                                 {'param_identifier': '2'})
        self.assertEqual(result.response_status, ResponseStatus.SEMANTIC_ERROR)

    def test_invalid_data_does_not_verify_or_fall_back(self):
        from test_runtime_v2 import FakeBackend, run
        from dawloop.runtime import BackendExecution, ExecutionMode
        backend, fallback = FakeBackend(), FakeBackend('fallback')
        async def invalid(plan, capability):
            backend.calls.append('execute')
            return BackendExecution(ExecutionStatus.SUCCESS, error_code='DECODE_ERROR',
                                    data_status=DataStatus.INVALID, response_status=ResponseStatus.DECODE_ERROR)
        backend.execute = invalid
        result = run(backend, mode=ExecutionMode.VERIFIED, others=(fallback,))
        self.assertEqual(result.data_status, DataStatus.INVALID)
        self.assertEqual(result.response_status, ResponseStatus.DECODE_ERROR)
        self.assertEqual(backend.calls, ['execute'])
        self.assertEqual(fallback.calls, [])
