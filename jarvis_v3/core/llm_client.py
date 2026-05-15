"""
JARVIS LLM Client — Ollama-first with model routing.
Routes coding tasks to deepseek-coder, general reasoning to llama3.2.
Falls back gracefully if a model is unavailable.
"""

import asyncio
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger("jarvis.llm")

CODE_KEYWORDS = {"code", "python", "function", "debug", "fix", "script",
                 "program", "error", "syntax", "refactor", "write code",
                 "implement", "class", "def ", "import "}


class LLMClient:
    def __init__(self, config: dict):
        cfg             = config.get("llm", {})
        self.provider   = cfg.get("provider", "ollama")
        if self.provider != "ollama" and not cfg.get("allow_cloud", False):
            logger.warning("Cloud LLM provider '%s' disabled; using local Ollama", self.provider)
            self.provider = "ollama"
        self.model      = cfg.get("model", "llama3.2")
        self.api_key    = cfg.get("api_key", "")
        self.max_tokens = cfg.get("max_tokens", 2048)
        self.ollama_url = cfg.get("ollama_url", "http://localhost:11434")
        self.coder_model   = cfg.get("coder_model", "deepseek-coder")
        self.fallback_model = cfg.get("fallback_model", "mistral")
        self._client    = None

    # ── Model routing ────────────────────────────────────────────────────────
    def _pick_model(self, prompt: str, force_model: str = None) -> str:
        if force_model:
            return force_model
        if self.provider == "ollama":
            low = prompt.lower()
            if any(kw in low for kw in CODE_KEYWORDS):
                return self.coder_model
        return self.model

    # ── Main async entry ─────────────────────────────────────────────────────
    async def complete(self, prompt: str, system: str = None,
                       temperature: float = 0.3, max_tokens: int = None,
                       model: str = None) -> str:
        loop = asyncio.get_event_loop()
        chosen = self._pick_model(prompt, model)
        return await loop.run_in_executor(
            None,
            lambda: self._complete_sync(prompt, system, temperature,
                                        max_tokens or self.max_tokens, chosen)
        )

    def _complete_sync(self, prompt, system, temperature, max_tokens, model) -> str:
        if self.provider == "ollama":
            return self._ollama(prompt, system, temperature, max_tokens, model)
        elif self.provider == "anthropic":
            self._init_client()
            return self._anthropic(prompt, system, temperature, max_tokens)
        elif self.provider == "openai":
            self._init_client()
            return self._openai(prompt, system, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    # ── Ollama ───────────────────────────────────────────────────────────────
    def _ollama(self, prompt, system, temperature, max_tokens, model) -> str:
        import requests
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system or "",
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        }
        try:
            resp = requests.post(f"{self.ollama_url}/api/generate",
                                 json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            logger.error("Ollama not running. Start with: ollama serve")
            return "[Ollama offline. Start Ollama and try again.]"
        except Exception as e:
            # Fallback to different model
            if model != self.fallback_model:
                logger.warning(f"Model {model} failed ({e}), trying {self.fallback_model}")
                return self._ollama(prompt, system, temperature, max_tokens, self.fallback_model)
            logger.error(f"Ollama error: {e}")
            return ""

    # ── Anthropic ────────────────────────────────────────────────────────────
    def _init_client(self):
        if self._client:
            return
        if self.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        elif self.provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)

    def _anthropic(self, prompt, system, temperature, max_tokens):
        kwargs = {"model": self.model, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        return resp.content[0].text

    def _openai(self, prompt, system, temperature, max_tokens):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    # ── Sync helper ──────────────────────────────────────────────────────────
    def complete_sync(self, prompt: str, system: str = None) -> str:
        chosen = self._pick_model(prompt)
        return self._complete_sync(prompt, system, 0.3, self.max_tokens, chosen)

    # ── Ollama model management ───────────────────────────────────────────────
    def list_models(self) -> list[str]:
        """Return locally available Ollama models."""
        if self.provider != "ollama":
            return []
        try:
            import requests
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            models = resp.json().get("models", [])
            return [m["name"] for m in models]
        except Exception:
            return []

    def is_ollama_running(self) -> bool:
        if self.provider != "ollama":
            return True
        try:
            import requests
            requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return True
        except Exception:
            try:
                parsed = urlparse(self.ollama_url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 11434
                with socket.create_connection((host, port), timeout=1.5):
                    return True
            except Exception:
                return False
