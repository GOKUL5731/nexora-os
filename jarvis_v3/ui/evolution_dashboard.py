"""Evolution dashboard view-models."""

from __future__ import annotations

from typing import Any


class EvolutionDashboard:
    """Combines experiments, skills, simulations, and research for UI display."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        return {
            "title": "Evolution",
            "skills": data.get("skills", {}).get("skills", []),
            "skill_recommendations": data.get("skills", {}).get("recommendations", []),
            "simulations": data.get("simulations", []),
            "research": data.get("research", []),
        }
