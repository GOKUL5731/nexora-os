from __future__ import annotations

import asyncio
import inspect
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable


class EventPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2


@dataclass(slots=True)
class Event:
    topic: str
    payload: Any
    source: str
    timestamp: float
    sequence: int
    priority: EventPriority = EventPriority.NORMAL


class EventBus:
    def __init__(self, history_size: int = 500, enable_async_delivery: bool = True) -> None:
        self._history: deque[Event] = deque(maxlen=history_size)
        self._subscribers: dict[str, list[Callable[[Event], Any]]] = {}
        self._state: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._sequence = 0
        self._errors = 0
        self._published_at: deque[float] = deque(maxlen=1000)
        
        # Async event delivery
        self._enable_async_delivery = enable_async_delivery
        self._event_queue: asyncio.PriorityQueue | None = None
        self._delivery_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_async_loop(self) -> None:
        """Ensure async delivery infrastructure is initialized"""
        if self._enable_async_delivery and self._event_queue is None:
            try:
                self._loop = asyncio.get_running_loop()
                self._event_queue = asyncio.PriorityQueue()
                self._delivery_task = self._loop.create_task(self._delivery_loop(), name="event_bus_delivery")
            except RuntimeError:
                # No running loop, will use synchronous delivery
                self._enable_async_delivery = False

    async def _delivery_loop(self) -> None:
        """Async event delivery loop for high throughput"""
        while True:
            try:
                priority, event = await self._event_queue.get()
                with self._lock:
                    listeners = [*self._subscribers.get(event.topic, []), *self._subscribers.get("*", [])]
                for listener in listeners:
                    try:
                        result = listener(event)
                        if inspect.isawaitable(result):
                            await result
                    except Exception:
                        with self._lock:
                            self._errors += 1
                self._event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                continue

    def publish(self, topic: str, payload: Any, source: str = "runtime", priority: EventPriority = EventPriority.NORMAL) -> Event:
        self._ensure_async_loop()
        
        with self._lock:
            self._sequence += 1
            event = Event(topic, payload, source, time.time(), self._sequence, priority)
            self._history.append(event)
            self._published_at.append(event.timestamp)
        
        # Use async delivery if available
        if self._enable_async_delivery and self._event_queue is not None:
            # Priority queue uses tuple (priority, sequence) for ordering
            # Lower priority value = higher priority (enum values: LOW=0, NORMAL=1, HIGH=2)
            # We invert to make HIGH priority come first
            priority_value = 2 - priority.value
            asyncio.run_coroutine_threadsafe(
                self._event_queue.put((priority_value, self._sequence, event)),
                self._loop
            )
        else:
            # Synchronous delivery (fallback)
            with self._lock:
                listeners = [*self._subscribers.get(topic, []), *self._subscribers.get("*", [])]
            for listener in listeners:
                try:
                    result = listener(event)
                    if inspect.isawaitable(result):
                        try:
                            asyncio.get_running_loop().create_task(result)
                        except RuntimeError:
                            asyncio.run(result)
                except Exception:
                    with self._lock:
                        self._errors += 1
        
        return event

    def subscribe(self, topic: str, callback: Callable[[Event], Any]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.setdefault(topic, []).append(callback)

        def unsubscribe() -> None:
            with self._lock:
                listeners = self._subscribers.get(topic, [])
                if callback in listeners:
                    listeners.remove(callback)

        return unsubscribe

    def set_state(self, key: str, value: Any, source: str = "runtime") -> None:
        with self._lock:
            self._state[key] = value
        self.publish(f"state.{key}", value, source)

    def get_state(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._state.get(key, default)

    def state_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(event) for event in list(self._history)[-limit:]]

    def metrics(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            while self._published_at and now - self._published_at[0] > 10:
                self._published_at.popleft()
            queue_size = self._event_queue.qsize() if self._event_queue else 0
            return {
                "events_per_sec": round(len(self._published_at) / 10, 2),
                "subscriber_error_count": self._errors,
                "published_count": self._sequence,
                "subscriber_count": sum(map(len, self._subscribers.values())),
                "async_delivery_enabled": self._enable_async_delivery,
                "queue_size": queue_size,
            }

    async def shutdown(self) -> None:
        """Shutdown async event delivery"""
        if self._delivery_task and not self._delivery_task.done():
            self._delivery_task.cancel()
            try:
                await self._delivery_task
            except asyncio.CancelledError:
                pass
        if self._event_queue:
            # Drain remaining events
            while not self._event_queue.empty():
                try:
                    self._event_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
