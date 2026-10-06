import asyncio
import json
import importlib.util
import shutil
import subprocess
import threading
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from dawloop.adapters.gopher_native import GopherNativeBackend, normalize_catalog
from dawloop.adapters.gopher_native.catalog import catalog_hash
from dawloop.adapters.gopher_native.transport import CDPTransport, find_target, validate_endpoint
from dawloop.runtime import BackendError, BackendRouter, DataStatus, ExecutionStatus, OperationPlan, ToolSafetyClassification


def tool(name="get_tempo", properties=None):
    properties = properties or {}
    return {"name": name, "inputSchema": {"type": "object", "properties": properties, "required": list(properties)}}


class FakeTransport:
    def __init__(self):
        self.epoch = "doc-1"
        self.poisoned_epoch = None
        self.tools = [tool()]
        self.calls = []
        self.payload = '{"jsonrpc":"2.0","id":1,"result":120}'
        self.closed = False

    def connect(self):
        if self.epoch == self.poisoned_epoch:
            raise BackendError("SESSION_POISONED")
        return {"session": self.epoch, "target_id": "target-1"}

    def invoke(self, kind, name=None, args=None):
        self.calls.append((kind, name, args))
        if self.epoch == self.poisoned_epoch:
            raise BackendError("SESSION_POISONED")
        if isinstance(self.payload, Exception) and kind == "call":
            self.poisoned_epoch = self.epoch
            raise self.payload
        return {"ok": True, "payload": json.dumps(self.tools) if kind == "catalog" else self.payload, "interference": 0}

    def close(self):
        self.closed = True


