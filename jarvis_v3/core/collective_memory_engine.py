"""Civilization-scale collective memory network."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "collective_memory.db"


class CollectiveMemoryEngine:
    """Stores collective, cultural, evolutionary, strategic, and scientific memory."""

    VALID_TYPES = {"collective", "cultural", "evolutionary_history", "strategic", "scientific"}

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("collective_memory", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS collective_memory (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    civilization TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 0.6,
                    contributors TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(memory_type,civilization,key)
                );
                CREATE INDEX IF NOT EXISTS idx_collective_memory_type ON collective_memory(memory_type,civilization);
                """
            )

    def remember(
        self,
        memory_type: str,
        civilization: str,
        key: str,
        value: Any,
        confidence: float = 0.6,
        contributors: list[str] | None = None,
    ) -> dict[str, Any]:
        memory_type = memory_type if memory_type in self.VALID_TYPES else "collective"
        now = datetime.now().isoformat()
        memory_id = f"cmem-{uuid.uuid4().hex[:12]}"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO collective_memory VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(memory_type,civilization,key) DO UPDATE SET
                  value=excluded.value,
                  confidence=excluded.confidence,
                  contributors=excluded.contributors,
                  updated_at=excluded.updated_at
                """,
                (
                    memory_id,
                    memory_type,
                    civilization,
                    key[:240],
                    json.dumps(value, ensure_ascii=False, default=str),
                    max(0.0, min(1.0, float(confidence))),
                    json.dumps(contributors or [], ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
        return self.get(memory_type, civilization, key)

    def get(self, memory_type: str, civilization: str, key: str, default: Any = None) -> dict[str, Any] | Any:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT id,memory_type,civilization,key,value,confidence,contributors,created_at,updated_at "
                "FROM collective_memory WHERE memory_type=? AND civilization=? AND key=?",
                (memory_type, civilization, key),
            ).fetchone()
        return self._row(row) if row else default

    def recall(self, memory_type: str | None = None, civilization: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = (
            "SELECT id,memory_type,civilization,key,value,confidence,contributors,created_at,updated_at "
            "FROM collective_memory"
        )
        params: list[Any] = []
        where = []
        if memory_type:
            where.append("memory_type=?")
            params.append(memory_type)
        if civilization:
            where.append("civilization=?")
            params.append(civilization)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY confidence DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(sql, params).fetchall()
        return [self._row(row) for row in rows]

    def synchronize(self, source_civilization: str, target_civilization: str, min_confidence: float = 0.55) -> dict[str, Any]:
        source = [item for item in self.recall(civilization=source_civilization, limit=500) if item["confidence"] >= min_confidence]
        synced = []
        for item in source:
            synced.append(
                self.remember(
                    item["type"],
                    target_civilization,
                    item["key"],
                    item["value"],
                    confidence=item["confidence"] * 0.95,
                    contributors=list(set(item["contributors"] + [source_civilization])),
                )
            )
        return {"source": source_civilization, "target": target_civilization, "synced": len(synced)}

    def consistency_report(self) -> dict[str, Any]:
        rows = self.recall(limit=2000)
        counts: dict[str, int] = {}
        low_confidence = []
        for row in rows:
            counts[row["type"]] = counts.get(row["type"], 0) + 1
            if row["confidence"] < 0.2:
                low_confidence.append(row["id"])
        return {"ok": not low_confidence, "counts": counts, "low_confidence": low_confidence, "total": len(rows)}

    def snapshot(self) -> dict[str, Any]:
        return {
            "collective": self.recall("collective", limit=50),
            "cultural": self.recall("cultural", limit=50),
            "evolutionary_history": self.recall("evolutionary_history", limit=50),
            "strategic": self.recall("strategic", limit=50),
            "scientific": self.recall("scientific", limit=50),
            "consistency": self.consistency_report(),
        }

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "type": row[1],
            "civilization": row[2],
            "key": row[3],
            "value": json.loads(row[4] or "{}"),
            "confidence": row[5],
            "contributors": json.loads(row[6] or "[]"),
            "created_at": row[7],
            "updated_at": row[8],
        }
