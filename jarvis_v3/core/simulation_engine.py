"""Outcome simulation and bounded preflight checks for autonomous actions."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import psutil

from core.sandbox_engine import SandboxEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "simulations.db"


class SimulationEngine:
    """Simulates plan execution, resource impact, and rollback risk before acting."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        sandbox: SandboxEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("simulation", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sandbox = sandbox or SandboxEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS simulations (
                    id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    risk_score REAL DEFAULT 0,
                    passed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                """
            )

    def simulate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        tasks = plan.get("tasks", [])
        dependency_ids = {dep for task in tasks for dep in task.get("dependencies", [])}
        task_ids = {task.get("id") for task in tasks}
        missing_dependencies = sorted(dep for dep in dependency_ids if dep not in task_ids)
        high_priority = sum(1 for task in tasks if task.get("priority", 5) >= 8)
        fanout = max((sum(1 for t in tasks if dep in t.get("dependencies", [])) for dep in task_ids), default=0)
        resource = self.estimate_resource_impact(tasks)
        rollback = self.rollback_risk(plan)
        risk_score = min(
            1.0,
            0.15
            + len(missing_dependencies) * 0.2
            + max(0, fanout - 3) * 0.05
            + resource["pressure_score"] * 0.3
            + rollback["risk_score"] * 0.25,
        )
        outcome = {
            "plan_id": plan.get("id", "unknown"),
            "task_count": len(tasks),
            "high_priority_tasks": high_priority,
            "missing_dependencies": missing_dependencies,
            "resource_impact": resource,
            "rollback": rollback,
            "expected_success": round(1.0 - risk_score, 3),
            "recommendations": self._recommendations(missing_dependencies, resource, rollback),
        }
        return self._record("plan", plan.get("id", "unknown"), outcome, risk_score)

    def simulate_workflow(self, spec: dict[str, Any]) -> dict[str, Any]:
        steps = spec.get("steps", [])
        destructive = [s for s in steps if s.get("action") in {"delete", "write", "deploy", "shell"}]
        waits = sum(float(s.get("params", {}).get("seconds", 0)) for s in steps if s.get("action") == "wait")
        risk_score = min(1.0, len(destructive) * 0.25 + min(waits / 60, 0.25))
        outcome = {
            "workflow": spec.get("name", "unnamed"),
            "step_count": len(steps),
            "destructive_steps": len(destructive),
            "estimated_wait_seconds": waits,
            "expected_success": round(1.0 - risk_score, 3),
            "recommendations": ["require rollback snapshot before destructive steps"] if destructive else [],
        }
        return self._record("workflow", spec.get("name", "unnamed"), outcome, risk_score)

    def sandbox_trial(self, label: str, files: dict[str, str], entry: str | None = None) -> dict[str, Any]:
        session = self.sandbox.create_session(label)
        try:
            for relative_path, content in files.items():
                self.sandbox.write_file(session, relative_path, content)
            compile_results = [self.sandbox.run_py_compile(session, path).to_dict() for path in files if path.endswith(".py")]
            run_result = self.sandbox.run_python(session, entry).to_dict() if entry else {}
            passed = all(result["ok"] for result in compile_results) and (not run_result or run_result.get("ok"))
            outcome = {"compile": compile_results, "run": run_result, "passed": passed}
            return self._record("sandbox", label, outcome, 0.1 if passed else 0.8)
        finally:
            self.sandbox.cleanup_session(session)

    def run_virtual_trial(self, label: str, trial: Callable[[], Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            result = trial()
            outcome = {"ok": True, "result": result, "duration_ms": round((time.perf_counter() - started) * 1000, 1)}
            return self._record("virtual_trial", label, outcome, 0.2)
        except Exception as exc:
            outcome = {"ok": False, "error": str(exc), "duration_ms": round((time.perf_counter() - started) * 1000, 1)}
            return self._record("virtual_trial", label, outcome, 0.85)

    def estimate_resource_impact(self, tasks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        tasks = tasks or []
        cpu = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        heavy = sum(1 for task in tasks if task.get("agent") in {"coder", "tester", "optimizer"})
        pressure = min(1.0, (cpu / 100) * 0.35 + (vm.percent / 100) * 0.45 + min(heavy / 12, 0.2))
        return {
            "cpu_percent": cpu,
            "memory_percent": vm.percent,
            "heavy_task_count": heavy,
            "pressure_score": round(pressure, 3),
            "recommended_concurrency": max(1, min(8, int(6 - pressure * 4))),
        }

    def rollback_risk(self, target: dict[str, Any]) -> dict[str, Any]:
        text = json.dumps(target, default=str).lower()
        markers = ["deploy", "delete", "write", "upgrade", "self", "plugin", "shell"]
        hits = [marker for marker in markers if marker in text]
        risk = min(1.0, len(hits) * 0.12)
        return {"risk_score": round(risk, 3), "risk_markers": hits, "snapshot_required": bool(hits)}

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,target_type,target_id,outcome,risk_score,passed,created_at "
                "FROM simulations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "target_type": row[1],
                "target_id": row[2],
                "outcome": json.loads(row[3] or "{}"),
                "risk_score": row[4],
                "passed": bool(row[5]),
                "created_at": row[6],
            }
            for row in rows
        ]

    def _record(self, target_type: str, target_id: str, outcome: dict[str, Any], risk_score: float) -> dict[str, Any]:
        simulation_id = f"sim-{uuid.uuid4().hex[:12]}"
        passed = risk_score < 0.65
        record = {
            "id": simulation_id,
            "target_type": target_type,
            "target_id": target_id,
            "outcome": outcome,
            "risk_score": round(risk_score, 3),
            "passed": passed,
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO simulations VALUES (?,?,?,?,?,?,?)",
                (
                    record["id"],
                    target_type,
                    str(target_id),
                    json.dumps(outcome, ensure_ascii=False, default=str),
                    record["risk_score"],
                    1 if passed else 0,
                    record["created_at"],
                ),
            )
        return record

    @staticmethod
    def _recommendations(missing_dependencies: list[str], resource: dict[str, Any], rollback: dict[str, Any]) -> list[str]:
        recs = []
        if missing_dependencies:
            recs.append("repair missing task dependencies before execution")
        if resource["pressure_score"] > 0.65:
            recs.append("lower concurrency until system pressure drops")
        if rollback["snapshot_required"]:
            recs.append("create rollback snapshot before deployment or file mutation")
        return recs
