"""Adaptive architecture evolution with sandboxed, benchmarked proposals."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.governance_engine import GovernanceEngine
from core.self_stability_engine import SelfStabilityEngine
from core.simulation_universe import SimulationUniverse


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "adaptive_architecture.db"


class AdaptiveArchitectureSystem:
    """Creates architecture alternatives and promotes only governed, stable candidates."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        universe: SimulationUniverse | None = None,
        stability: SelfStabilityEngine | None = None,
        governance: GovernanceEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("adaptive_architecture", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.universe = universe or SimulationUniverse(self.config)
        self.stability = stability or SelfStabilityEngine(self.config)
        self.governance = governance or GovernanceEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS architecture_candidates (
                    id TEXT PRIMARY KEY,
                    candidate TEXT NOT NULL,
                    benchmark TEXT DEFAULT '{}',
                    governance TEXT DEFAULT '{}',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def generate_candidates(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        pressure = snapshot.get("resources", {}).get("pressure_score", 0.0)
        opportunities = snapshot.get("graph", {}).get("opportunities", [])
        candidates = [
            {
                "id": f"arch-candidate-{uuid.uuid4().hex[:10]}",
                "name": "conservative_resource_pipeline" if pressure > 0.6 else "balanced_cognitive_pipeline",
                "components": ["resource_intelligence", "reasoning_strategy_engine", "distributed_cognition"],
                "changes": ["adjust concurrency", "route by confidence", "record observability traces"],
                "sandboxed": True,
                "benchmarked": False,
                "rollback_plan": True,
            }
        ]
        if opportunities:
            candidates.append(
                {
                    "id": f"arch-candidate-{uuid.uuid4().hex[:10]}",
                    "name": "graph_optimized_orchestration",
                    "components": ["knowledge_graph", "orchestration_intelligence"],
                    "changes": [item.get("action", "optimize graph") for item in opportunities[:3]],
                    "sandboxed": True,
                    "benchmarked": False,
                    "rollback_plan": True,
                }
            )
        return candidates

    def benchmark_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        scenario = {
            "components": [{"component": c} for c in candidate.get("components", [])],
            "rollback_plan": candidate.get("rollback_plan", False),
            "tests": ["architecture", "governance", "rollback"],
        }
        benchmark = self.universe.run_scenario("architecture", scenario)
        candidate = {**candidate, "benchmarked": True}
        governance = self.governance.evaluate(candidate)
        stability = self.stability.stability_gate(candidate, benchmark.get("result", {}))
        status = "approved" if benchmark["passed"] and governance["decision"] == "approved" and stability["stable"] else "blocked"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO architecture_candidates VALUES (?,?,?,?,?,?)",
                (
                    candidate["id"],
                    json.dumps(candidate, ensure_ascii=False, default=str),
                    json.dumps({"benchmark": benchmark, "stability": stability}, ensure_ascii=False, default=str),
                    json.dumps(governance, ensure_ascii=False, default=str),
                    status,
                    datetime.now().isoformat(),
                ),
            )
        return {"candidate": candidate, "benchmark": benchmark, "stability": stability, "governance": governance, "status": status}

    def evolve(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        candidates = self.generate_candidates(snapshot)
        results = [self.benchmark_candidate(candidate) for candidate in candidates]
        approved = [result for result in results if result["status"] == "approved"]
        best = approved[0] if approved else (results[0] if results else None)
        return {"candidates": results, "selected": best}

    def rollback_tree(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "candidate": candidate.get("id"),
            "rollback_steps": [
                "restore stability checkpoint",
                "reset active strategy",
                "rebuild graph-derived indexes",
                "replay last stable memory snapshot",
            ],
        }

    def recent_candidates(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,candidate,benchmark,governance,status,created_at FROM architecture_candidates ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "candidate": json.loads(row[1] or "{}"),
                "benchmark": json.loads(row[2] or "{}"),
                "governance": json.loads(row[3] or "{}"),
                "status": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]
