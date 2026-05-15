"""
JARVIS LLM Router — Intelligent model selection for RTX 4050
Routes tasks to the best local Ollama model based on intent.

Model tiers:
  phi        → instant commands, simple Q&A (fastest)
  mistral    → general knowledge, summarization (fast)
  llama3     → complex reasoning, multi-step (smart)
  deepseek-coder → any code task (best coder)
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger("jarvis.router")

OLLAMA_URL = "http://localhost:11434"

# ── Intent patterns → model mapping ──────────────────────────────────────────
ROUTING_RULES: list[tuple[str, list[str]]] = [
    # Code tasks → deepseek-coder
    ("deepseek-coder", [
        r"\bcode\b", r"\bpython\b", r"\bfunction\b", r"\bclass\b", r"\bdef \b",
        r"\bdebug\b", r"\berror\b", r"\bscript\b", r"\bimport\b", r"\brefactor\b",
        r"\boptimize code\b", r"\bwrite.*code\b", r"\bfix.*bug\b", r"\bjavascript\b",
        r"\bc\+\+\b", r"\bjava\b", r"\bsql\b", r"\bapi\b", r"\btest.*function\b",
    ]),
    # Simple/instant → phi
    ("phi", [
        r"^(hi|hello|hey|what time|what's the time|open |close |play |pause |ok).*$",
        r"^(yes|no|ok|thanks|sure|done|stop|cancel|quit)$",
        r"\bopen\s+\w+\b", r"\bclose\s+\w+\b", r"\bset.*timer\b",
        r"\btake screenshot\b", r"\bvolume\b", r"\bbrightness\b",
        r"\bclipboard\b", r"\bremember this\b",
    ]),
    # Summarization / knowledge → mistral
    ("mistral", [
        r"\bsummariz\b", r"\bexplain\b", r"\bwhat is\b", r"\bdefine\b",
        r"\bweb search\b", r"\bsearch for\b", r"\bfind information\b",
        r"\bnews\b", r"\bweather\b", r"\btranslate\b",
    ]),
    # Default → llama3 (complex reasoning)
]


@dataclass
class RouterStats:
    model: str
    calls: int = 0
    total_ms: float = 0
    failures: int = 0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.calls if self.calls else 0


class LLMRouter:
    """
    Intelligent multi-model router for local Ollama models.
    Auto-selects model per task, tracks latency, falls back on failure.
    """

    def __init__(self, config: dict):
        self.config      = config
        cfg              = config.get("llm", {})
        self.ollama_url  = cfg.get("ollama_url", OLLAMA_URL)
        self.max_tokens  = cfg.get("max_tokens", 2048)
        self.keep_alive  = cfg.get("keep_alive", "15m")
        self._available  = set()     # locally available model names
        self._stats: dict[str, RouterStats] = {}
        self._refresh_available()

    # ── Model availability ────────────────────────────────────────────────────
    def _refresh_available(self):
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=4)
            models = resp.json().get("models", [])
            # Normalize: strip :latest suffix
            self._available = {
                m["name"].replace(":latest", "").split(":")[0]
                for m in models
            }
            logger.info(f"Available models: {sorted(self._available)}")
        except Exception:
            logger.warning("Ollama not reachable — no models discovered")
            self._available = set()

    def is_available(self, model: str) -> bool:
        base = model.split(":")[0]
        return base in self._available or model in self._available

    def list_available(self) -> list[str]:
        return sorted(self._available)

    # ── Model selection ───────────────────────────────────────────────────────
    def select_model(self, prompt: str, force: Optional[str] = None) -> str:
        if force and self.is_available(force):
            return force

        low = prompt.lower().strip()

        for model, patterns in ROUTING_RULES:
            if model == "deepseek-coder" or model == "phi" or model == "mistral":
                for pat in patterns:
                    if re.search(pat, low):
                        if self.is_available(model):
                            logger.debug(f"Router: '{model}' (pattern match)")
                            return model
                        # Fall through to next tier if model not installed

        # Default: llama3 → llama3.2 → mistral → phi → whatever is available
        for fallback in ["llama3.2", "llama3", "mistral", "phi", "tinyllama"]:
            if self.is_available(fallback):
                return fallback

        # Last resort: first available model
        if self._available:
            return next(iter(self._available))

        return "llama3.2"   # offline hope

    # ── Core completion ───────────────────────────────────────────────────────
    def complete(self, prompt: str, system: str = None,
                 temperature: float = 0.3, max_tokens: int = None,
                 force_model: str = None) -> str:
        model   = self.select_model(prompt, force_model)
        payload = {
            "model":   model,
            "prompt":  prompt,
            "system":  system or "",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
            "stream": False,
            "keep_alive": self.keep_alive,
        }

        t0 = time.perf_counter()
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload, timeout=120,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            elapsed_ms = (time.perf_counter() - t0) * 1000

            # Track stats
            s = self._stats.setdefault(model, RouterStats(model))
            s.calls    += 1
            s.total_ms += elapsed_ms
            logger.debug(f"[{model}] {elapsed_ms:.0f}ms — {len(text)} chars")
            return text

        except requests.exceptions.ConnectionError:
            return "[Ollama offline. Start with: ollama serve]"
        except Exception as e:
            s = self._stats.setdefault(model, RouterStats(model))
            s.failures += 1
            # Try fallback
            if model != "mistral" and self.is_available("mistral"):
                logger.warning(f"Model {model} failed ({e}), falling back to mistral")
                payload["model"] = "mistral"
                try:
                    resp = requests.post(f"{self.ollama_url}/api/generate",
                                         json=payload, timeout=90)
                    return resp.json().get("response", "").strip()
                except Exception:
                    pass
            logger.error(f"LLM complete failed: {e}")
            return ""

    async def complete_async(self, prompt: str, system: str = None,
                             temperature: float = 0.3, max_tokens: int = None,
                             force_model: str = None) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.complete(prompt, system, temperature, max_tokens, force_model)
        )

    def warm_model(self, model: str) -> bool:
        target = model.replace(":latest", "").split(":")[0]
        if not self.is_available(target):
            return False
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": target,
                    "prompt": "Reply with READY.",
                    "options": {"temperature": 0, "num_predict": 1},
                    "stream": False,
                    "keep_alive": self.keep_alive,
                },
                timeout=90,
            )
            resp.raise_for_status()
            logger.info(f"Warmed model: {target}")
            return True
        except Exception as e:
            logger.debug(f"Warm-up skipped for {target}: {e}")
            return False

    def warm_models(self, models: list[str]) -> list[str]:
        warmed = []
        seen = set()
        for model in models:
            target = model.replace(":latest", "").split(":")[0]
            if target in seen:
                continue
            seen.add(target)
            if self.warm_model(target):
                warmed.append(target)
        return warmed

    async def warm_models_async(self, models: list[str]) -> list[str]:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.warm_models(models))

    # ── Performance stats ─────────────────────────────────────────────────────
    def get_stats(self) -> list[dict]:
        return [
            {"model": s.model, "calls": s.calls,
             "avg_ms": round(s.avg_ms, 1), "failures": s.failures}
            for s in sorted(self._stats.values(), key=lambda x: x.calls, reverse=True)
        ]

    def is_ollama_running(self) -> bool:
        try:
            requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return True
        except Exception:
            return False
