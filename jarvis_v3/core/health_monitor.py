"""System health snapshots for dashboard and startup verification."""

from __future__ import annotations

import platform
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
        }
        self.bus.set_state("health", data, source="health_monitor")
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


__all__ = ["HealthMonitor"]
