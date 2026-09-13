from __future__ import annotations

import time
from typing import Any, Awaitable, Callable


class ExecutionEngine:
    """Unified execution engine that dispatches bounded plan steps."""

    def __init__(self, bus: Any, executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]) -> None:
        self.bus = bus
        self.executor = executor

    async def execute_plan(self, goal_id: str, plan: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for step in plan:
            self.bus.publish("step.started", {"goal_id": goal_id, "step_id": step["id"], "action": step["action"]}, "execution_engine")
            started = time.perf_counter()
            try:
                action = step.get("action", "")
                if action == "verify_result":
                    prior_ok = bool(results) and all(item.get("ok", False) for item in results)
                    result = {"ok": prior_ok, "message": "Prior steps verified." if prior_ok else "Prior step failed."}
                elif action == "retrieve_knowledge":
                    result = {"ok": True, "message": "Knowledge retrieved.", "knowledge": context.get("relevant_knowledge", []), "memories": context.get("relevant_memories", [])}
                else:
                    target_text = context.get("request", action)
                    result = await self.executor(target_text, {**context, "step": step, "step_action": action})

                step_result = {
                    "step_id": step["id"],
                    "action": action,
                    "ok": bool(result.get("ok", False)),
                    "result": result,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
                results.append(step_result)
                step["status"] = "completed" if step_result["ok"] else "failed"
                self.bus.publish("step.completed" if step_result["ok"] else "step.failed", step_result, "execution_engine")
                if not step_result["ok"]:
                    return {"ok": False, "error": f"Step {step['id']} failed", "results": results}
            except Exception as exc:
                step["status"] = "failed"
                step_result = {"step_id": step["id"], "action": step.get("action", ""), "ok": False, "error": str(exc)}
                results.append(step_result)
                self.bus.publish("step.failed", step_result, "execution_engine")
                return {"ok": False, "error": str(exc), "results": results}
        return {"ok": True, "results": results}
