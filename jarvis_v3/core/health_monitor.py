"""System health snapshots for dashboard and startup verification."""

from __future__ import annotations

import platform
import threading
import time
from typing import Any

import psutil

from core.event_bus import EventBus, get_event_bus
from core.module_manager import ModuleManager, get_module_manager


class HealthMonitor:
    def __init__(self, bus: EventBus | None = None, modules: ModuleManager | None = None):
        self.bus = bus or get_event_bus()
        self.modules = modules or get_module_manager()

    def snapshot(self) -> dict[str, Any]:
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        gpu = self._gpu_status()
        modules = self.modules.run_health_checks()
        agents = self.bus.get_state("agents", [])
        workflows = self.bus.get_state("workflows", [])
        voice = self.bus.get_state("voice", {})
        plugins = self.bus.get_state("plugins", [])
        event_bus = self.bus.stats() if hasattr(self.bus, "stats") else {}
        async_runtime = self.bus.get_state("async_runtime", {})
        threads = self._thread_status()
        alerts = self._alerts(vm.percent, modules, event_bus, async_runtime)
        data = {
            "timestamp": time.time(),
            "platform": platform.platform(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": vm.percent,
            "memory_used_gb": round(vm.used / (1024 ** 3), 2),
            "memory_total_gb": round(vm.total / (1024 ** 3), 2),
            "storage_percent": disk.percent,
            "gpu": gpu,
            "modules": modules,
            "failed_modules": [m for m in modules.values() if m.get("status") in {"failed", "error"}],
            "agents": agents,
            "workflows": workflows,
            "voice": voice,
            "plugins": plugins,
            "threads": threads,
            "event_bus": event_bus,
            "async_runtime": async_runtime,
            "workflow_queue": {
                "running": self.bus.get_state("running_workflows", []),
                "count": len(self.bus.get_state("running_workflows", [])),
            },
            "alerts": alerts,
        }
        self.bus.set_state("health", data, source="health_monitor")
        if alerts:
            self.bus.publish("health.alert", {"alerts": alerts}, source="health_monitor")
        return data

    def startup_verification(self) -> dict[str, Any]:
        snap = self.snapshot()
        required = ["orchestrator", "memory", "agent_registry", "voice_engine", "workflow_engine"]
        module_map = snap.get("modules", {})
        missing = [name for name in required if name not in module_map]
        failed = snap.get("failed_modules", [])
        ok = not missing and not failed
        result = {"ok": ok, "missing": missing, "failed": failed, "snapshot": snap}
        self.bus.publish("health.startup", result, source="health_monitor")
        return result

    def report(self) -> dict[str, Any]:
        snap = self.snapshot()
        return {
            "ok": not snap.get("failed_modules") and not snap.get("alerts"),
            "timestamp": snap["timestamp"],
            "summary": {
                "cpu_percent": snap["cpu_percent"],
                "memory_percent": snap["memory_percent"],
                "gpu": snap["gpu"],
                "active_modules": len(snap["modules"]),
                "failed_modules": len(snap["failed_modules"]),
                "agents": len(snap["agents"]),
                "workflows": len(snap["workflows"]),
                "threads": snap["threads"]["count"],
                "event_bus_errors": snap["event_bus"].get("subscriber_error_count", 0),
            },
            "alerts": snap.get("alerts", []),
        }

    def _gpu_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {"cuda": False, "utilization": 0, "memory_percent": 0}
        try:
            import torch
            status["cuda"] = bool(torch.cuda.is_available())
            if status["cuda"]:
                status["name"] = torch.cuda.get_device_name(0)
                status["device_count"] = torch.cuda.device_count()
        except Exception as exc:
            status["torch_error"] = str(exc)

        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            status["utilization"] = int(util.gpu)
            status["memory_percent"] = int((mem.used / mem.total) * 100) if mem.total else 0
            status.setdefault("name", pynvml.nvmlDeviceGetName(handle))
        except Exception:
            pass
        return status

    def _thread_status(self) -> dict[str, Any]:
        threads = []
        for thread in threading.enumerate():
            threads.append({
                "name": thread.name,
                "ident": thread.ident,
                "daemon": thread.daemon,
                "alive": thread.is_alive(),
            })
        return {"count": len(threads), "threads": threads}

    def _alerts(
        self,
        memory_percent: float,
        modules: dict[str, Any],
        event_bus: dict[str, Any],
        async_runtime: dict[str, Any],
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        failed = [m for m in modules.values() if m.get("status") in {"failed", "error"}]
        if failed:
            alerts.append({"level": "error", "type": "module_failure", "count": len(failed)})
        if memory_percent >= 90:
            alerts.append({"level": "warning", "type": "memory_pressure", "value": memory_percent})
        if event_bus.get("subscriber_error_count", 0):
            alerts.append({
                "level": "warning",
                "type": "event_bus_errors",
                "count": event_bus.get("subscriber_error_count", 0),
            })
        if async_runtime and not async_runtime.get("thread_alive", True):
            alerts.append({"level": "error", "type": "async_runtime_stopped"})
        return alerts


__all__ = ["HealthMonitor"]
