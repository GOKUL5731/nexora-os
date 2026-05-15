"""Cognitive reflection engine: observe, analyze, improve, benchmark, learn."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "reflection.db"


class CognitiveReflectionEngine:
    """Detects repeated failures and slow modules, then creates improvement plans."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("reflection", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms REAL DEFAULT 0,
                    error TEXT DEFAULT '',
                    data TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis TEXT NOT NULL,
                    improvement_plan TEXT NOT NULL,
                    benchmark TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def observe(
        self,
        module: str,
        event_type: str,
        status: str,
        latency_ms: float = 0,
        error: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO observations(module,event_type,status,latency_ms,error,data,timestamp) VALUES(?,?,?,?,?,?,?)",
                (
                    module,
                    event_type,
                    status,
                    float(latency_ms),
                    error[:1000],
                    json.dumps(data or {}, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )

    def analyze(self, limit: int = 500) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT module,event_type,status,latency_ms,error,data,timestamp "
                "FROM observations ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        failures = Counter()
        latency = defaultdict(list)
        status_counts = Counter()
        for module, event_type, status, latency_ms, error, _data, _ts in rows:
            status_counts[status] += 1
            latency[module].append(latency_ms or 0)
            if status in {"failed", "error"} or error:
                signature = f"{module}:{event_type}:{(error or status)[:120]}"
                failures[signature] += 1
        slow_modules = [
            {"module": module, "avg_latency_ms": round(sum(values) / max(len(values), 1), 2), "samples": len(values)}
            for module, values in latency.items()
            if values and sum(values) / len(values) >= self.config.get("reflection", {}).get("slow_ms", 750)
        ]
        slow_modules.sort(key=lambda item: item["avg_latency_ms"], reverse=True)
        return {
            "sample_count": len(rows),
            "status_counts": dict(status_counts),
            "repeated_failures": [
                {"signature": sig, "count": count} for sig, count in failures.most_common(10) if count >= 2
            ],
            "slow_modules": slow_modules[:10],
        }

    def generate_improvement_plan(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        plan = []
        for failure in analysis.get("repeated_failures", []):
            module = failure["signature"].split(":", 1)[0]
            plan.append(
                {
                    "target": module,
                    "reason": "repeated_failure",
                    "action": "add retry guard, capture richer diagnostics, and route failing input to sandbox validation",
                    "priority": min(10, 5 + failure["count"]),
                }
            )
        for slow in analysis.get("slow_modules", []):
            plan.append(
                {
                    "target": slow["module"],
                    "reason": "latency",
                    "action": "profile hot path, cache stable inputs, and reduce concurrency when resource pressure is high",
                    "priority": 7,
                }
            )
        plan.sort(key=lambda item: item["priority"], reverse=True)
        return plan

    async def run_cycle(self, benchmark: Callable[[], Any] | None = None) -> dict[str, Any]:
        analysis = self.analyze()
        improvement_plan = self.generate_improvement_plan(analysis)
        benchmark_result = {}
        if benchmark:
            result = benchmark()
            if hasattr(result, "__await__"):
                result = await result
            benchmark_result = result if isinstance(result, dict) else {"result": result}
        cycle = {
            "cycle": ["observe", "analyze", "reflect", "improve", "benchmark", "learn"],
            "analysis": analysis,
            "improvement_plan": improvement_plan,
            "benchmark": benchmark_result,
            "timestamp": datetime.now().isoformat(),
        }
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO reflections(analysis,improvement_plan,benchmark,created_at) VALUES(?,?,?,?)",
                (
                    json.dumps(analysis, ensure_ascii=False, default=str),
                    json.dumps(improvement_plan, ensure_ascii=False, default=str),
                    json.dumps(benchmark_result, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )
        return cycle
