from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from core.event_bus import EventBus, get_event_bus
from core.health_monitor import HealthMonitor
from core.module_manager import ModuleManager, get_module_manager
from core.observability_engine import ObservabilityEngine

from jarvis_visual_core.observability import EventTraceRecorder

logger = logging.getLogger("jarvis.visual_runtime")


class JarvisVisualRuntime:
    """Single live runtime backing the visual JARVIS operating dashboard."""

    def __init__(self, config: dict):
        self.config = config
        self.bus: EventBus = get_event_bus()
        self.modules: ModuleManager = get_module_manager()
        self.health = HealthMonitor(bus=self.bus, modules=self.modules)
        self.observability = ObservabilityEngine(config)
        self.tracer = EventTraceRecorder(self.bus, self.observability)
        self.components: dict[str, Any] = {}
        self.started_at = time.time()
        self._started = False

    async def start(self) -> dict[str, Any]:
        if self._started:
            return self.snapshot()

        self.tracer.start()
        self.modules.register("event_bus", status="online", detail="Pub/sub and shared state ready")
        self.modules.register("visual_runtime", status="loading", detail="Starting integrated runtime")
        self._log("Starting JARVIS Visual Core runtime")

        await self._load_orchestrator()
        await self._load_voice()
        await self._load_phase2()
        await self._load_workflows()
        await self._load_agents()
        await self._load_self_improvement()
        await self._load_ai_lab()

        self._publish_memory_state()
        self.health.snapshot()
        self.modules.update("visual_runtime", "online", "Visual AI OS dashboard connected")
        self._started = True
        self.bus.publish("runtime.started", self.snapshot(), source="visual_runtime")
        return self.snapshot()

    async def shutdown(self) -> None:
        self._log("Shutting down visual runtime")
        voice = self.components.get("voice")
        if voice:
            try:
                voice.stop()
            except Exception:
                pass
        phase2 = self.components.get("phase2")
        if phase2:
            try:
                await phase2.shutdown()
            except Exception:
                pass
        self.tracer.stop()
        self.modules.update("visual_runtime", "disabled", "Runtime stopped")

    async def process_command(self, command: str, context: dict | None = None) -> dict[str, Any]:
        orchestrator = self.components.get("orchestrator")
        if not orchestrator:
            return {"type": "error", "message": "Orchestrator is offline."}
        self.bus.publish("console.command", {"command": command}, source="visual_runtime")
        result = await orchestrator.process(command, context=context or {"mode": "visual"})
        self._publish_memory_state()
        return result

    async def run_workflow(self, name: str, variables: dict | None = None) -> dict[str, Any]:
        engine = self.components.get("workflow_engine")
        if not engine:
            return {"error": "Workflow engine is offline"}
        return await engine.run(name, variables or {})

    def snapshot(self) -> dict[str, Any]:
        state = self.bus.state_snapshot()
        try:
            health = self.health.snapshot()
        except Exception as exc:
            health = {"error": str(exc)}
        state["health"] = health
        state["uptime_seconds"] = int(time.time() - self.started_at)
        state["timestamp"] = datetime.now().isoformat()
        state["observability"] = self.observability.dashboard(limit=30)
        return state

    def startup_diagnostics(self) -> dict[str, Any]:
        diag = self.health.startup_verification()
        router = getattr(self.components.get("orchestrator"), "router", None)
        diag["ollama_running"] = bool(router and router.is_ollama_running())
        diag["models"] = router.list_available() if router else []
        diag["required_agents"] = [
            "commander",
            "planner",
            "coder",
            "vision",
            "workflow",
            "researcher",
            "tester",
            "optimizer",
        ]
        agent_names = [a.get("name") for a in self.bus.get_state("agents", [])]
        diag["missing_agents"] = [a for a in diag["required_agents"] if a not in agent_names]
        self.bus.set_state("startup_diagnostics", diag, source="visual_runtime")
        self.bus.publish("diagnostics.startup", diag, source="visual_runtime")
        return diag

    async def _load_orchestrator(self) -> None:
        try:
            from core.orchestrator import JARVISOrchestrator
            orchestrator = JARVISOrchestrator(self.config)
            self.components["orchestrator"] = orchestrator
            self._log("Orchestrator online")
        except Exception as exc:
            self.modules.fail("orchestrator", exc)

    async def _load_voice(self) -> None:
        try:
            from core.voice import VoiceEngine
            voice = VoiceEngine(self.config)
            self.components["voice"] = voice
            self.modules.register("voice_engine", status="online", detail="STT/TTS ready")
            self._log("Voice engine online")
        except Exception as exc:
            self.modules.fail("voice_engine", exc)

    async def _load_phase2(self) -> None:
        try:
            from core.phase2.phase2_core import JARVISPhase2
            phase2 = JARVISPhase2(self.config)
            result = await phase2.start()
            self.components["phase2"] = phase2
            self.bus.set_state("phase2", phase2.get_status(), source="visual_runtime")
            status = "online" if result.get("status") == "ready" else "degraded"
            detail = "CNN/RNN/multimodal layer " + result.get("status", "unknown")
            self.modules.register("phase2_deep_learning", status=status, detail=detail, metadata=result)
            self._log(f"Phase 2 deep learning {result.get('status')}")
        except Exception as exc:
            self.modules.fail("phase2_deep_learning", exc)

    async def _load_workflows(self) -> None:
        try:
            from core.workflow_engine import WorkflowEngine
            workflow = WorkflowEngine(self.components.get("orchestrator"))
            workflow.install_default_workflows()
            self.components["workflow_engine"] = workflow
            self.modules.register("workflow_engine", status="online", detail="Workflow runtime ready")
            self._log("Workflow engine online")
        except Exception as exc:
            self.modules.fail("workflow_engine", exc)

    async def _load_agents(self) -> None:
        try:
            from core.agent_manager import AgentManager
            agents = AgentManager(self.config, self.components.get("orchestrator"))
            self.components["agent_manager"] = agents
            self.modules.register("agent_manager", status="online", detail=f"{len(agents._agents)} agents")
            self._log(f"Agent runtime online: {len(agents._agents)} agents")
        except Exception as exc:
            self.modules.fail("agent_manager", exc)

    async def _load_self_improvement(self) -> None:
        try:
            from core.self_improvement_engine import SelfImprovementEngine
            improver = SelfImprovementEngine(self.config, self.components.get("orchestrator"))
            self.components["self_improvement"] = improver
            self.modules.register("self_improvement", status="online", detail="Sandbox/test/deploy pipeline ready")
            self._log("Self-improvement pipeline online")
        except Exception as exc:
            self.modules.fail("self_improvement", exc)

    async def _load_ai_lab(self) -> None:
        try:
            from AI_LAB.lab_core import AILabCore
            lab = AILabCore(
                self.config,
                self.components.get("orchestrator"),
                self.components.get("agent_manager"),
                self.components.get("self_improvement"),
            )
            self.components["ai_lab"] = lab
            self.modules.register("ai_lab", status="online", detail="Experiment lab ready")
            self._log("AI LAB online")
        except Exception as exc:
            self.modules.fail("ai_lab", exc)

    def _publish_memory_state(self) -> None:
        memory = getattr(self.components.get("orchestrator"), "memory", None)
        if not memory:
            return
        try:
            payload = {
                "interactions": memory.get_interaction_count(),
                "recent_events": memory.recent_events(limit=20) if hasattr(memory, "recent_events") else [],
                "preferences": memory.get_preferences() if hasattr(memory, "get_preferences") else {},
            }
            self.bus.set_state("memory_network", payload, source="visual_runtime")
            self.bus.publish("memory.snapshot", payload, source="visual_runtime")
        except Exception as exc:
            self.bus.publish("memory.error", {"error": str(exc)}, source="visual_runtime")

    def _log(self, message: str, level: str = "info") -> None:
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
        self.bus.publish(f"log.{level}", {"message": message, "raw_message": message}, source="visual_runtime")
