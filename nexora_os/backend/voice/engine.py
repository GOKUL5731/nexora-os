from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable

from ..core.event_bus import EventBus

TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
TANGLISH_WORDS = {"pannu", "enna", "venum", "open", "close", "sollu", "kattu", "start", "stop"}


class VoiceEngine:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.state = "idle"

    def language(self, text: str) -> str:
        if TAMIL_RE.search(text):
            return "ta"
        words = set(re.findall(r"[a-z]+", text.lower()))
        return "ta-en" if words & TANGLISH_WORDS else "en"

    async def listen(self, timeout: float = 12) -> dict[str, Any]:
        self._state("listening")
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._listen_blocking), timeout=timeout + 2)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "Microphone listening timed out."}
        finally:
            self._state("idle")

    def _listen_blocking(self) -> dict[str, Any]:
        try:
            import speech_recognition as sr
        except ImportError:
            return {"ok": False, "error": "SpeechRecognition is not installed."}
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=20)
            for locale in ("ta-IN", "en-IN", "en-US"):
                try:
                    text = recognizer.recognize_google(audio, language=locale)
                    return {"ok": True, "text": text, "language": self.language(text), "stt": "google"}
                except sr.UnknownValueError:
                    continue
            return {"ok": False, "error": "Speech was not recognized."}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def speak(self, text: str) -> dict[str, Any]:
        self._state("speaking")
        try:
            return await asyncio.to_thread(self._speak_blocking, text)
        finally:
            self._state("idle")

    def _speak_blocking(self, text: str) -> dict[str, Any]:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            return {"ok": True, "tts": "pyttsx3", "language": self.language(text)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def pipeline(
        self,
        text: str,
        processor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        speak: bool = False,
    ) -> dict[str, Any]:
        language = self.language(text)
        self.bus.publish("voice.transcript", {"text": text, "language": language}, "voice_engine")
        result = await processor(text, {"mode": "voice", "language": language})
        if speak and result.get("message"):
            result["tts"] = await self.speak(str(result["message"]))
        return result

    def health(self) -> dict[str, Any]:
        try:
            import speech_recognition  # noqa: F401
            stt = True
        except ImportError:
            stt = False
        try:
            import pyttsx3  # noqa: F401
            tts = True
        except ImportError:
            tts = False
        return {"status": self.state, "stt_available": stt, "tts_available": tts, "languages": ["en", "ta", "ta-en"]}

    def _state(self, state: str) -> None:
        self.state = state
        self.bus.set_state("voice", self.health(), "voice_engine")
        self.bus.publish("voice.status", {"status": state}, "voice_engine")
