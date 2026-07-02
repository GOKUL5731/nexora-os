from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from .cache import Cache


class OllamaClient:
    def __init__(self, host: str | None = None, model: str | None = None, enable_cache: bool = True) -> None:
        self.host = (host or os.environ.get("NEXORA_OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or os.environ.get("NEXORA_OLLAMA_MODEL", "")
        self.system_prompt = """You are NEXORA, an advanced AI assistant with the following capabilities:
- Voice input/output (speech recognition and text-to-speech)
- Vision (webcam, face detection, object detection, OCR)
- Automation (app launch, file operations, browser automation)
- Memory (store, retrieve, and reflect on information)
- Workflow execution
- Multi-language support (English, Tamil, Tanglish)

You are helpful, direct, and action-oriented. When users ask you to do something, respond as if you can perform the action using your available capabilities. Be concise and practical."""
        
        # Cache for LLM responses
        self._cache = Cache(default_ttl=300, max_size=200) if enable_cache else None

    def models(self) -> list[str]:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=0.75) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]
        except Exception:
            return []

    def ready(self) -> bool:
        return bool(self.models())

    def status(self) -> dict[str, Any]:
        models = self.models()
        return {
            "host": self.host,
            "ready": bool(models),
            "model": self.model or (models[0] if models else ""),
            "models": models,
        }

    def generate(self, prompt: str, system: str | None = None, json_format: bool = False) -> dict[str, Any]:
        # Check cache first
        if self._cache:
            cache_key = f"generate:{prompt}:{system}:{json_format}"
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        
        status = self.status()
        model = self.model or status["model"]
        if not model:
            return {"ok": False, "message": "Ollama is running, but no local model is installed."}
        
        # Combine system prompt with user prompt
        system_prompt = system if system is not None else self.system_prompt
        full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nNEXORA:"
        
        req_data = {"model": model, "prompt": full_prompt, "stream": False}
        if json_format:
            req_data["format"] = "json"
            
        body = json.dumps(req_data).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
            result = {"ok": True, "message": payload.get("response", "").strip(), "model": model}
            
            # Cache the result
            if self._cache:
                self._cache.set(cache_key, result)
            
            return result
        except Exception as exc:
            return {"ok": False, "message": str(exc), "model": model}
