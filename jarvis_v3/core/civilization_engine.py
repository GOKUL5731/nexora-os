"""Evolutionary society engine for agent civilizations."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.cognitive_culture import CognitiveCultureSystem
from core.cognitive_economy import CognitiveEconomy
from core.collective_memory_engine import CollectiveMemoryEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "civilizations.db"


class CivilizationEngine:
    """Creates and evolves persistent civilizations of adaptive agents."""

    DEFAULT_CIVILIZATIONS = {
        "coding": {"purpose": "code generation, testing, and architecture repair", "culture": "deep_reasoning"},
        "automation": {"purpose": "workflow execution and user task automation", "culture": "fast_execution"},
        "research": {"purpose": "autonomous research and scientific discovery", "culture": "experimental"},
        "optimization": {"purpose": "performance, resources, and system optimization", "culture": "resource_efficient"},
    }

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        memory: CollectiveMemoryEngine | None = None,
        culture: CognitiveCultureSystem | None = None,
        economy: CognitiveEconomy | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("civilizations", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory = memory or CollectiveMemoryEngine(self.config)
        self.culture = culture or CognitiveCultureSystem(self.config)
        self.economy = economy or CognitiveEconomy(self.config)
        self._lock = threading.RLock()
        self._init_db()
        self.ensure_defaults()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS civilizations (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    purpose TEXT NOT NULL,
                    culture TEXT NOT NULL,
                    members TEXT DEFAULT '[]',
                    health REAL DEFAULT 0.7,
                    generation INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS civilization_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    civilization TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def ensure_defaults(self) -> None:
        for name, detail in self.DEFAULT_CIVILIZATIONS.items():
            if not self.get_civilization(name, default=None):
                self.create_civilization(name, detail["purpose"], detail["culture"], members=[f"{name}_lead"])

    def create_civilization(
        self,
        name: str,
        purpose: str,
        culture: str,
        members: list[str] | None = None,
    ) -> dict[str, Any]:
        civ_id = f"civ-{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT OR IGNORE INTO civilizations VALUES (?,?,?,?,?,?,?,?,?,?)",
                (civ_id, name, purpose, culture, json.dumps(members or []), 0.7, 1, "active", now, now),
            )
            db.execute(
                "INSERT INTO civilization_events(civilization,event_type,detail,created_at) VALUES(?,?,?,?)",
                (name, "created", json.dumps({"purpose": purpose, "culture": culture}), now),
            )
        self.culture.assign_culture(name, culture)
        self.economy.ensure_account(name)
        self.memory.remember("cultural", name, "founding_purpose", {"purpose": purpose, "culture": culture}, 0.75, [name])
        return self.get_civilization(name)

    def evolve(self, name: str, performance: dict[str, Any]) -> dict[str, Any]:
        civ = self.get_civilization(name)
        health_delta = performance.get("success_rate", 0.6) * 0.1 - performance.get("instability", 0.0) * 0.12
        new_health = round(max(0.0, min(1.0, civ["health"] + health_delta)), 3)
        generation = civ["generation"] + (1 if performance.get("innovation_score", 0) > 0.75 else 0)
        members = list(civ["members"])
        if performance.get("new_specialization") and performance["new_specialization"] not in members:
            members.append(performance["new_specialization"])
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE civilizations SET health=?, generation=?, members=?, updated_at=? WHERE name=?",
                (new_health, generation, json.dumps(members), datetime.now().isoformat(), name),
            )
            db.execute(
                "INSERT INTO civilization_events(civilization,event_type,detail,created_at) VALUES(?,?,?,?)",
                (name, "evolved", json.dumps(performance, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        self.economy.record_contribution(name, performance.get("contribution", 1.0), performance.get("efficiency", 0.6))
        self.memory.remember("evolutionary_history", name, f"generation_{generation}", performance, new_health, [name])
        return self.get_civilization(name)

    def form_research_group(self, topic: str, civilizations: list[str] | None = None) -> dict[str, Any]:
        civilizations = civilizations or ["research", "optimization"]
        group = {
            "id": f"research-group-{uuid.uuid4().hex[:10]}",
            "topic": topic,
            "civilizations": civilizations,
            "created_at": datetime.now().isoformat(),
        }
        for civ in civilizations:
            self.memory.remember("collective", civ, f"research_group:{topic}", group, 0.7, civilizations)
        return group

    def get_civilization(self, name: str, default: Any = None) -> dict[str, Any] | Any:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT id,name,purpose,culture,members,health,generation,status,created_at,updated_at FROM civilizations WHERE name=?",
                (name,),
            ).fetchone()
        return self._row(row) if row else default

    def list_civilizations(self) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,name,purpose,culture,members,health,generation,status,created_at,updated_at FROM civilizations ORDER BY health DESC,name"
            ).fetchall()
        return [self._row(row) for row in rows]

    def events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT civilization,event_type,detail,created_at FROM civilization_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"civilization": row[0], "type": row[1], "detail": json.loads(row[2] or "{}"), "created_at": row[3]}
            for row in rows
        ]

    def snapshot(self) -> dict[str, Any]:
        return {"civilizations": self.list_civilizations(), "events": self.events()}

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "name": row[1],
            "purpose": row[2],
            "culture": row[3],
            "members": json.loads(row[4] or "[]"),
            "health": row[5],
            "generation": row[6],
            "status": row[7],
            "created_at": row[8],
            "updated_at": row[9],
        }
