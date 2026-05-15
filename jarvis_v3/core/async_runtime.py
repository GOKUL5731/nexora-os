"""Central async runtime for JARVIS background execution.

The runtime owns one asyncio loop in a dedicated thread and a bounded thread
pool for blocking work. UI code should submit work here instead of running
blocking AI, voice, workflow, or automation operations on the UI thread.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from core.event_bus import EventBus, get_event_bus
from core.logger import get_logger
from core.module_manager import get_module_manager


logger = get_logger("async_runtime")


@dataclass
class RuntimeTask:
    id: str
    name: str
    kind: str
    submitted_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    status: str = "running"
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "submitted_at": self.submitted_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "error": self.error,
            "duration_ms": round(((self.completed_at or time.time()) - self.submitted_at) * 1000, 2),
        }


class AsyncRuntime:
    def __init__(self, *, bus: EventBus | None = None, max_workers: int = 6):
        self.bus = bus or get_event_bus()
        self.max_workers = max_workers
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="jarvis-worker")
        self._executor_shutdown = False
        self._lock = threading.RLock()
        self._tasks: dict[str, RuntimeTask] = {}
        self._started_at = 0.0
        self._stopping = threading.Event()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stopping.clear()
            if self._executor_shutdown:
                self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="jarvis-worker")
                self._executor_shutdown = False
            self._started_at = time.time()
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, name="jarvis-async-runtime", daemon=True)
            self._thread.start()
        get_module_manager().register(
            "async_runtime",
            status="running",
            detail="Background asyncio loop ready",
            stop=self.stop,
            health_check=self.health_check,
        )
        self.bus.publish("runtime.async.started", self.health_check(), source="async_runtime")

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
        if not loop:
            return
        self._stopping.set()
        loop.call_soon_threadsafe(loop.stop)
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._executor_shutdown = True
        get_module_manager().update("async_runtime", "disabled", "Stopped")
        self.bus.publish("runtime.async.stopped", self.health_check(), source="async_runtime")

    def submit(self, coro: Coroutine[Any, Any, Any], *, name: str = "task") -> concurrent.futures.Future:
        self.start()
        assert self._loop is not None
        task_id = uuid.uuid4().hex[:12]
        record = RuntimeTask(id=task_id, name=name, kind="coroutine")
        self._register_task(record)

        async def _wrapped():
            try:
                result = await coro
            except Exception as exc:
                self._finish_task(task_id, "failed", str(exc))
                logger.exception("Async task failed [%s]: %s", name, exc)
                raise
            else:
                self._finish_task(task_id, "completed")
                return result

        future = asyncio.run_coroutine_threadsafe(_wrapped(), self._loop)
        future.add_done_callback(lambda done: self._finalize_future(task_id, done))
        return future

    def run_blocking(self, fn: Callable[..., Any], *args: Any, name: str = "blocking", **kwargs: Any) -> concurrent.futures.Future:
        self.start()
        assert self._loop is not None
        task_id = uuid.uuid4().hex[:12]
        record = RuntimeTask(id=task_id, name=name, kind="blocking")
        self._register_task(record)

        async def _wrapped():
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(self._executor, lambda: fn(*args, **kwargs))
            except Exception as exc:
                self._finish_task(task_id, "failed", str(exc))
                logger.exception("Blocking task failed [%s]: %s", name, exc)
                raise
            else:
                self._finish_task(task_id, "completed")
                return result

        future = asyncio.run_coroutine_threadsafe(_wrapped(), self._loop)
        future.add_done_callback(lambda done: self._finalize_future(task_id, done))
        return future

    def health_check(self) -> dict[str, Any]:
        with self._lock:
            tasks = [task.to_dict() for task in self._tasks.values()]
            running = [task for task in tasks if task["status"] == "running"]
            failed = [task for task in tasks if task["status"] == "failed"]
            thread_alive = bool(self._thread and self._thread.is_alive())
            data = {
                "status": "running" if thread_alive and not self._stopping.is_set() else "disabled",
                "thread_alive": thread_alive,
                "thread_name": self._thread.name if self._thread else "",
                "max_workers": self.max_workers,
                "tasks_total": len(tasks),
                "tasks_running": len(running),
                "tasks_failed": len(failed),
                "recent_tasks": tasks[-25:],
                "uptime_seconds": int(time.time() - self._started_at) if self._started_at else 0,
            }
        self.bus.set_state("async_runtime", data, source="async_runtime", publish=False)
        return data

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.set_default_executor(self._executor)
        self._loop.run_forever()
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self._loop.close()

    def _register_task(self, record: RuntimeTask) -> None:
        with self._lock:
            self._tasks[record.id] = record
            self._trim_tasks_locked()
        self.bus.publish("runtime.task.started", record.to_dict(), source="async_runtime")

    def _finish_task(self, task_id: str, status: str, error: str = "") -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if not record:
                return
            record.status = status
            record.error = error
            record.completed_at = time.time()
        self.bus.publish(f"runtime.task.{status}", record.to_dict(), source="async_runtime")

    def _finalize_future(self, task_id: str, future: concurrent.futures.Future) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            already_finished = bool(record and record.completed_at is not None)
        if already_finished:
            self.health_check()
            return
        if future.cancelled():
            self._finish_task(task_id, "cancelled")
        elif future.exception() is not None:
            self._finish_task(task_id, "failed", str(future.exception()))
        else:
            self._finish_task(task_id, "completed")
        self.health_check()

    def _trim_tasks_locked(self, limit: int = 200) -> None:
        if len(self._tasks) <= limit:
            return
        for task_id in list(self._tasks)[: len(self._tasks) - limit]:
            task = self._tasks.get(task_id)
            if task and task.status != "running":
                self._tasks.pop(task_id, None)


_RUNTIME = AsyncRuntime()


def get_async_runtime() -> AsyncRuntime:
    return _RUNTIME


__all__ = ["AsyncRuntime", "RuntimeTask", "get_async_runtime"]
