"""Distributed cognitive network with asynchronous cognition layers."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "distributed_cognition.db"

LayerHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class DistributedCognitiveNetwork:
    """Separates perception, planning, execution, optimization, and reflection layers."""

    DEFAULT_LAYERS = ["perception", "planning", "execution", "optimization", "reflection"]

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("distributed_cognition", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.handlers: dict[str, LayerHandler] = {}
        self.memory: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._init_db()
        for layer in self.DEFAULT_LAYERS:
            self.register_layer(layer, self._default_handler(layer))

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS layer_messages (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS distributed_runs (
                    id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def register_layer(self, layer: str, handler: LayerHandler) -> None:
        self.handlers[layer] = handler

    def send(self, source: str, target: str, payload: dict[str, Any]) -> str:
        message_id = f"msg-{uuid.uuid4().hex[:12]}"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO layer_messages VALUES (?,?,?,?,?,?)",
                (
                    message_id,
                    source,
                    target,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    "queued",
                    datetime.now().isoformat(),
                ),
            )
        return message_id

    async def run_pipeline(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        state = {"task": task, "context": context or {}, "shared_memory": self.memory}
        route = []
        for layer in self.DEFAULT_LAYERS:
            handler = self.handlers[layer]
            self.send(route[-1] if route else "system", layer, state)
            result = await handler(state)
            state.update(result)
            route.append(layer)
        run_id = f"dist-{uuid.uuid4().hex[:12]}"
        output = {"id": run_id, "task": task, "route": route, "state": state, "created_at": datetime.now().isoformat()}
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO distributed_runs VALUES (?,?,?,?)",
                (run_id, task, json.dumps(output, ensure_ascii=False, default=str), output["created_at"]),
            )
        return output

    async def run_parallel(self, tasks: list[dict[str, Any]], concurrency: int = 4) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(max(1, concurrency))

        async def worker(item: dict[str, Any]) -> dict[str, Any]:
            async with sem:
                return await self.run_pipeline(item["task"], item.get("context", {}))

        return await asyncio.gather(*(worker(item) for item in tasks))

    def shared_set(self, key: str, value: Any) -> None:
        self.memory[key] = value

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT result FROM distributed_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0] or "{}") for row in rows]

    def message_snapshot(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,source,target,payload,status,created_at FROM layer_messages ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": row[0], "source": row[1], "target": row[2], "payload": json.loads(row[3] or "{}"), "status": row[4], "created_at": row[5]}
            for row in rows
        ]

    @staticmethod
    def _default_handler(layer: str) -> LayerHandler:
        async def handler(state: dict[str, Any]) -> dict[str, Any]:
            await asyncio.sleep(0)
            task = state.get("task", "")
            if layer == "perception":
                return {"perception": {"tokens": task.split(), "context_keys": sorted(state.get("context", {}).keys())}}
            if layer == "planning":
                return {"planning": {"steps": ["analyze", "simulate", "execute", "reflect"], "complexity": min(1.0, len(task) / 300)}}
            if layer == "execution":
                return {"execution": {"mode": "simulated", "ready": True}}
            if layer == "optimization":
                return {"optimization": {"recommendations": ["cache shared state", "bound concurrency"]}}
            return {"reflection": {"lesson": "distributed cognition pipeline completed", "confidence": 0.75}}

        return handler
