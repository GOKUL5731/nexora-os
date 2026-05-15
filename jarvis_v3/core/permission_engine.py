"""JARVIS Permission Engine — risk assessment before any action."""

import logging
from enum import Enum

logger = logging.getLogger("jarvis.permissions")

TOOL_RISK = {
    # LOW — safe, read-only
    "web_search": "low", "read_file": "low", "list_directory": "low",
    "take_screenshot": "low", "get_system_info": "low", "search_memory": "low",
    "remember": "low", "speak": "low", "clipboard_read": "low",
    "ocr_screen": "low", "detect_objects": "low", "get_battery": "low",
    "android_screenshot": "low", "android_get_battery": "low",
    "android_read_notifications": "low", "android_list_devices": "low",

    # MEDIUM — writes but reversible
    "write_file": "medium", "create_directory": "medium", "run_code": "medium",
    "browser_navigate": "medium", "download_file": "medium",
    "clipboard_write": "medium", "android_open_app": "medium",
    "android_tap": "medium", "android_type": "medium", "android_swipe": "medium",
    "android_push_file": "medium", "android_start_scrcpy": "medium",

    # HIGH — destructive / communication / financial
    "delete_file": "high", "system_command": "high", "run_command": "high",
    "send_email": "high", "send_message": "high", "install_software": "high",
    "android_send_sms": "high", "android_make_call": "high",
    "android_send_whatsapp": "high", "android_shell": "high",
    "android_install_apk": "high", "purchase": "high",
}

DANGER_KEYWORDS = [
    "rm -rf", "rmdir /s", "format", "del /f", "deltree",
    "drop table", "drop database", "shutdown", "password", "sudo",
    "--force", "-rf", "wipe", "erase",
]


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PermissionEngine:
    def __init__(self, config: dict):
        self.always_ask = set(config.get("always_ask_for", []))
        self.overrides  = config.get("permission_overrides", {})

    def assess_plan(self, plan: list[dict]) -> RiskLevel:
        max_risk = RiskLevel.LOW
        for step in plan:
            r = self._assess_step(step)
            if r == RiskLevel.HIGH:
                return RiskLevel.HIGH
            if r == RiskLevel.MEDIUM:
                max_risk = RiskLevel.MEDIUM
        return max_risk

    def _assess_step(self, step: dict) -> RiskLevel:
        tool = step.get("tool", "")
        args_str = str(step.get("args", "")).lower()

        if tool in self.always_ask:
            return RiskLevel.HIGH
        if any(kw in args_str for kw in DANGER_KEYWORDS):
            return RiskLevel.HIGH

        risk_str = self.overrides.get(tool) or TOOL_RISK.get(tool, "medium")
        return RiskLevel(risk_str)

    def confirmation_message(self, plan: list[dict]) -> str:
        high = [s for s in plan if self._assess_step(s) == RiskLevel.HIGH]
        lines = ["Sir, these actions need your approval:\n"]
        for i, s in enumerate(high, 1):
            lines.append(f"  {i}. {s.get('description', s.get('tool', '?'))}")
        lines.append("\nType YES to confirm or NO to cancel.")
        return "\n".join(lines)
