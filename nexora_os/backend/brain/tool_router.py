from __future__ import annotations

from typing import Any


class ToolRouter:
    """
    Risk-aware tool selection layer prioritizing structured APIs over generic UI automation.
    """
    def __init__(self, capability_registry: Any) -> None:
        self.capabilities = capability_registry

    def select_tool(self, action: str, required_permissions: list[str]) -> dict[str, Any]:
        """
        Selects the safest and most structured tool available for the action.
        """
        # A full system would map actions to specific tools and connectors.
        # Here we mock the router matching logic based on the action string.
        action_lower = action.lower()

        selected_tool = None
        risk_level = "low"

        if "browser" in action_lower or "url" in action_lower:
            selected_tool = "browser_connector"
            risk_level = "medium"
        elif "file" in action_lower or "write" in action_lower:
            selected_tool = "filesystem_connector"
            risk_level = "high" if "delete" in action_lower else "medium"
        elif "click" in action_lower or "move mouse" in action_lower:
            selected_tool = "vision_engine"
            risk_level = "low"
        elif "app" in action_lower or "process" in action_lower:
            selected_tool = "automation_engine"
            risk_level = "high"
        else:
            selected_tool = "agent_runtime"
            risk_level = "low"

        return {
            "ok": True,
            "tool": selected_tool,
            "risk_level": risk_level,
            "requires_approval": risk_level == "high"
        }
