"""Cognitive culture system for reasoning styles and civilization traditions."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "cognitive_culture.db"


class CognitiveCultureSystem:
    """Tracks and compares reasoning cultures across agent civilizations."""

    DEFAULT_CULTURES = {
        "fast_execution": {"latency": 0.9, "depth": 0.35, "efficiency": 0.7, "experimentation": 0.35},
        "deep_reasoning": {"latency": 0.35, "depth": 0.9, "efficiency": 0.55, "experimentation": 0.65},
        "resource_efficient": {"latency": 0.55, "depth": 0.55, "efficiency": 0.95, "experimentation": 0.45},
        "experimental": {"latency": 0.45, "depth": 0.75, "efficiency": 0.5, "experimentation": 0.95},
    }

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("cognitive_culture", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()
        self.ensure_defaults()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS cultures (
                    name TEXT PRIMARY KEY,
                    traits TEXT NOT NULL,
                    score REAL DEFAULT 0.5,
                    samples INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS civilization_culture (
                    civilization TEXT PRIMARY KEY,
                    culture TEXT NOT NULL,
                    adaptation TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                """
            )

    def ensure_defaults(self) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            for name, traits in self.DEFAULT_CULTURES.items():
                db.execute(
                    "INSERT OR IGNORE INTO cultures VALUES (?,?,?,?,?)",
                    (name, json.dumps(traits), 0.5, 0, datetime.now().isoformat()),
                )

    def assign_culture(self, civilization: str, culture: str, adaptation: dict[str, Any] | None = None) -> dict[str, Any]:
        if culture not in self.DEFAULT_CULTURES and not self.get_culture(culture, default=None):
            culture = "deep_reasoning"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO civilization_culture VALUES (?,?,?,?)
                ON CONFLICT(civilization) DO UPDATE SET
                  culture=excluded.culture,
                  adaptation=excluded.adaptation,
                  updated_at=excluded.updated_at
                """,
                (civilization, culture, json.dumps(adaptation or {}, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        return self.civilization_culture(civilization)

    def record_outcome(self, culture: str, score: float) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT score,samples FROM cultures WHERE name=?", (culture,)).fetchone()
            old, samples = row or (0.5, 0)
            new_samples = samples + 1
            new_score = round((old * samples + max(0.0, min(1.0, score))) / new_samples, 3)
            db.execute(
                "UPDATE cultures SET score=?, samples=?, updated_at=? WHERE name=?",
                (new_score, new_samples, datetime.now().isoformat(), culture),
            )
        return self.get_culture(culture)

    def compare_cultures(self, objective: str, resource_pressure: float = 0.0) -> list[dict[str, Any]]:
        ranked = []
        for culture in self.list_cultures():
            traits = culture["traits"]
            score = culture["score"]
            if "fast" in objective.lower():
                score += traits.get("latency", 0) * 0.2
            if "research" in objective.lower() or "discover" in objective.lower():
                score += traits.get("experimentation", 0) * 0.2
            if resource_pressure > 0.7:
                score += traits.get("efficiency", 0) * 0.25
            if "deep" in objective.lower() or "architecture" in objective.lower():
                score += traits.get("depth", 0) * 0.2
            ranked.append({**culture, "selection_score": round(min(1.0, score), 3)})
        return sorted(ranked, key=lambda item: item["selection_score"], reverse=True)

    def get_culture(self, culture: str, default: Any = None) -> dict[str, Any] | Any:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT name,traits,score,samples,updated_at FROM cultures WHERE name=?", (culture,)).fetchone()
        return self._culture_row(row) if row else default

    def list_cultures(self) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT name,traits,score,samples,updated_at FROM cultures ORDER BY score DESC,name").fetchall()
        return [self._culture_row(row) for row in rows]

    def civilization_culture(self, civilization: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT civilization,culture,adaptation,updated_at FROM civilization_culture WHERE civilization=?", (civilization,)).fetchone()
        if not row:
            return self.assign_culture(civilization, "deep_reasoning")
        return {"civilization": row[0], "culture": row[1], "adaptation": json.loads(row[2] or "{}"), "updated_at": row[3]}

    def snapshot(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT civilization,culture,adaptation,updated_at FROM civilization_culture").fetchall()
        return {
            "cultures": self.list_cultures(),
            "civilizations": [
                {"civilization": row[0], "culture": row[1], "adaptation": json.loads(row[2] or "{}"), "updated_at": row[3]}
                for row in rows
            ],
        }

    @staticmethod
    def _culture_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {"name": row[0], "traits": json.loads(row[1] or "{}"), "score": row[2], "samples": row[3], "updated_at": row[4]}
