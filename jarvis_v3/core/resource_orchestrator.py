"""Adaptive resource orchestration for models, workflows, and agents."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import psutil


@dataclass
class CachedModel:
    name: str
    size_mb: float = 0
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class ResourceOrchestrator:
    """Calculates resource pressure and produces bounded scheduling decisions."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        rcfg = self.config.get("resources", {})
        self.max_cached_models = int(rcfg.get("max_cached_models", 3))
        self._model_cache: dict[str, CachedModel] = {}

    def snapshot(self) -> dict[str, Any]:
        vm = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        disk = psutil.disk_usage("/")
        gpu = self._gpu_snapshot()
        pressure = min(1.0, cpu / 100 * 0.35 + vm.percent / 100 * 0.45 + gpu.get("memory_percent", 0) / 100 * 0.2)
        return {
            "cpu_percent": cpu,
            "memory_percent": vm.percent,
            "memory_available_gb": round(vm.available / (1024 ** 3), 2),
            "disk_percent": disk.percent,
            "gpu": gpu,
            "pressure_score": round(pressure, 3),
            "recommended_concurrency": self.recommended_concurrency(pressure),
            "cached_models": [model.__dict__ for model in self._model_cache.values()],
        }

    def recommended_concurrency(self, pressure: float | None = None) -> int:
        pressure = self.snapshot()["pressure_score"] if pressure is None else pressure
        return max(1, min(8, int(8 - pressure * 6)))

    def schedule(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        snap = self.snapshot()
        concurrency = snap["recommended_concurrency"]
        heavy_agents = {"tester", "coder", "optimizer", "vision"}
        sorted_tasks = sorted(
            tasks,
            key=lambda task: (task.get("agent") in heavy_agents, -task.get("priority", 5)),
        )
        return {
            "concurrency": concurrency,
            "resource_pressure": snap["pressure_score"],
            "batches": [sorted_tasks[i : i + concurrency] for i in range(0, len(sorted_tasks), concurrency)],
        }

    def cache_model(self, name: str, size_mb: float = 0, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if name in self._model_cache:
            self._model_cache[name].last_used = time.time()
            return {"cached": True, "evicted": [], "models": list(self._model_cache)}
        self._model_cache[name] = CachedModel(name=name, size_mb=size_mb, metadata=metadata or {})
        evicted = []
        while len(self._model_cache) > self.max_cached_models:
            oldest = min(self._model_cache.values(), key=lambda model: model.last_used)
            evicted.append(oldest.name)
            self._model_cache.pop(oldest.name, None)
        return {"cached": True, "evicted": evicted, "models": list(self._model_cache)}

    def unload_model(self, name: str) -> bool:
        return self._model_cache.pop(name, None) is not None

    @staticmethod
    def _gpu_snapshot() -> dict[str, Any]:
        status = {"available": False, "utilization": 0, "memory_percent": 0}
        try:
            import torch

            status["available"] = bool(torch.cuda.is_available())
            if status["available"]:
                status["device_count"] = torch.cuda.device_count()
                status["name"] = torch.cuda.get_device_name(0)
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
            status["available"] = True
        except Exception:
            pass
        return status
