import unittest

from dawloop.adapters.gopher_native import capabilities_from_catalog, normalize_catalog


class GopherNativeCatalogTests(unittest.TestCase):
    def test_normalizes_tool_catalog(self):
        payload = {
            "tools": [
                {"name": "get_tempo", "description": "Read tempo", "inputSchema": {"type": "object"}},
                {"name": "set_tempo", "description": "Write tempo", "inputSchema": {"type": "object"}},
            ]
        }
        tools = normalize_catalog(payload)
        self.assertEqual([tool.name for tool in tools], ["get_tempo", "set_tempo"])

    def test_classifies_destructive_tool_conservatively(self):
        capabilities = capabilities_from_catalog([
            {"name": "remove_channels", "description": "DESTRUCTIVE channel removal"},
            {"name": "get_session_context", "description": "session"},
        ])
        by_name = {item.name: item for item in capabilities}
        self.assertTrue(by_name["remove_channels"].writable)
        self.assertTrue(by_name["remove_channels"].destructive)
        self.assertTrue(by_name["get_session_context"].readable)


if __name__ == "__main__":
    unittest.main()
