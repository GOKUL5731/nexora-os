"""Meta-phase cognitive graph view-models."""

from __future__ import annotations

from typing import Any


class CognitiveGraphView:
    """Exposes live reasoning graph, meta observations, and health state."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        meta = data.get("meta_ecosystem", {})
        world = data.get("world_model", {})
        return {
            "title": "Cognitive Graph",
            "nodes": world.get("nodes", []),
            "edges": world.get("edges", []),
            "meta_observations": meta.get("meta_observations", []),
            "health": meta.get("health", []),
        }
