import json
import unittest
from research.error_return_contract import assess_error_response


class ErrorReturnTests(unittest.TestCase):
    def response(self, body):
        return dict(ok=True, payload=json.dumps(dict(jsonrpc='2.0', id=1, **body)))

    def test_error_message_and_tool_error(self):
        for body in (dict(error=dict(code=-32000, message='Exception: DAWLOOP_ERROR_V1|COUNT=3')),
                     dict(result=dict(isError=True, content=[dict(type='text', text='DAWLOOP_ERROR_V1|COUNT=3')]))):
            result = assess_error_response(self.response(body), 3)
            self.assertEqual(result['classification'], 'A')
            self.assertFalse(result['producer_target_verified'])
            self.assertFalse(result['freshness_verified'])

    def test_generic_error(self):
        self.assertEqual(assess_error_response(self.response(dict(error=dict(code=-32000, message='script failed'))), 3)['classification'], 'B')

    def test_unresolved_not_promoted(self):
        bodies = [dict(result=dict(content=[dict(type='text', text='DAWLOOP_ERROR_V1|COUNT=3')])),
                  dict(error=dict(code=-32000, message='DAWLOOP_ERROR_V1|COUNT=4')),
                  dict(error=dict(code=-32000, message='echo source: "DAWLOOP_ERROR_V1|COUNT=3"')),
                  dict(error=dict(code=-32000, message='DAWLOOP_ERROR_V1|COUNT=3\nDAWLOOP_ERROR_V1|COUNT=3'))]
        for body in bodies:
            self.assertEqual(assess_error_response(self.response(body), 3)['classification'], 'C')
        self.assertEqual(assess_error_response(dict(ok=False, code='EXECUTION_TIMEOUT'), 3)['classification'], 'C')


if __name__ == '__main__':
    unittest.main()
