"""
Continuous learning facade.

Combines the behavior trainer and self-learning loop behind one lifecycle
object so the UI/service layer can start and stop learning predictably.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from core.trainer import BehaviorTrainer
from self_learning.learning_engine import SelfLearningEngine


@dataclass
class ContinuousLearningEngine:
    config: dict
    memory: object
    router: object | None = None
    _tasks: list[asyncio.Task] = field(default_factory=list)
    _behavior: BehaviorTrainer | None = None
    _self_learning: SelfLearningEngine | None = None

    async def start(self) -> dict:
        if self._tasks:
            return {"status": "already_running", "tasks": len(self._tasks)}
        self._behavior = BehaviorTrainer(self.config, self.memory, self.router)
        self._self_learning = SelfLearningEngine(self.config, self.memory)
        self._tasks = [
            asyncio.create_task(self._behavior.start()),
            asyncio.create_task(self._self_learning.start()),
        ]
        return {"status": "started", "tasks": len(self._tasks)}

    def stop(self) -> dict:
        if self._behavior:
            self._behavior.stop()
        if self._self_learning:
            self._self_learning.stop()
        for task in self._tasks:
            task.cancel()
        stopped = len(self._tasks)
        self._tasks = []
        return {"status": "stopped", "tasks": stopped}

    def report(self) -> dict:
        return {
            "behavior": self._behavior.get_report() if self._behavior else {},
            "self_learning": self._self_learning.get_summary() if self._self_learning else {},
            "running": bool(self._tasks),
        }


__all__ = ["ContinuousLearningEngine", "BehaviorTrainer", "SelfLearningEngine"]
