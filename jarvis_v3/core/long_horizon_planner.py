"""Long-horizon goal engine with future planning trees."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.goal_manager import GoalManager


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "long_horizon.db"


class LongHorizonPlanner:
    """Maintains short, medium, and long horizon goals with dependency forecasting."""

    HORIZON_DAYS = {"short": 7, "medium": 30, "long": 180}

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        goals: GoalManager | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("long_horizon", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.goals = goals or GoalManager(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS horizon_nodes (
                    id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    parent_id TEXT DEFAULT '',
                    forecast TEXT DEFAULT '{}',
                    target_date TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_horizon_goal ON horizon_nodes(goal_id, horizon);
                """
            )

    def create_horizon_goal(
        self,
        title: str,
        horizon: str = "short",
        priority: int = 5,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        parent_id: str = "",
    ) -> dict[str, Any]:
        horizon = horizon if horizon in self.HORIZON_DAYS else "short"
        goal = self.goals.create_goal(
            title,
            metadata.get("goal_type", "system") if metadata else "system",
            priority,
            dependencies,
            {**(metadata or {}), "horizon": horizon},
        )
        node_id = f"horizon-{uuid.uuid4().hex[:12]}"
        forecast = self.forecast_goal(goal, horizon)
        target_date = (datetime.now() + timedelta(days=self.HORIZON_DAYS[horizon])).date().isoformat()
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO horizon_nodes VALUES (?,?,?,?,?,?,?)",
                (
                    node_id,
                    goal["id"],
                    horizon,
                    parent_id,
                    json.dumps(forecast, ensure_ascii=False, default=str),
                    target_date,
                    datetime.now().isoformat(),
                ),
            )
        return {"node_id": node_id, "goal": goal, "horizon": horizon, "forecast": forecast, "target_date": target_date}

    def forecast_goal(self, goal: dict[str, Any], horizon: str) -> dict[str, Any]:
        dep_count = len(goal.get("dependencies", []))
        days = self.HORIZON_DAYS.get(horizon, 7)
        complexity = min(1.0, dep_count * 0.15 + len(goal["title"]) / 300)
        return {
            "estimated_days": max(1, round(days * (0.2 + complexity), 1)),
            "dependency_risk": round(min(1.0, dep_count * 0.2), 3),
            "success_probability": round(max(0.15, 0.9 - complexity * 0.45), 3),
        }

    def build_planning_tree(self, root_title: str, horizons: list[str] | None = None) -> dict[str, Any]:
        horizons = horizons or ["short", "medium", "long"]
        root = self.create_horizon_goal(root_title, horizons[-1], priority=8)
        children = []
        previous_goal_id = root["goal"]["id"]
        for horizon in reversed(horizons[:-1]):
            child = self.create_horizon_goal(
                f"{horizon.title()} milestone for {root_title}",
                horizon,
                priority=7,
                dependencies=[] if horizon == "short" else [previous_goal_id],
                parent_id=root["node_id"],
            )
            children.append(child)
            previous_goal_id = child["goal"]["id"]
        return {"root": root, "children": children}

    def reprioritize(self, resource_pressure: float = 0.0) -> list[dict[str, Any]]:
        goals = self.goals.list_goals(limit=500)
        adjusted = []
        for goal in goals:
            horizon = goal.get("metadata", {}).get("horizon", "short")
            boost = 2 if horizon == "short" else (1 if horizon == "medium" else 0)
            penalty = 2 if resource_pressure > 0.75 and horizon == "long" else 0
            score = max(1, min(10, goal["priority"] + boost - penalty))
            adjusted.append({**goal, "adaptive_priority": score})
        return sorted(adjusted, key=lambda item: item["adaptive_priority"], reverse=True)

    def snapshot(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,goal_id,horizon,parent_id,forecast,target_date,created_at FROM horizon_nodes ORDER BY target_date"
            ).fetchall()
        return {
            "nodes": [
                {
                    "id": row[0],
                    "goal_id": row[1],
                    "horizon": row[2],
                    "parent_id": row[3],
                    "forecast": json.loads(row[4] or "{}"),
                    "target_date": row[5],
                    "created_at": row[6],
                }
                for row in rows
            ],
            "reprioritized": self.reprioritize(),
        }
