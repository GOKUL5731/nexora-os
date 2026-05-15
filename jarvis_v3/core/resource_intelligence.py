"""Autonomous resource intelligence for forecasting and adaptive balancing."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from core.resource_orchestrator import ResourceOrchestrator


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "resource_intelligence.db"


class ResourceIntelligence:
    """Forecasts resource demand and recommends model/concurrency/caching decisions."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        resources: ResourceOrchestrator | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("resource_intelligence", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.resources = resources or ResourceOrchestrator(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS resource_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS resource_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def sample(self) -> dict[str, Any]:
        snap = self.resources.snapshot()
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO resource_samples(sample,created_at) VALUES(?,?)",
                (json.dumps(snap, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        return snap

    def forecast(self, horizon_samples: int = 10) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT sample FROM resource_samples ORDER BY id DESC LIMIT ?",
                (horizon_samples,),
            ).fetchall()
        samples = [json.loads(row[0] or "{}") for row in rows]
        if not samples:
            samples = [self.sample()]
        avg_pressure = sum(s.get("pressure_score", 0.0) for s in samples) / len(samples)
        trend = 0.0
        if len(samples) >= 2:
            trend = samples[0].get("pressure_score", 0.0) - samples[-1].get("pressure_score", 0.0)
        predicted = max(0.0, min(1.0, avg_pressure + trend * 0.5))
        return {
            "average_pressure": round(avg_pressure, 3),
            "trend": round(trend, 3),
            "predicted_pressure": round(predicted, 3),
            "samples": len(samples),
        }

    def optimize(self, workload: dict[str, Any] | None = None) -> dict[str, Any]:
        workload = workload or {}
        snap = self.sample()
        forecast = self.forecast()
        pressure = max(snap.get("pressure_score", 0.0), forecast["predicted_pressure"])
        if pressure > 0.8:
            mode = "conserve"
            concurrency = 1
            model_action = "unload_idle_models"
        elif pressure > 0.55:
            mode = "balanced"
            concurrency = max(1, min(4, snap.get("recommended_concurrency", 2)))
            model_action = "prefer_cached_models"
        else:
            mode = "performance"
            concurrency = max(2, snap.get("recommended_concurrency", 4))
            model_action = "preload_likely_models"
        decision = {
            "mode": mode,
            "concurrency": concurrency,
            "model_action": model_action,
            "forecast": forecast,
            "workload": workload,
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO resource_decisions(decision,created_at) VALUES(?,?)",
                (json.dumps(decision, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        return decision

    def benchmark(self, workloads: list[dict[str, Any]]) -> dict[str, Any]:
        decisions = [self.optimize(workload) for workload in workloads]
        avg_concurrency = sum(d["concurrency"] for d in decisions) / max(1, len(decisions))
        return {
            "workloads": len(workloads),
            "average_concurrency": round(avg_concurrency, 3),
            "decisions": decisions,
        }

    def history(self, limit: int = 30) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            samples = db.execute("SELECT sample,created_at FROM resource_samples ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            decisions = db.execute("SELECT decision,created_at FROM resource_decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return {
            "samples": [{"sample": json.loads(row[0] or "{}"), "created_at": row[1]} for row in samples],
            "decisions": [{"decision": json.loads(row[0] or "{}"), "created_at": row[1]} for row in decisions],
        }
