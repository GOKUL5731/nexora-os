"""Text-to-speech facade built on the shared VoiceEngine."""

from __future__ import annotations

from core.voice import VoiceEngine


class TTSEngine:
    """Small TTS-only facade for modules that do not need STT."""

    def __init__(self, config: dict):
        self._voice = VoiceEngine(config)

    async def speak(self, text: str, interrupt: bool = True) -> dict:
        return await self._voice.speak(text, interrupt=interrupt)

    def stop(self):
        self._voice.stop_speaking()


__all__ = ["TTSEngine"]
