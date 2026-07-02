from __future__ import annotations

from typing import Any

from ..agents.runtime import AgentRuntime
from ..memory.engine import MemoryEngine
from ..monitoring.system_monitor import SystemMonitor
from ..workflows.engine import WorkflowEngine
from .async_runtime import AsyncRuntime
from .event_bus import EventBus
from .module_manager import ModuleManager


class HealthMonitor:
    def __init__(
        self,
        bus: EventBus,
        modules: ModuleManager,
        agents: AgentRuntime,
        workflows: WorkflowEngine,
        memory: MemoryEngine,
        async_runtime: AsyncRuntime,
    ) -> None:
        self.bus = bus
        self.modules = modules
        self.agents = agents
        self.workflows = workflows
        self.memory = memory
        self.async_runtime = async_runtime
        self.system_monitor = SystemMonitor(bus, modules, agents, workflows, memory)

    def snapshot(self) -> dict[str, Any]:
        snap = self.system_monitor.snapshot()
        snap["async_runtime"] = self.async_runtime.health()
        return snap

    def startup_verification(self) -> dict[str, Any]:
        modules = self.modules.list()
        required = {"core_runtime", "event_bus", "module_manager", "logger", "async_runtime", "health_monitor"}
        present = {module["name"] for module in modules}
        missing = sorted(required - present)
        return {
            "ok": not missing and self.async_runtime.started,
            "missing_modules": missing,
            "registered_modules": sorted(present),
        }
