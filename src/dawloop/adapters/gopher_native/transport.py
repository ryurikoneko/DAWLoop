from __future__ import annotations

import json
import math
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from dawloop.runtime import BackendError
from dawloop.runtime.diagnostics import observe


def validate_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("仅允许本机调试端点")
    return endpoint.rstrip("/")


def find_target(targets: list[dict]) -> dict:
    candidates = [target for target in targets if target.get("type") == "page"
                  and urlparse(target.get("url", "")).hostname == "gopher-fls.image-line.com"
                  and urlparse(target.get("url", "")).scheme == "https"]
    if len(candidates) != 1:
        raise BackendError("HOST_NOT_FOUND" if not candidates else "AMBIGUOUS_HOST")
    return candidates[0]


class CDPTransport:
    def __init__(self, endpoint: str = "http://127.0.0.1:9222", timeout: float = 35.0):
        self.endpoint = validate_endpoint(endpoint)
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
            raise ValueError("超时必须大于零且不超过六十秒")
        self.timeout = timeout
        self.socket = None
        self.counter = 0
        self.context_id = None
        self.host_generation = None
        self.target_id = None
        self.frame_id = None
        self.epoch = None
        self.poisoned_epoch = None
        self.events = []
        self.callbacks_restored = None

    def _rpc(self, method, params=None):
        self.counter += 1
        request_id = self.counter
        observe(getattr(self, 'diagnostics', None), 'cdp_request_send', 'transport', method=method)
        self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        deadline = time.monotonic() + self.timeout + 2
        while time.monotonic() < deadline:
            self.socket.settimeout(max(0.01, deadline - time.monotonic()))
            response = json.loads(self.socket.recv())
            if "method" in response:
                self.events.append(response)
                self.events = self.events[-100:]
                if response["method"] == "Runtime.executionContextCreated":
                    context = response["params"]["context"]
                    if (context.get("auxData", {}).get("isDefault")
                            and context.get("auxData", {}).get("frameId") == self.frame_id):
                        self.context_id = context["id"]
                        self.host_generation = context.get('uniqueId')
                elif response["method"] == "Runtime.executionContextsCleared":
                    self.context_id = None
                    self.host_generation = None
                elif (response["method"] == "Runtime.executionContextDestroyed"
                      and response["params"].get("executionContextId") == self.context_id):
                    self.context_id = None
                    self.host_generation = None
                continue
            if response.get("id") == request_id:
                observe(getattr(self, 'diagnostics', None), 'cdp_response_received', 'transport', method=method)
                if "error" in response:
                    raise BackendError("CDP_ERROR")
                return response.get("result", {})
        raise BackendError("CDP_TIMEOUT")

    def _evaluate(self, expression):
        if self.context_id is None:
            raise BackendError("PAGE_CONTEXT_UNAVAILABLE")
        result = self._rpc("Runtime.evaluate", {
            "expression": expression, "contextId": self.context_id,
            "awaitPromise": True, "returnByValue": True,
        })
        if "exceptionDetails" in result:
            raise BackendError("PAGE_EVALUATION_ERROR")
        return result.get("result", {}).get("value")

    def connect(self):
        try:
            import websocket
        except ImportError as error:
            raise BackendError("NATIVE_DEPENDENCY_MISSING") from error
        if self.socket is not None:
            self.close()
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(self.endpoint + "/json/list", timeout=3) as response:
                targets = json.loads(response.read(1024 * 1024).decode("utf-8"))
            target = find_target(targets)
            ws_url = target.get("webSocketDebuggerUrl", "")
            parsed = urlparse(ws_url)
            if (parsed.scheme != "ws" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or parsed.username or parsed.password):
                raise BackendError("UNSAFE_DEBUGGER_URL")
            self.target_id = target["id"]
            self.context_id = None
            self.host_generation = None
            self.socket = websocket.create_connection(ws_url, timeout=3, suppress_origin=True,
                                                       http_no_proxy=["localhost", "127.0.0.1", "::1"])
            self.frame_id = self._rpc("Page.getFrameTree")["frameTree"]["frame"]["id"]
            self._rpc("Runtime.enable")
            source = Path(__file__).with_name("bridge.js").read_text(encoding="utf-8")
            observation = self._evaluate(source)
            if not isinstance(observation, dict) or not observation.get("epoch"):
                raise BackendError("BRIDGE_UNAVAILABLE")
            self.epoch = observation["epoch"]
            if observation.get("poisoned") or self.epoch == self.poisoned_epoch:
                self.poisoned_epoch = self.epoch
                raise BackendError("SESSION_POISONED")
            return {"session": self.epoch, "bridge_epoch": self.epoch,
                    "host_generation": self.host_generation, "target_id": self.target_id}
        except BackendError:
            self.close()
            raise
        except Exception as error:
            self.close()
            raise BackendError("HOST_DISCONNECTED") from error

    def invoke(self, kind, name=None, arguments=None):
        if self.socket is None:
            raise BackendError("HOST_DISCONNECTED")
        if self.epoch is None or self.epoch == self.poisoned_epoch:
            raise BackendError("SESSION_POISONED")
        expression = "window.__dawloopReadonlyBridgeV1.invoke(%s,%s,%s,%s)" % (
            json.dumps(kind), json.dumps(name), json.dumps(arguments or {}, allow_nan=False),
            int(self.timeout * 1000),
        )
        try:
            response = self._evaluate(expression)
        except Exception as error:
            self.poisoned_epoch = self.epoch
            raise BackendError("DISPATCH_UNKNOWN", dispatched=True) from error
        if not isinstance(response, dict):
            self.poisoned_epoch = self.epoch
            raise BackendError("INVALID_BRIDGE_RESPONSE", dispatched=True)
        if not response.get("ok"):
            if response.get("dispatched"):
                self.poisoned_epoch = self.epoch
            raise BackendError(response.get("code", "BRIDGE_ERROR"), dispatched=bool(response.get("dispatched")))
        try:
            acknowledged = self._evaluate("window.__dawloopReadonlyBridgeV1.acknowledge(%s)" % json.dumps(self.epoch))
            if acknowledged is not True:
                raise BackendError("PAGE_CONTEXT_CHANGED")
        except Exception as error:
            self.poisoned_epoch = self.epoch
            raise BackendError("RESULT_ACKNOWLEDGEMENT_UNKNOWN", dispatched=True) from error
        return response

    def invoke_batch(self, notes, rendered, operation_id):
        from dawloop.runtime.native_write import PianoRollScriptRenderer, normalized_notes
        PianoRollScriptRenderer(getattr(self, 'diagnostics', None)).validate(notes, rendered)
        if self.socket is None:
            raise BackendError('HOST_DISCONNECTED')
        if self.epoch is None or self.epoch == self.poisoned_epoch:
            raise BackendError('SESSION_POISONED')
        expression = 'window.__dawloopReadonlyBridgeV1.invokeBatchAdd(%s,%s,%s,%s,%s,%s)' % (
            json.dumps(operation_id), json.dumps(normalized_notes(notes)),
            json.dumps(rendered.sha256), json.dumps(rendered.source.decode('utf-8')),
            json.dumps(self.epoch), int(self.timeout * 1000))
        try:
            response = self._evaluate(expression)
        except Exception as error:
            self.poisoned_epoch = self.epoch
            raise BackendError('DISPATCH_UNKNOWN', dispatched=True) from error
        if not isinstance(response, dict):
            self.poisoned_epoch = self.epoch
            raise BackendError('INVALID_BRIDGE_RESPONSE', dispatched=True)
        if response.get('ok') is not True:
            dispatched = response.get('dispatched') is True
            if dispatched:
                self.poisoned_epoch = self.epoch
            raise BackendError(response.get('code', 'BRIDGE_ERROR'), dispatched=dispatched)
        try:
            if self._evaluate('window.__dawloopReadonlyBridgeV1.acknowledge(%s)' % json.dumps(self.epoch)) is not True:
                raise BackendError('PAGE_CONTEXT_CHANGED')
        except Exception as error:
            self.poisoned_epoch = self.epoch
            raise BackendError('RESULT_ACKNOWLEDGEMENT_UNKNOWN', dispatched=True) from error
        return response

    def close(self):
        if self.socket is not None:
            try:
                observation = self._evaluate("window.__dawloopReadonlyBridgeV1 && window.__dawloopReadonlyBridgeV1.dispose()")
                self.callbacks_restored = isinstance(observation, dict) and observation.get("ok") is True
            except Exception:
                self.callbacks_restored = False
            finally:
                try:
                    self.socket.close()
                except Exception:
                    self.callbacks_restored = False
                finally:
                    self.socket = None
