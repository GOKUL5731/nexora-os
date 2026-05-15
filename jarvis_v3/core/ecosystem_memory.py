"""Long-term ecosystem memory for recursive adaptive intelligence."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "ecosystem_memory.db"


class EcosystemMemory:
    """Stores strategic, simulation, collective-agent, and optimization memory."""

    VALID_TYPES = {"evolutionary", "strategic", "simulation", "collective_agent", "optimization"}

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("ecosystem_memory", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS ecosystem_memory (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    score REAL DEFAULT 0.5,
                    source TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(memory_type, key)
                );
                CREATE INDEX IF NOT EXISTS idx_ecosystem_memory_type ON ecosystem_memory(memory_type, score);
                """
            )

    def remember(
        self,
        memory_type: str,
        key: str,
        value: Any,
        score: float = 0.5,
        source: str = "",
    ) -> dict[str, Any]:
        memory_type = memory_type if memory_type in self.VALID_TYPES else "optimization"
        now = datetime.now().isoformat()
        memory_id = f"eco-{uuid.uuid4().hex[:12]}"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO ecosystem_memory VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(memory_type,key) DO UPDATE SET
                  value=excluded.value,
                  score=excluded.score,
                  source=excluded.source,
                  updated_at=excluded.updated_at
                """,
                (
                    memory_id,
                    memory_type,
                    key[:200],
                    json.dumps(value, ensure_ascii=False, default=str),
                    max(0.0, min(1.0, float(score))),
                    source[:200],
                    now,
                    now,
                ),
            )
        return self.get(memory_type, key)

    def get(self, memory_type: str, key: str, default: Any = None) -> dict[str, Any] | Any:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT id,memory_type,key,value,score,source,created_at,updated_at FROM ecosystem_memory WHERE memory_type=? AND key=?",
                (memory_type, key),
            ).fetchone()
        return self._row(row) if row else default

    def recall(self, memory_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT id,memory_type,key,value,score,source,created_at,updated_at FROM ecosystem_memory"
        params: list[Any] = []
        if memory_type:
            sql += " WHERE memory_type=?"
            params.append(memory_type)
        sql += " ORDER BY score DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(sql, params).fetchall()
        return [self._row(row) for row in rows]

    def consistency_report(self) -> dict[str, Any]:
        rows = self.recall(limit=1000)
        by_type: dict[str, int] = {}
        invalid = []
        for row in rows:
            by_type[row["type"]] = by_type.get(row["type"], 0) + 1
            if row["score"] < 0 or row["score"] > 1:
                invalid.append(row["id"])
        return {"ok": not invalid, "counts": by_type, "invalid_scores": invalid, "total": len(rows)}

    def snapshot(self) -> dict[str, Any]:
        return {
            "strategic": self.recall("strategic", 20),
            "simulation": self.recall("simulation", 20),
            "collective_agent": self.recall("collective_agent", 20),
            "optimization": self.recall("optimization", 20),
            "evolutionary": self.recall("evolutionary", 20),
            "consistency": self.consistency_report(),
        }

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "type": row[1],
            "key": row[2],
            "value": json.loads(row[3] or "{}"),
            "score": row[4],
            "source": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
