"""Agent and architecture evolution view-models."""

from __future__ import annotations

from typing import Any


class AgentEvolutionView:
    """Displays society evolution, evolutionary memory, and architecture proposals."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        meta = data.get("meta_ecosystem", {})
        return {
            "title": "Agent Evolution",
            "society": data.get("society", {}),
            "evolutionary_memory": meta.get("evolutionary_memory", []),
            "architecture_health": meta.get("health", []),
        }
