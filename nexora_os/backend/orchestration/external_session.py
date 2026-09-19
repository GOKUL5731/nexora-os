from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SessionState(str, Enum):
    CREATED = "CREATED"
    LAUNCHING = "LAUNCHING"
    READY = "READY"
    PROMPTING = "PROMPTING"
    WORKING = "WORKING"
    WAITING = "WAITING"
    NEEDS_INPUT = "NEEDS_INPUT"
    COMPLETED = "COMPLETED"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    DISCONNECTED = "DISCONNECTED"


_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.CREATED: {SessionState.LAUNCHING, SessionState.WAITING, SessionState.CANCELLED},
    SessionState.LAUNCHING: {SessionState.READY, SessionState.WAITING, SessionState.FAILED, SessionState.DISCONNECTED},
    SessionState.READY: {SessionState.PROMPTING, SessionState.CANCELLED, SessionState.DISCONNECTED},
    SessionState.PROMPTING: {SessionState.WORKING, SessionState.WAITING, SessionState.FAILED, SessionState.DISCONNECTED},
    SessionState.WORKING: {SessionState.WAITING, SessionState.NEEDS_INPUT, SessionState.COMPLETED, SessionState.FAILED, SessionState.DISCONNECTED, SessionState.CANCELLED},
    SessionState.WAITING: {SessionState.PROMPTING, SessionState.WORKING, SessionState.NEEDS_INPUT, SessionState.FAILED, SessionState.CANCELLED, SessionState.DISCONNECTED},
    SessionState.NEEDS_INPUT: {SessionState.PROMPTING, SessionState.CANCELLED, SessionState.BLOCKED},
    SessionState.COMPLETED: {SessionState.VERIFYING, SessionState.SUCCESS, SessionState.FAILED},
    SessionState.VERIFYING: {SessionState.SUCCESS, SessionState.FAILED, SessionState.BLOCKED},
    SessionState.SUCCESS: set(), SessionState.FAILED: {SessionState.PROMPTING, SessionState.BLOCKED},
    SessionState.BLOCKED: {SessionState.PROMPTING, SessionState.CANCELLED},
    SessionState.CANCELLED: set(), SessionState.DISCONNECTED: {SessionState.LAUNCHING, SessionState.CANCELLED},
}


@dataclass
class ExternalAgentSession:
    application: str
    project_id: str
    task_id: str
    workspace_id: str = ""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.CREATED
    window_id: str = ""
    prompt_history: list[dict[str, Any]] = field(default_factory=list)
    last_observation: dict[str, Any] = field(default_factory=dict)
    blocker: str = ""
    files_changed: list[str] = field(default_factory=list)
    retry_count: int = 0
    updated_at: float = field(default_factory=time.time)

    def transition(self, state: SessionState, reason: str = "") -> None:
        target = SessionState(state)
        if target == self.state:
            return
        if target not in _TRANSITIONS[self.state]:
            raise ValueError(f"Invalid session transition {self.state} -> {target}")
        self.state = target
        self.blocker = reason if target in {SessionState.WAITING, SessionState.NEEDS_INPUT, SessionState.BLOCKED, SessionState.FAILED} else ""
        self.updated_at = time.time()

    def record_prompt(self, content: str, delivery_status: str, result: dict[str, Any] | None = None) -> None:
        self.prompt_history.append({"content": content, "sent_at": time.time(), "delivery_status": delivery_status, "result": result or {}})
        self.updated_at = time.time()

    def observe(self, observation: dict[str, Any]) -> None:
        self.last_observation = dict(observation)
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["state"] = self.state.value
        return result
