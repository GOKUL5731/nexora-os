"""Runtime module lifecycle tracking for JARVIS subsystems."""

from __future__ import annotations

import logging
import asyncio
import inspect
import threading
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
    start: Callable[[], Any] | None = None
    stop: Callable[[], Any] | None = None
    health_check: Callable[[], Any] | None = None
    dependencies: list[str] = field(default_factory=list)
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
            "dependencies": list(self.dependencies),
            "error": self.error,
        }


class ModuleManager:
    """Tracks active, failed, and restartable JARVIS modules."""

    def __init__(self, bus: EventBus | None = None):
        self.bus = bus or get_event_bus()
        self._modules: dict[str, ModuleRecord] = {}
        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        *,
        status: str = "online",
        detail: str = "",
        restart: Callable[[], Any] | None = None,
        start: Callable[[], Any] | None = None,
        stop: Callable[[], Any] | None = None,
        health_check: Callable[[], Any] | None = None,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        module: Any = None,
    ) -> ModuleRecord:
        if module is not None:
            start = start or getattr(module, "start", None)
            stop = stop or getattr(module, "stop", None)
            restart = restart or getattr(module, "restart", None)
            health_check = health_check or getattr(module, "health_check", None)
            status_fn = getattr(module, "status", None)
            if callable(status_fn):
                try:
                    status_value = status_fn()
                    if isinstance(status_value, str):
                        status = status_value
                except Exception:
                    pass
        with self._lock:
            existing = self._modules.get(name)
            if existing:
                existing.status = status
                existing.detail = detail or existing.detail
                existing.restart = restart or existing.restart
                existing.start = start or existing.start
                existing.stop = stop or existing.stop
                existing.health_check = health_check or existing.health_check
                existing.dependencies = dependencies or existing.dependencies
                if metadata:
                    existing.metadata.update(metadata)
                existing.updated_at = time.time()
                record = existing
            else:
                record = ModuleRecord(
                    name=name,
                    status=status,
                    detail=detail,
                    restart=restart,
                    start=start,
                    stop=stop,
                    health_check=health_check,
                    dependencies=dependencies or [],
                    metadata=metadata or {},
                )
                self._modules[name] = record
        self._publish(record)
        return record

    def update(self, name: str, status: str, detail: str = "", **metadata: Any) -> None:
        with self._lock:
            record = self._modules.get(name) or self.register(name, status="loading")
            record.status = status
            record.detail = detail or record.detail
            record.updated_at = time.time()
            record.error = "" if status not in {"failed", "error"} else record.error
            if metadata:
                record.metadata.update(metadata)
        self._publish(record)

    def fail(self, name: str, exc: Exception | str, detail: str = "") -> None:
        with self._lock:
            record = self._modules.get(name) or self.register(name, status="loading")
            record.status = "failed"
            record.detail = detail or str(exc)
            record.error = "".join(traceback.format_exception_only(type(exc), exc)).strip() if isinstance(exc, Exception) else str(exc)
            record.updated_at = time.time()
        self._publish(record)
        logger.warning("Module failed [%s]: %s", name, record.error)

    async def start_module(self, name: str) -> dict[str, Any]:
        record = self._modules.get(name)
        if not record:
            return {"ok": False, "error": f"Unknown module: {name}"}
        missing = [dep for dep in record.dependencies if dep not in self._modules or self._modules[dep].status in {"failed", "error", "disabled"}]
        if missing:
            self.update(name, "failed", f"Missing dependencies: {', '.join(missing)}")
            return {"ok": False, "error": f"Missing dependencies: {missing}"}
        if not record.start:
            self.update(name, "running", "No explicit start hook")
            return {"ok": True, "result": None}
        try:
            self.update(name, "starting")
            result = await self._call(record.start)
            self.update(name, "running", "Started")
            self.bus.publish("module.started", record.to_dict(), source="module_manager")
            return {"ok": True, "result": result}
        except Exception as exc:
            self.fail(name, exc, "Start failed")
            return {"ok": False, "error": str(exc)}

    async def stop_module(self, name: str) -> dict[str, Any]:
        record = self._modules.get(name)
        if not record:
            return {"ok": False, "error": f"Unknown module: {name}"}
        if not record.stop:
            self.update(name, "disabled", "No explicit stop hook")
            return {"ok": True, "result": None}
        try:
            self.update(name, "stopping")
            result = await self._call(record.stop)
            self.update(name, "disabled", "Stopped")
            self.bus.publish("module.stopped", record.to_dict(), source="module_manager")
            return {"ok": True, "result": result}
        except Exception as exc:
            self.fail(name, exc, "Stop failed")
            return {"ok": False, "error": str(exc)}

    async def restart_module(self, name: str) -> dict[str, Any]:
        record = self._modules.get(name)
        if not record:
            return {"ok": False, "error": f"Unknown module: {name}"}
        try:
            self.update(name, "restarting")
            if record.restart:
                result = await self._call(record.restart)
            else:
                stop_result = await self.stop_module(name)
                if not stop_result.get("ok"):
                    return stop_result
                result = await self.start_module(name)
            self.update(name, "running", "Restarted")
            self.bus.publish("module.restarted", record.to_dict(), source="module_manager")
            return {"ok": True, "result": result}
        except Exception as exc:
            self.fail(name, exc, "Restart failed")
            return {"ok": False, "error": str(exc)}

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
        with self._lock:
            items = list(self._modules.items())
        for name, record in items:
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
        with self._lock:
            return [record.to_dict() for record in self._modules.values()]

    def failed_modules(self) -> list[dict[str, Any]]:
        with self._lock:
            return [record.to_dict() for record in self._modules.values() if record.status in {"failed", "error"}]

    def _publish(self, record: ModuleRecord) -> None:
        modules = self.list_modules()
        self.bus.set_state("modules", modules, source="module_manager")
        self.bus.publish("module.status", record.to_dict(), source="module_manager")

    async def _call(self, fn: Callable[[], Any]) -> Any:
        result = fn()
        if inspect.isawaitable(result):
            return await result
        return result


_MANAGER = ModuleManager()


def get_module_manager() -> ModuleManager:
    return _MANAGER


__all__ = ["ModuleManager", "ModuleRecord", "get_module_manager"]
