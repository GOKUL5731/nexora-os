"""Strategic timeline view-model."""

from __future__ import annotations

from typing import Any


class StrategicTimeline:
    """Long-term planning and evolution trajectories."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        layer = data.get("meta_ecosystem", {}).get("civilization_layer", {})
        forecasts = layer.get("forecasts", [])
        events = layer.get("civilizations", {}).get("events", [])
        return {
            "title": "Strategic Timeline",
            "forecasts": forecasts,
            "events": events,
            "timeline": sorted(
                [
                    {"type": "forecast", "label": item.get("objective"), "created_at": item.get("created_at")}
                    for item in forecasts
                ]
                + [
                    {"type": "civilization_event", "label": item.get("type"), "created_at": item.get("created_at")}
                    for item in events
                ],
                key=lambda item: item.get("created_at") or "",
                reverse=True,
            ),
        }
