"""Internal simulation universe for architecture, strategy, workflow, and society trials."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.digital_twin_engine import DigitalTwinEngine
from core.simulation_engine import SimulationEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "simulation_universe.db"


class SimulationUniverse:
    """Runs isolated scenario simulations and records comparable outcomes."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        simulation: SimulationEngine | None = None,
        twins: DigitalTwinEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("simulation_universe", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.simulation = simulation or SimulationEngine(self.config)
        self.twins = twins or DigitalTwinEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS universe_runs (
                    id TEXT PRIMARY KEY,
                    scenario_type TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    result TEXT NOT NULL,
                    passed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                """
            )

    def run_scenario(self, scenario_type: str, scenario: dict[str, Any]) -> dict[str, Any]:
        if scenario_type == "workflow":
            result = self.simulation.simulate_workflow(scenario)
        elif scenario_type == "plan":
            result = self.simulation.simulate_plan(scenario)
        elif scenario_type == "digital_twin":
            result = self.twins.simulate_twin_outcome(
                scenario["twin_type"],
                scenario["name"],
                scenario.get("change", {}),
            )
            result = {"passed": result["risk_score"] < 0.65, "risk_score": result["risk_score"], "outcome": result}
        elif scenario_type == "architecture":
            result = self._simulate_architecture(scenario)
        elif scenario_type == "agent_coordination":
            result = self._simulate_agent_coordination(scenario)
        else:
            result = {"passed": False, "risk_score": 0.9, "outcome": {"error": f"unknown scenario: {scenario_type}"}}
        return self._record(scenario_type, scenario, result)

    def run_batch(self, scenarios: list[dict[str, Any]], concurrency: int = 4) -> list[dict[str, Any]]:
        results = []
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = [
                pool.submit(self.run_scenario, scenario["type"], scenario.get("scenario", {}))
                for scenario in scenarios
            ]
            for future in as_completed(futures):
                results.append(future.result())
        return sorted(results, key=lambda item: item["created_at"])

    def run_virtual_trial(self, label: str, trial: Callable[[], Any]) -> dict[str, Any]:
        result = self.simulation.run_virtual_trial(label, trial)
        return self._record("virtual_trial", {"label": label}, result)

    def recent_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,scenario_type,scenario,result,passed,created_at FROM universe_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "type": row[1],
                "scenario": json.loads(row[2] or "{}"),
                "result": json.loads(row[3] or "{}"),
                "passed": bool(row[4]),
                "created_at": row[5],
            }
            for row in rows
        ]

    def _simulate_architecture(self, scenario: dict[str, Any]) -> dict[str, Any]:
        changed_components = len(scenario.get("components", []))
        rollback = bool(scenario.get("rollback_plan"))
        tests = len(scenario.get("tests", []))
        risk = min(1.0, 0.2 + changed_components * 0.08 - (0.15 if rollback else 0) - min(0.25, tests * 0.04))
        return {
            "passed": risk < 0.65,
            "risk_score": round(max(0.0, risk), 3),
            "outcome": {
                "changed_components": changed_components,
                "rollback_available": rollback,
                "test_count": tests,
            },
        }

    def _simulate_agent_coordination(self, scenario: dict[str, Any]) -> dict[str, Any]:
        agents = scenario.get("agents", [])
        tasks = scenario.get("tasks", [])
        average_trust = sum(a.get("trust", 0.6) for a in agents) / max(1, len(agents))
        overload = max(0, len(tasks) - max(1, len(agents)) * 3)
        risk = min(1.0, 0.25 + overload * 0.05 + (1 - average_trust) * 0.35)
        return {
            "passed": risk < 0.65,
            "risk_score": round(risk, 3),
            "outcome": {"agent_count": len(agents), "task_count": len(tasks), "average_trust": round(average_trust, 3)},
        }

    def _record(self, scenario_type: str, scenario: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        run_id = f"universe-{uuid.uuid4().hex[:12]}"
        record = {
            "id": run_id,
            "type": scenario_type,
            "scenario": scenario,
            "result": result,
            "passed": bool(result.get("passed")),
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO universe_runs VALUES (?,?,?,?,?,?)",
                (
                    run_id,
                    scenario_type,
                    json.dumps(scenario, ensure_ascii=False, default=str),
                    json.dumps(result, ensure_ascii=False, default=str),
                    1 if record["passed"] else 0,
                    record["created_at"],
                ),
            )
        return record
