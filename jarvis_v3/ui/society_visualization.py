"""Recursive phase society visualization view-model."""

from __future__ import annotations

from typing import Any


class SocietyVisualization:
    """Agent coalitions, communication, role drift, and emergent specialization."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        recursive = data.get("meta_ecosystem", {}).get("recursive_infrastructure", {})
        emergent = recursive.get("emergent_societies", {})
        distributed = recursive.get("distributed_cognition", {})
        return {
            "title": "Agent Society Visualization",
            "agents": data.get("society", {}).get("agents", []),
            "coalitions": emergent.get("coalitions", []),
            "role_evolution": emergent.get("role_evolution", []),
            "specialization_drift": emergent.get("drift", []),
            "messages": distributed.get("messages", []),
        }
