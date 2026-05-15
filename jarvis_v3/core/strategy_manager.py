"""Cognitive strategy marketplace with benchmarking and active selection."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "strategies.db"


class CognitiveStrategyManager:
    """Maintains competing reasoning strategies and switches by benchmark score."""

    DEFAULT_STRATEGIES = {
        "fast_reasoning": {
            "description": "Low-latency reasoning with shallow planning.",
            "resource_weight": 0.2,
            "quality_weight": 0.55,
            "latency_weight": 0.25,
            "constraints": {"max_depth": 2, "preferred_concurrency": 6},
        },
        "deep_reasoning": {
            "description": "Higher-quality reasoning with more simulation and reflection.",
            "resource_weight": 0.25,
            "quality_weight": 0.65,
            "latency_weight": 0.1,
            "constraints": {"max_depth": 5, "preferred_concurrency": 3},
        },
        "low_resource": {
            "description": "Conservative strategy for high pressure environments.",
            "resource_weight": 0.55,
            "quality_weight": 0.35,
            "latency_weight": 0.1,
            "constraints": {"max_depth": 2, "preferred_concurrency": 1},
        },
        "coding_focused": {
            "description": "Prioritizes code quality, tests, and rollback evidence.",
            "resource_weight": 0.2,
            "quality_weight": 0.7,
            "latency_weight": 0.1,
            "constraints": {"max_depth": 4, "preferred_concurrency": 4, "requires_tests": True},
        },
    }

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("strategies", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()
        self.ensure_defaults()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS strategies (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    config TEXT NOT NULL,
                    active INTEGER DEFAULT 0,
                    score REAL DEFAULT 0.5,
                    samples INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS strategy_benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    score REAL NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def ensure_defaults(self) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            for name, cfg in self.DEFAULT_STRATEGIES.items():
                db.execute(
                    """
                    INSERT OR IGNORE INTO strategies(name,description,config,active,score,samples,updated_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        name,
                        cfg["description"],
                        json.dumps(cfg, ensure_ascii=False, default=str),
                        1 if name == "fast_reasoning" else 0,
                        0.5,
                        0,
                        datetime.now().isoformat(),
                    ),
                )

    def register_strategy(self, name: str, description: str, config: dict[str, Any]) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO strategies(name,description,config,active,score,samples,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                  description=excluded.description,
                  config=excluded.config,
                  updated_at=excluded.updated_at
                """,
                (name, description, json.dumps(config, ensure_ascii=False, default=str), 0, 0.5, 0, datetime.now().isoformat()),
            )
        return self.get_strategy(name)

    def benchmark_strategy(
        self,
        name: str,
        scenario: dict[str, Any],
        evaluator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        strategy = self.get_strategy(name)
        started = time.perf_counter()
        if evaluator:
            metrics = evaluator(strategy, scenario)
        else:
            metrics = self._deterministic_metrics(strategy, scenario)
        metrics.setdefault("latency_ms", round((time.perf_counter() - started) * 1000, 1))
        score = self._score(strategy["config"], metrics)
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT score,samples FROM strategies WHERE name=?", (name,)).fetchone()
            old_score, samples = row or (0.5, 0)
            new_samples = samples + 1
            new_score = round((old_score * samples + score) / new_samples, 3)
            db.execute(
                "UPDATE strategies SET score=?, samples=?, updated_at=? WHERE name=?",
                (new_score, new_samples, datetime.now().isoformat(), name),
            )
            db.execute(
                "INSERT INTO strategy_benchmarks(strategy,metrics,score,created_at) VALUES(?,?,?,?)",
                (name, json.dumps(metrics, ensure_ascii=False, default=str), score, datetime.now().isoformat()),
            )
        return {"strategy": name, "metrics": metrics, "score": score, "aggregate_score": self.get_strategy(name)["score"]}

    def choose_strategy(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        strategies = self.list_strategies()
        pressure = context.get("resource_pressure", 0.0)
        task = str(context.get("task", "")).lower()
        ranked = []
        for strategy in strategies:
            score = strategy["score"]
            if pressure > 0.7 and strategy["name"] == "low_resource":
                score += 0.25
            if any(word in task for word in ["code", "plugin", "test", "debug"]) and strategy["name"] == "coding_focused":
                score += 0.2
            if context.get("depth") == "deep" and strategy["name"] == "deep_reasoning":
                score += 0.15
            ranked.append({**strategy, "selection_score": round(score, 3)})
        ranked.sort(key=lambda item: item["selection_score"], reverse=True)
        selected = ranked[0] if ranked else self.get_strategy("fast_reasoning")
        self.set_active(selected["name"])
        return selected

    def set_active(self, name: str) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE strategies SET active=0")
            db.execute("UPDATE strategies SET active=1, updated_at=? WHERE name=?", (datetime.now().isoformat(), name))

    def active_strategy(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT name,description,config,active,score,samples,updated_at FROM strategies WHERE active=1 LIMIT 1"
            ).fetchone()
        return self._row(row) if row else self.get_strategy("fast_reasoning")

    def get_strategy(self, name: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT name,description,config,active,score,samples,updated_at FROM strategies WHERE name=?",
                (name,),
            ).fetchone()
        if not row:
            raise KeyError(f"Strategy not found: {name}")
        return self._row(row)

    def list_strategies(self) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT name,description,config,active,score,samples,updated_at FROM strategies ORDER BY score DESC,name"
            ).fetchall()
        return [self._row(row) for row in rows]

    def benchmark_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT strategy,metrics,score,created_at FROM strategy_benchmarks ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"strategy": row[0], "metrics": json.loads(row[1] or "{}"), "score": row[2], "created_at": row[3]}
            for row in rows
        ]

    @staticmethod
    def _deterministic_metrics(strategy: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
        complexity = min(1.0, len(str(scenario)) / 2000)
        constraints = strategy["config"].get("constraints", {})
        depth = constraints.get("max_depth", 2)
        quality = min(1.0, 0.45 + depth * 0.08 + complexity * 0.12)
        latency_ms = 60 + depth * 35 + complexity * 100
        resource_cost = min(1.0, 0.15 + depth * 0.08)
        return {"quality": round(quality, 3), "latency_ms": round(latency_ms, 1), "resource_cost": round(resource_cost, 3)}

    @staticmethod
    def _score(config: dict[str, Any], metrics: dict[str, Any]) -> float:
        quality = float(metrics.get("quality", 0.5))
        latency = min(1.0, float(metrics.get("latency_ms", 500)) / 1000)
        resource = min(1.0, float(metrics.get("resource_cost", 0.5)))
        score = (
            quality * config.get("quality_weight", 0.5)
            + (1 - latency) * config.get("latency_weight", 0.2)
            + (1 - resource) * config.get("resource_weight", 0.3)
        )
        return round(max(0.0, min(1.0, score)), 3)

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "name": row[0],
            "description": row[1],
            "config": json.loads(row[2] or "{}"),
            "active": bool(row[3]),
            "score": row[4],
            "samples": row[5],
            "updated_at": row[6],
        }
