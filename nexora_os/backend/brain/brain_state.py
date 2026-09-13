from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class BrainState:
    stage: str = "IDLE"
    current_goal_id: str = ""
    current_goal: str = ""
    current_plan: list[dict[str, Any]] = field(default_factory=list)
    selected_capability: str = ""
    active_model: str = ""
    verification_status: str = "UNKNOWN"
    last_error: str = ""
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["updated_at"] = time.time()
        return data
