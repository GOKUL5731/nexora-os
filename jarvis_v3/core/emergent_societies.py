"""Emergent agent society evolution: coalitions, role drift, and sub-agent proposals."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.society_engine import AgentSocietyEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "emergent_societies.db"


class EmergentSocietyEngine:
    """Models emergent specialization and cooperation patterns over agent societies."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        society: AgentSocietyEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("emergent_societies", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.society = society or AgentSocietyEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS coalitions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    agents TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    score REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS role_evolution (
                    id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    old_role TEXT DEFAULT '',
                    new_role TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def analyze_specialization_drift(self) -> list[dict[str, Any]]:
        drift = []
        for agent in self.society.snapshot().get("agents", []):
            specs = agent.get("specializations", {})
            if not specs:
                continue
            top = sorted(specs.items(), key=lambda item: item[1], reverse=True)[:3]
            if top and top[0][1] >= 0.7:
                drift.append(
                    {
                        "agent": agent["agent"],
                        "dominant_specialization": top[0][0],
                        "score": top[0][1],
                        "suggested_role": f"{top[0][0]}_specialist",
                    }
                )
        return drift

    def form_coalition(self, purpose: str, required_specializations: list[str]) -> dict[str, Any]:
        agents = self.society.snapshot().get("agents", [])
        selected = []
        for spec in required_specializations:
            ranked = sorted(
                agents,
                key=lambda agent: agent.get("specializations", {}).get(spec, 0) + agent.get("trust", 0.5),
                reverse=True,
            )
            if ranked and ranked[0]["agent"] not in selected:
                selected.append(ranked[0]["agent"])
        coalition_id = f"coalition-{uuid.uuid4().hex[:12]}"
        score = min(1.0, 0.4 + len(selected) * 0.15)
        record = {
            "id": coalition_id,
            "name": f"{purpose[:40]} coalition",
            "agents": selected,
            "purpose": purpose,
            "score": round(score, 3),
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO coalitions VALUES (?,?,?,?,?,?)",
                (
                    coalition_id,
                    record["name"],
                    json.dumps(selected),
                    purpose,
                    record["score"],
                    record["created_at"],
                ),
            )
        return record

    def propose_sub_agents(self) -> list[dict[str, Any]]:
        proposals = []
        for drift in self.analyze_specialization_drift():
            if drift["score"] >= 0.8:
                proposals.append(
                    {
                        "parent_agent": drift["agent"],
                        "sub_agent": f"{drift['agent']}_{drift['dominant_specialization']}",
                        "capability": drift["dominant_specialization"],
                        "reason": "stable high specialization",
                    }
                )
        return proposals

    def evolve_roles(self) -> list[dict[str, Any]]:
        changes = []
        for drift in self.analyze_specialization_drift():
            if drift["score"] < 0.75:
                continue
            change_id = f"role-{uuid.uuid4().hex[:12]}"
            record = {
                "id": change_id,
                "agent": drift["agent"],
                "old_role": "",
                "new_role": drift["suggested_role"],
                "reason": "specialization drift crossed evolution threshold",
                "created_at": datetime.now().isoformat(),
            }
            with self._lock, sqlite3.connect(self.db_path) as db:
                db.execute(
                    "INSERT INTO role_evolution VALUES (?,?,?,?,?,?)",
                    (
                        record["id"],
                        record["agent"],
                        record["old_role"],
                        record["new_role"],
                        record["reason"],
                        record["created_at"],
                    ),
                )
            changes.append(record)
        return changes

    def snapshot(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            coalitions = db.execute("SELECT id,name,agents,purpose,score,created_at FROM coalitions ORDER BY created_at DESC LIMIT 50").fetchall()
            roles = db.execute("SELECT id,agent,old_role,new_role,reason,created_at FROM role_evolution ORDER BY created_at DESC LIMIT 50").fetchall()
        return {
            "drift": self.analyze_specialization_drift(),
            "sub_agent_proposals": self.propose_sub_agents(),
            "coalitions": [
                {"id": row[0], "name": row[1], "agents": json.loads(row[2] or "[]"), "purpose": row[3], "score": row[4], "created_at": row[5]}
                for row in coalitions
            ],
            "role_evolution": [
                {"id": row[0], "agent": row[1], "old_role": row[2], "new_role": row[3], "reason": row[4], "created_at": row[5]}
                for row in roles
            ],
        }
