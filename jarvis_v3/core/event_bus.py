"""Thread-safe event bus and shared runtime state for JARVIS.

The bus is intentionally dependency-free so it can be used by CLI, Qt UI,
background threads, agents, plugins, and tests. UI code should poll snapshots or
bridge events onto Qt signals instead of mutating widgets directly from bus
callbacks.
"""

from __future__ import annotations

import logging
import asyncio
import inspect
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("jarvis.event_bus")


@dataclass(frozen=True)
class Event:
    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    sequence: int = 0


Subscriber = Callable[[Event], None]


class EventBus:
    """Publish/subscribe backbone plus a small shared state store."""

    def __init__(self, history_limit: int = 500):
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self._history: deque[Event] = deque(maxlen=history_limit)
        self._state: dict[str, Any] = {}
        self._sequence = 0
        self._published_count = 0
        self._subscriber_error_count = 0
        self._last_event_at = 0.0
        self._last_error: dict[str, Any] | None = None

    def subscribe(self, topic: str, callback: Subscriber) -> Callable[[], None]:
        """Subscribe to a topic.

        A topic ending in ``.*`` receives events with that prefix. The ``*``
        topic receives every event. Returns an unsubscribe function.
        """
        with self._lock:
            self._subscribers[topic].append(callback)
            self._publish_stats_locked()

        def unsubscribe() -> None:
            with self._lock:
                callbacks = self._subscribers.get(topic, [])
                if callback in callbacks:
                    callbacks.remove(callback)
                self._publish_stats_locked()

        return unsubscribe

    def subscribe_async(self, topic: str, callback: Subscriber) -> Callable[[], None]:
        """Alias for async call sites.

        Async subscribers are accepted by :meth:`subscribe`; `publish_async`
        awaits them, while `publish` schedules them on a running loop when one
        exists.
        """
        return self.subscribe(topic, callback)

    def publish(self, topic: str, payload: dict[str, Any] | None = None, source: str = "") -> Event:
        event = self._create_event(topic, payload or {}, source)
        callbacks = self._matching_callbacks(topic)
        with self._lock:
            self._history.append(event)
            self._published_count += 1
            self._last_event_at = event.timestamp
            self._publish_stats_locked()
        for callback in callbacks:
            try:
                result = callback(event)
                if inspect.isawaitable(result):
                    self._schedule_awaitable(result, event)
            except Exception as exc:
                self._record_subscriber_error(event, exc)
        return event

    async def publish_async(self, topic: str, payload: dict[str, Any] | None = None, source: str = "") -> Event:
        """Publish an event and await async subscribers.

        Sync subscribers still run inline. Async subscriber failures are traced
        but do not block other subscribers.
        """
        event = self._create_event(topic, payload or {}, source)
        callbacks = self._matching_callbacks(topic)
        with self._lock:
            self._history.append(event)
            self._published_count += 1
            self._last_event_at = event.timestamp
            self._publish_stats_locked()

        awaits = []
        for callback in callbacks:
            try:
                result = callback(event)
                if inspect.isawaitable(result):
                    awaits.append(result)
            except Exception as exc:
                self._record_subscriber_error(event, exc)
        if awaits:
            results = await asyncio.gather(*awaits, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self._record_subscriber_error(event, result)
        return event

    def set_state(self, key: str, value: Any, *, source: str = "", publish: bool = True) -> None:
        with self._lock:
            self._state[key] = value
        if publish:
            self.publish(f"state.{key}", {"key": key, "value": value}, source=source)

    def get_state(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._state.get(key, default)

    def state_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def history(self, limit: int = 100, topic_prefix: str | None = None) -> list[Event]:
        with self._lock:
            items = list(self._history)
        if topic_prefix:
            items = [event for event in items if event.topic.startswith(topic_prefix)]
        return items[-limit:]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "published_count": self._published_count,
                "subscriber_error_count": self._subscriber_error_count,
                "subscriber_count": sum(len(v) for v in self._subscribers.values()),
                "topics": sorted(self._subscribers.keys()),
                "history_size": len(self._history),
                "state_keys": sorted(self._state.keys()),
                "last_event_at": self._last_event_at,
                "last_error": self._last_error,
            }

    def _matching_callbacks(self, topic: str) -> list[Subscriber]:
        with self._lock:
            callbacks = list(self._subscribers.get("*", []))
            callbacks.extend(self._subscribers.get(topic, []))
            for pattern, subs in self._subscribers.items():
                if pattern.endswith(".*") and topic.startswith(pattern[:-1]):
                    callbacks.extend(subs)
        return callbacks

    def _create_event(self, topic: str, payload: dict[str, Any], source: str) -> Event:
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
        return Event(topic=topic, payload=payload, source=source, sequence=sequence)

    def _record_subscriber_error(self, event: Event, exc: Exception) -> None:
        with self._lock:
            self._subscriber_error_count += 1
            self._last_error = {
                "topic": event.topic,
                "source": event.source,
                "error": str(exc),
                "timestamp": time.time(),
            }
            self._publish_stats_locked()
        logger.warning("Event subscriber failed for %s: %s", event.topic, exc)

    def _schedule_awaitable(self, awaitable: Any, event: Event) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if inspect.iscoroutine(awaitable):
                try:
                    from core.async_runtime import get_async_runtime
                    get_async_runtime().submit(awaitable, name=f"event:{event.topic}")
                    return
                except Exception as exc:
                    self._record_subscriber_error(event, exc)
                    return
            self._record_subscriber_error(event, RuntimeError("async subscriber published without running event loop"))
            return

        task = loop.create_task(awaitable)

        def _done(done_task: asyncio.Task) -> None:
            try:
                done_task.result()
            except Exception as exc:
                self._record_subscriber_error(event, exc)

        task.add_done_callback(_done)

    def _publish_stats_locked(self) -> None:
        self._state["event_bus"] = {
            "published_count": self._published_count,
            "subscriber_error_count": self._subscriber_error_count,
            "subscriber_count": sum(len(v) for v in self._subscribers.values()),
            "history_size": len(self._history),
            "last_event_at": self._last_event_at,
        }


_BUS = EventBus()


def get_event_bus() -> EventBus:
    return _BUS


__all__ = ["Event", "EventBus", "get_event_bus"]
