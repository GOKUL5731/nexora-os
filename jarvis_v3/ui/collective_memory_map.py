"""Collective memory map view-model."""

from __future__ import annotations

from typing import Any


class CollectiveMemoryMap:
    """Shows shared knowledge, cultural memory, strategy memory, and scientific memory."""

    def __init__(self, autonomy: Any = None):
        self.autonomy = autonomy

    def snapshot(self) -> dict[str, Any]:
        data = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        memory = data.get("meta_ecosystem", {}).get("civilization_layer", {}).get("collective_memory", {})
        nodes = []
        for group in ["collective", "cultural", "evolutionary_history", "strategic", "scientific"]:
            for item in memory.get(group, []):
                nodes.append({"id": item["id"], "label": item["key"], "type": group, "civilization": item["civilization"]})
        return {
            "title": "Collective Memory Map",
            "nodes": nodes,
            "memory": memory,
            "consistency": memory.get("consistency", {}),
        }
