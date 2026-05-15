"""Continuous cognitive loop for the persistent autonomous environment."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable


AsyncStep = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class CognitiveCycle:
    id: int
    started_at: str
    steps: list[str] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0
    status: str = "running"
    error: str = ""


class ContinuousCognitiveLoop:
    """Runs Observe -> Analyze -> Predict -> Plan -> Simulate -> Decide -> Execute -> Reflect -> Learn."""

    STEP_NAMES = ["observe", "analyze", "predict", "plan", "simulate", "decide", "execute", "reflect", "learn"]

    def __init__(
        self,
        steps: dict[str, AsyncStep | Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
        min_interval: float = 3.0,
        max_interval: float = 60.0,
    ):
        self.steps = steps or {}
        self.min_interval = min_interval
        self.max_interval = max_interval
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.cycles: list[dict[str, Any]] = []
        self.interval = min_interval

    async def run_once(self, seed: dict[str, Any] | None = None) -> dict[str, Any]:
        cycle = CognitiveCycle(id=len(self.cycles) + 1, started_at=datetime.now().isoformat(), state=seed or {})
        started = time.perf_counter()
        try:
            state = cycle.state
            for name in self.STEP_NAMES:
                handler = self.steps.get(name)
                if handler:
                    value = handler(state)
                    if hasattr(value, "__await__"):
                        value = await value
                    if isinstance(value, dict):
                        state.update(value)
                cycle.steps.append(name)
            cycle.state = state
            cycle.status = "completed"
        except Exception as exc:
            cycle.status = "error"
            cycle.error = str(exc)
        cycle.duration_ms = round((time.perf_counter() - started) * 1000, 1)
        record = cycle.__dict__.copy()
        self.cycles.append(record)
        self.cycles = self.cycles[-100:]
        self._adapt_interval(record)
        return record

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": bool(self._task and not self._task.done()),
            "interval": self.interval,
            "last_cycle": self.cycles[-1] if self.cycles else None,
            "cycle_count": len(self.cycles),
        }

    async def _run_forever(self) -> None:
        while not self._stop.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                continue

    def _adapt_interval(self, cycle: dict[str, Any]) -> None:
        state = cycle.get("state", {})
        pressure = state.get("resources", {}).get("pressure_score", 0.0)
        has_suggestions = bool(state.get("suggestions") or state.get("decisions"))
        if cycle.get("status") == "error" or pressure > 0.75:
            self.interval = min(self.max_interval, self.interval * 1.5)
        elif has_suggestions:
            self.interval = max(self.min_interval, self.interval * 0.8)
        else:
            self.interval = min(self.max_interval, self.interval * 1.1)
