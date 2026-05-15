"""Logging handler that mirrors runtime logs onto the shared event bus."""

from __future__ import annotations

import logging

from core.event_bus import get_event_bus


class EventBusLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            get_event_bus().publish(
                "log.record",
                {
                    "level": record.levelname,
                    "logger": record.name,
                    "message": self.format(record),
                    "raw_message": record.getMessage(),
                    "created": record.created,
                },
                source="logging",
            )
        except Exception:
            pass


def install_event_log_handler() -> None:
    root = logging.getLogger()
    if any(isinstance(handler, EventBusLogHandler) for handler in root.handlers):
        return
    handler = EventBusLogHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(name)-20s] %(levelname)s: %(message)s"))
    root.addHandler(handler)


__all__ = ["EventBusLogHandler", "install_event_log_handler"]
