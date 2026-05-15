from __future__ import annotations

import time
from collections import deque
from typing import Any

from core.event_bus import Event, EventBus, get_event_bus
from core.observability_engine import ObservabilityEngine


class EventTraceRecorder:
    """Mirrors live bus events into observability storage and shared state."""

    def __init__(
        self,
        bus: EventBus | None = None,
        observability: ObservabilityEngine | None = None,
        history_limit: int = 250,
    ):
        self.bus = bus or get_event_bus()
        self.observability = observability or ObservabilityEngine()
        self.history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self._unsubscribe = None
        self._last_persist = 0.0

    def start(self) -> None:
        if self._unsubscribe is None:
            self._unsubscribe = self.bus.subscribe("*", self._on_event)

    def stop(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def _on_event(self, event: Event) -> None:
        if event.topic.startswith("state.event_trace"):
            return
        item = {
            "topic": event.topic,
            "source": event.source,
            "timestamp": event.timestamp,
            "payload": self._summarize_payload(event.payload),
        }
        self.history.append(item)
        self.bus.set_state("event_trace", list(self.history)[-120:], source="event_tracer", publish=False)

        now = time.monotonic()
        if now - self._last_persist > 0.25:
            self._last_persist = now
            try:
                self.observability.record_trace(event.topic, item["payload"])
            except Exception:
                pass

    def _summarize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        for key, value in (payload or {}).items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                summary[key] = value if not isinstance(value, str) else value[:500]
            elif isinstance(value, (list, tuple)):
                summary[key] = {"type": type(value).__name__, "count": len(value)}
            elif isinstance(value, dict):
                summary[key] = {"type": "dict", "keys": list(value.keys())[:12]}
            else:
                summary[key] = str(value)[:200]
        return summary
