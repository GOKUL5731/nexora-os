from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Intent(str, Enum):
    GENERAL_CHAT = "GENERAL_CHAT"
    QUESTION = "QUESTION"
    CODING = "CODING"
    DEBUGGING = "DEBUGGING"
    SEARCH = "SEARCH"
    RESEARCH = "RESEARCH"
    AUTOMATION = "AUTOMATION"
    VISION = "VISION"
    VOICE = "VOICE"
    WORKFLOW = "WORKFLOW"
    SYSTEM_CONTROL = "SYSTEM_CONTROL"


class ThinkingMode(str, Enum):
    CONVERSATION = "conversation"
    KNOWLEDGE = "knowledge"
    REASONING = "reasoning"
    EXECUTION = "execution"


@dataclass(slots=True)
class HumanResponse:
    handled: bool
    message: str = ""
    intent: Intent = Intent.GENERAL_CHAT
    mode: ThinkingMode = ThinkingMode.CONVERSATION
    background: bool = False
    needs_brain: bool = False
    data: dict[str, Any] = field(default_factory=dict)


class HumanResponseEngine:
    """Fast conversational front door for the runtime.

    This layer decides whether a request can be answered naturally without the
    planner. It keeps the system truthful by only answering deterministic facts
    and already indexed knowledge on the fast path.
    """

    _GREETINGS = {"hi", "hello", "hey", "hai", "vanakkam", "வணக்கம்"}
    _COMPLEX_HINTS = {
        "analyze", "audit", "scan", "inspect", "fix", "modify", "implement",
        "create workflow", "search all", "run tests", "refactor", "connect",
        "delete", "remove legacy", "repository", "project", "desktop",
        "control my", "build exe", "one click", "debug this", "broken",
    }
    _AUTOMATION_HINTS = {
        "open ", "launch ", "start ", "screenshot", "create file", "read file",
        "write file", "delete file", "browser", "shutdown", "restart",
        "lock screen", "kill process", "system status", "system info",
    }
    _VISION_HINTS = {"camera", "webcam", "vision", "ocr", "screen", "face", "object detection"}
    _VOICE_HINTS = {"voice", "mic", "microphone", "speak", "listen", "stt", "tts"}
    _WORKFLOW_HINTS = {"workflow", "node", "scheduler", "retry", "n8n"}

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def classify(self, text: str) -> Intent:
        lowered = self._normalize(text)
        if not lowered:
            return Intent.GENERAL_CHAT
        if any(hint in lowered for hint in self._VISION_HINTS):
            return Intent.VISION
        if any(hint in lowered for hint in self._VOICE_HINTS):
            return Intent.VOICE
        if any(hint in lowered for hint in self._WORKFLOW_HINTS):
            return Intent.WORKFLOW
        if re.search(r"\b(create|write|read|delete|remove)\s+(?:a\s+|the\s+)?file\b", lowered):
            return Intent.AUTOMATION
        if re.search(r"\bfile\s+(?:called|named)\b", lowered):
            return Intent.AUTOMATION
        if any(hint in lowered for hint in self._AUTOMATION_HINTS):
            return Intent.SYSTEM_CONTROL if "system" in lowered or "shutdown" in lowered or "restart" in lowered else Intent.AUTOMATION
        if any(hint in lowered for hint in ("debug", "traceback", "exception", "failing", "error")):
            return Intent.DEBUGGING
        if any(hint in lowered for hint in ("code", "function", "class", "python", "typescript", "javascript", "java", "rust")):
            return Intent.CODING
        if lowered.startswith(("search ", "find latest ", "look up ", "browse ")):
            return Intent.SEARCH
        if lowered.startswith(("research ", "study ", "learn ")):
            return Intent.RESEARCH
        if lowered.endswith("?") or lowered.startswith(("what ", "who ", "when ", "where ", "why ", "how ", "explain ")):
            return Intent.QUESTION
        return Intent.GENERAL_CHAT

    def respond(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        knowledge: Any | None = None,
        memory: Any | None = None,
    ) -> HumanResponse:
        context = context or {}
        started = time.perf_counter()
        session_id = str(context.get("session_id", "default"))
        lowered = self._normalize(text)
        intent = self.classify(text)

        if lowered.startswith(("plan ", "create goal ", "goal ")) or context.get("sync") is True:
            return HumanResponse(
                handled=False,
                intent=intent,
                needs_brain=True,
                mode=ThinkingMode.REASONING,
                data=self._meta(started, session_id),
            )

        if self._is_complex(lowered, intent):
            return HumanResponse(
                handled=True,
                message=self._background_ack(intent),
                intent=intent,
                mode=ThinkingMode.EXECUTION,
                background=True,
                needs_brain=True,
                data=self._meta(started, session_id),
            )

        message = self._direct_answer(text, lowered, intent, context, knowledge, memory)
        if message:
            message = self._polish(message)
            self._remember_turn(session_id, text, message, intent)
            return HumanResponse(
                handled=True,
                message=message,
                intent=intent,
                mode=ThinkingMode.KNOWLEDGE if intent in {Intent.QUESTION, Intent.CODING, Intent.RESEARCH} else ThinkingMode.CONVERSATION,
                data=self._meta(started, session_id),
            )

        return HumanResponse(handled=False, intent=intent, needs_brain=True, mode=ThinkingMode.REASONING, data=self._meta(started, session_id))

    def snapshot(self, session_id: str = "default") -> dict[str, Any]:
        session = self._sessions.get(session_id, {"turns": [], "topic": ""})
        return {
            "session_id": session_id,
            "current_topic": session.get("topic", ""),
            "recent_turns": session.get("turns", [])[-5:],
        }

    def meaningful_memory(self, text: str) -> str:
        lowered = self._normalize(text)
        preference_patterns = [
            r"\bi prefer (?P<value>.+)",
            r"\bi like (?P<value>.+)",
            r"\bmy project is (?P<value>.+)",
            r"\bi use (?P<value>windows|python|local ai|ollama|tamil|english).*$",
        ]
        for pattern in preference_patterns:
            match = re.search(pattern, lowered)
            if match:
                value = match.group("value").strip(" .")
                return f"User preference/context: {value}"
        return ""

    def _direct_answer(
        self,
        text: str,
        lowered: str,
        intent: Intent,
        context: dict[str, Any],
        knowledge: Any | None,
        memory: Any | None,
    ) -> str:
        tokens = set(re.findall(r"[\w\u0B80-\u0BFF]+", lowered, flags=re.UNICODE))
        if lowered in self._GREETINGS or (bool(tokens & self._GREETINGS) and len(tokens) <= 3):
            return "Hi. I'm here and ready."
        if lowered in {"how are you", "how are you?", "how are you doing", "how are you doing?"}:
            return "I'm running normally and ready to help."
        if lowered in {"what are you doing", "what are you doing?"}:
            return "I'm keeping the Jarvis runtime ready, watching the current project context, and waiting for your next task."
        if "what time" in lowered or lowered in {"time", "current time"}:
            return f"It's {datetime.now().strftime('%I:%M %p').lstrip('0')}."
        if lowered in {"who created java", "who created java?"}:
            return "Java was originally created by James Gosling at Sun Microsystems."
        if lowered.startswith("explain python") or lowered == "python":
            return "Python is a readable, general-purpose programming language used for automation, web apps, data work, AI, scripting, and backend services."
        if lowered.startswith("explain java"):
            return "Java is a class-based language designed for portable applications, especially backend systems, Android-era tooling, and enterprise software."
        if lowered.startswith(("what do you know about ", "search knowledge ", "knowledge search ")):
            query = re.sub(r"^(what do you know about|search knowledge|knowledge search)\s+", "", lowered).strip()
            if knowledge:
                hits = knowledge.search(query, limit=3)
                if hits:
                    top = hits[0]
                    return f"{top.get('title', 'I found a matching note')}: {top.get('content', '')} Source: {top.get('source', 'stored knowledge')}."
            return "I don't have indexed knowledge for that yet."
        if lowered.startswith("remember ") and memory:
            item = text.split(" ", 1)[1].strip() if " " in text else ""
            if item:
                memory.store(item, "semantic", ["user_requested", "conversation"])
                return "Got it. I'll remember that."
        if intent == Intent.GENERAL_CHAT and len(lowered.split()) <= 8:
            if "thank" in lowered:
                return "You're welcome."
            if lowered in {"ok", "okay", "yes", "yeah", "sure"}:
                return "Okay."
        return ""

    def _is_complex(self, lowered: str, intent: Intent) -> bool:
        if intent in {Intent.VISION, Intent.VOICE, Intent.WORKFLOW, Intent.DEBUGGING}:
            return True
        return any(hint in lowered for hint in self._COMPLEX_HINTS)

    def _background_ack(self, intent: Intent) -> str:
        if intent == Intent.DEBUGGING:
            return "Okay, I'll start tracing the failure and report what I find."
        if intent == Intent.WORKFLOW:
            return "I've started checking the workflow path."
        if intent in {Intent.AUTOMATION, Intent.SYSTEM_CONTROL}:
            return "Okay, I'll check the system action and proceed carefully."
        if intent == Intent.VISION:
            return "I'll check the vision system now."
        if intent == Intent.VOICE:
            return "I'll check the voice path now."
        return "I've started working on it."

    def _remember_turn(self, session_id: str, user_input: str, response: str, intent: Intent) -> None:
        session = self._sessions.setdefault(session_id, {"turns": [], "topic": ""})
        session["turns"].append({"user": user_input, "assistant": response, "intent": intent.value, "timestamp": time.time()})
        session["turns"] = session["turns"][-20:]
        topic = self._extract_topic(user_input)
        if topic:
            session["topic"] = topic

    @staticmethod
    def _extract_topic(text: str) -> str:
        lowered = " ".join(text.lower().split())
        for prefix in ("explain ", "what do you know about ", "learn ", "study "):
            if lowered.startswith(prefix):
                return lowered[len(prefix):].strip(" ?.")[:80]
        return ""

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().strip().split())

    @staticmethod
    def _polish(message: str) -> str:
        message = " ".join(message.split())
        if len(message) > 700:
            message = message[:697].rstrip() + "..."
        return message

    @staticmethod
    def _meta(started: float, session_id: str) -> dict[str, Any]:
        return {"latency_ms": round((time.perf_counter() - started) * 1000, 2), "session_id": session_id}
