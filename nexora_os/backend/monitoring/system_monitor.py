from __future__ import annotations

import os
import threading
from typing import Any

from ..agents.runtime import AgentRuntime
from ..core.event_bus import EventBus
from ..core.module_manager import ModuleManager
from ..memory.engine import MemoryEngine
from ..workflows.engine import WorkflowEngine


class SystemMonitor:
    def __init__(self, bus: EventBus, modules: ModuleManager, agents: AgentRuntime, workflows: WorkflowEngine, memory: MemoryEngine) -> None:
        self.bus = bus
        self.modules = modules
        self.agents = agents
        self.workflows = workflows
        self.memory = memory

    def snapshot(self) -> dict[str, Any]:
        cpu = ram = 0.0
        process_mb = 0.0
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            process_mb = round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2)
        except ImportError:
            pass
        gpu = {"utilization": 0, "available": False, "name": ""}
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu = {
                "utilization": pynvml.nvmlDeviceGetUtilizationRates(handle).gpu,
                "available": True,
                "name": pynvml.nvmlDeviceGetName(handle),
            }
        except Exception:
            pass
        workflow_rows = self.workflows.list()
        agent_rows = self.agents.health()
        return {
            "cpu_percent": cpu,
            "memory_percent": ram,
            "process_memory_mb": process_mb,
            "gpu": gpu,
            "modules": self.modules.list(),
            "agents": agent_rows,
            "active_agents": sum(row["status"] == "running" for row in agent_rows),
            "workflows": workflow_rows,
            "active_workflows": sum(row["last_status"] == "running" for row in workflow_rows),
            "memory": {"chunks": self.memory.count()},
            "event_bus": self.bus.metrics(),
            "threads": threading.active_count(),
        }
