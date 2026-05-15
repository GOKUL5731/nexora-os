"""Recursive phase evolution graph view-model."""

from __future__ import annotations

from typing import Any


class EvolutionGraphs:
    """Architecture and recursive optimization evolution over time."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        recursive = data.get("meta_ecosystem", {}).get("recursive_infrastructure", {})
        cycles = recursive.get("recursive_cycles", [])
        candidates = recursive.get("adaptive_architecture", [])
        return {
            "title": "Evolution Graphs",
            "cycles": cycles,
            "architecture_candidates": candidates,
            "timeline": [
                {"id": item.get("id"), "status": item.get("status"), "created_at": item.get("created_at")}
                for item in cycles + candidates
            ],
        }
