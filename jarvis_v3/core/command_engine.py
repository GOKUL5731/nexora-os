"""
JARVIS Command Engine.

Fast deterministic routing for simple local commands. This keeps obvious
operator tasks off the LLM path: time/date, system status, screenshots,
clipboard reads, common app launches, and memory captures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CommandDecision:
    handled: bool
    message: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    confidence: float = 0.0
    requires_confirmation: bool = False
    plan: list[dict] = field(default_factory=list)
    result: Any = None

    def to_response(self, task_id: str) -> dict:
        if self.requires_confirmation:
            return {
                "type": "confirmation_required",
                "message": self.message,
                "task_id": task_id,
                "plan": self.plan,
                "confidence": self.confidence,
            }
        return {
            "type": "success",
            "message": self.message,
            "task_id": task_id,
            "steps": [
                {
                    "step": "direct command",
                    "tool": self.tool,
                    "result": self.result,
                    "ok": True,
                    "confidence": self.confidence,
                }
            ] if self.tool else [],
            "confidence": self.confidence,
        }


class CommandEngine:
    """Deterministic action router for safe high-frequency commands."""

    APP_ALIASES = {
        "notepad": "notepad",
        "calculator": "calc",
        "calc": "calc",
        "paint": "mspaint",
        "explorer": "explorer",
        "file explorer": "explorer",
        "powershell": "powershell",
        "terminal": "wt",
        "cmd": "cmd",
        "chrome": "chrome",
        "edge": "msedge",
        "vscode": "code",
        "vs code": "code",
    }

    def __init__(self, config: dict, memory=None, registry=None, reliability=None):
        self.config = config
        self.memory = memory
        self.registry = registry
        self.reliability = reliability

    async def try_execute(self, user_input: str, context: dict | None = None) -> CommandDecision:
        text = " ".join(user_input.strip().split())
        low = text.lower()
        if not text:
            return CommandDecision(False)

        if low in {"stop", "cancel", "never mind", "nevermind"}:
            return CommandDecision(True, "Cancelled.", tool="direct_cancel", confidence=0.98)

        if self._is_time_query(low):
            now = datetime.now()
            return CommandDecision(
                True,
                now.strftime("It is %I:%M %p on %A, %B %d, %Y."),
                tool="direct_time",
                confidence=0.99,
            )

        if self._is_date_query(low):
            now = datetime.now()
            return CommandDecision(
                True,
                now.strftime("Today is %A, %B %d, %Y."),
                tool="direct_date",
                confidence=0.99,
            )

        remember = self._parse_remember(text)
        if remember:
            return await self._remember(remember, text)

        if low in {"status", "system status", "system info", "pc status", "computer status"}:
            return await self._system_info()

        if re.search(r"\b(take|capture|save)\b.*\bscreenshot\b", low) or low == "screenshot":
            return await self._tool("take_screenshot", {}, "Screenshot saved to {saved}.", confidence=0.9)

        if low in {"read clipboard", "what is on my clipboard", "clipboard"}:
            return await self._tool("clipboard_read", {}, "{content}", confidence=0.88)

        app = self._parse_open_app(low)
        if app:
            executable = self.APP_ALIASES.get(app, app)
            return await self._tool(
                "open_app",
                {"name": executable},
                f"Opened {app}.",
                confidence=0.84,
                fallback_error=f"I could not open {app}.",
            )

        terminal = self._parse_terminal_command(text)
        if terminal:
            plan = [{
                "tool": "run_command",
                "args": {"command": terminal},
                "description": f"Run terminal command: {terminal}",
                "risk_level": "high",
                "requires_previous": False,
            }]
            return CommandDecision(
                True,
                "That terminal command needs your approval before I run it.",
                tool="run_command",
                args={"command": terminal},
                confidence=0.82,
                requires_confirmation=True,
                plan=plan,
            )

        return CommandDecision(False)

    def _is_time_query(self, low: str) -> bool:
        return low in {"time", "what time is it", "what's the time", "current time"} or low.startswith("tell me the time")

    def _is_date_query(self, low: str) -> bool:
        return low in {"date", "what date is it", "today's date", "todays date", "current date"}

    def _parse_remember(self, text: str) -> str:
        match = re.match(r"(?i)remember(?: that)?\s+(.+)$", text)
        return match.group(1).strip() if match else ""

    def _parse_open_app(self, low: str) -> str:
        match = re.match(r"(?:open|launch|start)\s+(.+)$", low)
        if not match:
            return ""
        app = match.group(1).strip(" .")
        if app.startswith("the "):
            app = app[4:]
        return app[:80]

    def _parse_terminal_command(self, text: str) -> str:
        match = re.match(r"(?i)(?:run|execute)\s+(?:terminal\s+)?command\s+(.+)$", text)
        return match.group(1).strip() if match else ""

    async def _remember(self, value: str, original: str) -> CommandDecision:
        if not self.memory:
            return CommandDecision(True, "I do not have memory available in this session.", tool="remember", confidence=0.5)

        low = value.lower()
        if "prefer" in low or "preference" in low:
            key, pref = self._split_preference(value)
            if hasattr(self.memory, "learn_preference"):
                self.memory.learn_preference(key, pref, source=original, confidence=0.75)
            else:
                self.memory.store_fact("preferences", key, pref)
        else:
            if hasattr(self.memory, "store_event"):
                self.memory.store_event("memory", value, {"source": original}, importance=0.5)
            self.memory.store_interaction(original, f"remembered: {value}", tags=["remembered"])

        return CommandDecision(True, "Remembered.", tool="remember", args={"value": value}, confidence=0.93, result={"stored": True})

    def _split_preference(self, value: str) -> tuple[str, str]:
        match = re.search(r"(?i)(?:i\s+)?prefer\s+(.+)", value)
        pref = (match.group(1) if match else value).strip()
        key = re.sub(r"[^a-z0-9]+", "_", pref.lower()).strip("_")[:48] or "preference"
        return key, pref

    async def _system_info(self) -> CommandDecision:
        decision = await self._tool("get_system_info", {}, "", confidence=0.9)
        if isinstance(decision.result, dict) and not decision.result.get("error"):
            info = decision.result
            decision.message = (
                f"{info.get('os', 'Windows')} with CPU at {info.get('cpu_percent', '?')}%, "
                f"RAM at {info.get('ram_used_percent', '?')}%, "
                f"and {info.get('disk_free_gb', '?')} GB free on disk."
            )
        return decision

    async def _tool(
        self,
        tool: str,
        args: dict,
        success_template: str,
        confidence: float,
        fallback_error: str = "I could not complete that command.",
    ) -> CommandDecision:
        if not self.registry:
            return CommandDecision(True, "Command registry is not available.", tool=tool, args=args, confidence=0.4)

        try:
            agent = self.registry.get_agent(tool)
            result = await agent.execute(tool, args)
            if self.reliability:
                report = self.reliability.score_result(result)
                confidence = min(confidence, max(0.3, report.score))
            if isinstance(result, dict) and result.get("error"):
                return CommandDecision(True, f"{fallback_error} {result['error']}", tool=tool, args=args, confidence=0.35, result=result)
            message = success_template
            if isinstance(result, dict):
                try:
                    message = success_template.format(**result)
                except Exception:
                    message = success_template
            return CommandDecision(True, message, tool=tool, args=args, confidence=confidence, result=result)
        except Exception as exc:
            return CommandDecision(True, f"{fallback_error} {exc}", tool=tool, args=args, confidence=0.25, result={"error": str(exc)})
