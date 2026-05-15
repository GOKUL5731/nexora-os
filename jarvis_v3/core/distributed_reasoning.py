"""Distributed multi-model reasoning architecture."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


Reasoner = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class ReasoningRoute:
    name: str
    mode: str
    keywords: tuple[str, ...]
    weight: float
    reasoner: Reasoner | None = None


class DistributedReasoningEngine:
    """Routes classification, planning, coding, and perception to different reasoners."""

    def __init__(self, config: dict | None = None, orchestrator: Any = None):
        self.config = config or {}
        self.orchestrator = orchestrator
        self.routes: dict[str, ReasoningRoute] = {}
        self._register_defaults()

    def register_route(
        self,
        name: str,
        mode: str,
        keywords: tuple[str, ...] | list[str],
        weight: float = 1.0,
        reasoner: Reasoner | None = None,
    ) -> None:
        self.routes[name] = ReasoningRoute(name, mode, tuple(keywords), weight, reasoner)

    async def reason(self, prompt: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        selected = self._select_routes(prompt, context)
        outputs = await asyncio.gather(*(self._run_route(route, prompt, context) for route in selected))
        return self.combine(outputs)

    def combine(self, outputs: list[dict[str, Any]]) -> dict[str, Any]:
        if not outputs:
            return {"answer": "", "confidence": 0, "outputs": []}
        total = sum(o.get("confidence", 0.5) * o.get("weight", 1.0) for o in outputs) or 1
        ranked = sorted(outputs, key=lambda o: o.get("confidence", 0.5) * o.get("weight", 1.0), reverse=True)
        answer_parts = [o.get("answer", "") for o in ranked if o.get("answer")]
        return {
            "answer": "\n".join(answer_parts[:4]),
            "confidence": round(min(0.99, total / max(len(outputs), 1)), 3),
            "outputs": ranked,
            "routes": [o["route"] for o in ranked],
        }

    def _select_routes(self, prompt: str, context: dict[str, Any]) -> list[ReasoningRoute]:
        lower = prompt.lower()
        mode = context.get("mode", "")
        selected = [
            route
            for route in self.routes.values()
            if route.mode == mode or any(keyword in lower for keyword in route.keywords)
        ]
        if not selected:
            selected = [self.routes["small_classifier"], self.routes["reasoning_planner"]]
        return selected[:4]

    async def _run_route(self, route: ReasoningRoute, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        if route.reasoner:
            result = await route.reasoner(prompt, context)
        elif self.orchestrator and hasattr(self.orchestrator, "process"):
            response = await self.orchestrator.process(prompt, context={**context, "reasoning_mode": route.mode})
            result = {"answer": response.get("message", str(response)), "confidence": response.get("confidence", 0.6)}
        else:
            result = self._deterministic_reason(route, prompt, context)
        return {"route": route.name, "mode": route.mode, "weight": route.weight, **result}

    def _deterministic_reason(self, route: ReasoningRoute, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        if route.mode == "classification":
            label = "coding" if "code" in prompt.lower() else "planning" if "plan" in prompt.lower() else "general"
            return {"answer": f"classification={label}", "confidence": 0.65, "label": label}
        if route.mode == "planning":
            return {"answer": "Plan: clarify objective, decompose work, execute dependencies, validate, summarize.", "confidence": 0.7}
        if route.mode == "coding":
            return {"answer": "Coding route: implement in the smallest compatible module and run focused tests.", "confidence": 0.7}
        if route.mode == "vision":
            return {"answer": "Vision route: gather perception input, detect objects/text, then ground the response.", "confidence": 0.6}
        return {"answer": prompt, "confidence": 0.5}

    def _register_defaults(self) -> None:
        self.register_route("small_classifier", "classification", ("classify", "route", "intent"), 0.7)
        self.register_route("reasoning_planner", "planning", ("plan", "goal", "workflow", "architecture"), 1.0)
        self.register_route("coding_model", "coding", ("code", "implement", "debug", "test"), 1.0)
        self.register_route("vision_model", "vision", ("vision", "image", "screen", "camera", "see"), 0.9)
