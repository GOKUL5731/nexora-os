"""
JARVIS Reliability Engine.

Provides lightweight confidence scoring, bounded retry, result verification,
and failure memory hooks. It does not promise correctness; it makes uncertainty
visible and gives the orchestrator a consistent fallback path.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger("jarvis.reliability")


@dataclass
class ConfidenceReport:
    score: float
    level: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"score": round(self.score, 3), "level": self.level, "reasons": self.reasons}


class ReliabilityEngine:
    """Score, verify, retry, and record failures for JARVIS actions."""

    def __init__(self, config: dict | None = None, memory: Any = None):
        self.config = config or {}
        self.memory = memory
        rcfg = self.config.get("reliability", {})
        self.max_retries = int(rcfg.get("max_retries", 2))
        self.retry_backoff_ms = int(rcfg.get("retry_backoff_ms", 250))

    def score_plan(self, plan: list[dict]) -> ConfidenceReport:
        if not plan:
            return ConfidenceReport(0.1, "low", ["empty plan"])

        score = 0.9
        reasons: list[str] = []
        for step in plan:
            if not step.get("tool"):
                score -= 0.25
                reasons.append("step missing tool")
            if step.get("risk_level") == "high":
                score -= 0.15
                reasons.append("high-risk step present")
            if step.get("_fallback"):
                score -= 0.2
                reasons.append("fallback plan used")
            if step.get("requires_previous") and len(plan) == 1:
                score -= 0.1
                reasons.append("requires previous output but no prior step")

        return self._report(score, reasons or ["plan has executable steps"])

    def score_result(self, result: Any) -> ConfidenceReport:
        if result is None:
            return ConfidenceReport(0.1, "low", ["empty result"])
        if isinstance(result, dict):
            if result.get("error"):
                return ConfidenceReport(0.2, "low", [str(result.get("error"))[:120]])
            if result.get("ok") is False:
                return ConfidenceReport(0.35, "low", ["result explicitly marked not ok"])
            useful_keys = [k for k in result.keys() if k not in {"ok", "status"}]
            score = 0.75 + min(0.2, len(useful_keys) * 0.03)
            return self._report(score, ["structured result"])
        if isinstance(result, str) and result.strip():
            return self._report(0.72, ["non-empty text result"])
        return ConfidenceReport(0.35, "low", ["result exists but is not informative"])

    async def execute_with_retry(
        self,
        label: str,
        operation: Callable[[], Any | Awaitable[Any]],
        validator: Callable[[Any], bool] | None = None,
        max_retries: int | None = None,
    ) -> dict:
        attempts = int(max_retries if max_retries is not None else self.max_retries) + 1
        last_error = ""
        started = time.perf_counter()

        for attempt in range(1, attempts + 1):
            try:
                value = operation()
                if inspect.isawaitable(value):
                    value = await value
                valid = validator(value) if validator else self.score_result(value).score >= 0.5
                if valid:
                    return {
                        "ok": True,
                        "label": label,
                        "attempts": attempt,
                        "result": value,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                last_error = "validator rejected result"
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Retryable operation failed [%s] attempt %s/%s: %s", label, attempt, attempts, exc)

            if attempt < attempts:
                await asyncio.sleep(self.retry_backoff_ms / 1000 * attempt)

        self.record_failure(label, last_error)
        return {
            "ok": False,
            "label": label,
            "attempts": attempts,
            "error": last_error or "operation failed",
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    def verify_file_exists(self, path: str | Path, min_bytes: int = 0) -> dict:
        target = Path(path)
        if not target.exists():
            return {"ok": False, "error": f"File not found: {target}"}
        if target.is_file() and target.stat().st_size < min_bytes:
            return {"ok": False, "error": f"File too small: {target}"}
        return {"ok": True, "path": str(target), "bytes": target.stat().st_size if target.is_file() else None}

    def fallback_response(self, user_input: str, reason: str = "") -> str:
        if reason:
            return f"I could not verify that safely yet: {reason}"
        if user_input.strip():
            return "I need a more reliable path before I act on that."
        return "I did not receive a command to execute."

    def record_failure(self, label: str, error: str, solution: str = "") -> None:
        if not self.memory:
            return
        try:
            signature = f"{label}:{error[:120]}"
            if hasattr(self.memory, "remember_error"):
                self.memory.remember_error(signature, solution, {"label": label, "error": error}, resolved=False)
            else:
                self.memory.store_interaction(label, error, outcome="failed", tags=["reliability"])
        except Exception:
            logger.debug("Failure memory hook skipped", exc_info=True)

    def _report(self, score: float, reasons: list[str]) -> ConfidenceReport:
        score = max(0.0, min(1.0, score))
        level = "high" if score >= 0.75 else ("medium" if score >= 0.5 else "low")
        return ConfidenceReport(score, level, reasons)
