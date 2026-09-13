from __future__ import annotations

from typing import Any


class AutonomyController:
    """
    Enforces explicit autonomy levels (0-4) and blocks high-risk actions.
    """
    def __init__(self, level: int = 2) -> None:
        self.level = level

    def check_permission(self, action: str, risk_level: str) -> dict[str, Any]:
        """
        Checks if the requested action is permitted under the current autonomy level.

        LEVEL 0: Answer only.
        LEVEL 1: Plan and recommend.
        LEVEL 2: Execute low-risk reversible actions.
        LEVEL 3: Execute approved workflows and multi-step tasks.
        LEVEL 4: Background proactive assistance.
        """
        if self.level == 0:
            if risk_level != "none":
                return {"permitted": False, "reason": "Autonomy Level 0 prohibits all execution."}

        if self.level == 1:
            if risk_level not in ["none", "read_only"]:
                return {"permitted": False, "reason": "Autonomy Level 1 permits only planning and reading."}

        if self.level == 2:
            if risk_level in ["high", "critical"]:
                return {"permitted": False, "reason": "Autonomy Level 2 prohibits high-risk actions (e.g. deletion, system changes)."}

        if self.level == 3:
            if risk_level == "critical":
                return {"permitted": False, "reason": "Autonomy Level 3 prohibits critical irreversible actions without explicit prompt."}

        # Level 4 allows most things within explicit configured permissions

        return {"permitted": True}
