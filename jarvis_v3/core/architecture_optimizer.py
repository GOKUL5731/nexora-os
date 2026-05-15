"""Self-organizing architecture optimizer with benchmark-first proposals."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.evolutionary_memory import EvolutionaryMemory
from core.self_stability_engine import SelfStabilityEngine
from core.simulation_universe import SimulationUniverse


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "architecture_optimizer.db"


class ArchitectureOptimizer:
    """Proposes architecture reorganizations and gates them through simulation and stability."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        universe: SimulationUniverse | None = None,
        stability: SelfStabilityEngine | None = None,
        evolutionary_memory: EvolutionaryMemory | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("architecture_optimizer", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.universe = universe or SimulationUniverse(self.config)
        self.stability = stability or SelfStabilityEngine(self.config)
        self.evolutionary_memory = evolutionary_memory or EvolutionaryMemory(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS architecture_proposals (
                    id TEXT PRIMARY KEY,
                    proposal TEXT NOT NULL,
                    benchmark TEXT DEFAULT '{}',
                    stability TEXT DEFAULT '{}',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def propose(self, autonomy_snapshot: dict[str, Any], synthesis: dict[str, Any] | None = None) -> dict[str, Any]:
        proposals = []
        resources = autonomy_snapshot.get("resources", {})
        graph = autonomy_snapshot.get("graph", {})
        skills = autonomy_snapshot.get("skills", {}).get("recommendations", [])
        if resources.get("pressure_score", 0) > 0.7:
            proposals.append({"component": "resource_scheduler", "change": "lower default concurrency and prefer low_resource strategy"})
        if graph.get("opportunities"):
            proposals.append({"component": "knowledge_graph", "change": "repair bottlenecks and invalid dependencies"})
        for skill in skills[:3]:
            proposals.append({"component": "skill_evolution", "change": f"run targeted trials for {skill['skill']}"})
        for item in (synthesis or {}).get("proposals", [])[:3]:
            proposals.append({"component": item.get("type", "synthesis"), "change": item.get("action", "apply synthesized improvement")})
        if not proposals:
            proposals.append({"component": "architecture", "change": "maintain current topology and continue benchmarking"})
        proposal = {
            "id": f"arch-proposal-{uuid.uuid4().hex[:12]}",
            "components": proposals,
            "rollback_plan": True,
            "tests": ["meta_cognitive", "cognitive_autonomy", "core_os"],
        }
        return proposal

    def benchmark_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        scenario = {
            "components": proposal.get("components", []),
            "rollback_plan": proposal.get("rollback_plan", False),
            "tests": proposal.get("tests", []),
        }
        benchmark = self.universe.run_scenario("architecture", scenario)
        stability = self.stability.stability_gate(proposal, benchmark.get("result", {}))
        status = "approved" if benchmark["passed"] and stability["stable"] else "blocked"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO architecture_proposals VALUES (?,?,?,?,?,?)",
                (
                    proposal["id"],
                    json.dumps(proposal, ensure_ascii=False, default=str),
                    json.dumps(benchmark, ensure_ascii=False, default=str),
                    json.dumps(stability, ensure_ascii=False, default=str),
                    status,
                    datetime.now().isoformat(),
                ),
            )
        self.evolutionary_memory.record(
            "architecture_proposal",
            proposal["id"],
            status,
            {"score": 1.0 - benchmark["result"].get("risk_score", 1.0)},
            {"proposal": proposal, "benchmark": benchmark, "stability": stability},
        )
        return {"proposal": proposal, "benchmark": benchmark, "stability": stability, "status": status}

    def restructuring_plan(self, autonomy_snapshot: dict[str, Any]) -> dict[str, Any]:
        proposal = self.propose(autonomy_snapshot)
        return self.benchmark_proposal(proposal)

    def recent_proposals(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,proposal,benchmark,stability,status,created_at FROM architecture_proposals ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "proposal": json.loads(row[1] or "{}"),
                "benchmark": json.loads(row[2] or "{}"),
                "stability": json.loads(row[3] or "{}"),
                "status": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]
