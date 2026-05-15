"""Autonomous cognitive governance for safe recursive evolution."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "governance.db"


class GovernanceEngine:
    """Enforces integrity, resource, sandbox, plugin, and workflow safety policies."""

    DEFAULT_POLICIES = {
        "sandbox_required": {"enabled": True, "severity": "high"},
        "benchmark_required": {"enabled": True, "severity": "high"},
        "rollback_required": {"enabled": True, "severity": "high"},
        "max_resource_pressure": {"enabled": True, "severity": "medium", "threshold": 0.85},
        "no_recursive_self_modification": {"enabled": True, "severity": "critical"},
        "plugin_verification_required": {"enabled": True, "severity": "high"},
    }

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("governance", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()
        self.ensure_default_policies()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS policies (
                    name TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS governance_decisions (
                    id TEXT PRIMARY KEY,
                    proposal TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    violations TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def ensure_default_policies(self) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            for name, config in self.DEFAULT_POLICIES.items():
                db.execute(
                    "INSERT OR IGNORE INTO policies VALUES (?,?,?)",
                    (name, json.dumps(config), datetime.now().isoformat()),
                )

    def evaluate(
        self,
        proposal: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        policies = self.policies()
        violations = []
        text = json.dumps(proposal, default=str).lower()
        if policies["sandbox_required"]["enabled"] and not proposal.get("sandboxed", False):
            violations.append({"policy": "sandbox_required", "severity": "high"})
        if policies["benchmark_required"]["enabled"] and not proposal.get("benchmarked", False):
            violations.append({"policy": "benchmark_required", "severity": "high"})
        if policies["rollback_required"]["enabled"] and not proposal.get("rollback_plan", False):
            violations.append({"policy": "rollback_required", "severity": "high"})
        if "recursive self-modification" in text or "disable safety" in text:
            violations.append({"policy": "no_recursive_self_modification", "severity": "critical"})
        threshold = policies["max_resource_pressure"].get("threshold", 0.85)
        if context.get("resource_pressure", 0) > threshold:
            violations.append({"policy": "max_resource_pressure", "severity": "medium", "value": context["resource_pressure"]})
        if proposal.get("type") == "plugin" and not proposal.get("plugin_verified", False):
            violations.append({"policy": "plugin_verification_required", "severity": "high"})
        decision = "approved" if not violations else ("blocked" if any(v["severity"] in {"high", "critical"} for v in violations) else "deferred")
        record = {
            "id": f"gov-{uuid.uuid4().hex[:12]}",
            "decision": decision,
            "violations": violations,
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO governance_decisions VALUES (?,?,?,?,?)",
                (
                    record["id"],
                    json.dumps(proposal, ensure_ascii=False, default=str),
                    decision,
                    json.dumps(violations, ensure_ascii=False, default=str),
                    record["created_at"],
                ),
            )
        return record

    def policies(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT name,config FROM policies").fetchall()
        return {row[0]: json.loads(row[1] or "{}") for row in rows}

    def recent_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,proposal,decision,violations,created_at FROM governance_decisions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "proposal": json.loads(row[1] or "{}"),
                "decision": row[2],
                "violations": json.loads(row[3] or "[]"),
                "created_at": row[4],
            }
            for row in rows
        ]