class NativeTests(unittest.TestCase):
    def test_exact_host_selection_and_loopback_endpoint(self):
        target = {"type": "page", "id": "1", "url": "https://gopher-fls.image-line.com/"}
        self.assertEqual(find_target([target])["id"], "1")
        for targets in ([], [target, target], [{**target, "url": "https://gopher-fls.image-line.com.evil/"}]):
            with self.assertRaises(BackendError):
                find_target(targets)
        for endpoint in ("https://localhost:9222", "http://example.com", "http://user@localhost:9222", "http://localhost/path"):
            with self.assertRaises(ValueError):
                validate_endpoint(endpoint)

    def test_catalog_changes_do_not_silently_allow_tools(self):
        unknown = tool("set_tempo")
        changed = tool(properties={"extra": {"type": "string"}})
        capabilities = normalize_catalog([tool(), unknown, changed | {"name": "get_session_context"}])
        self.assertEqual(capabilities[0].safety, ToolSafetyClassification.READ_ONLY)
        self.assertTrue(all(item.safety == ToolSafetyClassification.UNKNOWN for item in capabilities[1:]))
        self.assertIsNone(capabilities[0].latency_ms)
        self.assertEqual(catalog_hash([tool(), unknown]), catalog_hash([unknown, tool()]))
        with self.assertRaises(ValueError):
            normalize_catalog([tool(), tool()])
        references = tool("get_plugin_parameter_list", {"target": {"type": "string", "$ref": "https://example.com"},
                                                       "slot_number": {"type": "integer"}})
        self.assertEqual(normalize_catalog([references])[0].safety, ToolSafetyClassification.UNKNOWN)

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "需要原生可选依赖")
    def test_read_only_backend_returns_result_and_rejects_extra_parameters(self):
        async def check():
            transport = FakeTransport()
            backend = GopherNativeBackend(transport=transport)
            router = BackendRouter([backend])
            await router.discover()
            plan = OperationPlan("transport.tempo.read", {"session": "doc-1"})
            result = await router.execute(plan)
            self.assertEqual(result.value, {'tempo_bpm': 120})
            self.assertEqual(result.execution_status, ExecutionStatus.SUCCESS)
            invalid = await router.execute(OperationPlan(plan.operation, plan.target, {"source": "unsafe"}))
            self.assertEqual(invalid.execution_status, ExecutionStatus.NOT_DISPATCHED)
            self.assertEqual(len([call for call in transport.calls if call[0] == "call"]), 1)
            await backend.close()
            self.assertTrue(transport.closed)
        asyncio.run(check())

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "需要原生可选依赖")
    def test_timeout_and_same_document_reconnect_remain_locked(self):
        async def check():
            transport = FakeTransport()
            backend = GopherNativeBackend(transport=transport)
            await backend.discover()
            capability = backend.capabilities[0]
            transport.payload = BackendError("EXECUTION_TIMEOUT", dispatched=True)
            with self.assertRaises(BackendError):
                await backend.execute(OperationPlan(capability.name, {"session": "doc-1"}), capability)
            with self.assertRaises(BackendError):
                await backend.connect()
            transport.epoch = "doc-2"
            transport.payload = "120"
            await backend.connect()
            await backend.discover()
            result = await backend.execute(OperationPlan(capability.name, {"session": "doc-2"}), backend.capabilities[0])
            self.assertEqual(result.value, {'tempo_bpm': 120})
        asyncio.run(check())

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "需要原生可选依赖")
    def test_catalog_refresh_invalidates_removed_capabilities(self):
        async def check():
            transport = FakeTransport()
            backend = GopherNativeBackend(transport=transport)
            await backend.discover()
            capability = backend.capabilities[0]
            transport.tools = [tool("set_tempo")]
            await backend.discover()
            with self.assertRaises(ValueError):
                await backend.validate(OperationPlan(capability.name, {"session": "doc-1"}), capability)
        asyncio.run(check())

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "需要原生可选依赖")
    def test_nested_tool_error_is_not_execution_success(self):
        async def check():
            transport = FakeTransport()
            backend = GopherNativeBackend(transport=transport)
            await backend.discover()
            transport.payload = '{"jsonrpc":"2.0","id":1,"result": {"isError": true}}'
            result = await backend.execute(OperationPlan("transport.tempo.read", {"session": "doc-1"}), backend.capabilities[0])
            self.assertEqual(result.status, ExecutionStatus.FAILED)
        asyncio.run(check())

    def test_transport_disconnect_after_dispatch_is_unknown(self):
        transport = CDPTransport()
        transport.socket = object()
        transport.epoch = "document"
        with patch.object(transport, "_evaluate", side_effect=OSError()):
            with self.assertRaises(BackendError) as error:
                transport.invoke("call", "get_tempo", {})
        self.assertTrue(error.exception.dispatched)
        self.assertEqual(transport.poisoned_epoch, "document")
        with self.assertRaises(BackendError) as error:
            transport.invoke("call", "get_tempo", {})
        self.assertFalse(error.exception.dispatched)

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "需要原生可选依赖")
    def test_plugin_target_and_slot_are_explicit(self):
        async def check():
            transport = FakeTransport()
            transport.tools = [tool("get_plugin_parameter_list", {
                "target": {"type": "string"}, "slot_number": {"type": "integer"},
            })]
            backend = GopherNativeBackend(transport=transport)
            await backend.discover()
            capability = backend.capabilities[0]
            for target, slot in (("Synth", -1), ("0", -1), ("1", 0), ("1", True)):
                with self.assertRaises(ValueError):
                    await backend.validate(OperationPlan(capability.name, {"session": "doc-1"},
                                           {"target": target, "slot_number": slot}), capability)
            plan = OperationPlan(capability.name, {"session": "doc-1", "plugin_target": "1", "slot_number": -1},
                                 {"target": "1", "slot_number": -1})
            transport.payload = {'content': [{'type': 'text', 'text': "Parameters for 'Test':\n  Index 1: Gain"}]}
            result = await backend.execute(plan, capability)
            self.assertEqual(result.status, ExecutionStatus.SUCCESS)
            self.assertEqual(result.data_status, DataStatus.VALID)
        asyncio.run(check())

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "需要原生可选依赖")
    def test_cancellation_waits_for_worker_and_locks_the_session(self):
        async def check():
            transport = FakeTransport()
            backend = GopherNativeBackend(transport=transport)
            await backend.discover()
            started, release = threading.Event(), threading.Event()
            def delayed(*args):
                started.set()
                release.wait(2)
                return {"payload": "120"}
            transport.invoke = delayed
            task = asyncio.create_task(backend.execute(OperationPlan("transport.tempo.read", {"session": "doc-1"}),
                                                       backend.capabilities[0]))
            await asyncio.to_thread(started.wait, 1)
            task.cancel()
            await asyncio.sleep(0)
            self.assertTrue(backend.lock.locked())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(transport.poisoned_epoch, "doc-1")
            self.assertFalse(backend.lock.locked())
        asyncio.run(check())

    def test_cdp_connection_uses_main_frame_and_acknowledges_result(self):
        class Socket:
            def __init__(self):
                self.pending = []
                self.closed = False
            def send(self, data):
                request = json.loads(data)
                method = request["method"]
                result = {}
                if method == "Page.getFrameTree":
                    result = {"frameTree": {"frame": {"id": "main"}}}
                elif method == "Runtime.enable":
                    for frame, number in (("main", 1), ("iframe", 2)):
                        self.pending.append({"method": "Runtime.executionContextCreated", "params": {
                            "context": {"id": number, "auxData": {"isDefault": True, "frameId": frame}}}})
                elif method == "Runtime.evaluate":
                    self.assert_context = request["params"]["contextId"]
                    expression = request["params"]["expression"]
                    value = {"epoch": "new-document", "poisoned": False}
                    if ".invoke(" in expression:
                        value = {"ok": True, "payload": "120"}
                    elif ".acknowledge(" in expression:
                        value = True
                    elif ".dispose()" in expression:
                        value = {"ok": True}
                    result = {"result": {"value": value}}
                self.pending.append({"id": request["id"], "result": result})
            def recv(self):
                return json.dumps(self.pending.pop(0))
            def settimeout(self, timeout):
                pass
            def close(self):
                self.closed = True
        socket = Socket()
        target = {"type": "page", "id": "target", "url": "https://gopher-fls.image-line.com/",
                  "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/target"}
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps([target]).encode("utf-8")
        opener = MagicMock()
        opener.open.return_value = response
        transport = CDPTransport()
        with patch("urllib.request.build_opener", return_value=opener), \
                patch.dict("sys.modules", {"websocket": SimpleNamespace(create_connection=lambda *a, **k: socket)}):
            session = transport.connect()
            self.assertEqual(session['session'], 'new-document')
            self.assertEqual(session['bridge_epoch'], 'new-document')
            self.assertIsNone(session['host_generation'])
            self.assertEqual(transport.context_id, 1)
            self.assertEqual(transport.invoke("call", "get_tempo", {})["payload"], "120")
            transport.close()
        self.assertTrue(socket.closed)
        self.assertTrue(transport.callbacks_restored)

    @unittest.skipUnless(shutil.which("node"), "需要本地脚本引擎验证网页桥接时序")
    def test_actual_javascript_bridge_timing_and_restore(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([shutil.which("node"), str(root / "tests/native_bridge_harness.cjs"),
                                 str(root / "src/dawloop/adapters/gopher_native/bridge.js")],
                                capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
