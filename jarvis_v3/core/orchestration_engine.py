"""Background autonomous orchestration layer that composes all engines."""

from __future__ import annotations

import asyncio
from typing import Any

from core.advanced_memory import AdvancedMemorySystem
from core.adaptive_personality import AdaptivePersonalityEngine
from core.autonomous_research import AutonomousResearchEngine
from core.collaboration_engine import CollaborationEngine
from core.cognitive_loop import ContinuousCognitiveLoop
from core.contextual_awareness import ContextualAwarenessEngine
from core.distributed_reasoning import DistributedReasoningEngine
from core.evolution_engine import AdvancedEvolutionEngine
from core.goal_manager import GoalManager
from core.graph_reasoning import GraphReasoningEngine
from core.knowledge_graph import KnowledgeGraph
from core.orchestration_core import GlobalOrchestrationCore
from core.planner_engine import PlanningEngine
from core.prediction_engine import PredictiveIntelligenceEngine
from core.proactive_engine import ProactiveAssistanceEngine
from core.reflective_memory import ReflectiveMemory
from core.reflection_engine import CognitiveReflectionEngine
from core.resource_orchestrator import ResourceOrchestrator
from core.self_healing_engine import SelfHealingEngine
from core.simulation_engine import SimulationEngine
from core.skill_evolution import SkillEvolutionEngine
from core.society_engine import AgentSocietyEngine
from core.world_model_engine import WorldModelEngine
from core.workflow_generator import WorkflowGenerator


