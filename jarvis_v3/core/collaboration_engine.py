"""Multi-agent collaboration, messaging, shared memory, and queues."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "collaboration.db"

AgentHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class CollaborativeAgent:
    name: str
    role: str
    capabilities: tuple[str, ...]
    handler: AgentHandler | None = None


class CollaborationEngine:
    """Operational multi-agent bus with real queues and execution."""

    REQUIRED_AGENTS = {
        "commander": ("Commander Agent", ("coordinate", "delegate", "review")),
        "planner": ("Planner Agent", ("plan", "dependency", "priority")),
        "researcher": ("Research Agent", ("research", "requirements", "summarize")),
        "coder": ("Coding Agent", ("code", "implement", "debug")),
        "tester": ("Testing Agent", ("test", "validate", "benchmark")),
        "vision": ("Vision Agent", ("vision", "image", "screen")),
        "optimizer": ("Optimization Agent", ("optimize", "performance", "routing")),
        "deployer": ("Deployment Agent", ("deploy", "package", "rollback")),
    }

    def __init__(
        self,
        config: dict | None = None,
        agent_manager: Any = None,
        db_path: str | Path | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("collaboration", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.agent_manager = agent_manager
        self._agents: dict[str, CollaborativeAgent] = {}
        self._queue_lock = threading.RLock()
        self._init_db()
        self.register_required_agents()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    name TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    capabilities TEXT NOT NULL,
                    status TEXT DEFAULT 'idle',
                    load INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    read INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shared_memory (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_by TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_queue (
                    id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    task TEXT NOT NULL,
                    context TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'queued',
                    result TEXT DEFAULT '{}',
                    error TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS negotiations (
                    id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    bids TEXT NOT NULL,
                    selected_agent TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_queue_agent ON task_queue(agent,status);
                CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent,read);
                """
            )

    def register_required_agents(self) -> None:
        for name, (role, capabilities) in self.REQUIRED_AGENTS.items():
            self.register_agent(name, role, capabilities)

    def register_agent(
        self,
        name: str,
        role: str,
        capabilities: tuple[str, ...] | list[str],
        handler: AgentHandler | None = None,
    ) -> None:
        self._agents[name] = CollaborativeAgent(name, role, tuple(capabilities), handler)
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO agents(name,role,capabilities,status,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                  role=excluded.role,
                  capabilities=excluded.capabilities,
                  updated_at=excluded.updated_at
                """,
                (name, role, json.dumps(list(capabilities)), "idle", datetime.now().isoformat()),
            )

    def list_agents(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT name,role,capabilities,status,load,updated_at FROM agents ORDER BY name"
            ).fetchall()
        return [
            {
                "name": r[0],
                "role": r[1],
                "capabilities": json.loads(r[2] or "[]"),
                "status": r[3],
                "load": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        message_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
                (
                    message_id,
                    from_agent,
                    to_agent,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    0,
                    datetime.now().isoformat(),
                ),
            )
        return message_id

    def receive_messages(self, agent: str, mark_read: bool = True) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,from_agent,content,metadata,created_at FROM messages "
                "WHERE to_agent=? AND read=0 ORDER BY created_at",
                (agent,),
            ).fetchall()
            if mark_read and rows:
                ids = [row[0] for row in rows]
                db.executemany("UPDATE messages SET read=1 WHERE id=?", [(i,) for i in ids])
        return [
            {
                "id": row[0],
                "from": row[1],
                "content": row[2],
                "metadata": json.loads(row[3] or "{}"),
                "created_at": row[4],
            }
            for row in rows
        ]

    def set_shared_memory(self, key: str, value: Any, updated_by: str = "") -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO shared_memory VALUES (?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                  value=excluded.value,
                  updated_by=excluded.updated_by,
                  updated_at=excluded.updated_at
                """,
                (
                    key,
                    json.dumps(value, ensure_ascii=False, default=str),
                    updated_by,
                    datetime.now().isoformat(),
                ),
            )

    def get_shared_memory(self, key: str, default: Any = None) -> Any:
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT value FROM shared_memory WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def negotiate_assignment(self, task: str, preferred: str | None = None) -> dict[str, Any]:
        task_words = Counter(w.strip(".,:;!?").lower() for w in task.split())
        agents = self.list_agents()
        bids = []
        for agent in agents:
            caps = [c.lower() for c in agent["capabilities"]]
            capability_score = sum(2 for cap in caps if cap in task_words or cap in task.lower())
            role_score = 1 if agent["name"] in task.lower() or agent["role"].lower() in task.lower() else 0
            load_penalty = min(agent["load"], 5) * 0.2
            preferred_bonus = 2 if preferred and agent["name"] == preferred else 0
            score = capability_score + role_score + preferred_bonus - load_penalty
            bids.append({"agent": agent["name"], "score": round(score, 3), "load": agent["load"]})
        bids.sort(key=lambda b: b["score"], reverse=True)
        selected = bids[0]["agent"] if bids else "planner"
        negotiation_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO negotiations VALUES (?,?,?,?,?)",
                (negotiation_id, task, json.dumps(bids), selected, datetime.now().isoformat()),
            )
        return {"id": negotiation_id, "selected_agent": selected, "bids": bids}

    def submit_task(self, task: str, agent: str | None = None, context: dict[str, Any] | None = None) -> str:
        selected = agent or self.negotiate_assignment(task)["selected_agent"]
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with self._queue_lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO task_queue VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    selected,
                    task,
                    json.dumps(context or {}, ensure_ascii=False, default=str),
                    "queued",
                    "{}",
                    "",
                    now,
                    now,
                ),
            )
            db.execute(
                "UPDATE agents SET load=load+1, updated_at=? WHERE name=?",
                (now, selected),
            )
        return task_id

    async def run_task(
        self,
        agent: str,
        task: str,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        if not task_id:
            task_id = self.submit_task(task, agent, context)
        self._update_task(task_id, "running")
        self._set_agent_status(agent, "running")
        try:
            result = await self._execute_agent(agent, task, context or {})
            self._complete_task(task_id, result)
            self.send_message(agent, "commander", f"Completed task {task_id}", {"result": result})
            return {"task_id": task_id, "agent": agent, "status": "completed", "result": result}
        except Exception as exc:
            error = str(exc)
            self._fail_task(task_id, error)
            self.send_message(agent, "commander", f"Failed task {task_id}: {error}")
            return {"task_id": task_id, "agent": agent, "status": "failed", "error": error}
        finally:
            self._set_agent_status(agent, "idle")

    async def run_queued(self, concurrency: int = 4, limit: int | None = None) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as db:
            sql = "SELECT id,agent,task,context FROM task_queue WHERE status='queued' ORDER BY created_at"
            if limit:
                sql += f" LIMIT {int(limit)}"
            rows = db.execute(sql).fetchall()
        sem = asyncio.Semaphore(max(1, concurrency))

        async def worker(row: tuple[str, str, str, str]) -> dict[str, Any]:
            async with sem:
                return await self.run_task(row[1], row[2], json.loads(row[3] or "{}"), row[0])

        return await asyncio.gather(*(worker(row) for row in rows))

    async def _execute_agent(self, agent: str, task: str, context: dict[str, Any]) -> dict[str, Any]:
        collab_agent = self._agents.get(agent)
        if collab_agent and collab_agent.handler:
            return await collab_agent.handler(task, context)
        if self.agent_manager and hasattr(self.agent_manager, "run_agent"):
            return await self.agent_manager.run_agent(agent, task, context)
        messages = self.receive_messages(agent)
        prior = self.get_shared_memory(f"agent:{agent}:last_result")
        result = {
            "agent": agent,
            "role": collab_agent.role if collab_agent else agent,
            "task": task,
            "used_messages": len(messages),
            "prior_available": prior is not None,
            "output": self._deterministic_agent_output(agent, task, context),
        }
        self.set_shared_memory(f"agent:{agent}:last_result", result, updated_by=agent)
        return result

    def _deterministic_agent_output(self, agent: str, task: str, context: dict[str, Any]) -> dict[str, Any]:
        if agent == "researcher":
            return {"requirements": self._keywords(task), "summary": f"Research scope identified for {task}"}
        if agent == "planner":
            return {"steps": [s for s in context.get("steps", [])] or [task]}
        if agent == "coder":
            return {"implementation_notes": f"Implement {task}", "language": context.get("language", "python")}
        if agent == "tester":
            return {"validated": True, "checks": context.get("checks", ["unit", "integration"])}
        if agent == "optimizer":
            return {"optimizations": ["cache repeated state", "limit concurrency by resource pressure"]}
        if agent == "deployer":
            return {"deployable": True, "target": context.get("target", "sandbox")}
        if agent == "vision":
            return {"vision_task": task, "mode": context.get("mode", "analysis")}
        return {"coordinated": True, "next": context.get("next")}

    def _update_task(self, task_id: str, status: str) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE task_queue SET status=?, updated_at=? WHERE id=?",
                (status, datetime.now().isoformat(), task_id),
            )

    def _complete_task(self, task_id: str, result: dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT agent FROM task_queue WHERE id=?", (task_id,)).fetchone()
            db.execute(
                "UPDATE task_queue SET status='completed', result=?, updated_at=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False, default=str), now, task_id),
            )
            if row:
                db.execute("UPDATE agents SET load=MAX(load-1,0), updated_at=? WHERE name=?", (now, row[0]))

    def _fail_task(self, task_id: str, error: str) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT agent FROM task_queue WHERE id=?", (task_id,)).fetchone()
            db.execute(
                "UPDATE task_queue SET status='failed', error=?, updated_at=? WHERE id=?",
                (error, now, task_id),
            )
            if row:
                db.execute("UPDATE agents SET load=MAX(load-1,0), updated_at=? WHERE name=?", (now, row[0]))

    def _set_agent_status(self, agent: str, status: str) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE agents SET status=?, updated_at=? WHERE name=?",
                (status, datetime.now().isoformat(), agent),
            )

    def queue_snapshot(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,agent,task,context,status,result,error,created_at,updated_at "
                "FROM task_queue ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "id": row[0],
                "agent": row[1],
                "task": row[2],
                "context": json.loads(row[3] or "{}"),
                "status": row[4],
                "result": json.loads(row[5] or "{}"),
                "error": row[6],
                "created_at": row[7],
                "updated_at": row[8],
            }
            for row in rows
        ]

    @staticmethod
    def _keywords(text: str) -> list[str]:
        return sorted({w.strip(".,:;!?").lower() for w in text.split() if len(w) > 3})[:12]
