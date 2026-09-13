from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class GoalManager:
    STATES = {"PENDING", "PLANNING", "READY", "EXECUTING", "WAITING", "BLOCKED", "VERIFYING", "COMPLETED", "FAILED", "CANCELLED"}

    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self._db = sqlite3.connect(database, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS goals(
            id TEXT PRIMARY KEY, original_request TEXT NOT NULL, normalized_objective TEXT NOT NULL,
            status TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 5,
            required_capabilities TEXT NOT NULL, execution_plan TEXT NOT NULL,
            completed_steps TEXT NOT NULL, failed_steps TEXT NOT NULL,
            current_blocker TEXT NOT NULL, retry_count INTEGER NOT NULL DEFAULT 0,
            result TEXT NOT NULL, verification_status TEXT NOT NULL,
            created_at REAL NOT NULL, updated_at REAL NOT NULL)"""
        )
        self._db.commit()

    def create_goal(self, request: str, priority: int = 5) -> dict[str, Any]:
        now = time.time()
        goal_id = uuid.uuid4().hex
        row = {
            "id": goal_id,
            "original_request": request,
            "normalized_objective": " ".join(request.split()),
            "status": "PENDING",
            "priority": priority,
            "required_capabilities": [],
            "execution_plan": [],
            "completed_steps": [],
            "failed_steps": [],
            "current_blocker": "",
            "retry_count": 0,
            "result": {},
            "verification_status": "UNKNOWN",
            "created_at": now,
            "updated_at": now,
        }
        self._db.execute(
            """INSERT INTO goals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["id"], row["original_request"], row["normalized_objective"], row["status"], row["priority"],
                json.dumps(row["required_capabilities"]), json.dumps(row["execution_plan"]),
                json.dumps(row["completed_steps"]), json.dumps(row["failed_steps"]),
                row["current_blocker"], row["retry_count"], json.dumps(row["result"]),
                row["verification_status"], row["created_at"], row["updated_at"],
            ),
        )
        self._db.commit()
        return row

    def update_goal(self, goal_id: str, **changes: Any) -> dict[str, Any]:
        current = self.get_goal(goal_id)
        if not current:
            raise KeyError(goal_id)
        current.update(changes)
        if current["status"] not in self.STATES:
            raise ValueError(f"Invalid goal status: {current['status']}")
        current["updated_at"] = time.time()
        self._db.execute(
            """UPDATE goals SET normalized_objective=?, status=?, priority=?, required_capabilities=?,
            execution_plan=?, completed_steps=?, failed_steps=?, current_blocker=?, retry_count=?,
            result=?, verification_status=?, updated_at=? WHERE id=?""",
            (
                current["normalized_objective"], current["status"], current["priority"],
                json.dumps(current["required_capabilities"]), json.dumps(current["execution_plan"]),
                json.dumps(current["completed_steps"]), json.dumps(current["failed_steps"]),
                current["current_blocker"], current["retry_count"], json.dumps(current["result"]),
                current["verification_status"], current["updated_at"], goal_id,
            ),
        )
        self._db.commit()
        return current

    def get_goal(self, goal_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
        return self._decode(row) if row else None

    def list_goals(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT * FROM goals ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in ("required_capabilities", "execution_plan", "completed_steps", "failed_steps", "result"):
            data[key] = json.loads(data[key]) if data[key] else ([] if key != "result" else {})
        return data