class AutonomousOrchestrationEngine:
    """Coordinates goals, agents, simulation, memory, graph, resources, and reflection."""

    def __init__(
        self,
        config: dict | None = None,
        orchestrator: Any = None,
        agent_manager: Any = None,
        workflow_engine: Any = None,
    ):
        self.config = config or {}
        self.orchestrator = orchestrator
        self.planner = PlanningEngine(self.config)
        self.collaboration = CollaborationEngine(self.config, agent_manager=agent_manager)
        self.workflow_generator = WorkflowGenerator(self.config, workflow_engine=workflow_engine)
        self.prediction = PredictiveIntelligenceEngine(self.config)
        self.reflection = CognitiveReflectionEngine(self.config)
        self.evolution = AdvancedEvolutionEngine(self.config)
        self.reasoning = DistributedReasoningEngine(self.config, orchestrator=orchestrator)
        self.context = ContextualAwarenessEngine(self.config)
        self.proactive = ProactiveAssistanceEngine(self.config, self.workflow_generator)
        self.memory = AdvancedMemorySystem(self.config)
        self.graph = KnowledgeGraph(self.config)
        self.goals = GoalManager(self.config)
        self.simulation = SimulationEngine(self.config)
        self.society = AgentSocietyEngine(self.config, self.collaboration)
        self.world_model = WorldModelEngine(self.config, self.graph)
        self.graph_reasoning = GraphReasoningEngine(self.config, self.graph)
        self.research = AutonomousResearchEngine(self.config, memory=self.memory, collaboration=self.collaboration)
        self.skills = SkillEvolutionEngine(self.config)
        self.resources = ResourceOrchestrator(self.config)
        self.self_healing = SelfHealingEngine(self.config)
        self.personality = AdaptivePersonalityEngine(self.config)
        self.reflective_memory = ReflectiveMemory(self.config, self.memory)
        self.workflow_engine = workflow_engine
        self.meta_core = GlobalOrchestrationCore(self.config, autonomy=self)
        self.cognitive_loop = ContinuousCognitiveLoop(
            {
                "observe": self._loop_observe,
                "analyze": self._loop_analyze,
                "predict": self._loop_predict,
                "plan": self._loop_plan,
                "simulate": self._loop_simulate,
                "decide": self._loop_decide,
                "execute": self._loop_execute,
                "reflect": self._loop_reflect,
                "learn": self._loop_learn,
            },
            min_interval=float(self.config.get("cognitive_loop", {}).get("min_interval", 5.0)),
            max_interval=float(self.config.get("cognitive_loop", {}).get("max_interval", 120.0)),
        )
        self._background_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def handle_goal(self, goal: str, context: dict[str, Any] | None = None, execute: bool = True) -> dict[str, Any]:
        context = context or {}
        self.personality.observe_interaction(goal, context)
        self.context.record_action(goal, context)
        self.prediction.record_action(goal, context)
        goal_record = self.goals.create_goal(
            goal,
            context.get("goal_type", "user"),
            int(context.get("priority", 7)),
            context.get("dependencies", []),
            context,
        )
        self.memory.remember_episode("goal_received", goal, context, importance=0.7)
        plan = self.planner.create_plan(goal, {**context, "goal_id": goal_record["id"]})
        self.graph.ingest_plan(plan)
        self.world_model.update_goal_map([goal_record])
        simulation = self.simulation.simulate_plan(plan)
        if not execute:
            return {"goal": goal_record, "plan": plan, "simulation": simulation, "executed": False}
        if not simulation["passed"] and not context.get("force"):
            self.goals.update_progress(goal_record["id"], 0.05, status="blocked", event="simulation_blocked", detail=simulation)
            return {"goal": self.goals.get_goal(goal_record["id"]), "plan": plan, "simulation": simulation, "executed": False}
        schedule = self.resources.schedule(plan.get("tasks", []))
        result = await self.planner.execute_plan(
            plan["id"],
            self.collaboration,
            concurrency=schedule["concurrency"],
        )
        self.graph.ingest_plan(result)
        self.memory.remember_episode("goal_executed", goal, {"plan_id": plan["id"], "status": result["status"]}, 0.8)
        self.reflection.observe("orchestration", "goal", result["status"], data={"goal": goal, "plan_id": plan["id"]})
        progress = 1.0 if result["status"] == "completed" else 0.45
        goal_record = self.goals.update_progress(goal_record["id"], progress, status=result["status"], event="executed")
        for task in result.get("tasks", []):
            self.society.record_outcome(
                task["agent"],
                task["title"],
                task.get("status") == "completed",
                quality=0.8 if task.get("status") == "completed" else 0.2,
            )
        self.skills.record_result("workflow_optimization", 0.7 if result["status"] == "completed" else -0.4, {"goal": goal})
        return {"goal": goal_record, "plan": result, "simulation": simulation, "schedule": schedule, "executed": True}

    async def cognitive_tick(self) -> dict[str, Any]:
        cycle = await self.cognitive_loop.run_once()
        state = cycle.get("state", {})
        return {
            "cycle": cycle,
            "context": state.get("context", {}),
            "predictions": state.get("predictions", {}),
            "reflection": state.get("reflection", {}),
            "suggestions": state.get("suggestions", []),
            "goals": state.get("goals", {}),
            "resources": state.get("resources", {}),
            "world_model": state.get("world_model", {}),
            "society": state.get("society", {}),
        }

    async def meta_cognitive_tick(self, topic: str = "autonomous cognitive ecosystem") -> dict[str, Any]:
        return await self.meta_core.run_meta_cycle(topic)

    async def recursive_intelligence_tick(self, objective: str = "recursive adaptive intelligence") -> dict[str, Any]:
        return await self.meta_core.run_recursive_cycle(objective)

    async def civilization_tick(self, objective: str = "collective cognitive civilization") -> dict[str, Any]:
        return await self.meta_core.run_civilization_cycle(objective)

    def start_background(self, interval_seconds: float = 30.0) -> None:
        if self._background_task and not self._background_task.done():
            return
        self._stop = asyncio.Event()
        self._background_task = asyncio.create_task(self._background_loop(interval_seconds))

    async def stop_background(self) -> None:
        self._stop.set()
        if self._background_task:
            await self._background_task

    async def _background_loop(self, interval_seconds: float) -> None:
        while not self._stop.is_set():
            try:
                await self.cognitive_tick()
            except Exception as exc:
                self.reflection.observe("background_orchestration", "tick", "error", error=str(exc))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _loop_observe(self, state: dict[str, Any]) -> dict[str, Any]:
        ctx = self.context.current_context()
        resources = self.resources.snapshot()
        world_system = self.world_model.observe_system()
        goals = self.goals.progress_summary()
        self.world_model.update_goal_map(self.goals.list_goals(limit=100))
        return {"context": ctx, "resources": resources, "world_system": world_system, "goals": goals}

    async def _loop_analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        graph_validation = self.graph_reasoning.validate()
        opportunities = self.graph_reasoning.optimization_opportunities()
        anomalies = self.self_healing.detect_anomalies()
        world_model = self.world_model.snapshot(limit=150)
        return {
            "graph_validation": graph_validation,
            "optimization_opportunities": opportunities,
            "anomalies": anomalies,
            "world_model": world_model,
        }

    async def _loop_predict(self, state: dict[str, Any]) -> dict[str, Any]:
        ctx = state.get("context", {})
        recent = [item["action"] for item in ctx.get("recent_actions", [])]
        predictions = self.prediction.predict(recent)
        return {"predictions": predictions}

    async def _loop_plan(self, state: dict[str, Any]) -> dict[str, Any]:
        ready_goals = state.get("goals", {}).get("ready", [])
        if not ready_goals:
            return {"candidate_plan": None}
        top_goal = ready_goals[0]
        plan = self.planner.create_plan(top_goal["title"], {"goal_id": top_goal["id"], "autonomous": True})
        self.graph.ingest_plan(plan)
        return {"candidate_plan": plan}

    async def _loop_simulate(self, state: dict[str, Any]) -> dict[str, Any]:
        plan = state.get("candidate_plan")
        return {"plan_simulation": self.simulation.simulate_plan(plan) if plan else None}

    async def _loop_decide(self, state: dict[str, Any]) -> dict[str, Any]:
        decisions = []
        simulation = state.get("plan_simulation")
        if simulation and simulation["passed"] and simulation["risk_score"] < 0.45:
            decisions.append({"type": "execute_candidate_plan", "reason": "simulation_passed"})
        for anomaly in state.get("anomalies", []):
            decisions.append({"type": "recover_module", "module": anomaly.get("module")})
        return {"decisions": decisions}

    async def _loop_execute(self, state: dict[str, Any]) -> dict[str, Any]:
        recoveries = self.self_healing.recover(state.get("anomalies", [])) if state.get("anomalies") else []
        # Fully autonomous plan execution is intentionally conservative. The
        # loop prepares and simulates candidate plans, while handle_goal owns
        # execution unless a caller explicitly enables it through that API.
        return {"recoveries": recoveries}

    async def _loop_reflect(self, state: dict[str, Any]) -> dict[str, Any]:
        reflection = await self.reflection.run_cycle()
        workflow_suggestions = self.workflow_generator.suggest_from_patterns(min_count=2)
        suggestions = self.proactive.evaluate(
            state.get("context", {}),
            state.get("predictions", {}),
            reflection,
            workflow_suggestions,
        )
        return {"reflection": reflection, "suggestions": suggestions}

    async def _loop_learn(self, state: dict[str, Any]) -> dict[str, Any]:
        self.memory.store_fact("runtime", "last_context", state.get("context", {}))
        self.memory.store_fact("runtime", "last_predictions", state.get("predictions", {}))
        if state.get("reflection", {}).get("improvement_plan"):
            self.reflective_memory.remember_lesson(
                "latest_improvement_plan",
                "Reflection generated improvement actions.",
                "pending",
                state.get("reflection", {}),
                confidence=0.65,
            )
        skill_snapshot = self.skills.snapshot()
        society = self.society.snapshot()
        return {"skills": skill_snapshot, "society": society, "personality": self.personality.response_guidance()}

    def autonomy_snapshot(self) -> dict[str, Any]:
        snapshot = {
            "loop": self.cognitive_loop.snapshot(),
            "goals": self.goals.progress_summary(),
            "society": self.society.snapshot(),
            "skills": self.skills.snapshot(),
            "resources": self.resources.snapshot(),
            "world_model": self.world_model.snapshot(limit=100),
            "graph": {
                "validation": self.graph_reasoning.validate(),
                "opportunities": self.graph_reasoning.optimization_opportunities(),
            },
            "simulations": self.simulation.list_recent(limit=10),
            "research": self.research.list_reports(limit=10),
            "personality": self.personality.response_guidance(),
        }
        if hasattr(self, "meta_core"):
            snapshot["meta_ecosystem"] = self.meta_core.snapshot()
        return snapshot
