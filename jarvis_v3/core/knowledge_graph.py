"""Real-time knowledge graph for tasks, workflows, plugins, and agents."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "knowledge_graph.db"


class KnowledgeGraph:
    """Small persistent graph store with typed nodes and edges."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("knowledge_graph", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    data TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    data TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    UNIQUE(source,target,relation)
                );
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
                """
            )

    def upsert_node(self, node_id: str, node_type: str, label: str, data: dict[str, Any] | None = None) -> str:
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO nodes VALUES (?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  type=excluded.type,
                  label=excluded.label,
                  data=excluded.data,
                  updated_at=excluded.updated_at
                """,
                (
                    node_id,
                    node_type,
                    label,
                    json.dumps(data or {}, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )
        return node_id

    def connect(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        data: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO edges(source,target,relation,weight,data,updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(source,target,relation) DO UPDATE SET
                  weight=excluded.weight,
                  data=excluded.data,
                  updated_at=excluded.updated_at
                """,
                (
                    source,
                    target,
                    relation,
                    float(weight),
                    json.dumps(data or {}, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )

    def neighbors(self, node_id: str, relation: str | None = None, direction: str = "out") -> list[dict[str, Any]]:
        edge_column, other_column = ("source", "target") if direction == "out" else ("target", "source")
        sql = (
            f"SELECT e.relation,e.weight,n.id,n.type,n.label,n.data "
            f"FROM edges e JOIN nodes n ON n.id=e.{other_column} WHERE e.{edge_column}=?"
        )
        params: list[Any] = [node_id]
        if relation:
            sql += " AND e.relation=?"
            params.append(relation)
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(sql, params).fetchall()
        return [
            {
                "relation": row[0],
                "weight": row[1],
                "id": row[2],
                "type": row[3],
                "label": row[4],
                "data": json.loads(row[5] or "{}"),
            }
            for row in rows
        ]

    def ingest_plan(self, plan: dict[str, Any]) -> None:
        plan_id = plan["id"]
        self.upsert_node(plan_id, "plan", plan.get("goal", plan_id), plan)
        for task in plan.get("tasks", []):
            task_id = task["id"]
            self.upsert_node(task_id, "task", task["title"], task)
            self.connect(plan_id, task_id, "contains")
            agent = task.get("agent")
            if agent:
                agent_id = f"agent:{agent}"
                self.upsert_node(agent_id, "agent", agent, {"role": task.get("role", "")})
                self.connect(task_id, agent_id, "assigned_to")
            for dep in task.get("dependencies", []):
                self.connect(dep, task_id, "precedes")

    def ingest_workflow(self, spec: dict[str, Any]) -> None:
        workflow_id = f"workflow:{spec.get('name', 'unnamed')}"
        self.upsert_node(workflow_id, "workflow", spec.get("name", "unnamed"), spec)
        previous = None
        for idx, step in enumerate(spec.get("steps", []), start=1):
            step_id = f"{workflow_id}:step:{idx}"
            self.upsert_node(step_id, "workflow_step", step.get("action", "step"), step)
            self.connect(workflow_id, step_id, "contains")
            if previous:
                self.connect(previous, step_id, "precedes")
            previous = step_id

    def snapshot(self, limit: int = 200) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            nodes = db.execute(
                "SELECT id,type,label,data FROM nodes ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            edges = db.execute(
                "SELECT source,target,relation,weight,data FROM edges ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return {
            "nodes": [
                {"id": n[0], "type": n[1], "label": n[2], "data": json.loads(n[3] or "{}")}
                for n in nodes
            ],
            "edges": [
                {
                    "source": e[0],
                    "target": e[1],
                    "relation": e[2],
                    "weight": e[3],
                    "data": json.loads(e[4] or "{}"),
                }
                for e in edges
            ],
        }
