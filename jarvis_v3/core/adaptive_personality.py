"""Adaptive personality preferences with persistent user style learning."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "personality_adaptation.db"


class AdaptivePersonalityEngine:
    """Learns tone, detail, and workflow preferences while keeping a stable base style."""

    DEFAULT_PROFILE = {
        "tone": "professional_warm",
        "detail_level": "balanced",
        "interaction_style": "proactive",
        "workflow_preference": "safe_incremental",
    }

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("personality_adaptation", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS personality_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS personality_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal TEXT NOT NULL,
                    inference TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            for key, value in self.DEFAULT_PROFILE.items():
                db.execute(
                    "INSERT OR IGNORE INTO personality_preferences VALUES (?,?,?,?)",
                    (key, json.dumps(value), 0.5, datetime.now().isoformat()),
                )

    def observe_interaction(self, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        lower = text.lower()
        inference: dict[str, Any] = {}
        if any(word in lower for word in ["brief", "short", "concise"]):
            inference["detail_level"] = "concise"
        elif any(word in lower for word in ["thorough", "detailed", "explain"]):
            inference["detail_level"] = "detailed"
        if any(word in lower for word in ["just do", "go ahead", "implement"]):
            inference["interaction_style"] = "decisive"
        if any(word in lower for word in ["careful", "safe", "rollback", "test first"]):
            inference["workflow_preference"] = "safety_first"
        if inference:
            for key, value in inference.items():
                self.set_preference(key, value, confidence_delta=0.08)
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO personality_events(signal,inference,created_at) VALUES(?,?,?)",
                (text[:500], json.dumps(inference, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        return self.profile()

    def set_preference(self, key: str, value: Any, confidence_delta: float = 0.05) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT confidence FROM personality_preferences WHERE key=?", (key,)).fetchone()
            confidence = min(1.0, (row[0] if row else 0.5) + confidence_delta)
            db.execute(
                """
                INSERT INTO personality_preferences VALUES (?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, confidence=excluded.confidence, updated_at=excluded.updated_at
                """,
                (key, json.dumps(value), confidence, datetime.now().isoformat()),
            )

    def profile(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT key,value,confidence,updated_at FROM personality_preferences").fetchall()
        return {
            row[0]: {"value": json.loads(row[1]), "confidence": row[2], "updated_at": row[3]}
            for row in rows
        }

    def response_guidance(self) -> dict[str, Any]:
        profile = self.profile()
        return {key: item["value"] for key, item in profile.items()}
