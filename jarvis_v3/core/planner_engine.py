"""Autonomous hierarchical planning engine with dependency tracking."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "planning.db"


@dataclass
class PlanTask:
    id: str
    title: str
    agent: str
    dependencies: list[str] = field(default_factory=list)
    priority: int = 5
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    attempts: int = 0
    max_retries: int = 2
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class PlanningEngine:
    """Builds and executes dependency-aware plans."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("planning", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    context TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'created',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    dependencies TEXT DEFAULT '[]',
                    priority INTEGER DEFAULT 5,
                    context TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'pending',
                    attempts INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 2,
                    result TEXT DEFAULT '{}',
                    error TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_plan_status ON tasks(plan_id,status);
                """
            )

    def create_plan(self, goal: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        plan_id = f"plan-{uuid.uuid4().hex[:10]}"
        tasks = self._decompose(goal, context or {})
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO plans VALUES (?,?,?,?,?,?)",
                (plan_id, goal, json.dumps(context or {}, default=str), "created", now, now),
            )
            for idx, task in enumerate(tasks):
                task.id = f"{plan_id}:t{idx + 1}"
            old_to_new = {f"t{idx + 1}": task.id for idx, task in enumerate(tasks)}
            for task in tasks:
                task.dependencies = [old_to_new.get(dep, dep) for dep in task.dependencies]
                db.execute(
                    "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        task.id,
                        plan_id,
                        task.title,
                        task.agent,
                        json.dumps(task.dependencies),
                        task.priority,
                        json.dumps(task.context, default=str),
                        task.status,
                        task.attempts,
                        task.max_retries,
                        json.dumps(task.result, default=str),
                        task.error,
                        now,
                    ),
                )
        return self.get_plan(plan_id)

    def _decompose(self, goal: str, context: dict[str, Any]) -> list[PlanTask]:
        lower = goal.lower()
        if "plugin" in lower:
            template = [
                ("Research plugin requirements", "researcher", [], 9),
                ("Create plugin architecture", "planner", ["t1"], 8),
                ("Generate plugin implementation", "coder", ["t2"], 8),
                ("Run plugin tests", "tester", ["t3"], 9),
                ("Benchmark plugin behavior", "tester", ["t4"], 7),
                ("Optimize plugin package", "optimizer", ["t5"], 6),
                ("Deploy plugin artifact", "deployer", ["t6"], 5),
            ]
        elif any(word in lower for word in ["debug", "fix", "bug", "error"]):
            template = [
                ("Reproduce failure", "tester", [], 9),
                ("Analyze root cause", "researcher", ["t1"], 8),
                ("Implement fix", "coder", ["t2"], 8),
                ("Run regression tests", "tester", ["t3"], 9),
                ("Record prevention rule", "optimizer", ["t4"], 5),
            ]
        elif any(word in lower for word in ["workflow", "automation", "automate"]):
            template = [
                ("Observe repetitive task pattern", "researcher", [], 8),
                ("Design workflow graph", "planner", ["t1"], 8),
                ("Create executable workflow", "coder", ["t2"], 7),
                ("Validate workflow execution", "tester", ["t3"], 9),
                ("Optimize workflow bottlenecks", "optimizer", ["t4"], 6),
            ]
        else:
            template = [
                ("Clarify objective and constraints", "planner", [], 8),
                ("Research required context", "researcher", ["t1"], 7),
                ("Execute primary work", "coder", ["t2"], 7),
                ("Validate output", "tester", ["t3"], 8),
                ("Summarize and prepare next action", "commander", ["t4"], 5),
            ]
        return [
            PlanTask(
                id=f"t{idx + 1}",
                title=f"{title}: {goal}",
                agent=agent,
                dependencies=list(deps),
                priority=priority,
                context={**context, "goal": goal, "step_index": idx + 1},
            )
            for idx, (title, agent, deps, priority) in enumerate(template)
        ]

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as db:
            plan = db.execute("SELECT id,goal,context,status,created_at,updated_at FROM plans WHERE id=?", (plan_id,)).fetchone()
            rows = db.execute(
                "SELECT id,title,agent,dependencies,priority,context,status,attempts,max_retries,result,error "
                "FROM tasks WHERE plan_id=? ORDER BY priority DESC,id",
                (plan_id,),
            ).fetchall()
        if not plan:
            raise KeyError(f"Plan not found: {plan_id}")
        return {
            "id": plan[0],
            "goal": plan[1],
            "context": json.loads(plan[2] or "{}"),
            "status": plan[3],
            "created_at": plan[4],
            "updated_at": plan[5],
            "tasks": [
                {
                    "id": row[0],
                    "title": row[1],
                    "agent": row[2],
                    "dependencies": json.loads(row[3] or "[]"),
                    "priority": row[4],
                    "context": json.loads(row[5] or "{}"),
                    "status": row[6],
                    "attempts": row[7],
                    "max_retries": row[8],
                    "result": json.loads(row[9] or "{}"),
                    "error": row[10],
                }
                for row in rows
            ],
        }

    def ready_tasks(self, plan_id: str) -> list[dict[str, Any]]:
        plan = self.get_plan(plan_id)
        status_by_id = {task["id"]: task["status"] for task in plan["tasks"]}
        ready = [
            task
            for task in plan["tasks"]
            if task["status"] == "pending"
            and all(status_by_id.get(dep) == "completed" for dep in task["dependencies"])
        ]
        return sorted(ready, key=lambda task: task["priority"], reverse=True)

    def update_task(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
        increment_attempts: bool = False,
    ) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                UPDATE tasks SET
                  status=?,
                  result=?,
                  error=?,
                  attempts=attempts + ?,
                  updated_at=?
                WHERE id=?
                """,
                (
                    status,
                    json.dumps(result or {}, ensure_ascii=False, default=str),
                    error,
                    1 if increment_attempts else 0,
                    datetime.now().isoformat(),
                    task_id,
                ),
            )
            row = db.execute("SELECT plan_id FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row:
                self._refresh_plan_status(db, row[0])

    def retry_failed_tasks(self, plan_id: str) -> list[str]:
        plan = self.get_plan(plan_id)
        retried = []
        with sqlite3.connect(self.db_path) as db:
            for task in plan["tasks"]:
                if task["status"] == "failed" and task["attempts"] < task["max_retries"]:
                    db.execute(
                        "UPDATE tasks SET status='pending', error='', updated_at=? WHERE id=?",
                        (datetime.now().isoformat(), task["id"]),
                    )
                    retried.append(task["id"])
            self._refresh_plan_status(db, plan_id)
        return retried

    async def execute_plan(self, plan_id: str, collaboration_engine: Any, concurrency: int = 3) -> dict[str, Any]:
        sem = asyncio.Semaphore(max(1, concurrency))
        executed: list[dict[str, Any]] = []
        while True:
            ready = self.ready_tasks(plan_id)
            if not ready:
                retried = self.retry_failed_tasks(plan_id)
                if retried:
                    continue
                break

            async def run_one(task: dict[str, Any]) -> dict[str, Any]:
                async with sem:
                    self.update_task(task["id"], "running", increment_attempts=True)
                    result = await collaboration_engine.run_task(
                        task["agent"], task["title"], task["context"]
                    )
                    if result.get("status") == "completed":
                        self.update_task(task["id"], "completed", result=result)
                    else:
                        self.update_task(task["id"], "failed", result=result, error=result.get("error", "task failed"))
                    return result

            executed.extend(await asyncio.gather(*(run_one(task) for task in ready)))
        final = self.get_plan(plan_id)
        final["executed"] = executed
        return final

    def dependency_graph(self, plan_id: str) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        return {
            "nodes": [{"id": task["id"], "label": task["title"], "status": task["status"]} for task in plan["tasks"]],
            "edges": [
                {"from": dep, "to": task["id"]}
                for task in plan["tasks"]
                for dep in task["dependencies"]
            ],
        }

    def _refresh_plan_status(self, db: sqlite3.Connection, plan_id: str) -> None:
        statuses = [row[0] for row in db.execute("SELECT status FROM tasks WHERE plan_id=?", (plan_id,)).fetchall()]
        if statuses and all(status == "completed" for status in statuses):
            plan_status = "completed"
        elif any(status == "running" for status in statuses):
            plan_status = "running"
        elif any(status == "failed" for status in statuses):
            plan_status = "blocked"
        else:
            plan_status = "created"
        db.execute(
            "UPDATE plans SET status=?, updated_at=? WHERE id=?",
            (plan_status, datetime.now().isoformat(), plan_id),
        )
