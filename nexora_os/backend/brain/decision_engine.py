from __future__ import annotations

import time
from typing import Any

from ..core.event_bus import EventBus


class DecisionEngine:
    """
    Block 2: Central Brain — Decision Engine.

    Takes a goal, context, plan, and available capabilities and decides:
    - Which capability to use
    - Whether to proceed autonomously or request user confirmation
    - What the fallback strategy is if the primary path fails
    """

    # Risk level → required autonomy level
    RISK_THRESHOLDS = {
        "none": 1,
        "low": 2,
        "medium": 3,
        "high": 4,
        "critical": 5,
    }

    def __init__(self, bus: EventBus, autonomy_level: int = 3) -> None:
        self.bus = bus
        self.autonomy_level = autonomy_level
        self._decision_log: list[dict[str, Any]] = []

    def decide(
        self,
        goal: str,
        plan: list[dict[str, Any]],
        tool_info: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Make a decision about how to proceed with a goal.
        Returns a decision dict with: action, capability, risk_level, requires_confirmation, fallback.
        """
        risk_level = tool_info.get("risk_level", "low")
        capability = tool_info.get("tool", "model.ollama")
        required_autonomy = self.RISK_THRESHOLDS.get(risk_level, 2)

        # Can we proceed autonomously?
        can_proceed = self.autonomy_level >= required_autonomy
        requires_confirmation = not can_proceed

        # Determine fallback capability
        fallback = self._select_fallback(capability, risk_level)

        decision = {
            "goal": goal,
            "selected_capability": capability,
            "risk_level": risk_level,
            "can_proceed": can_proceed,
            "requires_confirmation": requires_confirmation,
            "fallback_capability": fallback,
            "steps": len(plan),
            "timestamp": time.time(),
        }

        self._decision_log.append(decision)
        self.bus.publish("brain.decision", decision, "decision_engine")
        return decision

    def _select_fallback(self, primary: str, risk_level: str) -> str:
        """Select a safe fallback capability."""
        if risk_level in ("high", "critical"):
            return "user.confirm"
        if primary.startswith("automation"):
            return "model.ollama"
        return "memory.retrieve_store"

    def get_decision_log(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._decision_log[-limit:]

    def set_autonomy_level(self, level: int) -> None:
        """Dynamically adjust the autonomy level (1-5)."""
        self.autonomy_level = max(1, min(5, level))
        self.bus.publish("brain.autonomy.changed", {"level": self.autonomy_level}, "decision_engine")
