"""Research network view-model."""

from __future__ import annotations

from typing import Any


class ResearchNetworkView:
    """Shows active research labs, runs, experiments, and discoveries."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        layer = data.get("meta_ecosystem", {}).get("civilization_layer", {})
        research = layer.get("research", {})
        return {
            "title": "Research Network",
            "labs": research.get("labs", []),
            "runs": research.get("runs", []),
            "discoveries": layer.get("scientific_discovery", []),
        }
