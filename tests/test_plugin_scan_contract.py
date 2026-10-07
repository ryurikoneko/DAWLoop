# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""直接运行 bundled handler，严格模拟官方位置参数，无实际宿主。"""

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dawloop.mix_plan import decode_plugin_scan


ROOT = Path(__file__).resolve().parents[1]


class SyntheticPlugins:
    def __init__(self, count=80):
        self.count = count
        self.count_reads = 0
        self.calls = []
        self.fail_index = None
        self.no_display = False
        self.change_count = False
        self.change_names = False
        self.values = {}

    def isValid(self, index, slotIndex=-1, useGlobalIndex=False):
        return 1

    def getPluginName(self, index, slotIndex=-1, userName=0, useGlobalIndex=False):
        self.calls.append(("name", index, slotIndex, userName, useGlobalIndex))
        return "User label" if userName else "Synthetic EQ"

    def getParamCount(self, index, slotIndex=-1, useGlobalIndex=False):
        self.count_reads += 1
        return self.count + int(self.change_count and self.count_reads > 1)

    def getParamName(self, paramIndex, index, slotIndex=-1, useGlobalIndex=False):
        if self.fail_index == paramIndex:
            raise RuntimeError("synthetic read failure")
        return f"P{paramIndex}" + (" changed" if self.change_names and self.count_reads > 1 else "")

    def getParamValue(self, paramIndex, index, slotIndex=-1, useGlobalIndex=False):
        return self.values.get(paramIndex, 0.5)

    def getParamValueString(self, paramIndex, index, slotIndex=-1, useGlobalIndex=False):
        if self.no_display:
            raise NotImplementedError("synthetic display unavailable")
        return "50%"

    def setParamValue(self, value, paramIndex, index, slotIndex=-1, pickupMode=0, useGlobalIndex=False):
        self.calls.append(("set", value, paramIndex, index, slotIndex, pickupMode, useGlobalIndex))
        self.values[paramIndex] = value

    def getColor(self, index, slotIndex=-1, flag=0, paramIndex=0, useGlobalIndex=False):
        self.calls.append(("color", index, slotIndex, flag, paramIndex, useGlobalIndex))
        return 255


def controller(plugins, version=40):
    name = "dawloop_synthetic_plugin_controller"
    spec = importlib.util.spec_from_file_location(name,
        ROOT / "third_party/fl-studio-mcp/fl_controller/device_FLStudioMCP.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {key: SimpleNamespace() for key in ("channels", "mixer", "transport")}
    stubs.update(plugins=plugins, general=SimpleNamespace(getVersion=lambda: version))
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


class PluginHandlerTests(unittest.TestCase):
    def test_complete_scan_and_original_name_separate_from_label(self):
        plugins = SyntheticPlugins()
        result = controller(plugins).handle_plugins_get_params({"index": 1, "slot_index": 0})
        fp, values = decode_plugin_scan(result)
        self.assertEqual(len(values), 80)
        self.assertEqual(fp.plugin_name, "Synthetic EQ")
        self.assertEqual(result["plugin_user_name"], "User label")
        self.assertIn(("name", 1, 0, 0, True), plugins.calls)
        self.assertFalse(any(c[0] == "set" for c in plugins.calls))

    def test_explicit_cap_and_hard_cap_are_never_complete(self):
        for count, cap in ((80, 50), (5000, None)):
            with self.subTest(count=count):
                result = controller(SyntheticPlugins(count)).handle_plugins_get_params(
                    {"index": 1, "max_params": cap})
                self.assertTrue(result["truncated"])
                self.assertFalse(result["complete"])
                self.assertEqual(result["parameter_count"], count)
                with self.assertRaises(ValueError):
                    decode_plugin_scan(result)

    def test_read_failure_is_retained_and_scan_cannot_bind(self):
        plugins = SyntheticPlugins()
        plugins.fail_index = 7
        result = controller(plugins).handle_plugins_get_params({"index": 1})
        self.assertEqual(result["errors"][0]["index"], 7)
        self.assertEqual(len(result["params"]), 79)
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            decode_plugin_scan(result)

    def test_optional_display_unavailable_keeps_normalized_values(self):
        plugins = SyntheticPlugins(3)
        plugins.no_display = True
        module = controller(plugins)
        result = module.handle_plugins_get_params({"index": 1})
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["warnings"]), 3)
        self.assertEqual(decode_plugin_scan(result)[1], (0.5,) * 3)
        single = module.handle_plugins_get_param_value({"plugin_index": 1, "param_index": 0})
        self.assertIsNone(single["value_string"])
        self.assertEqual(single["value"], 0.5)

    def test_count_or_name_layout_changed_is_incomplete(self):
        for field in ("change_count", "change_names"):
            plugins = SyntheticPlugins(3)
            setattr(plugins, field, True)
            result = controller(plugins).handle_plugins_get_params({"index": 1})
            self.assertFalse(result["complete"])
            self.assertTrue(result["errors"])

    def test_unsupported_api_or_invalid_arguments_stop_before_scanning(self):
        for version in (25, True, None):
            with self.assertRaisesRegex(ValueError, "API_VERSION"):
                controller(SyntheticPlugins(), version).handle_plugins_get_params({"index": 1})
        for values in ({"index": True}, {"index": -1}, {"index": 1, "slot_index": -2},
                       {"index": 1, "use_global": 1}, {"index": 1, "max_params": True}):
            with self.assertRaises(ValueError):
                controller(SyntheticPlugins()).handle_plugins_get_params(values)

    def test_setter_uses_explicit_pickup_and_global_argument_once(self):
        for slot, global_index in ((-1, True), (-1, False), (2, True)):
            plugins = SyntheticPlugins(3)
            module = controller(plugins)
            module.handle_plugins_set_param_value({"plugin_index": 4, "slot_index": slot,
                "use_global": global_index, "param_index": 1, "value": 0.25})
            self.assertEqual([c for c in plugins.calls if c[0] == "set"],
                             [("set", 0.25, 1, 4, slot, 0, global_index)])
            self.assertEqual(module.handle_plugins_get_name({"index": 4, "slot_index": slot,
                             "use_global": global_index}), {"name": "Synthetic EQ"})
            self.assertIn(("name", 4, slot, 0, global_index), plugins.calls)
            self.assertEqual(module.handle_plugins_get_color({"index": 4, "slot_index": slot,
                "use_global": global_index}), {"color": "0xff"})
            self.assertIn(("color", 4, slot, 0, 0, global_index), plugins.calls)

    def test_invalid_write_and_old_api_do_not_reach_mock_setter(self):
        for values in ({"value": 2}, {"value": True}, {"value": float("nan")},
                       {"param_index": True}, {"param_index": 3}):
            plugins = SyntheticPlugins(3)
            request = {"plugin_index": 1, "param_index": 0, "value": 0.5, **values}
            with self.assertRaises(ValueError):
                controller(plugins).handle_plugins_set_param_value(request)
            self.assertFalse(any(c[0] == "set" for c in plugins.calls))
        plugins = SyntheticPlugins(3)
        with self.assertRaises(ValueError):
            controller(plugins, 25).handle_plugins_set_param_value(
                {"plugin_index": 1, "param_index": 0, "value": 0.5})
        self.assertFalse(any(c[0] == "set" for c in plugins.calls))


