"""Cognitive health system for drift, instability, corruption, and degradation."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "cognitive_health.db"


class CognitiveHealthSystem:
    """Monitors cognitive consistency and creates recovery recommendations."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("cognitive_health", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS health_reports (
                    id TEXT PRIMARY KEY,
                    report TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def evaluate(
        self,
        autonomy_snapshot: dict[str, Any],
        meta_observation: dict[str, Any] | None = None,
        twin_failures: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        checks = []
        meta = (meta_observation or {}).get("analysis", {})
        if meta.get("cognitive_quality", 1.0) < 0.55:
            checks.append({"type": "reasoning_drift", "severity": "high", "detail": meta})
        graph_valid = autonomy_snapshot.get("graph", {}).get("validation", {}).get("valid", True)
        if not graph_valid:
            checks.append({"type": "memory_graph_inconsistency", "severity": "high"})
        for agent in autonomy_snapshot.get("society", {}).get("agents", []):
            if agent.get("trust", 1.0) < 0.35 or agent.get("reputation", 1.0) < 0.35:
                checks.append({"type": "unstable_agent", "severity": "medium", "agent": agent.get("agent")})
        predictions = ((autonomy_snapshot.get("loop", {}).get("last_cycle") or {}).get("state", {}) or {}).get("predictions", {})
        top = predictions.get("top") if isinstance(predictions, dict) else None
        if top and top.get("confidence", 1.0) < 0.25:
            checks.append({"type": "prediction_degradation", "severity": "medium"})
        for failure in twin_failures or []:
            checks.append({"type": f"twin_{failure['type']}", "severity": failure.get("severity", "medium"), "detail": failure})
        status = "healthy" if not checks else ("critical" if any(c["severity"] == "high" for c in checks) else "degraded")
        report = {
            "id": f"health-{uuid.uuid4().hex[:12]}",
            "status": status,
            "checks": checks,
            "recovery_plan": self.recovery_plan(checks),
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO health_reports VALUES (?,?,?,?)",
                (report["id"], json.dumps(report, ensure_ascii=False, default=str), status, report["created_at"]),
            )
        return report

    def recovery_plan(self, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        actions = []
        for check in checks:
            ctype = check["type"]
            if ctype == "reasoning_drift":
                actions.append({"action": "switch strategy and run benchmark comparison", "priority": 9})
            elif ctype == "memory_graph_inconsistency":
                actions.append({"action": "validate graph and rebuild derived relationships", "priority": 10})
            elif ctype == "unstable_agent":
                actions.append({"action": "reduce agent load and lower hierarchy until reputation recovers", "priority": 7})
            elif ctype == "prediction_degradation":
                actions.append({"action": "collect fresh action history and retrain prediction patterns", "priority": 6})
            elif ctype.startswith("twin_"):
                actions.append({"action": "run digital twin simulation before next deployment", "priority": 7})
        return sorted(actions, key=lambda item: item["priority"], reverse=True)

    def recent_reports(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT report FROM health_reports ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row[0] or "{}") for row in rows]
