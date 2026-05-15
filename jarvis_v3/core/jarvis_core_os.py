"""
JARVIS CORE OS facade.

This object wires the perception, cognition, memory, action, evolution, and
safety layers into one local-first runtime that can be used by CLI, UI, service,
or tests.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime

from core.benchmark_engine import BenchmarkEngine
from core.command_engine import CommandEngine
from core.llm_router import LLMRouter
from core.orchestrator import JARVISOrchestrator
from core.reliability_engine import ReliabilityEngine
from core.safety_engine import PermissionEngine, SafetyEngine
from core.sandbox_engine import SandboxEngine
from core.upgrade_engine import EvolutionEngine
from core.voice_engine import VoiceEngine
from core.vision_engine import VisionEngine
from core.health_monitor import HealthMonitor
from core.module_manager import get_module_manager
from core.orchestration_engine import AutonomousOrchestrationEngine


@dataclass
class JarvisCoreOS:
    config: dict
    orchestrator: JARVISOrchestrator = field(init=False)
    router: LLMRouter = field(init=False)
    memory: object = field(init=False)
    command_engine: CommandEngine = field(init=False)
    reliability: ReliabilityEngine = field(init=False)
    safety: SafetyEngine = field(init=False)
    permissions: PermissionEngine = field(init=False)
    sandbox: SandboxEngine = field(init=False)
    benchmark: BenchmarkEngine = field(init=False)
    evolution: EvolutionEngine = field(init=False)
    voice: VoiceEngine = field(init=False)
    vision: VisionEngine = field(init=False)
    health_monitor: HealthMonitor = field(init=False)
    autonomy: AutonomousOrchestrationEngine = field(init=False)

    def __post_init__(self):
        self.orchestrator = JARVISOrchestrator(self.config)
        self.router = self.orchestrator.router
        self.memory = self.orchestrator.memory
        self.command_engine = self.orchestrator.commands
        self.reliability = self.orchestrator.reliability
        self.safety = SafetyEngine(self.config)
        self.permissions = self.orchestrator.perms
        self.sandbox = SandboxEngine(self.config)
        self.benchmark = BenchmarkEngine(self.config)
        self.evolution = EvolutionEngine(self.config, self.router)
        self.voice = VoiceEngine(self.config)
        self.vision = VisionEngine(self.config)
        self.health_monitor = HealthMonitor(modules=get_module_manager())
        self.autonomy = AutonomousOrchestrationEngine(self.config, orchestrator=self.orchestrator)
        get_module_manager().register("voice_engine", status="online", detail="Core OS voice ready")
        get_module_manager().register("vision_engine", status="online", detail="Core OS vision ready")
        get_module_manager().register("autonomous_intelligence", status="online", detail="Advanced planning/collaboration layer ready")

    async def process(self, user_input: str, context: dict | None = None) -> dict:
        return await self.orchestrator.process(user_input, context=context or {})

    def health(self) -> dict:
        runtime = self.health_monitor.snapshot()
        return {
            "status": "online",
            "timestamp": datetime.now().isoformat(),
            "python": sys.version.split()[0],
            "ollama_running": self.router.is_ollama_running(),
            "models": self.router.list_available(),
            "gpu": self._gpu_status(),
            "memory_interactions": self.memory.get_interaction_count(),
            "tools": len(self.orchestrator.registry.list_tools()),
            "autonomy": self.autonomy_status(),
            "modules": runtime.get("modules", {}),
            "failed_modules": runtime.get("failed_modules", []),
        }

    def autonomy_status(self) -> dict:
        snapshot = self.autonomy.autonomy_snapshot()
        return {
            "cognitive_loop": snapshot["loop"],
            "goals": snapshot["goals"]["status_counts"],
            "collaboration_agents": len(self.autonomy.collaboration.list_agents()),
            "society_agents": len(snapshot["society"]["agents"]),
            "memory": "episodic/semantic/procedural/agent",
            "graph_nodes": len(self.autonomy.graph.snapshot(limit=25).get("nodes", [])),
            "resource_pressure": snapshot["resources"]["pressure_score"],
        }

    def _gpu_status(self) -> dict:
        try:
            import torch
            if torch.cuda.is_available():
                return {
                    "cuda": True,
                    "name": torch.cuda.get_device_name(0),
                    "device_count": torch.cuda.device_count(),
                }
            return {"cuda": False, "reason": "torch reports no CUDA device"}
        except Exception as exc:
            return {"cuda": False, "reason": str(exc)}


__all__ = ["JarvisCoreOS"]
