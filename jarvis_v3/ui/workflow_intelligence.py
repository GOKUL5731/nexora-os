"""Workflow intelligence dashboard view-models."""

from __future__ import annotations

from typing import Any


class WorkflowIntelligencePanel:
    """Shows optimization opportunities, analytics, and predictive suggestions."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        if not self.autonomy:
            return {"title": "Workflow Intelligence", "opportunities": [], "resources": {}, "goals": {}}
        data = self.autonomy.autonomy_snapshot()
        last_cycle = data.get("loop", {}).get("last_cycle") or {}
        state = last_cycle.get("state", {})
        return {
            "title": "Workflow Intelligence",
            "opportunities": data.get("graph", {}).get("opportunities", []),
            "resources": data.get("resources", {}),
            "goals": data.get("goals", {}),
            "suggestions": state.get("suggestions", []),
            "predictions": state.get("predictions", {}),
        }
