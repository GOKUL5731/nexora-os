"""Recursive phase observability dashboard view-model."""

from __future__ import annotations

from typing import Any


class ObservabilityDashboard:
    """Metrics and traces for cognition, orchestration, resources, and memory flows."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        recursive = data.get("meta_ecosystem", {}).get("recursive_infrastructure", {})
        return {
            "title": "Observability",
            "observability": recursive.get("observability", {}),
            "resource_intelligence": recursive.get("resource_intelligence", {}),
            "governance": recursive.get("governance", {}),
            "stability": data.get("meta_ecosystem", {}).get("stability", {}),
        }
