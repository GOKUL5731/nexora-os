"""Internal cognitive economy for resources, knowledge modules, workflows, and strategies."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "cognitive_economy.db"


class CognitiveEconomy:
    """Tracks contributions, reputation, efficiency, and exchanges between civilizations."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("cognitive_economy", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    civilization TEXT PRIMARY KEY,
                    compute_credits REAL DEFAULT 100,
                    reputation REAL DEFAULT 0.6,
                    efficiency REAL DEFAULT 0.6,
                    contribution REAL DEFAULT 0.0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS exchanges (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    detail TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def ensure_account(self, civilization: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT OR IGNORE INTO accounts VALUES (?,?,?,?,?,?)",
                (civilization, 100.0, 0.6, 0.6, 0.0, datetime.now().isoformat()),
            )
        return self.account(civilization)

    def exchange(
        self,
        source: str,
        target: str,
        asset_type: str,
        value: float,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.ensure_account(source)
        self.ensure_account(target)
        value = max(0.0, float(value))
        exchange_id = f"exchange-{uuid.uuid4().hex[:12]}"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE accounts SET compute_credits=compute_credits-?, contribution=contribution+?, updated_at=? WHERE civilization=?",
                (value, value * 0.1, datetime.now().isoformat(), source),
            )
            db.execute(
                "UPDATE accounts SET compute_credits=compute_credits+?, reputation=MIN(reputation+?,1.0), updated_at=? WHERE civilization=?",
                (value, min(0.05, value / 1000), datetime.now().isoformat(), target),
            )
            db.execute(
                "INSERT INTO exchanges VALUES (?,?,?,?,?,?,?)",
                (
                    exchange_id,
                    source,
                    target,
                    asset_type,
                    value,
                    json.dumps(detail or {}, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )
        return {"id": exchange_id, "source": source, "target": target, "asset_type": asset_type, "value": value}

    def record_contribution(self, civilization: str, contribution: float, efficiency: float = 0.6) -> dict[str, Any]:
        self.ensure_account(civilization)
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                UPDATE accounts
                SET contribution=contribution+?,
                    efficiency=?,
                    reputation=MIN(1.0, reputation + ?),
                    updated_at=?
                WHERE civilization=?
                """,
                (
                    max(0.0, contribution),
                    max(0.0, min(1.0, efficiency)),
                    min(0.1, contribution / 100),
                    datetime.now().isoformat(),
                    civilization,
                ),
            )
        return self.account(civilization)

    def account(self, civilization: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT civilization,compute_credits,reputation,efficiency,contribution,updated_at FROM accounts WHERE civilization=?",
                (civilization,),
            ).fetchone()
        if not row:
            raise KeyError(f"Civilization account not found: {civilization}")
        return self._account_row(row)

    def leaderboard(self) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT civilization,compute_credits,reputation,efficiency,contribution,updated_at FROM accounts ORDER BY reputation DESC, efficiency DESC"
            ).fetchall()
        return [self._account_row(row) for row in rows]

    def recent_exchanges(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,source,target,asset_type,value,detail,created_at FROM exchanges ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "source": row[1],
                "target": row[2],
                "asset_type": row[3],
                "value": row[4],
                "detail": json.loads(row[5] or "{}"),
                "created_at": row[6],
            }
            for row in rows
        ]

    def snapshot(self) -> dict[str, Any]:
        return {"leaderboard": self.leaderboard(), "exchanges": self.recent_exchanges()}

    @staticmethod
    def _account_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "civilization": row[0],
            "compute_credits": round(row[1], 3),
            "reputation": row[2],
            "efficiency": row[3],
            "contribution": row[4],
            "updated_at": row[5],
        }
