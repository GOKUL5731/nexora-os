"""Dynamic reasoning strategy engine for recursive adaptive intelligence."""

from __future__ import annotations

from typing import Any

from core.strategy_manager import CognitiveStrategyManager


class DynamicReasoningStrategyEngine:
    """Selects fast, deep, distributed, predictive, or reflective reasoning modes."""

    MODES = {
        "fast": {"base_strategy": "fast_reasoning", "latency_target_ms": 250},
        "deep": {"base_strategy": "deep_reasoning", "latency_target_ms": 1500},
        "distributed": {"base_strategy": "deep_reasoning", "latency_target_ms": 2500},
        "predictive": {"base_strategy": "fast_reasoning", "latency_target_ms": 700},
        "reflective": {"base_strategy": "deep_reasoning", "latency_target_ms": 2000},
    }

    def __init__(self, config: dict | None = None, strategies: CognitiveStrategyManager | None = None):
        self.config = config or {}
        self.strategies = strategies or CognitiveStrategyManager(self.config)

    def select(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        complexity = self.estimate_complexity(task, context)
        pressure = context.get("resource_pressure", 0.0)
        confidence = context.get("confidence", 0.7)
        latency_target = context.get("latency_target_ms", 1000)
        if pressure > 0.75:
            mode = "fast"
        elif confidence < 0.45:
            mode = "reflective"
        elif complexity > 0.75 and latency_target > 1200:
            mode = "distributed"
        elif "predict" in task.lower() or context.get("predictive"):
            mode = "predictive"
        elif complexity > 0.55:
            mode = "deep"
        else:
            mode = "fast"
        base = self.strategies.get_strategy(self.MODES[mode]["base_strategy"])
        selected = self.strategies.choose_strategy(
            {"task": task, "resource_pressure": pressure, "depth": "deep" if mode in {"deep", "distributed", "reflective"} else None}
        )
        return {
            "mode": mode,
            "strategy": selected if selected["score"] >= base["score"] else base,
            "complexity": complexity,
            "latency_target_ms": latency_target,
            "reason": self._reason(mode, complexity, pressure, confidence),
        }

    def estimate_complexity(self, task: str, context: dict[str, Any]) -> float:
        words = len(task.split())
        deps = len(context.get("dependencies", []))
        modalities = len(context.get("modalities", []))
        risk = 0.25 if context.get("risk") == "high" else 0
        return round(max(0.0, min(1.0, words / 80 + deps * 0.08 + modalities * 0.08 + risk)), 3)

    @staticmethod
    def _reason(mode: str, complexity: float, pressure: float, confidence: float) -> str:
        return f"mode={mode}; complexity={complexity:.3f}; pressure={pressure:.3f}; confidence={confidence:.3f}"
