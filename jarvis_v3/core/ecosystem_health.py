"""Civilization health, containment, rollback tree, and stability scoring."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "civilization_health.db"


class EcosystemHealthEngine:
    """Scores civilization health and proposes containment for instability."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("ecosystem_health", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS ecosystem_health_reports (
                    id TEXT PRIMARY KEY,
                    report TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def evaluate(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        civs = snapshot.get("civilizations", {}).get("civilizations", [])
        memory_ok = snapshot.get("collective_memory", {}).get("consistency", {}).get("ok", True)
        governance_blocks = [
            item for item in snapshot.get("governance", {}).get("decisions", [])
            if item.get("decision") == "blocked"
        ]
        avg_health = sum(c.get("health", 0.7) for c in civs) / max(1, len(civs))
        score = avg_health
        if not memory_ok:
            score -= 0.2
        score -= min(0.25, len(governance_blocks) * 0.03)
        score = round(max(0.0, min(1.0, score)), 3)
        issues = []
        if score < 0.5:
            issues.append({"type": "civilization_health_low", "severity": "high"})
        if not memory_ok:
            issues.append({"type": "collective_memory_inconsistency", "severity": "high"})
        if governance_blocks:
            issues.append({"type": "governance_block_pressure", "severity": "medium", "count": len(governance_blocks)})
        status = "healthy" if score >= 0.7 and not issues else ("critical" if any(i["severity"] == "high" for i in issues) else "degraded")
        report = {
            "id": f"civ-health-{uuid.uuid4().hex[:12]}",
            "score": score,
            "status": status,
            "issues": issues,
            "containment": self.containment_plan(issues),
            "rollback_tree": self.rollback_tree(issues),
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO ecosystem_health_reports VALUES (?,?,?,?)",
                (report["id"], json.dumps(report, ensure_ascii=False, default=str), status, report["created_at"]),
            )
        return report

    @staticmethod
    def containment_plan(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        actions = []
        for issue in issues:
            if issue["type"] == "collective_memory_inconsistency":
                actions.append({"action": "pause memory synchronization and rebuild low-confidence records", "priority": 10})
            elif issue["type"] == "civilization_health_low":
                actions.append({"action": "switch all civilizations to conservative culture and reduce experiments", "priority": 9})
            else:
                actions.append({"action": "require governance approval for new competitions", "priority": 7})
        return sorted(actions, key=lambda item: item["priority"], reverse=True)

    @staticmethod
    def rollback_tree(issues: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "required": bool(issues),
            "steps": [
                "restore last healthy collective memory snapshot",
                "revert active civilization culture changes",
                "disable failed research lab runs",
                "re-run governance validation",
            ] if issues else [],
        }

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT report FROM ecosystem_health_reports ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0] or "{}") for row in rows]