class PluginToolContractTests(unittest.TestCase):
    def test_real_fastmcp_tool_schema_and_response_transport(self):
        from fastmcp import Client, FastMCP
        spec = importlib.util.spec_from_file_location("synthetic_sdk_plugin_tools",
            ROOT / "third_party/fl-studio-mcp/src/fl_studio_mcp/tools/plugins.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = {"success": True, **controller(SyntheticPlugins(3)).handle_plugins_get_params({"index": 1})}
        mcp = FastMCP("Synthetic plugin contract")
        with patch.dict(sys.modules, {"fl_studio_mcp.utils.connection": SimpleNamespace(
            get_connection=lambda: SimpleNamespace(send_command=lambda *args: payload))}):
            module.register_plugin_tools(mcp)
        async def probe():
            async with Client(mcp) as client:
                metadata = await client.call_tool("fl_get_plugin_params", {"index": 1, "include_metadata": True})
                legacy = await client.call_tool("fl_get_plugin_params", {"index": 1})
                return metadata, legacy
        metadata, legacy = asyncio.run(probe())
        self.assertFalse(metadata.is_error)
        self.assertEqual(decode_plugin_scan(metadata.data)[1], (0.5,) * 3)
        # SDK 可把任意字段字典转换成模型；列表兼容性以原始响应为准。
        self.assertEqual(legacy.structured_content["result"], payload["params"])
        self.assertEqual(json.loads(legacy.content[0].text), payload["params"])

    def test_metadata_and_legacy_list_share_existing_tool(self):
        spec = importlib.util.spec_from_file_location("synthetic_plugin_tools",
            ROOT / "third_party/fl-studio-mcp/src/fl_studio_mcp/tools/plugins.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registered, calls = {}, []
        result = {"success": True, "params": [{"index": 0}], "errors": [{"index": 1, "error": "ReadError"}],
                  "truncated": False, "complete": False}
        def send(action, args):
            calls.append((action, args))
            return result
        class MCP:
            def tool(self):
                def register(fn):
                    registered[fn.__name__] = fn
                    return fn
                return register
        with patch.dict(sys.modules, {"fl_studio_mcp.utils.connection":
             SimpleNamespace(get_connection=lambda: SimpleNamespace(send_command=send))}):
            module.register_plugin_tools(MCP())
        tool = registered["fl_get_plugin_params"]
        self.assertEqual(tool(1, include_metadata=True), result)
        self.assertEqual(calls[0][1]["max_params"], None)
        self.assertEqual(tool(1), result["params"] + result["errors"])
        result["truncated"] = True
        self.assertEqual(tool(1)[-1], {"error": "PARAMETER_SCAN_TRUNCATED"})
        self.assertEqual(set(registered), {"fl_is_plugin_valid", "fl_get_plugin_name",
            "fl_get_plugin_param_count", "fl_get_plugin_params", "fl_get_plugin_param_value",
            "fl_set_plugin_param_value", "fl_get_preset_count", "fl_next_preset", "fl_prev_preset",
            "fl_get_plugin_color"})

    def test_adapter_rejects_old_or_incomplete_response_without_writing(self):
        from dawloop.adapters.fl_studio_mcp.adapter import FLStudioMCPAdapter
        plugins = SyntheticPlugins(3)
        complete = controller(plugins).handle_plugins_get_params({"index": 1})
        for payload, status in ((complete, "READBACK_RECEIVED"),
                                ({**complete, "complete": False}, "STOP"), ([], "STOP")):
            calls = []
            class Client:
                def __init__(self, *args, **kwargs):
                    pass
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
            async def fake_call(client, name, arguments=None):
                calls.append(name)
                return True if name == "fl_is_plugin_valid" else payload
            with patch.dict(sys.modules, {"fastmcp": SimpleNamespace(Client=Client)}), \
                 patch("dawloop.adapters.fl_studio_mcp.adapter._call", fake_call):
                result = asyncio.run(FLStudioMCPAdapter().inspect_plugin(1, 0))
            self.assertEqual(result["status"], status)
            self.assertEqual(calls, ["fl_is_plugin_valid", "fl_get_plugin_params"])


if __name__ == "__main__":
    unittest.main()
