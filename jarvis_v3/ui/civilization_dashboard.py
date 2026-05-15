"""Civilization dashboard view-model."""

from __future__ import annotations

from typing import Any


class CivilizationDashboard:
    """Visualizes civilizations, cultures, economy, and health."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        layer = data.get("meta_ecosystem", {}).get("civilization_layer", {})
        return {
            "title": "Civilization Dashboard",
            "civilizations": layer.get("civilizations", {}).get("civilizations", []),
            "events": layer.get("civilizations", {}).get("events", []),
            "cultures": layer.get("culture", {}).get("cultures", []),
            "economy": layer.get("economy", {}),
            "health": layer.get("health", []),
        }
