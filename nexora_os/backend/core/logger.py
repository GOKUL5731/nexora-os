from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .event_bus import EventBus


class EventBusLogHandler(logging.Handler):
    def __init__(self, bus: EventBus) -> None:
        super().__init__(level=logging.WARNING)
        self.bus = bus

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.bus.publish(
                "log.record",
                {
                    "level": record.levelname,
                    "logger": record.name,
                    "message": self.format(record),
                },
                "logger",
            )
        except Exception:
            self.handleError(record)


def configure_core_logging(root: Path, bus: EventBus | None = None) -> logging.Logger:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nexora")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_path = log_dir / "nexora.log"

    if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        file_handler = RotatingFileHandler(file_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if bus and not any(isinstance(handler, EventBusLogHandler) for handler in logger.handlers):
        bus_handler = EventBusLogHandler(bus)
        bus_handler.setFormatter(formatter)
        logger.addHandler(bus_handler)

    logger.info("Core logging initialized at %s", file_path)
    return logger


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    suffix = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("%s%s", message, f" {suffix}" if suffix else "")
