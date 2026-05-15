"""Recursive cognitive optimization engine."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.adaptive_architecture import AdaptiveArchitectureSystem
from core.ecosystem_memory import EcosystemMemory
from core.ecosystem_stability import EcosystemStabilityEngine
from core.governance_engine import GovernanceEngine
from core.observability_engine import ObservabilityEngine
from core.reasoning_strategy_engine import DynamicReasoningStrategyEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "recursive_optimizer.db"


class RecursiveCognitiveOptimizer:
    """Observe -> evaluate -> compare -> simulate -> benchmark -> evolve -> deploy safely."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        architecture: AdaptiveArchitectureSystem | None = None,
        stability: EcosystemStabilityEngine | None = None,
        governance: GovernanceEngine | None = None,
        strategies: DynamicReasoningStrategyEngine | None = None,
        memory: EcosystemMemory | None = None,
        observability: ObservabilityEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("recursive_optimizer", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.architecture = architecture or AdaptiveArchitectureSystem(self.config)
        self.stability = stability or EcosystemStabilityEngine(self.config)
        self.governance = governance or GovernanceEngine(self.config)
        self.strategies = strategies or DynamicReasoningStrategyEngine(self.config)
        self.memory = memory or EcosystemMemory(self.config)
        self.observability = observability or ObservabilityEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS recursive_cycles (
                    id TEXT PRIMARY KEY,
                    snapshot_summary TEXT NOT NULL,
                    evaluation TEXT NOT NULL,
                    architecture TEXT NOT NULL,
                    governance TEXT NOT NULL,
                    stability TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def evaluate_cognition(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        loop = snapshot.get("loop", {}).get("last_cycle") or {}
        resources = snapshot.get("resources", {})
        skills = snapshot.get("skills", {}).get("skills", [])
        goals = snapshot.get("goals", {})
        avg_skill = sum(s.get("score", 0.5) for s in skills) / max(1, len(skills))
        completed = goals.get("status_counts", {}).get("completed", 0)
        total = goals.get("total", 0)
        score = 0.35
        score += min(0.25, avg_skill * 0.25)
        score += min(0.2, completed / max(1, total) * 0.2)
        score += max(0.0, 0.2 - resources.get("pressure_score", 0.0) * 0.2)
        if loop.get("status") == "error":
            score -= 0.2
        return {
            "cognition_efficiency": round(max(0.0, min(1.0, score)), 3),
            "avg_skill": round(avg_skill, 3),
            "goal_completion": round(completed / max(1, total), 3),
            "resource_pressure": resources.get("pressure_score", 0.0),
        }

    def run_cycle(self, snapshot: dict[str, Any], objective: str = "recursive optimization") -> dict[str, Any]:
        cycle_id = f"recursive-{uuid.uuid4().hex[:12]}"
        self.observability.ingest_autonomy_snapshot(snapshot)
        evaluation = self.evaluate_cognition(snapshot)
        strategy = self.strategies.select(objective, {"resource_pressure": evaluation["resource_pressure"], "confidence": evaluation["cognition_efficiency"]})
        architecture = self.architecture.evolve(snapshot)
        proposal = {
            "type": "architecture",
            "id": cycle_id,
            "sandboxed": True,
            "benchmarked": bool(architecture.get("selected")),
            "rollback_plan": True,
            "strategy": strategy,
            "architecture": architecture,
        }
        governance = self.governance.evaluate(proposal, {"resource_pressure": evaluation["resource_pressure"]})
        stability = self.stability.stabilize(snapshot)
        status = "deployed" if governance["decision"] == "approved" and stability["governance"]["decision"] == "approved" and architecture.get("selected", {}).get("status") == "approved" else "simulated"
        record = {
            "id": cycle_id,
            "evaluation": evaluation,
            "strategy": strategy,
            "architecture": architecture,
            "governance": governance,
            "stability": stability,
            "status": status,
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO recursive_cycles VALUES (?,?,?,?,?,?,?,?)",
                (
                    cycle_id,
                    json.dumps({"keys": sorted(snapshot.keys())}, ensure_ascii=False, default=str),
                    json.dumps(evaluation, ensure_ascii=False, default=str),
                    json.dumps(architecture, ensure_ascii=False, default=str),
                    json.dumps(governance, ensure_ascii=False, default=str),
                    json.dumps(stability, ensure_ascii=False, default=str),
                    status,
                    record["created_at"],
                ),
            )
        self.memory.remember("optimization", cycle_id, record, score=evaluation["cognition_efficiency"], source="recursive_optimizer")
        return record

    def recent_cycles(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,evaluation,architecture,governance,stability,status,created_at FROM recursive_cycles ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "evaluation": json.loads(row[1] or "{}"),
                "architecture": json.loads(row[2] or "{}"),
                "governance": json.loads(row[3] or "{}"),
                "stability": json.loads(row[4] or "{}"),
                "status": row[5],
                "created_at": row[6],
            }
            for row in rows
        ]
