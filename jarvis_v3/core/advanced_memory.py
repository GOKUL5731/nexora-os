"""Advanced cognitive memory stores for JARVIS.

This module extends the existing memory manager with explicit episodic,
semantic, procedural, and per-agent memory tables. It is dependency-free and
safe to use from agents, workflows, tests, and background orchestration.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "advanced_memory.db"


class AdvancedMemorySystem:
    """Persistent cognitive memory divided by memory type."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("advanced_memory", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    data TEXT DEFAULT '{}',
                    importance REAL DEFAULT 0.5
                );
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 0.7,
                    updated_at TEXT NOT NULL,
                    UNIQUE(namespace, key)
                );
                CREATE TABLE IF NOT EXISTS procedural_memory (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT DEFAULT '',
                    workflow TEXT NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 0.7,
                    updated_at TEXT NOT NULL,
                    UNIQUE(agent, key)
                );
                CREATE INDEX IF NOT EXISTS idx_episode_time ON episodic_memory(timestamp);
                CREATE INDEX IF NOT EXISTS idx_semantic_ns ON semantic_memory(namespace);
                CREATE INDEX IF NOT EXISTS idx_agent_memory_agent ON agent_memory(agent);
                """
            )

    def remember_episode(
        self,
        event_type: str,
        summary: str,
        data: dict[str, Any] | None = None,
        importance: float = 0.5,
    ) -> str:
        memory_id = self._id("episode", event_type, summary, datetime.now().isoformat())
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO episodic_memory VALUES (?,?,?,?,?,?)",
                (
                    memory_id,
                    datetime.now().isoformat(),
                    event_type[:80],
                    summary[:1500],
                    json.dumps(data or {}, ensure_ascii=False, default=str),
                    self._clamp(importance),
                ),
            )
        return memory_id

    def recall_episodes(self, limit: int = 20, event_type: str | None = None) -> list[dict[str, Any]]:
        query = (
            "SELECT id,timestamp,event_type,summary,data,importance FROM episodic_memory "
            "WHERE event_type=? ORDER BY timestamp DESC LIMIT ?"
            if event_type
            else "SELECT id,timestamp,event_type,summary,data,importance FROM episodic_memory "
            "ORDER BY timestamp DESC LIMIT ?"
        )
        params: tuple[Any, ...] = (event_type, limit) if event_type else (limit,)
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(query, params).fetchall()
        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "event_type": row[2],
                "summary": row[3],
                "data": json.loads(row[4] or "{}"),
                "importance": row[5],
            }
            for row in rows
        ]

    def store_fact(self, namespace: str, key: str, value: Any, confidence: float = 0.7) -> str:
        memory_id = self._id("semantic", namespace, key)
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO semantic_memory VALUES (?,?,?,?,?,?)
                ON CONFLICT(namespace,key) DO UPDATE SET
                  value=excluded.value,
                  confidence=excluded.confidence,
                  updated_at=excluded.updated_at
                """,
                (
                    memory_id,
                    namespace[:80],
                    key[:160],
                    json.dumps(value, ensure_ascii=False, default=str),
                    self._clamp(confidence),
                    datetime.now().isoformat(),
                ),
            )
        return memory_id

    def get_fact(self, namespace: str, key: str, default: Any = None) -> Any:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT value FROM semantic_memory WHERE namespace=? AND key=?",
                (namespace, key),
            ).fetchone()
        return json.loads(row[0]) if row else default

    def list_facts(self, namespace: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT key,value FROM semantic_memory WHERE namespace=? ORDER BY updated_at DESC",
                (namespace,),
            ).fetchall()
        return {key: json.loads(value) for key, value in rows}

    def store_procedure(self, name: str, workflow: dict[str, Any], description: str = "") -> str:
        memory_id = self._id("procedure", name)
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO procedural_memory(id,name,description,workflow,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                  description=excluded.description,
                  workflow=excluded.workflow,
                  updated_at=excluded.updated_at
                """,
                (
                    memory_id,
                    name[:160],
                    description[:1000],
                    json.dumps(workflow, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )
        return memory_id

    def get_procedure(self, name: str) -> dict[str, Any] | None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT name,description,workflow,success_count,failure_count,updated_at "
                "FROM procedural_memory WHERE name=?",
                (name,),
            ).fetchone()
        if not row:
            return None
        return {
            "name": row[0],
            "description": row[1],
            "workflow": json.loads(row[2] or "{}"),
            "success_count": row[3],
            "failure_count": row[4],
            "updated_at": row[5],
        }

    def record_procedure_result(self, name: str, success: bool) -> None:
        column = "success_count" if success else "failure_count"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                f"UPDATE procedural_memory SET {column}={column}+1, updated_at=? WHERE name=?",
                (datetime.now().isoformat(), name),
            )

    def remember_for_agent(self, agent: str, key: str, value: Any, confidence: float = 0.7) -> str:
        memory_id = self._id("agent", agent, key)
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO agent_memory VALUES (?,?,?,?,?,?)
                ON CONFLICT(agent,key) DO UPDATE SET
                  value=excluded.value,
                  confidence=excluded.confidence,
                  updated_at=excluded.updated_at
                """,
                (
                    memory_id,
                    agent[:120],
                    key[:160],
                    json.dumps(value, ensure_ascii=False, default=str),
                    self._clamp(confidence),
                    datetime.now().isoformat(),
                ),
            )
        return memory_id

    def recall_for_agent(self, agent: str, key: str | None = None) -> Any:
        with self._lock, sqlite3.connect(self.db_path) as db:
            if key:
                row = db.execute(
                    "SELECT value FROM agent_memory WHERE agent=? AND key=?",
                    (agent, key),
                ).fetchone()
                return json.loads(row[0]) if row else None
            rows = db.execute(
                "SELECT key,value FROM agent_memory WHERE agent=? ORDER BY updated_at DESC",
                (agent,),
            ).fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

    @staticmethod
    def _id(*parts: str) -> str:
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _clamp(value: float) -> float:
        return float(max(0.0, min(1.0, value)))
