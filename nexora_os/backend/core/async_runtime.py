from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any, Awaitable

from .event_bus import EventBus


@dataclass(slots=True)
class TaskInfo:
    name: str
    status: str
    created_at: float
    done_at: float | None = None
    error: str = ""


class AsyncRuntime:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._tasks: dict[str, tuple[asyncio.Task, TaskInfo]] = {}
        self.started = False

    async def start(self) -> None:
        self.started = True
        self.bus.publish("async_runtime.started", {"status": "running"}, "async_runtime")

    def create_task(self, name: str, awaitable: Awaitable[Any]) -> asyncio.Task:
        if not self.started:
            raise RuntimeError("AsyncRuntime has not been started")
        info = TaskInfo(name=name, status="running", created_at=time.time())
        task = asyncio.create_task(awaitable, name=name)
        self._tasks[name] = (task, info)
        self.bus.publish("async_runtime.task_started", asdict(info), "async_runtime")
        task.add_done_callback(lambda done_task, task_name=name: self._complete(task_name, done_task))
        return task

    async def shutdown(self) -> None:
        for task, info in list(self._tasks.values()):
            if not task.done():
                info.status = "cancelled"
                task.cancel()
        pending = [task for task, _ in self._tasks.values() if not task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self.started = False
        self.bus.publish("async_runtime.stopped", {"status": "stopped"}, "async_runtime")

    def health(self) -> dict[str, Any]:
        return {
            "started": self.started,
            "tasks": [asdict(info) for _, info in self._tasks.values()],
            "running": sum(1 for task, _ in self._tasks.values() if not task.done()),
        }

    def _complete(self, name: str, task: asyncio.Task) -> None:
        entry = self._tasks.get(name)
        if not entry:
            return
        _, info = entry
        info.done_at = time.time()
        if task.cancelled():
            info.status = "cancelled"
        else:
            exc = task.exception()
            if exc:
                info.status = "failed"
                info.error = str(exc)
            else:
                info.status = "completed"
        self.bus.publish("async_runtime.task_finished", asdict(info), "async_runtime")
