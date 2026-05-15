"""Thread-safe event bus and shared runtime state for JARVIS.

The bus is intentionally dependency-free so it can be used by CLI, Qt UI,
background threads, agents, plugins, and tests. UI code should poll snapshots or
bridge events onto Qt signals instead of mutating widgets directly from bus
callbacks.
"""

from __future__ import annotations

import logging
import threading
import time
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


Subscriber = Callable[[Event], None]


class EventBus:
    """Publish/subscribe backbone plus a small shared state store."""

    def __init__(self, history_limit: int = 500):
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self._history: deque[Event] = deque(maxlen=history_limit)
        self._state: dict[str, Any] = {}

    def subscribe(self, topic: str, callback: Subscriber) -> Callable[[], None]:
        """Subscribe to a topic.

        A topic ending in ``.*`` receives events with that prefix. The ``*``
        topic receives every event. Returns an unsubscribe function.
        """
        with self._lock:
            self._subscribers[topic].append(callback)

        def unsubscribe() -> None:
            with self._lock:
                callbacks = self._subscribers.get(topic, [])
                if callback in callbacks:
                    callbacks.remove(callback)

        return unsubscribe

    def publish(self, topic: str, payload: dict[str, Any] | None = None, source: str = "") -> Event:
        event = Event(topic=topic, payload=payload or {}, source=source)
        callbacks = self._matching_callbacks(topic)
        with self._lock:
            self._history.append(event)
        for callback in callbacks:
            try:
                callback(event)
            except Exception as exc:
                logger.debug("Event subscriber failed for %s: %s", topic, exc)
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

    def _matching_callbacks(self, topic: str) -> list[Subscriber]:
        with self._lock:
            callbacks = list(self._subscribers.get("*", []))
            callbacks.extend(self._subscribers.get(topic, []))
            for pattern, subs in self._subscribers.items():
                if pattern.endswith(".*") and topic.startswith(pattern[:-1]):
                    callbacks.extend(subs)
        return callbacks


_BUS = EventBus()


def get_event_bus() -> EventBus:
    return _BUS


__all__ = ["Event", "EventBus", "get_event_bus"]
