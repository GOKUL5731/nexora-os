"""Long-horizon strategic forecasting for cognitive civilization evolution."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "strategic_forecasting.db"


class StrategicForecastingEngine:
    """Forecasts weeks/months evolution trajectories and adaptive priorities."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("strategic_forecasting", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS forecasts (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    forecast TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def forecast(self, objective: str, snapshot: dict[str, Any], horizon_days: int = 30) -> dict[str, Any]:
        civs = snapshot.get("civilizations", {}).get("civilizations", [])
        avg_health = sum(c.get("health", 0.7) for c in civs) / max(1, len(civs))
        memory_ok = snapshot.get("collective_memory", {}).get("consistency", {}).get("ok", True)
        research_count = len(snapshot.get("research", {}).get("runs", []))
        risk = min(1.0, (1 - avg_health) * 0.45 + (0 if memory_ok else 0.25) + max(0, 3 - research_count) * 0.05)
        forecast = {
            "objective": objective,
            "target_date": (datetime.now() + timedelta(days=horizon_days)).date().isoformat(),
            "success_probability": round(1.0 - risk, 3),
            "risk_score": round(risk, 3),
            "recommended_priorities": self.reprioritize(snapshot, risk),
        }
        forecast_id = f"forecast-{uuid.uuid4().hex[:12]}"
        record = {"id": forecast_id, **forecast, "horizon_days": horizon_days, "created_at": datetime.now().isoformat()}
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO forecasts VALUES (?,?,?,?,?)",
                (forecast_id, objective, horizon_days, json.dumps(forecast, ensure_ascii=False, default=str), record["created_at"]),
            )
        return record

    def reprioritize(self, snapshot: dict[str, Any], risk: float) -> list[dict[str, Any]]:
        priorities = [
            {"target": "ecosystem_stability", "priority": 10 if risk > 0.5 else 6},
            {"target": "scientific_discovery", "priority": 8},
            {"target": "collective_memory_sync", "priority": 7 if snapshot.get("collective_memory", {}).get("consistency", {}).get("ok", True) else 10},
            {"target": "resource_civilization", "priority": 7},
        ]
        return sorted(priorities, key=lambda item: item["priority"], reverse=True)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT id,objective,horizon_days,forecast,created_at FROM forecasts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": row[0], "objective": row[1], "horizon_days": row[2], "forecast": json.loads(row[3] or "{}"), "created_at": row[4]} for row in rows]
