"""Strategy marketplace dashboard view-models."""

from __future__ import annotations

from typing import Any


class StrategyDashboard:
    """Shows active, competing, and benchmarked reasoning strategies."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        strategies = data.get("meta_ecosystem", {}).get("strategies", {})
        return {
            "title": "Strategy Dashboard",
            "active": strategies.get("active", {}),
            "strategies": strategies.get("all", []),
            "benchmarks": strategies.get("benchmarks", []),
        }
