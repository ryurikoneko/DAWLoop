import asyncio
import importlib.util
import unittest

from dawloop.adapters.fl_studio_mcp.adapter import _server_script


@unittest.skipUnless(importlib.util.find_spec("fastmcp"), "需要安装 flstudio extra")
class BundledMCPIntegrationTests(unittest.TestCase):
    def test_bundled_server_lists_note_readback_and_target_tools(self):
        from fastmcp import Client

        async def inspect_server():
            async with Client(str(_server_script()), timeout=10) as client:
                return {tool.name for tool in await client.list_tools()}

        names = asyncio.run(inspect_server())
        self.assertTrue({
            "fl_send_notes",
            "fl_get_piano_roll_state",
            "fl_get_selected_channel",
            "fl_get_piano_roll_info",
        }.issubset(names))


if __name__ == "__main__":
    unittest.main()
