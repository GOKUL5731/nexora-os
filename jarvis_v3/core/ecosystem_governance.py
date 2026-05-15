"""Evolutionary governance for competing civilizations and intelligence systems."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.governance_engine import GovernanceEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "ecosystem_governance.db"


class EcosystemGovernanceSystem:
    """Governs competing architectures, civilizations, plugins, and workflow ecosystems."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        governance: GovernanceEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("ecosystem_governance", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.governance = governance or GovernanceEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS ecosystem_decisions (
                    id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def evaluate_competition(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        governed = []
        for candidate in candidates:
            decision = self.governance.evaluate(
                {
                    "type": candidate.get("target_type", "architecture"),
                    "sandboxed": candidate.get("sandboxed", True),
                    "benchmarked": candidate.get("benchmarked", True),
                    "rollback_plan": candidate.get("rollback_plan", True),
                    "plugin_verified": candidate.get("plugin_verified", candidate.get("target_type") != "plugin"),
                },
                {"resource_pressure": candidate.get("resource_pressure", 0.0)},
            )
            score = candidate.get("score", 0.5) - (0.3 if decision["decision"] == "blocked" else 0)
            governed.append({**candidate, "governance": decision, "governed_score": round(max(0.0, score), 3)})
        governed.sort(key=lambda item: item["governed_score"], reverse=True)
        winner = governed[0] if governed else None
        if winner:
            self.record_decision(winner.get("target_type", "architecture"), winner.get("name", winner.get("id", "unknown")), winner["governance"]["decision"], {"winner": winner})
        return {"winner": winner, "candidates": governed}

    def record_decision(self, target_type: str, target: str, decision: str, rationale: dict[str, Any]) -> dict[str, Any]:
        decision_id = f"egov-{uuid.uuid4().hex[:12]}"
        record = {
            "id": decision_id,
            "target_type": target_type,
            "target": target,
            "decision": decision,
            "rationale": rationale,
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO ecosystem_decisions VALUES (?,?,?,?,?,?)",
                (
                    decision_id,
                    target_type,
                    target,
                    decision,
                    json.dumps(rationale, ensure_ascii=False, default=str),
                    record["created_at"],
                ),
            )
        return record

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,target_type,target,decision,rationale,created_at FROM ecosystem_decisions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": row[0], "target_type": row[1], "target": row[2], "decision": row[3], "rationale": json.loads(row[4] or "{}"), "created_at": row[5]}
            for row in rows
        ]
