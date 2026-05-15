"""Simulation universe panel view-models."""

from __future__ import annotations

from typing import Any


class SimulationUniversePanel:
    """Shows internal simulation universe runs and outcomes."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        meta = data.get("meta_ecosystem", {})
        return {
            "title": "Simulation Universe",
            "runs": meta.get("simulation_universe", []),
            "cognitive_simulations": data.get("simulations", []),
            "stability": meta.get("stability", {}),
        }
