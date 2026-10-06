"""现场衔接必须复用后端的实际目录协议。"""

import asyncio
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from runtime_v2_target_prepare_observe_live import discover_catalog
from dawloop.adapters.gopher_native.catalog import catalog_hash


class CatalogProtocolTests(unittest.TestCase):
    def test_actual_payload_protocol_without_write(self):
        tools = [dict(name='get_tempo', inputSchema=dict(type='object', properties={}, required=[]))]
        calls = []

        class Transport:
            def invoke(self, kind):
                calls.append(kind)
                return dict(ok=True, payload=json.dumps(dict(tools=tools)))

        actual = asyncio.run(discover_catalog(Transport(), dict(session='test')))
        self.assertEqual(actual, catalog_hash(tools))
        self.assertEqual(calls, ['catalog'])

    def test_invalid_payload_fails_without_fallback(self):
        calls = []

        class Transport:
            def invoke(self, kind):
                calls.append(kind)
                return dict(ok=True, value=[])

        with self.assertRaises(KeyError):
            asyncio.run(discover_catalog(Transport(), dict(session='test')))
        self.assertEqual(calls, ['catalog'])
