"""Contextual awareness for current app, task, system state, and routines."""

from __future__ import annotations

import platform
from datetime import datetime
from typing import Any


class ContextualAwarenessEngine:
    """Collects lightweight context without taking disruptive actions."""

    def __init__(self, config: dict | None = None, event_bus: Any = None):
        self.config = config or {}
        self.event_bus = event_bus or self._try_bus()
        self._recent_actions: list[dict[str, Any]] = []

    def record_action(self, action: str, metadata: dict[str, Any] | None = None) -> None:
        self._recent_actions.append({"action": action, "metadata": metadata or {}, "timestamp": datetime.now().isoformat()})
        self._recent_actions = self._recent_actions[-100:]

    def current_context(self) -> dict[str, Any]:
        now = datetime.now()
        state = self.event_bus.state_snapshot() if self.event_bus else {}
        return {
            "time": {
                "iso": now.isoformat(),
                "hour": now.hour,
                "weekday": now.strftime("%A"),
                "daypart": self._daypart(now.hour),
            },
            "system": self._system_state(),
            "current_app": self._active_window(),
            "recent_actions": self._recent_actions[-15:],
            "workflow_context": {
                "running_workflows": state.get("running_workflows", []),
                "agents": state.get("agents", []),
                "health": state.get("health", {}),
            },
            "task_mode": self._infer_task_mode(),
        }

    def _infer_task_mode(self) -> str:
        text = " ".join(item["action"].lower() for item in self._recent_actions[-5:])
        if any(word in text for word in ["code", "debug", "test", "vscode"]):
            return "coding"
        if any(word in text for word in ["research", "summarize", "browser", "search"]):
            return "research"
        if any(word in text for word in ["train", "model", "dataset"]):
            return "training"
        return "general"

    @staticmethod
    def _system_state() -> dict[str, Any]:
        state = {"platform": platform.platform()}
        try:
            import psutil

            state.update(
                {
                    "cpu_percent": psutil.cpu_percent(interval=0.0),
                    "ram_percent": psutil.virtual_memory().percent,
                    "battery": getattr(psutil.sensors_battery(), "percent", None) if hasattr(psutil, "sensors_battery") else None,
                }
            )
        except Exception as exc:
            state["error"] = str(exc)
        return state

    @staticmethod
    def _active_window() -> dict[str, Any]:
        try:
            import win32gui

            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            return {"title": title, "handle": int(hwnd)}
        except Exception:
            return {"title": "", "handle": None}

    @staticmethod
    def _daypart(hour: int) -> str:
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 22:
            return "evening"
        return "night"

    @staticmethod
    def _try_bus() -> Any:
        try:
            from core.event_bus import get_event_bus

            return get_event_bus()
        except Exception:
            return None
