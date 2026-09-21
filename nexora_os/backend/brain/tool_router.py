from __future__ import annotations

import re
from typing import Any


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class ToolRouter:
    """
    Risk-aware capability selection layer.

    The router consumes the live CapabilityRegistry instead of returning
    hard-coded pretend connector names. It produces auditable routing evidence
    that downstream goal state and UI can expose.
    """

    INTENT_HINTS: tuple[tuple[set[str], tuple[str, ...]], ...] = (
        ({"browser", "url", "website", "google", "search", "web", "page"}, ("connector.browser", "automation.local")),
        ({"file", "folder", "directory", "read", "write", "create", "delete", "remove"}, ("connector.filesystem", "automation.local")),
        ({"terminal", "command", "powershell", "cmd", "shell"}, ("connector.terminal", "automation.local")),
        ({"app", "launch", "open", "process", "window"}, ("connector.desktop", "automation.local")),
        ({"camera", "webcam", "vision", "ocr", "screen", "screenshot"}, ("vision.capture", "automation.local")),
        ({"voice", "listen", "speak", "audio", "microphone", "tts", "stt"}, ("voice.listen_speak",)),
        ({"workflow", "flow", "graph", "schedule"}, ("workflow.execute",)),
        ({"learn", "study", "knowledge", "research", "index"}, ("knowledge.learn_retrieve",)),
        ({"memory", "remember", "recall", "context"}, ("memory.retrieve_store",)),
        ({"agent", "plan", "inspect", "analyze"}, ("brain.plan",)),
    )

    HIGH_RISK_WORDS = {
        "delete",
        "remove",
        "erase",
        "kill",
        "terminate",
        "shutdown",
        "restart",
        "reboot",
        "install",
        "uninstall",
        "format",
        "permission",
        "secret",
        "token",
        "password",
    }

    def __init__(self, capability_registry: Any) -> None:
        self.capabilities = capability_registry

    def select_tool(self, action: str, required_permissions: list[str] | None = None) -> dict[str, Any]:
        """
        Select the safest available capability for an action.

        Returns a stable structure with both the selected capability id and the
        legacy `tool` key for existing callers.
        """

        required_permissions = required_permissions or []
        candidates = self._candidate_capabilities(action)
        if not candidates:
            candidates = self._discover()

        scored = [
            (self._score(action, candidate, required_permissions), candidate)
            for candidate in candidates
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        selected = scored[0][1] if scored else None

        if not selected:
            return {
                "ok": False,
                "tool": "agent_runtime",
                "capability_id": "",
                "provider": "agent_runtime",
                "risk_level": "low",
                "requires_approval": False,
                "available": False,
                "reason": "No registered capabilities are available",
                "candidates": [],
            }

        risk_level = self._effective_risk(action, str(selected.get("risk_level", "low")))
        missing_permissions = [
            permission
            for permission in selected.get("permissions", [])
            if permission not in required_permissions
        ]
        requires_approval = risk_level in {"high", "critical"} or bool(missing_permissions)
        candidate_payload = [
            {
                "id": candidate.get("id"),
                "provider": candidate.get("provider"),
                "risk_level": candidate.get("risk_level"),
                "available": candidate.get("available"),
                "health": candidate.get("health"),
                "score": score,
            }
            for score, candidate in scored[:5]
        ]

        return {
            "ok": True,
            "tool": selected["id"],
            "capability_id": selected["id"],
            "provider": selected.get("provider", ""),
            "risk_level": risk_level,
            "requires_approval": requires_approval,
            "available": bool(selected.get("available")),
            "health": selected.get("health", "unknown"),
            "required_permissions": selected.get("permissions", []),
            "granted_permissions": required_permissions,
            "missing_permissions": missing_permissions,
            "candidates": candidate_payload,
        }

    def _discover(self) -> list[dict[str, Any]]:
        if hasattr(self.capabilities, "discover_capabilities"):
            items = self.capabilities.discover_capabilities()
            return [item for item in items if item.get("available", True)]
        return []

    def _candidate_capabilities(self, action: str) -> list[dict[str, Any]]:
        action_lower = action.lower()
        words = set(re.findall(r"[\w.-]+", action_lower))
        preferred_ids: list[str] = []
        for triggers, ids in self.INTENT_HINTS:
            if words & triggers or any(trigger in action_lower for trigger in triggers):
                preferred_ids.extend(ids)

        discovered = self._discover()
        if not preferred_ids:
            if hasattr(self.capabilities, "search_by_goal"):
                searched = self.capabilities.search_by_goal(action)
                return [item for item in searched if item.get("available", True)]
            return discovered

        by_id = {item["id"]: item for item in discovered}
        preferred = [by_id[item_id] for item_id in preferred_ids if item_id in by_id]
        if preferred:
            return preferred

        # If a preferred capability is currently unavailable, include it in the
        # evidence payload rather than silently pretending another tool exists.
        all_items = self.capabilities.discover_capabilities() if hasattr(self.capabilities, "discover_capabilities") else []
        return [item for item in all_items if item.get("id") in preferred_ids] or discovered

    def _score(self, action: str, candidate: dict[str, Any], granted_permissions: list[str]) -> int:
        action_lower = action.lower()
        score = 0
        haystack = [
            str(candidate.get("id", "")),
            str(candidate.get("name", "")),
            str(candidate.get("provider", "")),
            *[str(capability) for capability in candidate.get("capabilities", [])],
        ]
        for value in haystack:
            lowered = value.lower()
            if lowered and lowered in action_lower:
                score += 5
            score += sum(1 for word in re.findall(r"[\w.-]+", action_lower) if word and word in lowered)
        if candidate.get("available", True):
            score += 4
        if candidate.get("health") == "healthy":
            score += 2
        if candidate.get("health") == "degraded":
            score += 1
        missing = set(candidate.get("permissions", [])) - set(granted_permissions)
        score -= len(missing) * 2
        score -= _RISK_ORDER.get(str(candidate.get("risk_level", "low")), 0)
        return score

    def _effective_risk(self, action: str, registered_risk: str) -> str:
        action_words = set(re.findall(r"[\w.-]+", action.lower()))
        if action_words & self.HIGH_RISK_WORDS:
            return "high"
        return registered_risk if registered_risk in _RISK_ORDER else "low"
