"""Digital twin panel view-models."""

from __future__ import annotations

from typing import Any


class DigitalTwinPanel:
    """Shows user, workflow, system, application, and society twins."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        meta = data.get("meta_ecosystem", {})
        twins = meta.get("twins", [])
        return {
            "title": "Digital Twins",
            "twins": twins,
            "by_type": self._by_type(twins),
        }

    @staticmethod
    def _by_type(twins: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for twin in twins:
            grouped.setdefault(twin.get("type", "unknown"), []).append(twin)
        return grouped
