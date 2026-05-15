"""Digital twin system for users, workflows, applications, system behavior, and agent societies."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "digital_twins.db"


class DigitalTwinEngine:
    """Maintains virtual models that can be updated and simulated safely."""

    VALID_TYPES = {"user", "workflow", "application", "system", "agent_society"}

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("digital_twins", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS twins (
                    id TEXT PRIMARY KEY,
                    twin_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    version INTEGER DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    UNIQUE(twin_type, name)
                );
                CREATE TABLE IF NOT EXISTS twin_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    twin_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def upsert_twin(
        self,
        twin_type: str,
        name: str,
        state: dict[str, Any],
        confidence: float = 0.6,
    ) -> dict[str, Any]:
        twin_type = twin_type if twin_type in self.VALID_TYPES else "system"
        twin_id = f"twin:{twin_type}:{name}"
        now = datetime.now().isoformat()
        with self._lock, sqlite3.connect(self.db_path) as db:
            current = db.execute("SELECT version,state FROM twins WHERE twin_type=? AND name=?", (twin_type, name)).fetchone()
            version = (current[0] + 1) if current else 1
            merged = {**(json.loads(current[1]) if current else {}), **state}
            db.execute(
                """
                INSERT INTO twins VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(twin_type,name) DO UPDATE SET
                  state=excluded.state,
                  confidence=excluded.confidence,
                  version=excluded.version,
                  updated_at=excluded.updated_at
                """,
                (
                    twin_id,
                    twin_type,
                    name,
                    json.dumps(merged, ensure_ascii=False, default=str),
                    max(0.0, min(1.0, confidence)),
                    version,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO twin_events(twin_id,event_type,payload,created_at) VALUES(?,?,?,?)",
                (twin_id, "upsert", json.dumps(state, ensure_ascii=False, default=str), now),
            )
        return self.get_twin(twin_type, name)

    def update_from_autonomy(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        twins = [
            self.upsert_twin("system", "local", snapshot.get("resources", {}), 0.75),
            self.upsert_twin("agent_society", "primary", snapshot.get("society", {}), 0.7),
            self.upsert_twin("workflow", "active_goals", snapshot.get("goals", {}), 0.68),
            self.upsert_twin("user", "default", {"personality": snapshot.get("personality", {})}, 0.62),
        ]
        return twins

    def simulate_twin_outcome(self, twin_type: str, name: str, change: dict[str, Any]) -> dict[str, Any]:
        twin = self.get_twin(twin_type, name)
        state = twin["state"]
        projected = {**state, **change}
        risk = 0.1
        if twin_type == "system":
            pressure = projected.get("pressure_score", projected.get("resource_pressure", 0))
            risk += min(0.6, float(pressure or 0) * 0.6)
        if twin_type == "workflow":
            blocked = projected.get("status_counts", {}).get("blocked", 0)
            risk += min(0.5, blocked * 0.08)
        if twin_type == "agent_society":
            low_trust = [
                agent for agent in projected.get("agents", []) if agent.get("trust", 1.0) < 0.4
            ]
            risk += min(0.5, len(low_trust) * 0.1)
        return {
            "twin": twin["id"],
            "change": change,
            "projected_state": projected,
            "risk_score": round(min(1.0, risk), 3),
            "expected_success": round(1.0 - min(1.0, risk), 3),
        }

    def predict_failures(self, twin_type: str | None = None) -> list[dict[str, Any]]:
        failures = []
        for twin in self.list_twins(twin_type=twin_type, limit=200):
            if twin["type"] == "system" and twin["state"].get("pressure_score", 0) > 0.8:
                failures.append({"twin": twin["id"], "type": "resource_pressure", "severity": "high"})
            if twin["type"] == "workflow" and twin["state"].get("status_counts", {}).get("blocked", 0) > 0:
                failures.append({"twin": twin["id"], "type": "blocked_goals", "severity": "medium"})
            if twin["confidence"] < 0.35:
                failures.append({"twin": twin["id"], "type": "low_confidence_model", "severity": "medium"})
        return failures

    def get_twin(self, twin_type: str, name: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT id,twin_type,name,state,confidence,version,updated_at FROM twins WHERE twin_type=? AND name=?",
                (twin_type, name),
            ).fetchone()
        if not row:
            raise KeyError(f"Digital twin not found: {twin_type}/{name}")
        return self._row(row)

    def list_twins(self, twin_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT id,twin_type,name,state,confidence,version,updated_at FROM twins"
        params: list[Any] = []
        if twin_type:
            sql += " WHERE twin_type=?"
            params.append(twin_type)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(sql, params).fetchall()
        return [self._row(row) for row in rows]

    def clone_twin(self, twin_type: str, name: str, clone_name: str | None = None) -> dict[str, Any]:
        twin = self.get_twin(twin_type, name)
        return self.upsert_twin(twin_type, clone_name or f"{name}_clone_{uuid.uuid4().hex[:6]}", twin["state"], twin["confidence"])

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "type": row[1],
            "name": row[2],
            "state": json.loads(row[3] or "{}"),
            "confidence": row[4],
            "version": row[5],
            "updated_at": row[6],
        }
