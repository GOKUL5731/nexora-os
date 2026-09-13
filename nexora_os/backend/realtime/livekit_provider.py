from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


@dataclass(slots=True)
class LiveKitProvider:
    """Server-side LiveKit configuration and token issuer.

    LiveKit is used as Jarvis' realtime AI voice/video transport. It is not an
    LLM by itself; Jarvis still routes reasoning through the configured LLM.
    """

    url: str = ""
    api_key: str = ""
    api_secret: str = ""

    @classmethod
    def from_env(cls) -> "LiveKitProvider":
        return cls(
            url=os.environ.get("LIVEKIT_URL", "").strip(),
            api_key=os.environ.get("LIVEKIT_API_KEY", "").strip(),
            api_secret=os.environ.get("LIVEKIT_API_SECRET", "").strip(),
        )

    @property
    def configured(self) -> bool:
        return bool(self.url and self.api_key and self.api_secret)

    def status(self) -> dict[str, Any]:
        return {
            "provider": "livekit",
            "role": "realtime_ai_transport",
            "configured": self.configured,
            "url": self.url if self.url else "",
            "api_key": self._redact(self.api_key),
            "secret_configured": bool(self.api_secret),
            "llm_provider": "ollama",
            "message": (
                "LiveKit is configured for realtime Jarvis voice/video sessions."
                if self.configured
                else "Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in .env to enable LiveKit."
            ),
        }

    def issue_token(self, room: str, identity: str, name: str = "Jarvis User", ttl_seconds: int = 3600) -> dict[str, Any]:
        room = room.strip() or "jarvis-ai"
        identity = identity.strip() or "jarvis-user"
        name = name.strip() or identity
        ttl = max(60, min(int(ttl_seconds), 24 * 3600))
        if not self.configured:
            return {"ok": False, "error": "LiveKit is not configured.", **self.status()}

        now = int(time.time())
        payload = {
            "iss": self.api_key,
            "sub": identity,
            "name": name,
            "nbf": now - 5,
            "exp": now + ttl,
            "video": {
                "room": room,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": True,
            },
            "metadata": json.dumps({"provider": "jarvis", "mode": "realtime-ai"}),
        }
        token = self._jwt(payload)
        return {
            "ok": True,
            "url": self.url,
            "room": room,
            "identity": identity,
            "expires_at": payload["exp"],
            "token": token,
        }

    def _jwt(self, payload: dict[str, Any]) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        head = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{head}.{body}".encode("ascii")
        signature = hmac.new(self.api_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        return f"{head}.{body}.{_b64url(signature)}"

    @staticmethod
    def _redact(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return value[:2] + "***"
        return value[:4] + "***" + value[-4:]
