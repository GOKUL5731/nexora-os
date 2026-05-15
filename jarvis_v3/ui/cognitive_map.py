"""Cognitive map view-models for the UI."""

from __future__ import annotations

from typing import Any


class CognitiveMapPanel:
    """Builds a UI-ready cognitive graph from autonomy snapshots."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        world = data.get("world_model", {})
        return {
            "title": "Cognitive Map",
            "nodes": world.get("nodes", []),
            "edges": world.get("edges", []),
            "loop": data.get("loop", {}),
            "graph_validation": data.get("graph", {}).get("validation", {}),
        }
