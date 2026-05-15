"""Evolutionary memory for architecture, strategy, and society changes."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "evolutionary_memory.db"


class EvolutionaryMemory:
    """Records attempted, benchmarked, deployed, and rolled-back evolution events."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("evolutionary_memory", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS evolution_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metrics TEXT DEFAULT '{}',
                    detail TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_evolution_target ON evolution_events(target, created_at);
                """
            )

    def record(
        self,
        event_type: str,
        target: str,
        status: str,
        metrics: dict[str, Any] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_id = f"evo-{uuid.uuid4().hex[:12]}"
        record = {
            "id": event_id,
            "event_type": event_type,
            "target": target,
            "status": status,
            "metrics": metrics or {},
            "detail": detail or {},
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO evolution_events VALUES (?,?,?,?,?,?,?)",
                (
                    record["id"],
                    event_type,
                    target,
                    status,
                    json.dumps(record["metrics"], ensure_ascii=False, default=str),
                    json.dumps(record["detail"], ensure_ascii=False, default=str),
                    record["created_at"],
                ),
            )
        return record

    def timeline(self, target: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT id,event_type,target,status,metrics,detail,created_at FROM evolution_events"
        params: list[Any] = []
        if target:
            sql += " WHERE target=?"
            params.append(target)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(sql, params).fetchall()
        return [
            {
                "id": row[0],
                "event_type": row[1],
                "target": row[2],
                "status": row[3],
                "metrics": json.loads(row[4] or "{}"),
                "detail": json.loads(row[5] or "{}"),
                "created_at": row[6],
            }
            for row in rows
        ]

    def performance_summary(self, target: str | None = None) -> dict[str, Any]:
        events = self.timeline(target=target, limit=500)
        counts: dict[str, int] = {}
        scores = []
        for event in events:
            counts[event["status"]] = counts.get(event["status"], 0) + 1
            score = event.get("metrics", {}).get("score")
            if isinstance(score, (int, float)):
                scores.append(float(score))
        return {
            "events": len(events),
            "status_counts": counts,
            "average_score": round(sum(scores) / max(1, len(scores)), 3),
            "latest": events[:10],
        }
