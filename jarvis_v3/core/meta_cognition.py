"""Meta-cognition engine: reasoning about reasoning quality and strategy fit."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.strategy_manager import CognitiveStrategyManager


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "meta_cognition.db"


class MetaCognitionEngine:
    """Observes cognition, compares strategies, and proposes bounded improvements."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        strategies: CognitiveStrategyManager | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("meta_cognition", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.strategies = strategies or CognitiveStrategyManager(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS cognition_observations (
                    id TEXT PRIMARY KEY,
                    metrics TEXT NOT NULL,
                    analysis TEXT NOT NULL,
                    active_strategy TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cognition_deployments (
                    id TEXT PRIMARY KEY,
                    proposal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def observe_cognition(self, autonomy_snapshot: dict[str, Any]) -> dict[str, Any]:
        loop = autonomy_snapshot.get("loop", {})
        goals = autonomy_snapshot.get("goals", {})
        skills = autonomy_snapshot.get("skills", {}).get("skills", [])
        graph = autonomy_snapshot.get("graph", {})
        resources = autonomy_snapshot.get("resources", {})
        society = autonomy_snapshot.get("society", {}).get("agents", [])
        metrics = {
            "cycle_status": (loop.get("last_cycle") or {}).get("status", "unknown"),
            "cycle_duration_ms": (loop.get("last_cycle") or {}).get("duration_ms", 0),
            "goal_completion_ratio": self._goal_completion_ratio(goals),
            "average_skill_score": self._average([s.get("score", 0.5) for s in skills]),
            "graph_valid": graph.get("validation", {}).get("valid", True),
            "resource_pressure": resources.get("pressure_score", 0.0),
            "average_agent_reputation": self._average([a.get("reputation", 0.5) for a in society]),
            "simulation_pass_rate": self._simulation_pass_rate(autonomy_snapshot.get("simulations", [])),
        }
        analysis = self.analyze_cognition(metrics)
        record_id = f"meta-{uuid.uuid4().hex[:12]}"
        active = self.strategies.active_strategy()["name"]
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO cognition_observations VALUES (?,?,?,?,?)",
                (
                    record_id,
                    json.dumps(metrics, ensure_ascii=False, default=str),
                    json.dumps(analysis, ensure_ascii=False, default=str),
                    active,
                    datetime.now().isoformat(),
                ),
            )
        return {"id": record_id, "metrics": metrics, "analysis": analysis, "active_strategy": active}

    def analyze_cognition(self, metrics: dict[str, Any]) -> dict[str, Any]:
        issues = []
        if metrics["cycle_status"] == "error":
            issues.append({"type": "reasoning_loop_error", "severity": "high"})
        if metrics["goal_completion_ratio"] < 0.35:
            issues.append({"type": "low_goal_completion", "severity": "medium"})
        if metrics["average_skill_score"] < 0.55:
            issues.append({"type": "skill_degradation", "severity": "medium"})
        if not metrics["graph_valid"]:
            issues.append({"type": "graph_inconsistency", "severity": "high"})
        if metrics["resource_pressure"] > 0.75:
            issues.append({"type": "resource_pressure", "severity": "high"})
        if metrics["average_agent_reputation"] < 0.5:
            issues.append({"type": "society_quality_drop", "severity": "medium"})
        score = 1.0
        for issue in issues:
            score -= 0.18 if issue["severity"] == "high" else 0.1
        return {
            "cognitive_quality": round(max(0.0, min(1.0, score)), 3),
            "issues": issues,
            "recommendations": self._recommend(metrics, issues),
        }

    def compare_strategies(self, scenario: dict[str, Any]) -> dict[str, Any]:
        results = [
            self.strategies.benchmark_strategy(strategy["name"], scenario)
            for strategy in self.strategies.list_strategies()
        ]
        results.sort(key=lambda item: item["score"], reverse=True)
        selected = self.strategies.choose_strategy(
            {
                "resource_pressure": scenario.get("resource_pressure", 0.0),
                "task": scenario.get("task", ""),
                "depth": scenario.get("depth"),
            }
        )
        return {"results": results, "selected": selected}

    def optimize_cognition(self, observation: dict[str, Any]) -> dict[str, Any]:
        metrics = observation.get("metrics", {})
        analysis = observation.get("analysis", {})
        scenario = {
            "task": "cognitive optimization",
            "resource_pressure": metrics.get("resource_pressure", 0.0),
            "depth": "deep" if analysis.get("issues") else "normal",
        }
        strategy_result = self.compare_strategies(scenario)
        proposal = {
            "id": f"proposal-{uuid.uuid4().hex[:12]}",
            "selected_strategy": strategy_result["selected"]["name"],
            "strategy_results": strategy_result["results"],
            "actions": analysis.get("recommendations", []),
            "requires_stability_gate": True,
        }
        return proposal

    def deploy_improved_cognition(self, proposal: dict[str, Any], stability_report: dict[str, Any]) -> dict[str, Any]:
        status = "deployed" if stability_report.get("stable") and stability_report.get("integrity", {}).get("ok") else "blocked"
        if status == "deployed":
            self.strategies.set_active(proposal["selected_strategy"])
        deployment_id = f"cog-deploy-{uuid.uuid4().hex[:10]}"
        record = {"id": deployment_id, "proposal": proposal, "status": status, "created_at": datetime.now().isoformat()}
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO cognition_deployments VALUES (?,?,?,?)",
                (deployment_id, json.dumps(proposal, ensure_ascii=False, default=str), status, record["created_at"]),
            )
        return record

    def recent_observations(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,metrics,analysis,active_strategy,created_at FROM cognition_observations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "metrics": json.loads(row[1] or "{}"),
                "analysis": json.loads(row[2] or "{}"),
                "active_strategy": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    @staticmethod
    def _goal_completion_ratio(goals: dict[str, Any]) -> float:
        counts = goals.get("status_counts", {})
        total = goals.get("total", 0) or sum(counts.values())
        return round(counts.get("completed", 0) / max(1, total), 3)

    @staticmethod
    def _simulation_pass_rate(simulations: list[dict[str, Any]]) -> float:
        if not simulations:
            return 1.0
        return round(sum(1 for sim in simulations if sim.get("passed")) / len(simulations), 3)

    @staticmethod
    def _average(values: list[float]) -> float:
        return round(sum(values) / max(1, len(values)), 3)

    @staticmethod
    def _recommend(metrics: dict[str, Any], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        actions = []
        for issue in issues:
            if issue["type"] == "resource_pressure":
                actions.append({"action": "switch to low_resource strategy", "priority": 9})
            elif issue["type"] == "graph_inconsistency":
                actions.append({"action": "repair graph before planning", "priority": 10})
            elif issue["type"] == "skill_degradation":
                actions.append({"action": "increase sandbox trials for weak skills", "priority": 7})
            elif issue["type"] == "society_quality_drop":
                actions.append({"action": "rebalance agent hierarchy and specialization", "priority": 7})
            else:
                actions.append({"action": f"investigate {issue['type']}", "priority": 6})
        if not actions and metrics.get("simulation_pass_rate", 1.0) >= 0.8:
            actions.append({"action": "continue current cognitive strategy", "priority": 3})
        return sorted(actions, key=lambda item: item["priority"], reverse=True)
