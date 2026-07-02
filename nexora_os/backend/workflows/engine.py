from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..core.event_bus import EventBus


class WorkflowEngine:
    NODE_TYPES = {
        "trigger", "scheduler", "voice_input", "llm", "memory_save", "browser", "ocr", "camera",
        "file_save", "agent_spawn", "api_call", "workflow_trigger", "condition", "loop", "wait", "notify",
    }

    def __init__(self, database: Path, bus: EventBus) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.bus = bus
        self._db = sqlite3.connect(database, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS workflows(
            name TEXT PRIMARY KEY, description TEXT NOT NULL, graph TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1, schedule_seconds INTEGER NOT NULL DEFAULT 0,
            retries INTEGER NOT NULL DEFAULT 2, last_status TEXT NOT NULL DEFAULT 'never',
            updated_at REAL NOT NULL)"""
        )
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS traces(
            id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, workflow TEXT NOT NULL,
            node_id TEXT NOT NULL, node_type TEXT NOT NULL, status TEXT NOT NULL,
            duration_ms REAL NOT NULL, error TEXT NOT NULL, created_at REAL NOT NULL)"""
        )
        self._db.commit()
        self._scheduler: asyncio.Task | None = None
        self._last_scheduled: dict[str, float] = {}
        self.node_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None

    def start(self) -> None:
        if not self._scheduler or self._scheduler.done():
            self._scheduler = asyncio.create_task(self._schedule_loop(), name="workflow-scheduler")

    async def stop(self) -> None:
        if self._scheduler and not self._scheduler.done():
            self._scheduler.cancel()
            try:
                await self._scheduler
            except asyncio.CancelledError:
                pass

    def save(self, spec: dict[str, Any]) -> dict[str, Any]:
        name = spec["name"].strip()
        if not name:
            raise ValueError("Workflow name is required")
        graph = spec.get("graph") or {"nodes": [], "edges": []}
        unknown = {node.get("type") for node in graph.get("nodes", [])} - self.NODE_TYPES
        if unknown:
            raise ValueError(f"Unsupported node types: {sorted(unknown)}")
        self._db.execute(
            """INSERT INTO workflows(name,description,graph,enabled,schedule_seconds,retries,updated_at)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET description=excluded.description,
            graph=excluded.graph, enabled=excluded.enabled, schedule_seconds=excluded.schedule_seconds,
            retries=excluded.retries, updated_at=excluded.updated_at""",
            (
                name,
                spec.get("description", ""),
                json.dumps(graph),
                int(spec.get("enabled", True)),
                int(spec.get("schedule_seconds", 0)),
                int(spec.get("retries", 2)),
                time.time(),
            ),
        )
        self._db.commit()
        self.bus.publish("workflow.saved", {"name": name}, "workflow_engine")
        self.sync()
        return {"ok": True, "name": name}

    def get(self, name: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM workflows WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        return {
            "name": row["name"], "description": row["description"], "graph": json.loads(row["graph"]),
            "enabled": bool(row["enabled"]), "schedule_seconds": row["schedule_seconds"], "retries": row["retries"],
        }

    def list(self) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT * FROM workflows ORDER BY updated_at DESC").fetchall()
        return [
            {
                "name": row["name"], "description": row["description"], "enabled": bool(row["enabled"]),
                "last_status": row["last_status"], "step_count": len(json.loads(row["graph"]).get("nodes", [])),
                "node_count": len(json.loads(row["graph"]).get("nodes", [])),
                "edge_count": len(json.loads(row["graph"]).get("edges", [])),
            }
            for row in rows
        ]

    async def _execute_condition(self, node: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        """Execute a condition node for if-then logic"""
        condition_data = node.get("data", {})
        condition_type = condition_data.get("type", "simple")
        
        if condition_type == "simple":
            # Simple condition: check if a value equals expected
            field = condition_data.get("field", "")
            operator = condition_data.get("operator", "==")
            value = condition_data.get("value", "")
            
            # For now, return true for demonstration
            # In production, this would check against workflow context/state
            return {"ok": True, "result": True}
        
        elif condition_type == "expression":
            # Expression-based condition
            expression = condition_data.get("expression", "")
            # For now, return true for demonstration
            return {"ok": True, "result": True}
        
        else:
            return {"ok": False, "error": f"Unknown condition type: {condition_type}"}

    async def run(self, name: str) -> dict[str, Any]:
        spec = self.get(name)
        if not spec:
            return {"ok": False, "error": "Workflow not found"}
        run_id = uuid.uuid4().hex
        nodes = {node["id"]: node for node in spec["graph"].get("nodes", [])}
        incoming = {node_id: 0 for node_id in nodes}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for edge in spec["graph"].get("edges", []):
            if edge["source"] in nodes and edge["target"] in nodes:
                outgoing[edge["source"]].append(edge["target"])
                incoming[edge["target"]] += 1
        queue = [node_id for node_id, count in incoming.items() if count == 0]
        completed: list[str] = []
        while queue:
            node_id = queue.pop(0)
            node = nodes[node_id]
            started = time.perf_counter()
            status, error = "completed", ""
            
            # Handle condition nodes
            if node["type"] == "condition":
                condition_result = await self._execute_condition(node, spec)
                if not condition_result.get("ok"):
                    status = "failed"
                    error = condition_result.get("error", "Condition evaluation failed")
                elif not condition_result.get("result", False):
                    status = "skipped"
                    error = "Condition evaluated to false"
                else:
                    status = "completed"
                self._trace(run_id, name, node_id, node["type"], status, started, error)
                
                # Only add outgoing edges if condition was true
                if status == "completed":
                    completed.append(node_id)
                    for target in outgoing[node_id]:
                        incoming[target] -= 1
                        if incoming[target] == 0:
                            queue.append(target)
                else:
                    completed.append(node_id)
                continue
            
            # Handle other node types
            for attempt in range(spec["retries"] + 1):
                try:
                    if self.node_executor:
                        await self.node_executor(node["type"], node.get("data", {}))
                    elif node["type"] == "wait":
                        await asyncio.sleep(min(float(node.get("data", {}).get("seconds", 0.1)), 5))
                    break
                except Exception as exc:
                    error = str(exc)
                    status = "failed"
                    if attempt < spec["retries"]:
                        await asyncio.sleep(min(2 ** attempt, 4))
                    else:
                        self._trace(run_id, name, node_id, node["type"], status, started, error)
                        self._db.execute("UPDATE workflows SET last_status='failed' WHERE name=?", (name,))
                        self._db.commit()
                        self.bus.publish("workflow.failed", {"name": name, "run_id": run_id, "error": error}, "workflow_engine")
                        self.sync()
                        return {"ok": False, "run_id": run_id, "error": error, "completed": completed}
            self._trace(run_id, name, node_id, node["type"], status, started, error)
            completed.append(node_id)
            for target in outgoing[node_id]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    queue.append(target)
        if len(completed) != len(nodes):
            return {"ok": False, "run_id": run_id, "error": "Workflow graph contains a cycle"}
        self._db.execute("UPDATE workflows SET last_status='completed' WHERE name=?", (name,))
        self._db.commit()
        result = {"ok": True, "run_id": run_id, "completed": completed}
        self.bus.publish("workflow.completed", {"name": name, **result}, "workflow_engine")
        self.sync()
        return result

    def trace(self, name: str, run_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM traces WHERE workflow=?"
        params: list[Any] = [name]
        if run_id:
            sql += " AND run_id=?"
            params.append(run_id)
        sql += " ORDER BY id DESC LIMIT 100"
        return [dict(row) for row in reversed(self._db.execute(sql, params).fetchall())]

    def generate(self, description: str) -> dict[str, Any]:
        words = description.lower()
        types = ["trigger"]
        mapping = [
            ("schedule", "scheduler"), ("voice", "voice_input"), ("remember", "memory_save"),
            ("memory", "memory_save"), ("ocr", "ocr"), ("camera", "camera"), ("browser", "browser"),
            ("agent", "agent_spawn"), ("notify", "notify"), ("wait", "wait"), ("api", "api_call"),
        ]
        types.extend(node_type for keyword, node_type in mapping if keyword in words)
        if len(types) == 1:
            types.extend(["agent_spawn", "notify"])
        nodes = [
            {"id": f"{node_type}_{index}", "type": node_type, "data": {}, "position": {"x": 90 + index * 190, "y": 140}}
            for index, node_type in enumerate(types)
        ]
        edges = [
            {"id": f"e{index}", "source": nodes[index]["id"], "target": nodes[index + 1]["id"]}
            for index in range(len(nodes) - 1)
        ]
        name = "_".join(re.findall(r"[a-z0-9]+", words)[:4]) or f"workflow_{int(time.time())}"
        return {"spec": {"name": name, "description": description, "graph": {"nodes": nodes, "edges": edges}}, "generated": True}

    def _trace(self, run_id: str, name: str, node_id: str, node_type: str, status: str, started: float, error: str) -> None:
        self._db.execute(
            "INSERT INTO traces(run_id,workflow,node_id,node_type,status,duration_ms,error,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (run_id, name, node_id, node_type, status, (time.perf_counter() - started) * 1000, error, time.time()),
        )
        self._db.commit()

    async def _schedule_loop(self) -> None:
        while True:
            now = time.time()
            rows = self._db.execute("SELECT name,schedule_seconds FROM workflows WHERE enabled=1 AND schedule_seconds>0").fetchall()
            for row in rows:
                last = self._last_scheduled.get(row["name"], 0)
                if now - last >= row["schedule_seconds"]:
                    self._last_scheduled[row["name"]] = now
                    asyncio.create_task(self.run(row["name"]))
            await asyncio.sleep(1)

    def sync(self) -> None:
        self.bus.set_state("workflows", self.list(), "workflow_engine")


import re
