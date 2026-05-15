"""Recursive phase world model view-model."""

from __future__ import annotations

from typing import Any


class WorldModelView:
    """System understanding graphs, topology, plugin relationships, and inferred focus."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        world = data.get("world_model", {})
        graph = data.get("graph", {})
        return {
            "title": "World Model",
            "nodes": world.get("nodes", []),
            "edges": world.get("edges", []),
            "inference": world.get("inference", {}),
            "validation": graph.get("validation", {}),
            "opportunities": graph.get("opportunities", []),
        }
