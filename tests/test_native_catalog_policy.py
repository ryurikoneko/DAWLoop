import asyncio
import copy
import unittest

from dawloop.adapters.gopher_native.catalog import known_catalog, normalize_catalog
from dawloop.adapters.gopher_native.backend import GopherNativeBackend
from dawloop.runtime import BackendRouter, ExecutionStatus, OperationPlan


def tools():
    return [{'name': name, 'description': item['description'], 'inputSchema': copy.deepcopy(item['input_schema'])}
            for name, item in known_catalog()['tools'].items()]


class NativeCatalogPolicyTests(unittest.TestCase):
    def test_full_catalog_classification_and_dispatch_are_separate(self):
        capabilities = normalize_catalog(tools())
        counts = {risk: sum(c.safety.value == risk for c in capabilities)
                  for risk in ['READ_ONLY', 'LOW_RISK_WRITE', 'TARGETED_WRITE', 'DESTRUCTIVE', 'UNKNOWN']}
        self.assertEqual(counts, {'READ_ONLY': 11, 'LOW_RISK_WRITE': 6, 'TARGETED_WRITE': 24, 'DESTRUCTIVE': 7, 'UNKNOWN': 0})
        self.assertEqual(sum(c.dispatch_supported for c in capabilities), 5)
        self.assertTrue(all(c.classification_reason and c.confidence for c in capabilities))
        self.assertTrue(all(not c.verifiable for c in capabilities))

    def test_description_schema_changes_and_unknown_prefix_are_not_trusted(self):
        catalog = tools()
        tempo = next(t for t in catalog if t['name'] == 'get_tempo')
        for changed in ({**tempo, 'description': 'Reads and changes the tempo'},
                        {**tempo, 'inputSchema': {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}},
                        {**tempo, 'name': 'get_future_state'}):
            self.assertEqual(normalize_catalog([changed])[0].safety.value, 'UNKNOWN')
            self.assertFalse(normalize_catalog([changed])[0].dispatch_supported)

    def test_analysis_only_capability_cannot_dispatch(self):
        from test_gopher_native import FakeTransport
        async def check():
            transport = FakeTransport()
            transport.tools = tools()
            backend = GopherNativeBackend(transport=transport)
            router = BackendRouter([backend])
            await router.discover()
            for operation in ('browser.names.read', 'transport.tempo.write', 'piano_roll.script.execute'):
                result = await router.execute(OperationPlan(operation, {'session': 'doc-1'}))
                self.assertEqual(result.execution_status, ExecutionStatus.NOT_DISPATCHED)
                self.assertEqual(result.error_code, 'DISPATCH_UNSUPPORTED')
            self.assertFalse(any(call[0]=='call' for call in transport.calls))
        asyncio.run(check())
