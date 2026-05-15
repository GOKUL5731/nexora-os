"""Agent society coordination with hierarchy, reputation, and specialization."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from core.collaboration_engine import CollaborationEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "society.db"


class AgentSocietyEngine:
    """Turns collaborative agents into a persistent society model."""

    DEFAULT_HIERARCHY = {
        "commander": 100,
        "planner": 80,
        "researcher": 60,
        "coder": 60,
        "tester": 60,
        "optimizer": 55,
        "vision": 50,
        "deployer": 50,
    }

    def __init__(
        self,
        config: dict | None = None,
        collaboration: CollaborationEngine | None = None,
        db_path: str | Path | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("society", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.collaboration = collaboration or CollaborationEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()
        self.sync_agents()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS society_agents (
                    agent TEXT PRIMARY KEY,
                    hierarchy INTEGER DEFAULT 50,
                    trust REAL DEFAULT 0.6,
                    reputation REAL DEFAULT 0.6,
                    specializations TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS society_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def sync_agents(self) -> None:
        now = datetime.now().isoformat()
        with self._lock, sqlite3.connect(self.db_path) as db:
            for agent in self.collaboration.list_agents():
                caps = {cap: 0.5 for cap in agent.get("capabilities", [])}
                db.execute(
                    """
                    INSERT INTO society_agents VALUES (?,?,?,?,?,?)
                    ON CONFLICT(agent) DO UPDATE SET updated_at=excluded.updated_at
                    """,
                    (
                        agent["name"],
                        self.DEFAULT_HIERARCHY.get(agent["name"], 50),
                        0.6,
                        0.6,
                        json.dumps(caps),
                        now,
                    ),
                )

    def record_outcome(self, agent: str, task: str, success: bool, quality: float = 0.7) -> dict[str, Any]:
        quality = max(0.0, min(1.0, quality))
        delta = (0.05 + quality * 0.05) if success else -0.1
        tokens = [w.strip(".,:;!?").lower() for w in task.split() if len(w) > 3][:8]
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT trust,reputation,specializations FROM society_agents WHERE agent=?",
                (agent,),
            ).fetchone()
            if not row:
                self.sync_agents()
                row = db.execute(
                    "SELECT trust,reputation,specializations FROM society_agents WHERE agent=?",
                    (agent,),
                ).fetchone()
            trust, reputation, specs_raw = row or (0.5, 0.5, "{}")
            specs = json.loads(specs_raw or "{}")
            for token in tokens:
                specs[token] = round(max(0.0, min(1.0, specs.get(token, 0.4) + (0.04 if success else -0.03))), 3)
            trust = round(max(0.0, min(1.0, trust + delta)), 3)
            reputation = round(max(0.0, min(1.0, reputation + delta * 0.8)), 3)
            db.execute(
                "UPDATE society_agents SET trust=?, reputation=?, specializations=?, updated_at=? WHERE agent=?",
                (trust, reputation, json.dumps(specs), datetime.now().isoformat(), agent),
            )
            db.execute(
                "INSERT INTO society_events(event_type,detail,created_at) VALUES(?,?,?)",
                (
                    "outcome",
                    json.dumps({"agent": agent, "task": task, "success": success, "quality": quality}),
                    datetime.now().isoformat(),
                ),
            )
        return self.get_agent(agent)

    def assign_task(self, task: str, candidates: list[str] | None = None) -> dict[str, Any]:
        words = {w.strip(".,:;!?").lower() for w in task.split() if len(w) > 3}
        agents = self.snapshot()["agents"]
        if candidates:
            agents = [agent for agent in agents if agent["agent"] in candidates]
        bids = []
        for agent in agents:
            spec_score = sum(agent["specializations"].get(word, 0) for word in words)
            score = (
                spec_score
                + agent["trust"] * 1.5
                + agent["reputation"] * 1.2
                + min(agent["hierarchy"], 100) / 100 * 0.5
            )
            bids.append({"agent": agent["agent"], "score": round(score, 3), "trust": agent["trust"]})
        bids.sort(key=lambda item: item["score"], reverse=True)
        selected = bids[0]["agent"] if bids else self.collaboration.negotiate_assignment(task)["selected_agent"]
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO society_events(event_type,detail,created_at) VALUES(?,?,?)",
                ("assignment", json.dumps({"task": task, "selected": selected, "bids": bids}), datetime.now().isoformat()),
            )
        return {"selected_agent": selected, "bids": bids}

    def broadcast(self, from_agent: str, content: str, metadata: dict[str, Any] | None = None) -> list[str]:
        message_ids = []
        for agent in self.collaboration.list_agents():
            if agent["name"] != from_agent:
                message_ids.append(self.collaboration.send_message(from_agent, agent["name"], content, metadata))
        return message_ids

    def get_agent(self, agent: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT agent,hierarchy,trust,reputation,specializations,updated_at FROM society_agents WHERE agent=?",
                (agent,),
            ).fetchone()
        if not row:
            raise KeyError(f"Society agent not found: {agent}")
        return self._row(row)

    def snapshot(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT agent,hierarchy,trust,reputation,specializations,updated_at FROM society_agents ORDER BY hierarchy DESC, reputation DESC"
            ).fetchall()
            events = db.execute(
                "SELECT event_type,detail,created_at FROM society_events ORDER BY id DESC LIMIT 20"
            ).fetchall()
        return {
            "agents": [self._row(row) for row in rows],
            "events": [
                {"type": row[0], "detail": json.loads(row[1] or "{}"), "created_at": row[2]}
                for row in events
            ],
        }

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "agent": row[0],
            "hierarchy": row[1],
            "trust": row[2],
            "reputation": row[3],
            "specializations": json.loads(row[4] or "{}"),
            "updated_at": row[5],
        }
