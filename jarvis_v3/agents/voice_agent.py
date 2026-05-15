"""
JARVIS Voice Agent - thin wrapper around the shared VoiceEngine.
Keeps the agent tool interface while reusing the newer GPU-capable voice stack.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.agent_registry import BaseAgent
from core.voice import VoiceEngine


class VoiceAgent(BaseAgent):
    def __init__(self, config: dict):
        super().__init__(config)
        self.engine = VoiceEngine(config)

    def supported_tools(self):
        return [
            "speak",
            "listen",
            "start_wake_word",
            "stop_listening",
            "transcribe_file",
            "set_voice_language",
        ]

    async def execute(self, tool: str, args: dict) -> Any:
        if tool == "speak":
            return await self.engine.speak(args.get("text", ""))
        if tool == "listen":
            return await self.engine.listen(args.get("timeout", 10))
        if tool == "start_wake_word":
            return self.engine.start_wake_word(args.get("callback"))
        if tool == "stop_listening":
            self.engine.stop()
            return {"status": "stopped"}
        if tool == "transcribe_file":
            return await self.transcribe_file(args["path"])
        if tool == "set_voice_language":
            self.engine.language = args.get("language", "auto")
            return {"language": self.engine.language}
        raise ValueError(f"VoiceAgent: unknown tool '{tool}'")

    async def speak(self, text: str) -> dict:
        return await self.engine.speak(text)

    async def listen(self, timeout: float = 10) -> dict:
        return await self.engine.listen(timeout)

    async def transcribe_file(self, path: str) -> dict:
        target = Path(path)
        if not target.exists():
            return {"text": "", "error": f"File not found: {path}"}
        return self.engine._transcribe_bytes(target.read_bytes())

    def start_wake_word(self, callback=None) -> dict:
        return self.engine.start_wake_word(callback)

    def stop(self) -> dict:
        self.engine.stop()
        return {"status": "stopped"}
