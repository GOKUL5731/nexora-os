"""Skill scoring and reinforcement tracking."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "skill_evolution.db"


class SkillEvolutionEngine:
    """Tracks skill quality over time and recommends adaptive optimization."""

    DEFAULT_SKILLS = [
        "coding_quality",
        "workflow_optimization",
        "automation_accuracy",
        "prediction_accuracy",
        "voice_interaction_quality",
    ]

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("skill_evolution", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()
        self.ensure_defaults()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS skills (
                    name TEXT PRIMARY KEY,
                    score REAL DEFAULT 0.5,
                    confidence REAL DEFAULT 0.5,
                    samples INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skill_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill TEXT NOT NULL,
                    reward REAL NOT NULL,
                    context TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def ensure_defaults(self) -> None:
        now = datetime.now().isoformat()
        with self._lock, sqlite3.connect(self.db_path) as db:
            for skill in self.DEFAULT_SKILLS:
                db.execute(
                    "INSERT OR IGNORE INTO skills(name,score,confidence,samples,metadata,updated_at) VALUES(?,?,?,?,?,?)",
                    (skill, 0.5, 0.5, 0, "{}", now),
                )

    def record_result(self, skill: str, reward: float, context: dict[str, Any] | None = None) -> dict[str, Any]:
        reward = max(-1.0, min(1.0, float(reward)))
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT score,confidence,samples FROM skills WHERE name=?", (skill,)).fetchone()
            if not row:
                db.execute(
                    "INSERT INTO skills(name,score,confidence,samples,metadata,updated_at) VALUES(?,?,?,?,?,?)",
                    (skill, 0.5, 0.4, 0, "{}", datetime.now().isoformat()),
                )
                row = (0.5, 0.4, 0)
            score, confidence, samples = row
            target = (reward + 1.0) / 2.0
            new_samples = samples + 1
            alpha = max(0.05, min(0.35, 1.0 / (new_samples ** 0.5)))
            new_score = round(score * (1 - alpha) + target * alpha, 3)
            new_confidence = round(min(1.0, confidence + 0.03), 3)
            db.execute(
                "UPDATE skills SET score=?, confidence=?, samples=?, updated_at=? WHERE name=?",
                (new_score, new_confidence, new_samples, datetime.now().isoformat(), skill),
            )
            db.execute(
                "INSERT INTO skill_events(skill,reward,context,created_at) VALUES(?,?,?,?)",
                (skill, reward, json.dumps(context or {}, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        return self.get_skill(skill)

    def get_skill(self, skill: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT name,score,confidence,samples,metadata,updated_at FROM skills WHERE name=?",
                (skill,),
            ).fetchone()
        if not row:
            raise KeyError(f"Skill not found: {skill}")
        return self._row(row)

    def snapshot(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT name,score,confidence,samples,metadata,updated_at FROM skills ORDER BY score ASC, samples DESC"
            ).fetchall()
        skills = [self._row(row) for row in rows]
        return {"skills": skills, "recommendations": self.recommendations(skills)}

    def recommendations(self, skills: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        skills = skills or self.snapshot()["skills"]
        recs = []
        for skill in skills:
            if skill["score"] < 0.55 or skill["confidence"] < 0.55:
                recs.append(
                    {
                        "skill": skill["name"],
                        "action": "increase sandbox trials and collect richer outcome feedback",
                        "priority": round((1 - skill["score"]) * 10, 2),
                    }
                )
        return sorted(recs, key=lambda item: item["priority"], reverse=True)

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "name": row[0],
            "score": row[1],
            "confidence": row[2],
            "samples": row[3],
            "metadata": json.loads(row[4] or "{}"),
            "updated_at": row[5],
        }
