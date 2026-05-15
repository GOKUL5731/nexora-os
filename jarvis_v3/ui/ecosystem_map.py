"""Recursive phase ecosystem map view-model."""

from __future__ import annotations

from typing import Any


class EcosystemMap:
    """Live infrastructure topology across cognition, resources, twins, and orchestration."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        meta = data.get("meta_ecosystem", {})
        recursive = meta.get("recursive_infrastructure", {})
        orchestration = recursive.get("orchestration_intelligence", [])
        latest_graph = orchestration[0]["graph"] if orchestration else {"nodes": [], "edges": []}
        return {
            "title": "Ecosystem Map",
            "topology": latest_graph,
            "world_model": data.get("world_model", {}),
            "digital_twins": meta.get("twins", []),
            "resources": data.get("resources", {}),
        }
