"""Global intelligence orchestration with graphs, balancing, conflicts, and prioritization."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.reasoning_strategy_engine import DynamicReasoningStrategyEngine
from core.resource_intelligence import ResourceIntelligence


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "orchestration_intelligence.db"


class OrchestrationIntelligence:
    """Coordinates workflows, memory, simulations, agents, evolution, and resources."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        reasoning: DynamicReasoningStrategyEngine | None = None,
        resources: ResourceIntelligence | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("orchestration_intelligence", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.reasoning = reasoning or DynamicReasoningStrategyEngine(self.config)
        self.resources = resources or ResourceIntelligence(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS orchestration_graphs (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    graph TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def build_graph(self, objective: str, components: list[str] | None = None) -> dict[str, Any]:
        components = components or ["memory", "agents", "simulation", "evolution", "resources", "reflection"]
        nodes = [{"id": f"node:{component}", "type": component, "label": component.title()} for component in components]
        edges = []
        for idx in range(len(nodes) - 1):
            edges.append({"source": nodes[idx]["id"], "target": nodes[idx + 1]["id"], "relation": "feeds"})
        return {"objective": objective, "nodes": nodes, "edges": edges}

    def resolve_conflicts(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_targets: dict[str, dict[str, Any]] = {}
        resolved = []
        for task in sorted(tasks, key=lambda item: item.get("priority", 5), reverse=True):
            target = task.get("target", task.get("id", "unknown"))
            if target in seen_targets:
                resolved.append({**task, "status": "deferred", "conflict_with": seen_targets[target].get("id")})
            else:
                seen_targets[target] = task
                resolved.append({**task, "status": "ready"})
        return resolved

    def prioritize(self, tasks: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        context = context or {}
        prioritized = []
        for task in tasks:
            strategy = self.reasoning.select(task.get("title", task.get("id", "")), context)
            score = task.get("priority", 5) + (1 - strategy["complexity"]) + (0.5 if task.get("urgent") else 0)
            prioritized.append({**task, "adaptive_score": round(score, 3), "reasoning_mode": strategy["mode"]})
        return sorted(prioritized, key=lambda item: item["adaptive_score"], reverse=True)

    def schedule(self, objective: str, tasks: list[dict[str, Any]], context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        graph = self.build_graph(objective)
        resolved = self.resolve_conflicts(tasks)
        prioritized = self.prioritize(resolved, context)
        resource_decision = self.resources.optimize({"tasks": len(tasks), "objective": objective})
        schedule = {
            "concurrency": resource_decision["concurrency"],
            "tasks": prioritized,
            "resource_decision": resource_decision,
        }
        graph_id = f"orch-{uuid.uuid4().hex[:12]}"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO orchestration_graphs VALUES (?,?,?,?,?)",
                (
                    graph_id,
                    objective,
                    json.dumps(graph, ensure_ascii=False, default=str),
                    json.dumps(schedule, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )
        return {"id": graph_id, "graph": graph, "schedule": schedule}

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,objective,graph,schedule,created_at FROM orchestration_graphs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": row[0], "objective": row[1], "graph": json.loads(row[2] or "{}"), "schedule": json.loads(row[3] or "{}"), "created_at": row[4]}
            for row in rows
        ]
