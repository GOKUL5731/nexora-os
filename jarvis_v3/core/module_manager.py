"""Runtime module lifecycle tracking for JARVIS subsystems."""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from core.event_bus import EventBus, get_event_bus

logger = logging.getLogger("jarvis.modules")


@dataclass
class ModuleRecord:
    name: str
    status: str = "loading"
    detail: str = ""
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    restart: Callable[[], Any] | None = None
    health_check: Callable[[], Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
            "error": self.error,
        }


class ModuleManager:
    """Tracks active, failed, and restartable JARVIS modules."""

    def __init__(self, bus: EventBus | None = None):
        self.bus = bus or get_event_bus()
        self._modules: dict[str, ModuleRecord] = {}

    def register(
        self,
        name: str,
        *,
        status: str = "online",
        detail: str = "",
        restart: Callable[[], Any] | None = None,
        health_check: Callable[[], Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ModuleRecord:
        record = ModuleRecord(
            name=name,
            status=status,
            detail=detail,
            restart=restart,
            health_check=health_check,
            metadata=metadata or {},
        )
        self._modules[name] = record
        self._publish(record)
        return record

    def update(self, name: str, status: str, detail: str = "", **metadata: Any) -> None:
        record = self._modules.get(name) or self.register(name, status="loading")
        record.status = status
        record.detail = detail or record.detail
        record.updated_at = time.time()
        record.error = "" if status not in {"failed", "error"} else record.error
        if metadata:
            record.metadata.update(metadata)
        self._publish(record)

    def fail(self, name: str, exc: Exception | str, detail: str = "") -> None:
        record = self._modules.get(name) or self.register(name, status="loading")
        record.status = "failed"
        record.detail = detail or str(exc)
        record.error = "".join(traceback.format_exception_only(type(exc), exc)).strip() if isinstance(exc, Exception) else str(exc)
        record.updated_at = time.time()
        self._publish(record)
        logger.warning("Module failed [%s]: %s", name, record.error)

    def restart(self, name: str) -> dict[str, Any]:
        record = self._modules.get(name)
        if not record:
            return {"ok": False, "error": f"Unknown module: {name}"}
        if not record.restart:
            return {"ok": False, "error": f"Module is not restartable: {name}"}
        try:
            record.status = "restarting"
            self._publish(record)
            result = record.restart()
            record.status = "online"
            record.detail = "Restarted"
            record.updated_at = time.time()
            self._publish(record)
            return {"ok": True, "result": result}
        except Exception as exc:
            self.fail(name, exc, "Restart failed")
            return {"ok": False, "error": str(exc)}

    def run_health_checks(self) -> dict[str, Any]:
        results = {}
        for name, record in list(self._modules.items()):
            if not record.health_check:
                results[name] = record.to_dict()
                continue
            try:
                health = record.health_check()
                if isinstance(health, dict):
                    record.metadata.update(health)
                    status = health.get("status")
                    if status:
                        record.status = status
                record.updated_at = time.time()
                results[name] = record.to_dict()
                self._publish(record)
            except Exception as exc:
                self.fail(name, exc, "Health check failed")
                results[name] = self._modules[name].to_dict()
        return results

    def list_modules(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self._modules.values()]

    def failed_modules(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self._modules.values() if record.status in {"failed", "error"}]

    def _publish(self, record: ModuleRecord) -> None:
        modules = self.list_modules()
        self.bus.set_state("modules", modules, source="module_manager")
        self.bus.publish("module.status", record.to_dict(), source="module_manager")


_MANAGER = ModuleManager()


def get_module_manager() -> ModuleManager:
    return _MANAGER


__all__ = ["ModuleManager", "ModuleRecord", "get_module_manager"]
