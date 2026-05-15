"""Autonomous scientific discovery engine for cognitive civilization research."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.collective_memory_engine import CollectiveMemoryEngine
from core.simulation_universe import SimulationUniverse


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "scientific_discovery.db"


class ScientificDiscoveryEngine:
    """Generates hypotheses, designs experiments, benchmarks, and synthesizes discoveries."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        universe: SimulationUniverse | None = None,
        memory: CollectiveMemoryEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("scientific_discovery", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.universe = universe or SimulationUniverse(self.config)
        self.memory = memory or CollectiveMemoryEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS discoveries (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    hypothesis TEXT NOT NULL,
                    experiment TEXT NOT NULL,
                    benchmark TEXT NOT NULL,
                    conclusion TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def identify_opportunities(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        opportunities = []
        for item in snapshot.get("graph", {}).get("opportunities", [])[:3]:
            opportunities.append({"topic": item.get("target", "graph optimization"), "signal": item.get("type", "graph")})
        for item in snapshot.get("skills", {}).get("recommendations", [])[:3]:
            opportunities.append({"topic": item.get("skill", "skill evolution"), "signal": "skill_gap"})
        if snapshot.get("resources", {}).get("pressure_score", 0) > 0.65:
            opportunities.append({"topic": "resource scheduling", "signal": "resource_pressure"})
        if not opportunities:
            opportunities.append({"topic": "reasoning strategy evolution", "signal": "baseline_exploration"})
        return opportunities

    def generate_hypothesis(self, opportunity: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": f"hypothesis-{uuid.uuid4().hex[:10]}",
            "topic": opportunity["topic"],
            "claim": f"Changing the {opportunity['topic']} strategy can improve ecosystem efficiency without reducing stability.",
            "signal": opportunity["signal"],
        }

    def design_experiment(self, hypothesis: dict[str, Any]) -> dict[str, Any]:
        topic = hypothesis["topic"]
        if "resource" in topic:
            scenario = {"components": [{"component": "resource_intelligence"}], "rollback_plan": True, "tests": ["resource_benchmark"]}
        elif "graph" in topic:
            scenario = {"components": [{"component": "knowledge_graph"}], "rollback_plan": True, "tests": ["graph_validation"]}
        else:
            scenario = {"components": [{"component": "reasoning_strategy"}], "rollback_plan": True, "tests": ["strategy_benchmark"]}
        return {"type": "architecture", "scenario": scenario, "hypothesis": hypothesis}

    def run_discovery(self, snapshot: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
        results = []
        for opportunity in self.identify_opportunities(snapshot)[:limit]:
            hypothesis = self.generate_hypothesis(opportunity)
            experiment = self.design_experiment(hypothesis)
            benchmark = self.universe.run_scenario(experiment["type"], experiment["scenario"])
            conclusion = self.synthesize_discovery(hypothesis, benchmark)
            record = {
                "id": f"discovery-{uuid.uuid4().hex[:12]}",
                "topic": opportunity["topic"],
                "hypothesis": hypothesis,
                "experiment": experiment,
                "benchmark": benchmark,
                "conclusion": conclusion,
                "created_at": datetime.now().isoformat(),
            }
            with self._lock, sqlite3.connect(self.db_path) as db:
                db.execute(
                    "INSERT INTO discoveries VALUES (?,?,?,?,?,?,?)",
                    (
                        record["id"],
                        record["topic"],
                        json.dumps(hypothesis, ensure_ascii=False, default=str),
                        json.dumps(experiment, ensure_ascii=False, default=str),
                        json.dumps(benchmark, ensure_ascii=False, default=str),
                        json.dumps(conclusion, ensure_ascii=False, default=str),
                        record["created_at"],
                    ),
                )
            self.memory.remember("scientific", "research", record["topic"], conclusion, conclusion["confidence"], ["scientific_discovery"])
            results.append(record)
        return results

    @staticmethod
    def synthesize_discovery(hypothesis: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
        passed = bool(benchmark.get("passed"))
        risk = benchmark.get("result", {}).get("risk_score", 0.5)
        return {
            "supported": passed and risk < 0.65,
            "confidence": round(max(0.2, 1.0 - risk), 3),
            "summary": f"Hypothesis {hypothesis['id']} {'supported' if passed else 'not supported'} under simulation.",
        }

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,topic,hypothesis,experiment,benchmark,conclusion,created_at FROM discoveries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "topic": row[1],
                "hypothesis": json.loads(row[2] or "{}"),
                "experiment": json.loads(row[3] or "{}"),
                "benchmark": json.loads(row[4] or "{}"),
                "conclusion": json.loads(row[5] or "{}"),
                "created_at": row[6],
            }
            for row in rows
        ]
