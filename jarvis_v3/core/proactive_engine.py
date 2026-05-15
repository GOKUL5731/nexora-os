"""Proactive assistance and automation recommendation engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class ProactiveAssistanceEngine:
    """Turns context, predictions, and reflection output into useful actions."""

    def __init__(self, config: dict | None = None, workflow_generator: Any = None):
        self.config = config or {}
        self.workflow_generator = workflow_generator

    def evaluate(
        self,
        context: dict[str, Any],
        predictions: dict[str, Any] | None = None,
        reflection: dict[str, Any] | None = None,
        workflow_suggestions: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        system = context.get("system", {})
        if system.get("ram_percent", 0) >= 85:
            suggestions.append(
                {
                    "type": "system_warning",
                    "message": "Memory pressure is high; I can pause background orchestration.",
                    "action": "throttle_background_tasks",
                    "priority": 9,
                }
            )
        if context.get("task_mode") == "coding":
            suggestions.append(
                {
                    "type": "workspace",
                    "message": "Coding context detected; prepare tests and diagnostics.",
                    "action": "prepare_coding_workspace",
                    "priority": 6,
                }
            )
        for pred in (predictions or {}).get("predictions", [])[:3]:
            if pred.get("confidence", 0) >= 0.45:
                suggestions.append(
                    {
                        "type": "prediction",
                        "message": f"Likely next: {pred['action'].replace('_', ' ')}",
                        "action": pred["action"],
                        "confidence": pred["confidence"],
                        "priority": 5,
                    }
                )
        for item in (reflection or {}).get("improvement_plan", [])[:3]:
            suggestions.append(
                {
                    "type": "self_improvement",
                    "message": f"Optimize {item['target']} due to {item['reason']}.",
                    "action": "create_evolution_experiment",
                    "payload": item,
                    "priority": item.get("priority", 5),
                }
            )
        for item in (workflow_suggestions or [])[:3]:
            suggestions.append(
                {
                    "type": "automation",
                    "message": f"Create automation: {item['spec']['name']}",
                    "action": "save_workflow",
                    "payload": item["spec"],
                    "priority": int(item.get("score", 0.5) * 10),
                }
            )
        if context.get("time", {}).get("daypart") == "morning":
            suggestions.append(
                {
                    "type": "routine",
                    "message": "Morning routine available.",
                    "action": "morning_startup",
                    "priority": 4,
                }
            )
        suggestions.sort(key=lambda item: item.get("priority", 0), reverse=True)
        return suggestions

    async def execute_suggestion(self, suggestion: dict[str, Any], workflow_engine: Any = None) -> dict[str, Any]:
        action = suggestion.get("action")
        if action == "save_workflow" and self.workflow_generator:
            spec = suggestion.get("payload", {})
            if workflow_engine:
                workflow_engine.save_workflow(spec)
            return {"executed": True, "action": action, "workflow": spec.get("name")}
        if workflow_engine and action:
            workflow = workflow_engine.get_workflow(action)
            if workflow:
                return await workflow_engine.run(action)
        return {"executed": False, "action": action, "timestamp": datetime.now().isoformat()}
