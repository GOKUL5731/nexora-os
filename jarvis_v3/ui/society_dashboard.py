"""Agent society dashboard view-models."""

from __future__ import annotations

from typing import Any


class SocietyDashboard:
    """Exposes live society state for the UI layer."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        society = data.get("society", {})
        return {
            "title": "Agent Society",
            "agents": society.get("agents", []),
            "events": society.get("events", []),
        }
