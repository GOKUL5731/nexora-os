from __future__ import annotations

import asyncio
import json
import re
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
            
            actual = condition_data.get("actual", condition_data.get("input", ""))
            if field:
                actual = condition_data.get(field, actual)
            if operator == "==":
                result = str(actual) == str(value)
            elif operator == "!=":
                result = str(actual) != str(value)
            elif operator == "contains":
                result = str(value) in str(actual)
            else:
                return {"ok": False, "error": f"Unsupported condition operator: {operator}"}
            return {"ok": True, "result": result}
        
        elif condition_type == "expression":
            return {"ok": False, "error": "Expression conditions are not enabled in recovery mode"}
        
        else:
            return {"ok": False, "error": f"Unknown condition type: {condition_type}"}

    def health(self) -> dict[str, Any]:
        return {"status": "online", "workflows": len(self.list())}

    async def save_graph(self, name: str, graph: dict[str, Any]) -> dict[str, Any]:
        return self.save({"name": name, "graph": graph})

    def graphs(self) -> list[dict[str, Any]]:
        return self.list()

    async def run(self, name: str) -> dict[str, Any]:
        spec = self.get(name)
        if not spec:
            return {"ok": False, "error": "Workflow not found"}
        run_id = uuid.uuid4().hex
        nodes = {node["id"]: node for node in spec["graph"].get("nodes", [])}
        incoming = {node_id: 0 for node_id in nodes}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for edge in spec["graph"].get("edges", []):
            src = edge.get("source") or edge.get("from")
            tgt = edge.get("target") or edge.get("to")
            if src in nodes and tgt in nodes:
                outgoing[src].append(tgt)
                incoming[tgt] += 1
        queue = [node_id for node_id, count in incoming.items() if count == 0]
        completed: list[str] = []
        context: dict[str, Any] = {}
        while queue:
            node_id = queue.pop(0)
            node = nodes[node_id]
            started = time.perf_counter()
            status, error = "completed", ""
            output: dict[str, Any] = {}
            
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
                        node_data = dict(node.get("data", {}))
                        node_data["_context"] = context
                        output = await self.node_executor(node["type"], node_data)
                        if not isinstance(output, dict):
                            output = {"ok": False, "error": f"Node executor returned unsupported result: {type(output).__name__}"}
                        if not output.get("ok", False):
                            raise RuntimeError(str(output.get("error") or output.get("message") or "Node execution failed"))
                    elif node["type"] == "wait":
                        await asyncio.sleep(min(float(node.get("data", {}).get("seconds", 0.1)), 5))
                        output = {"ok": True}
                    elif node["type"] == "notify":
                        message = str(
                            node.get("data", {}).get("message")
                            or context.get("last", {}).get("message")
                            or context.get("last", {}).get("text")
                            or "Workflow notification"
                        )
                        self.bus.publish("workflow.notification", {"name": name, "run_id": run_id, "message": message}, "workflow_engine")
                        output = {"ok": True, "message": message}
                    elif node["type"] in {"trigger", "scheduler"}:
                        output = {"ok": True, "message": f"{node['type']} control node acknowledged."}
                    else:
                        raise RuntimeError(f"No executor registered for node type: {node['type']}")
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
                        outputs = {key: value for key, value in context.items() if key != "last"}
                        return {"ok": False, "run_id": run_id, "error": error, "completed": completed, "outputs": outputs}
            self._trace(run_id, name, node_id, node["type"], status, started, error)
            context[node_id] = output
            context["last"] = output
            completed.append(node_id)
            for target in outgoing[node_id]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    queue.append(target)
        if len(completed) != len(nodes):
            outputs = {key: value for key, value in context.items() if key != "last"}
            return {"ok": False, "run_id": run_id, "error": "Workflow graph contains a cycle", "outputs": outputs}
        self._db.execute("UPDATE workflows SET last_status='completed' WHERE name=?", (name,))
        self._db.commit()
        outputs = {key: value for key, value in context.items() if key != "last"}
        result = {"ok": True, "run_id": run_id, "completed": completed, "outputs": outputs}
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
        """Generate a workflow graph from a natural language description.

        Attempts LLM-powered generation first, falls back to keyword templates.
        """
        # Attempt LLM-powered generation
        try:
            from ..staging.llm import OllamaClient
            llm = OllamaClient()
            if llm.ready():
                system = """You are a workflow designer. Given a description, produce a JSON workflow graph.
Respond ONLY with a JSON object matching this schema exactly:
{
  "name": "<snake_case_name>",
  "description": "<original description>",
  "nodes": [
    {"id": "<id>", "type": "<type>", "data": {}, "position": {"x": <int>, "y": 140}}
  ],
  "edges": [
    {"id": "<id>", "source": "<node_id>", "target": "<node_id>"}
  ]
}
Valid node types: trigger, scheduler, voice_input, llm, memory_save, browser, ocr, camera, file_save, agent_spawn, api_call, workflow_trigger, condition, loop, wait, notify.
Spacing: x starts at 90 and increases by 190 per node. No extra text outside JSON."""
                result = llm.chat([{"role": "user", "content": f"Description: {description}"}], system, json_format=True)
                raw = result.get("message", "")
                import re as _re
                json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    name = parsed.get("name") or "_".join(re.findall(r"[a-z0-9]+", description.lower())[:4]) or f"workflow_{int(time.time())}"
                    nodes = parsed.get("nodes", [])
                    edges = parsed.get("edges", [])
                    # Validate node types
                    nodes = [n for n in nodes if n.get("type") in self.NODE_TYPES]
                    if nodes:
                        return {
                            "spec": {
                                "name": name,
                                "description": description,
                                "graph": {"nodes": nodes, "edges": edges},
                            },
                            "generated": True,
                            "llm_powered": True,
                        }
        except Exception:
            pass

        # Keyword-template fallback
        words = description.lower()
        types = ["trigger"]
        mapping = [
            ("schedule", "scheduler"), ("voice", "voice_input"), ("remember", "memory_save"),
            ("memory", "memory_save"), ("ocr", "ocr"), ("camera", "camera"), ("browser", "browser"),
            ("agent", "agent_spawn"), ("notify", "notify"), ("wait", "wait"), ("api", "api_call"),
            ("llm", "llm"), ("file", "file_save"), ("condition", "condition"),
        ]
        types.extend(node_type for keyword, node_type in mapping if keyword in words)
        if len(types) == 1:
            types.extend(["llm", "notify"])
        nodes = [
            {"id": f"{node_type}_{index}", "type": node_type, "data": {}, "position": {"x": 90 + index * 190, "y": 140}}
            for index, node_type in enumerate(types)
        ]
        edges = [
            {"id": f"e{index}", "source": nodes[index]["id"], "target": nodes[index + 1]["id"]}
            for index in range(len(nodes) - 1)
        ]
        name = "_".join(re.findall(r"[a-z0-9]+", words)[:4]) or f"workflow_{int(time.time())}"
        return {
            "spec": {"name": name, "description": description, "graph": {"nodes": nodes, "edges": edges}},
            "generated": True,
            "llm_powered": False,
        }

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
