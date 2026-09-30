from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from dawloop.runtime import Capability


_READ_PREFIXES = ("get_", "list_", "is_", "describe_")
_WRITE_PREFIXES = ("set_", "add_", "remove_", "rename_", "route_", "open_", "show_", "play", "stop", "run_")
_DESTRUCTIVE_PREFIXES = ("remove_", "delete_", "clear_", "reset_")


@dataclass(frozen=True)
class NativeTool:
    name: str
    description: str
    input_schema: dict[str, Any]



def normalize_catalog(payload: Any) -> tuple[NativeTool, ...]:
    """Normalize the live FL/Gopher MCP catalog into stable DAWLoop records."""
    if isinstance(payload, dict):
        payload = payload.get("tools", payload)
    if isinstance(payload, dict):
        payload = list(payload.values())
    if not isinstance(payload, Iterable) or isinstance(payload, (str, bytes)):
        raise ValueError("native tool catalog must be a list-like payload")

    tools: list[NativeTool] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        schema = item.get("inputSchema") or item.get("input_schema") or {}
        if not isinstance(schema, dict):
            schema = {}
        description = item.get("description")
        tools.append(NativeTool(name=name.strip(), description=str(description or ""), input_schema=schema))
    return tuple(tools)



def _classify(tool: NativeTool) -> tuple[bool, bool, bool]:
    name = tool.name
    readable = name.startswith(_READ_PREFIXES)
    writable = name.startswith(_WRITE_PREFIXES)
    destructive = name.startswith(_DESTRUCTIVE_PREFIXES) or "DESTRUCTIVE" in tool.description.upper()

    # Some FL tools are both semantically inspectable and writable even when
    # their names do not make that obvious. Keep classification conservative:
    # runtime discovery can later augment this from tested metadata.
    if name in {"get_plugin_parameter_value", "get_plugin_parameter_list", "get_session_context"}:
        readable = True
    if name in {"set_plugin_parameter_value", "set_tempo", "quantize_channel"}:
        writable = True
    return readable, writable, destructive



def capabilities_from_catalog(payload: Any, backend: str = "gopher_native") -> tuple[Capability, ...]:
    capabilities: list[Capability] = []
    for tool in normalize_catalog(payload):
        readable, writable, destructive = _classify(tool)
        capabilities.append(
            Capability(
                name=tool.name,
                backend=backend,
                readable=readable,
                writable=writable,
                verifiable=False,
                destructive=destructive,
                description=tool.description,
            )
        )
    return tuple(capabilities)
