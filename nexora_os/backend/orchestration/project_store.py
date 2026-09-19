from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class ProjectStore:
    """Durable store for orchestration state needed across process restarts."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS projects (project_id TEXT PRIMARY KEY, state TEXT NOT NULL)")
            db.commit()

    def save(self, project: dict[str, Any]) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO projects(project_id, state) VALUES(?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET state=excluded.state",
                (project["project_id"], json.dumps(project)),
            )
            db.commit()

    def load_all(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT state FROM projects ORDER BY rowid").fetchall()
        return [json.loads(state) for (state,) in rows]
