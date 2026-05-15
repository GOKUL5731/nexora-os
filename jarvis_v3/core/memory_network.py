"""Multi-layer memory network for the meta-cognitive phase."""

from __future__ import annotations

import time
from collections import deque
from typing import Any

from core.advanced_memory import AdvancedMemorySystem
from core.evolutionary_memory import EvolutionaryMemory


class MultiLayerMemoryNetwork:
    """Combines sensory, working, episodic, semantic, procedural, reflective, and evolutionary memory."""

    def __init__(
        self,
        config: dict | None = None,
        memory: AdvancedMemorySystem | None = None,
        evolutionary: EvolutionaryMemory | None = None,
        sensory_limit: int = 100,
    ):
        self.config = config or {}
        self.memory = memory or AdvancedMemorySystem(self.config)
        self.evolutionary = evolutionary or EvolutionaryMemory(self.config)
        self.sensory = deque(maxlen=sensory_limit)
        self.working: dict[str, Any] = {}

    def record_sensory(self, source: str, payload: Any) -> dict[str, Any]:
        item = {"source": source, "payload": payload, "timestamp": time.time()}
        self.sensory.append(item)
        return item

    def set_working(self, key: str, value: Any) -> None:
        self.working[key] = {"value": value, "timestamp": time.time()}
        self.memory.store_fact("working_memory", key, value, confidence=0.8)

    def remember_reflection(self, title: str, lesson: str, context: dict[str, Any] | None = None) -> str:
        return self.memory.store_fact(
            "reflective_memory",
            title,
            {"lesson": lesson, "context": context or {}},
            confidence=0.75,
        )

    def remember_evolution(self, target: str, status: str, metrics: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
        return self.evolutionary.record("architecture_evolution", target, status, metrics, detail)

    def snapshot(self) -> dict[str, Any]:
        return {
            "sensory": list(self.sensory),
            "working": self.working,
            "episodic_recent": self.memory.recall_episodes(limit=10),
            "semantic_runtime": self.memory.list_facts("runtime"),
            "procedural_count": len(self.memory.list_facts("procedural_index")) if hasattr(self.memory, "list_facts") else 0,
            "reflective": self.memory.list_facts("reflective_memory"),
            "evolutionary": self.evolutionary.performance_summary(),
        }
