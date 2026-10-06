from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from dawloop.runtime import Capability, ToolSafetyClassification


READ_TOOLS = {
    "get_tempo": ("transport.tempo.read", {}),
    "list_channel_names": ("channel.list", {}),
    "get_session_context": ("system.session_context", {}),
    "get_plugin_parameter_list": ("plugin.parameter.list", {"target": "string", "slot_number": "integer"}),
    "get_plugin_parameter_value": ("plugin.parameter.read", {
        "target": "string", "slot_number": "integer", "param_identifier": "string",
    }),
}


@lru_cache(maxsize=1)
def known_catalog():
    return json.loads(Path(__file__).with_name('known_catalog.json').read_text(encoding='utf-8'))


def _contains_reference(value):
    if isinstance(value, dict):
        return any(key in {"$ref", "$dynamicRef", "$recursiveRef"} or _contains_reference(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_reference(item) for item in value)
    return False


def catalog_hash(tools: list[dict]) -> str:
    data = json.dumps(sorted(tools, key=lambda item: item["name"]),
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def normalize_catalog(tools: list[dict]) -> list[Capability]:
    if not isinstance(tools, list) or any(
        not isinstance(tool, dict) or not isinstance(tool.get("name"), str) for tool in tools
    ):
        raise ValueError("INVALID_CATALOG")
    if len({tool["name"] for tool in tools}) != len(tools):
        raise ValueError("DUPLICATE_TOOL")
    capabilities = []
    for tool in tools:
        name = tool["name"]
        schema = tool.get("inputSchema", {})
        known = READ_TOOLS.get(name)
        mapping = known_catalog()['tools'].get(name)
        exact = bool(mapping and schema == mapping['input_schema']
                     and tool.get('description') == mapping['description'])
        matches = False
        if known and isinstance(schema, dict):
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            expected = known[1]
            matches = (
                schema.get("type") == "object" and isinstance(properties, dict)
                and isinstance(required, list) and len(required) == len(expected)
                and set(properties) == set(expected) and set(required) == set(expected)
                and all(isinstance(properties[key], dict) and properties[key].get("type") == kind
                        for key, kind in expected.items())
                and not any(key in schema for key in ("$ref", "$dynamicRef", "oneOf", "anyOf", "allOf", "not", "if"))
                and not _contains_reference(schema)
            )
        if 'description' in tool and not exact:
            matches = False
        risk = (ToolSafetyClassification(mapping['risk']) if exact else
                ToolSafetyClassification.READ_ONLY if matches else ToolSafetyClassification.UNKNOWN)
        capabilities.append(Capability(
            name=mapping['capability'] if exact else known[0] if matches else "native.unclassified." + name,
            backend="gopher_native", raw_tool=tool,
            safety=risk, readable=risk == ToolSafetyClassification.READ_ONLY,
            writable=risk not in {ToolSafetyClassification.READ_ONLY, ToolSafetyClassification.UNKNOWN},
            dispatch_supported=matches and name in READ_TOOLS,
            evidence=mapping['evidence'] if exact else '只读结构映射' if matches else '没有匹配的已知描述与结构',
            classification_reason=mapping['classification_reason'] if exact else None,
            confidence=mapping['confidence'] if exact else None,
        ))
    return capabilities
