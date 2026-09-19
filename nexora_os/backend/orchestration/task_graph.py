from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphTask:
    task_id: str
    title: str
    description: str
    owner: str
    dependencies: list[str] = field(default_factory=list)
    state: str = "PENDING"
    expected_artifacts: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)


class TaskGraph:
    """Small dependency DAG with explicit readiness and cycle validation."""

    def __init__(self) -> None:
        self.tasks: dict[str, GraphTask] = {}

    def add(self, task: GraphTask) -> None:
        if task.task_id in self.tasks:
            raise ValueError(f"Duplicate task id: {task.task_id}")
        if task.task_id in task.dependencies:
            raise ValueError("A task cannot depend on itself")
        missing = [dep for dep in task.dependencies if dep not in self.tasks]
        if missing:
            raise ValueError(f"Unknown task dependencies: {missing}")
        self.tasks[task.task_id] = task
        if self._has_cycle():
            del self.tasks[task.task_id]
            raise ValueError("Task dependency cycle detected")

    def ready(self) -> list[GraphTask]:
        return [task for task in self.tasks.values() if task.state == "PENDING" and all(self.tasks[dep].state in {"COMPLETED", "SUCCESS"} for dep in task.dependencies)]

    def set_state(self, task_id: str, state: str) -> None:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        if state == "STARTED" and self.tasks[task_id] not in self.ready():
            raise ValueError(f"Task {task_id} is not ready")
        self.tasks[task_id].state = state

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {task_id: vars(task).copy() for task_id, task in self.tasks.items()}

    def _has_cycle(self) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> bool:
            if task_id in visiting:
                return True
            if task_id in visited:
                return False
            visiting.add(task_id)
            if any(visit(dep) for dep in self.tasks[task_id].dependencies):
                return True
            visiting.remove(task_id)
            visited.add(task_id)
            return False

        return any(visit(task_id) for task_id in self.tasks)
