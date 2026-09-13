from __future__ import annotations

import time
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from ..core.event_bus import EventBus


@dataclass(slots=True)
class BrainState:
    """Richer runtime state snapshot for the Central Brain."""
    stage: str = "IDLE"
    current_goal_id: str = ""
    current_goal: str = ""
    current_plan: list[dict[str, Any]] = field(default_factory=list)
    selected_capability: str = ""
    active_model: str = ""
    verification_status: str = "UNKNOWN"
    last_error: str = ""
    autonomy_level: int = 3
    session_id: str = "default"
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["updated_at"] = time.time()
        return data


class StateManager:
    """
    Block 2: Central Brain — State Manager.

    Owns the canonical BrainState and propagates changes via the EventBus.
    All Brain components should read/write state through this manager,
    never mutating BrainState directly.
    """

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._state = BrainState()
        self._lock = threading.RLock()
        self._history: List[Dict[str, Any]] = []

    def transition(self, stage: str, **updates: Any) -> None:
        """Move to a new cognitive stage and optionally update fields."""
        with self._lock:
            self._state.stage = stage
            self._state.updated_at = time.time()
            for key, value in updates.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            snapshot = self._state.to_dict()
            self._history.append(snapshot)

        self.bus.set_state("brain", snapshot, "state_manager")
        self.bus.publish("brain.state.changed", snapshot, "state_manager")

    def get(self) -> BrainState:
        with self._lock:
            return self._state

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._state.to_dict()

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return self._history[-limit:]

    def reset(self) -> None:
        """Reset the brain to IDLE state."""
        with self._lock:
            self._state = BrainState()
        self.bus.publish("brain.state.reset", {}, "state_manager")
