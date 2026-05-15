"""Distributed research lab network for AI_LAB civilization evolution."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.scientific_discovery import ScientificDiscoveryEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "distributed_research.db"


class DistributedResearchNetwork:
    """Runs multiple autonomous research labs and compares their results."""

    DEFAULT_LABS = {
        "architecture_lab": "competing architecture experiments",
        "optimization_lab": "workflow and resource optimization",
        "reasoning_lab": "reasoning strategy evolution",
        "plugin_lab": "plugin ecosystem research",
    }

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        discovery: ScientificDiscoveryEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("distributed_research", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.discovery = discovery or ScientificDiscoveryEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()
        self.ensure_labs()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS labs (
                    name TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_runs (
                    id TEXT PRIMARY KEY,
                    lab TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def ensure_labs(self) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            for name, purpose in self.DEFAULT_LABS.items():
                db.execute(
                    "INSERT OR IGNORE INTO labs VALUES (?,?,?,?)",
                    (name, purpose, "active", datetime.now().isoformat()),
                )

    async def run_lab(self, lab: str, topic: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0)
        scoped = {**snapshot, "lab": lab, "topic": topic}
        discoveries = self.discovery.run_discovery(scoped, limit=1)
        result = {"lab": lab, "topic": topic, "discoveries": discoveries}
        run_id = f"labrun-{uuid.uuid4().hex[:12]}"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO research_runs VALUES (?,?,?,?,?)",
                (run_id, lab, topic, json.dumps(result, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        return {"id": run_id, **result}

    async def run_parallel_research(self, topic: str, snapshot: dict[str, Any], labs: list[str] | None = None) -> list[dict[str, Any]]:
        labs = labs or [lab["name"] for lab in self.list_labs()]
        return await asyncio.gather(*(self.run_lab(lab, topic, snapshot) for lab in labs))

    def list_labs(self) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT name,purpose,status,updated_at FROM labs ORDER BY name").fetchall()
        return [{"name": row[0], "purpose": row[1], "status": row[2], "updated_at": row[3]} for row in rows]

    def recent_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT id,lab,topic,result,created_at FROM research_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": row[0], "lab": row[1], "topic": row[2], "result": json.loads(row[3] or "{}"), "created_at": row[4]} for row in rows]

    def snapshot(self) -> dict[str, Any]:
        return {"labs": self.list_labs(), "runs": self.recent_runs()}
