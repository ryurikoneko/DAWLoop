from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    name: str
    backend: str
    readable: bool = False
    writable: bool = False
    verifiable: bool = False
    destructive: bool = False
    description: str = ""


class CapabilityRegistry:
    def __init__(self, capabilities: tuple[Capability, ...] = ()) -> None:
        self._items: dict[tuple[str, str], Capability] = {
            (item.backend, item.name): item for item in capabilities
        }

    def register(self, capability: Capability) -> None:
        self._items[(capability.backend, capability.name)] = capability

    def get(self, backend: str, name: str) -> Capability | None:
        return self._items.get((backend, name))

    def for_backend(self, backend: str) -> tuple[Capability, ...]:
        return tuple(
            item for (item_backend, _), item in sorted(self._items.items())
            if item_backend == backend
        )

    def backends_for(self, name: str, *, write: bool = False) -> tuple[str, ...]:
        matches = []
        for (backend, capability_name), item in self._items.items():
            if capability_name != name:
                continue
            if write and not item.writable:
                continue
            matches.append(backend)
        return tuple(sorted(matches))
