import json
import unittest

from research.scalar_return_contract import assess_scalar_response


class ScalarContractTests(unittest.TestCase):
    def response(self, text, **extra):
        return {'ok': True, 'payload': json.dumps({'jsonrpc': '2.0', 'id': 1,
                'result': {'content': [{'type': 'text', 'text': text}], **extra}})}

    def test_scalar_candidate_does_not_certify_target_or_freshness(self):
        result = assess_scalar_response(self.response('DAWLOOP_RETURN_V1|3'), 3)
        self.assertEqual(result['classification'], 'A')
        self.assertFalse(result['producer_target_verified'])
        self.assertFalse(result['freshness_verified'])

    def test_completion_only_remains_unresolved(self):
        result = assess_scalar_response(self.response('Script executed without errors'), 3)
        self.assertEqual(result['classification'], 'B')
        self.assertEqual(result['direct_return_contract'], 'UNRESOLVED')

    def test_error_log_mismatch_and_dual_results_do_not_pass(self):
        for response in (
            self.response('DAWLOOP_RETURN_V1|3', isError=True),
            self.response('debug: DAWLOOP_RETURN_V1|3'),
            self.response('DAWLOOP_RETURN_V1|4'),
            self.response('DAWLOOP_RETURN_V1|3', structuredContent={'sentinel': 'other'}),
            {'ok': False, 'code': 'EXECUTION_TIMEOUT'},
        ):
            with self.subTest(response=response):
                self.assertEqual(assess_scalar_response(response, 3)['classification'], 'D')
