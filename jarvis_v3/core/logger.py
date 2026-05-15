"""Centralized logging for JARVIS runtime infrastructure.

This module provides queue-backed, rotating, event-bus mirrored logging. It is
safe to call repeatedly from entrypoints; handlers are installed once.
"""

from __future__ import annotations

import logging
import queue
import sys
import time
from contextlib import contextmanager
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_LISTENER: QueueListener | None = None
_LOG_QUEUE: queue.Queue | None = None


def setup_runtime_logging(
    name: str = "jarvis",
    *,
    level: int = logging.INFO,
    log_file: str | Path | None = None,
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> logging.Logger:
    """Install centralized async-safe logging and return a module logger."""

    global _LISTENER, _LOG_QUEUE

    if sys.platform == "win32":
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = logging.getLogger()
    root.setLevel(level)

    if not any(isinstance(handler, QueueHandler) and getattr(handler, "_jarvis_queue_handler", False) for handler in root.handlers):
        _LOG_QUEUE = queue.Queue(-1)
        queue_handler = QueueHandler(_LOG_QUEUE)
        queue_handler._jarvis_queue_handler = True
        queue_handler.setLevel(level)
        root.addHandler(queue_handler)

        fmt = logging.Formatter("%(asctime)s [%(name)-24s] %(levelname)s: %(message)s")
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(fmt)
        file_handler = RotatingFileHandler(
            log_file or LOG_DIR / "jarvis.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        handlers: list[logging.Handler] = [stream, file_handler]

        try:
            from core.log_bus import EventBusLogHandler
            event_handler = EventBusLogHandler()
            event_handler.setLevel(level)
            event_handler.setFormatter(fmt)
            handlers.append(event_handler)
        except Exception:
            pass

        _LISTENER = QueueListener(_LOG_QUEUE, *handlers, respect_handler_level=True)
        _LISTENER.start()

    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger


def get_logger(module: str) -> logging.Logger:
    """Return a namespaced logger under `jarvis`."""

    setup_runtime_logging()
    if module.startswith("jarvis"):
        return logging.getLogger(module)
    return logging.getLogger(f"jarvis.{module}")


@contextmanager
def log_timing(logger: logging.Logger, operation: str, *, level: int = logging.INFO) -> Iterator[None]:
    """Log execution time for a runtime operation."""

    started = time.perf_counter()
    logger.log(level, "%s started", operation)
    try:
        yield
    except Exception:
        logger.exception("%s failed", operation)
        raise
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.log(level, "%s finished in %.2fms", operation, elapsed_ms)


def shutdown_runtime_logging() -> None:
    global _LISTENER
    if _LISTENER:
        _LISTENER.stop()
        _LISTENER = None


__all__ = ["get_logger", "log_timing", "setup_runtime_logging", "shutdown_runtime_logging"]
