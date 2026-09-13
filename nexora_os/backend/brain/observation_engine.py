from __future__ import annotations

from typing import Any


class ObservationEngine:
    """
    Observes the results of execution in real-time, checking side effects.
    """
    def __init__(self, bus: Any) -> None:
        self.bus = bus

    def observe(self, action: str, result: dict[str, Any]) -> dict[str, Any]:
        """
        Observes side effects beyond just the return value of an action.
        """
        # A full system would check screen state, file system state, etc.
        # Here we structure the observation output.
        return {
            "action": action,
            "raw_result": result,
            "observed_side_effects": [],
            "status": "success" if result.get("ok") else "failure"
        }
