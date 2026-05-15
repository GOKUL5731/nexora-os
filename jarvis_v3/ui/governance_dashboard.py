"""Civilization governance dashboard view-model."""

from __future__ import annotations

from typing import Any


class GovernanceDashboard:
    """Policy, competition governance, ecosystem health, and containment state."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        meta = data.get("meta_ecosystem", {})
        layer = meta.get("civilization_layer", {})
        recursive = meta.get("recursive_infrastructure", {})
        return {
            "title": "Governance Dashboard",
            "civilization_governance": layer.get("governance", {}),
            "recursive_governance": recursive.get("governance", {}),
            "health": layer.get("health", []),
        }
