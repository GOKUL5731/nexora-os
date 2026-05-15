"""Persistent goal management for the cognitive autonomy layer."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "goals.db"


class GoalManager:
    """Stores long-lived goals with priorities, dependencies, and progress."""

    VALID_TYPES = {"user", "system", "optimization", "learning", "workflow"}
    ACTIVE_STATUSES = {"active", "blocked", "in_progress"}

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("goals", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'active',
                    progress REAL DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS goal_dependencies (
                    goal_id TEXT NOT NULL,
                    depends_on TEXT NOT NULL,
                    PRIMARY KEY(goal_id, depends_on)
                );
                CREATE TABLE IF NOT EXISTS goal_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_goals_status_priority ON goals(status, priority);
                """
            )

    def create_goal(
        self,
        title: str,
        goal_type: str = "user",
        priority: int = 5,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        goal_type = goal_type if goal_type in self.VALID_TYPES else "user"
        goal_id = f"goal-{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO goals VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    goal_id,
                    title[:500],
                    goal_type,
                    int(max(1, min(10, priority))),
                    "active",
                    0.0,
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    now,
                    now,
                    "",
                ),
            )
            for dep in dependencies or []:
                db.execute("INSERT OR IGNORE INTO goal_dependencies VALUES (?,?)", (goal_id, dep))
            db.execute(
                "INSERT INTO goal_events(goal_id,event_type,detail,created_at) VALUES(?,?,?,?)",
                (goal_id, "created", json.dumps({"title": title}), now),
            )
        return self.get_goal(goal_id)

    def get_goal(self, goal_id: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT id,title,goal_type,priority,status,progress,metadata,created_at,updated_at,completed_at "
                "FROM goals WHERE id=?",
                (goal_id,),
            ).fetchone()
            deps = [r[0] for r in db.execute("SELECT depends_on FROM goal_dependencies WHERE goal_id=?", (goal_id,))]
        if not row:
            raise KeyError(f"Goal not found: {goal_id}")
        return self._row_to_goal(row, deps)

    def list_goals(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = (
            "SELECT id,title,goal_type,priority,status,progress,metadata,created_at,updated_at,completed_at "
            "FROM goals"
        )
        params: list[Any] = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY priority DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(sql, params).fetchall()
            deps_by_goal = {
                row[0]: [d[0] for d in db.execute("SELECT depends_on FROM goal_dependencies WHERE goal_id=?", (row[0],))]
                for row in rows
            }
        return [self._row_to_goal(row, deps_by_goal.get(row[0], [])) for row in rows]

    def update_progress(
        self,
        goal_id: str,
        progress: float,
        status: str | None = None,
        event: str = "progress",
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        progress = max(0.0, min(1.0, float(progress)))
        now = datetime.now().isoformat()
        completed_at = now if progress >= 1.0 or status == "completed" else ""
        new_status = status or ("completed" if progress >= 1.0 else "in_progress")
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                UPDATE goals
                SET progress=?, status=?, updated_at=?, completed_at=COALESCE(NULLIF(?, ''), completed_at)
                WHERE id=?
                """,
                (progress, new_status, now, completed_at, goal_id),
            )
            db.execute(
                "INSERT INTO goal_events(goal_id,event_type,detail,created_at) VALUES(?,?,?,?)",
                (goal_id, event, json.dumps(detail or {}, ensure_ascii=False, default=str), now),
            )
        return self.get_goal(goal_id)

    def next_goals(self, limit: int = 5) -> list[dict[str, Any]]:
        goals = [g for g in self.list_goals(limit=500) if g["status"] in self.ACTIVE_STATUSES]
        completed = {g["id"] for g in self.list_goals(status="completed", limit=1000)}
        ready = [g for g in goals if all(dep in completed for dep in g["dependencies"])]
        blocked = [g for g in goals if g not in ready]
        for goal in blocked:
            if goal["status"] != "blocked":
                self.update_progress(goal["id"], goal["progress"], status="blocked", event="blocked")
        ready.sort(key=lambda g: (g["priority"], -g["progress"]), reverse=True)
        return ready[:limit]

    def progress_summary(self) -> dict[str, Any]:
        goals = self.list_goals(limit=1000)
        counts: dict[str, int] = {}
        for goal in goals:
            counts[goal["status"]] = counts.get(goal["status"], 0) + 1
        average = sum(g["progress"] for g in goals) / max(1, len(goals))
        return {
            "total": len(goals),
            "status_counts": counts,
            "average_progress": round(average, 3),
            "ready": self.next_goals(limit=10),
        }

    @staticmethod
    def _row_to_goal(row: tuple[Any, ...], dependencies: list[str]) -> dict[str, Any]:
        return {
            "id": row[0],
            "title": row[1],
            "type": row[2],
            "priority": row[3],
            "status": row[4],
            "progress": row[5],
            "metadata": json.loads(row[6] or "{}"),
            "created_at": row[7],
            "updated_at": row[8],
            "completed_at": row[9],
            "dependencies": dependencies,
        }
