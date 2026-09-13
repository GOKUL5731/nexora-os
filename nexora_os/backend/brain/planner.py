from __future__ import annotations

import uuid
from typing import Any


class Planner:
    """Creates bounded structured plans from goals."""

    def __init__(self, capability_registry: Any) -> None:
        self.capabilities = capability_registry

    def create_plan(self, goal: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        goal_lower = goal.lower().strip()
        matched_caps = self.capabilities.search_by_goal(goal)
        primary_cap = matched_caps[0]["id"] if matched_caps else "model.ollama"

        if goal_lower.startswith(("learn ", "study ", "update ", "update your ", "index ")):
            plan = [
                {
                    "id": f"step_{uuid.uuid4().hex[:6]}",
                    "action": "learn_domain",
                    "capability": "knowledge.learn_retrieve",
                    "dependencies": [],
                    "status": "pending",
                }
            ]
        elif "research" in goal_lower or "explain" in goal_lower or "what do you know" in goal_lower:
            plan = [
                {
                    "id": f"step_{uuid.uuid4().hex[:6]}",
                    "action": "retrieve_knowledge",
                    "capability": "knowledge.learn_retrieve",
                    "dependencies": [],
                    "status": "pending",
                },
                {
                    "id": f"step_{uuid.uuid4().hex[:6]}",
                    "action": "synthesize_response",
                    "capability": "model.ollama",
                    "dependencies": [0],
                    "status": "pending",
                },
            ]
        elif "open" in goal_lower or "launch" in goal_lower or "click" in goal_lower:
            plan = [
                {
                    "id": f"step_{uuid.uuid4().hex[:6]}",
                    "action": "execute_ui_action",
                    "capability": "automation.local",
                    "dependencies": [],
                    "status": "pending",
                }
            ]
        else:
            plan = [
                {
                    "id": f"step_{uuid.uuid4().hex[:6]}",
                    "action": "evaluate_and_execute",
                    "capability": primary_cap,
                    "dependencies": [],
                    "status": "pending",
                }
            ]

        plan.append(
            {
                "id": f"step_{uuid.uuid4().hex[:6]}",
                "action": "verify_result",
                "capability": "brain.plan",
                "dependencies": [len(plan) - 1],
                "status": "pending",
            }
        )
        return plan
