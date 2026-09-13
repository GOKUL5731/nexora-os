from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from ..core.event_bus import EventBus
from ..memory.engine import MemoryEngine
from .brain_state import BrainState
from .capability_registry import CapabilityRegistry
from .goal_manager import GoalManager
from .context_manager import ContextManager
from .planner import Planner
from .model_router import ModelRouter
from .tool_router import ToolRouter
from .execution_engine import ExecutionEngine
from .observation_engine import ObservationEngine
from .verifier import Verifier
from .reflection_engine import ReflectionEngine
from .autonomy_controller import AutonomyController

Executor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class CognitiveCore:
    LOOP = ["PERCEIVE", "UNDERSTAND", "RETRIEVE_MEMORY", "REASON", "FORM_GOAL", "SELECT_CAPABILITY", "EXECUTE", "OBSERVE_RESULT", "VERIFY", "REFLECT", "LEARN", "COMPLETE"]

    def __init__(
        self,
        bus: EventBus,
        memory: MemoryEngine,
        goals: GoalManager,
        capabilities: CapabilityRegistry,
        executor: Executor,
        model_status: Callable[[], dict[str, Any]],
        knowledge: Any | None = None,
    ) -> None:
        self.bus = bus
        self.memory = memory
        self.goals = goals
        self.capabilities = capabilities
        self.model_status = model_status
        self.knowledge = knowledge
        self.state = BrainState()
        self.context_manager = ContextManager(self.memory)
        self.planner = Planner(self.capabilities)
        self.model_router = ModelRouter(self.model_status)
        self.tool_router = ToolRouter(self.capabilities)
        self.execution_engine = ExecutionEngine(self.bus, executor)
        self.observation_engine = ObservationEngine(self.bus)
        self.verifier = Verifier()
        self.reflection_engine = ReflectionEngine(self.memory)
        self.autonomy = AutonomyController(level=3)

    async def process_request(
        self,
        input_text: str,
        source: str = "text",
        context: dict[str, Any] | None = None,
        permissions: dict[str, Any] | None = None,
        session_id: str = "default",
    ) -> dict[str, Any]:
        context = context or {}
        permissions = permissions or {}
        started = time.perf_counter()
        goal = self.goals.create_goal(input_text)
        self._stage("PERCEIVE", goal, source=source, session_id=session_id)
        try:
            self._stage("UNDERSTAND", goal)
            self.goals.update_goal(goal["id"], status="PLANNING")

            self._stage("RETRIEVE_MEMORY", goal)
            unified_context = self.context_manager.build_context(input_text, source, {**context, "permissions": permissions})
            if self.knowledge:
                unified_context["relevant_knowledge"] = self.knowledge.search(input_text, limit=5)

            self._stage("REASON", goal)
            # The REASON stage allows the system to pause and analyze context before planning.
            reasoning_result = self.model_router.route("reasoning", unified_context)
            if reasoning_result:
                unified_context["reasoning_insight"] = "Reasoning complete based on context."

            self._stage("FORM_GOAL", goal)
            plan = self.planner.create_plan(input_text, unified_context)
            self.goals.update_goal(goal["id"], status="READY", execution_plan=plan)

            self._stage("SELECT_CAPABILITY", goal, current_plan=plan)
            tool_info = self.tool_router.select_tool(input_text, [])
            auth = self.autonomy.check_permission(input_text, tool_info["risk_level"])
            if not auth.get("permitted"):
                raise PermissionError(auth.get("reason"))
            model_info = self.model_router.route("reasoning", {})
            selected_capability = plan[0].get("capability") if plan else tool_info["tool"]
            self.state.active_model = str(model_info.get("selected_model") or "")
            self.goals.update_goal(goal["id"], required_capabilities=[str(selected_capability)])

            self._stage("EXECUTE", goal, current_plan=plan, selected_capability=str(selected_capability))
            self.goals.update_goal(goal["id"], status="EXECUTING")
            execution_res = await self.execution_engine.execute_plan(goal["id"], plan, unified_context)
            execution_results = execution_res.get("results", [])

            self._stage("OBSERVE_RESULT", goal)
            observations = [self.observation_engine.observe(step.get("action", ""), step.get("result", {})) for step in execution_results]

            self._stage("VERIFY", goal)
            verification = self.verifier.verify(input_text, execution_results, observations)
            verified = verification.get("verified", False)
            verification_status = verification.get("status", "FAILED")
            self.goals.update_goal(
                goal["id"],
                status="COMPLETED" if verified else "FAILED",
                completed_steps=[step["id"] for step in plan] if verified else [],
                failed_steps=[] if verified else [item.get("step_id", "execute") for item in execution_results if not item.get("ok")],
                current_blocker="" if verified else verification.get("reason", "Verification failed"),
                result={"execution": execution_results, "observations": observations},
                verification_status=verification_status,
            )

            self._stage("REFLECT", goal, verification_status=verification_status)
            reflection = self.reflection_engine.reflect(input_text, verification, plan, execution_results)

            self._stage("LEARN", goal)
            if self.knowledge and reflection.get("summary"):
                self.knowledge.index_text(
                    domain="self_reflection",
                    title=f"Insight from {goal['id']}",
                    content=reflection["summary"],
                    source="reflection_engine",
                    tags=["reflection", "learning"]
                )

            primary_result: dict[str, Any] = {}
            for item in execution_results:
                if item.get("action") == "verify_result":
                    continue
                result = item.get("result")
                if isinstance(result, dict):
                    primary_result = result
                    break
            response = {
                "type": "success" if verified else "error",
                "ok": verified,
                "message": reflection.get("summary", "Task completed."),
                "goal_id": goal["id"],
                "brain": self.snapshot(),
                "execution_results": execution_results,
            }
            if primary_result:
                response.update({k: v for k, v in primary_result.items() if k not in {"ok"}})
            self.bus.publish("runtime.response", response, "central_brain")
            self._stage("COMPLETE" if verified else "FAILED", goal, verification_status=verification_status)
            return response
        except Exception as exc:
            self.goals.update_goal(
                goal["id"],
                status="FAILED",
                current_blocker=str(exc),
                result={"error": str(exc)},
                verification_status="FAILED",
            )
            self._stage("FAILED", goal, last_error=str(exc), verification_status="FAILED")
            response = {"type": "error", "ok": False, "message": str(exc), "goal_id": goal["id"], "brain": self.snapshot()}
            self.bus.publish("runtime.response", response, "central_brain")
            return response
        finally:
            self.bus.publish(
                "brain.request.completed",
                {"goal_id": goal["id"], "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
                "central_brain",
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            **self.state.to_dict(),
            "goals": self.goals.list_goals(5),
            "capabilities": self.capabilities.discover_capabilities(),
            "models": self.model_status(),
            "knowledge": self.knowledge.status() if self.knowledge else {},
        }

    def _stage(self, stage: str, goal: dict[str, Any], **updates: Any) -> None:
        self.state.stage = stage
        self.state.current_goal_id = goal["id"]
        self.state.current_goal = goal["normalized_objective"]
        self.state.updated_at = time.time()
        for key, value in updates.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        snapshot = self.snapshot()
        self.bus.set_state("brain", snapshot, "central_brain")
        self.bus.publish("brain.state.changed", snapshot, "central_brain")
