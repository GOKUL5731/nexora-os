from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Capability:
    id: str
    name: str
    provider: str
    capabilities: list[str]
    permissions: list[str] = field(default_factory=list)
    risk_level: str = "low"
    available: bool = True
    health: str = "healthy"
    latency_ms: float = 0.0
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Capability] = {}

    def register_capability(
        self,
        capability_id: str,
        name: str,
        provider: str,
        capabilities: list[str],
        permissions: list[str] | None = None,
        risk_level: str = "low",
        available: bool = True,
        health: str = "healthy",
        latency_ms: float = 0.0,
    ) -> dict[str, Any]:
        item = Capability(
            id=capability_id,
            name=name,
            provider=provider,
            capabilities=capabilities,
            permissions=permissions or [],
            risk_level=risk_level,
            available=available,
            health=health,
            latency_ms=latency_ms,
            updated_at=time.time(),
        )
        self._items[capability_id] = item
        return item.to_dict()

    def unregister_capability(self, capability_id: str) -> None:
        self._items.pop(capability_id, None)

    def discover_capabilities(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._items.values()]

    def check_availability(self, capability_id: str) -> bool:
        item = self._items.get(capability_id)
        return bool(item and item.available and item.health in {"healthy", "degraded"})

    def check_permissions(self, capability_id: str, granted: list[str] | None = None) -> bool:
        item = self._items.get(capability_id)
        if not item:
            return False
        granted_set = set(granted or [])
        return set(item.permissions).issubset(granted_set) if item.permissions else True

    def search_by_goal(self, goal: str) -> list[dict[str, Any]]:
        words = {word.lower() for word in goal.split()}
        scored: list[tuple[int, Capability]] = []
        for item in self._items.values():
            haystack = {item.id.lower(), item.name.lower(), item.provider.lower(), *[c.lower() for c in item.capabilities]}
            score = sum(1 for word in words for value in haystack if word in value)
            if score or item.available:
                scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], pair[1].available), reverse=True)
        return [item.to_dict() for _, item in scored]

    def health_check(self) -> dict[str, Any]:
        items = self.discover_capabilities()
        return {
            "count": len(items),
            "available": sum(1 for item in items if item["available"]),
            "degraded": sum(1 for item in items if item["health"] == "degraded"),
        }
