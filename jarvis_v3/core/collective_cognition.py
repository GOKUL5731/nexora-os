"""Civilization-scale collective cognitive network."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.collective_memory_engine import CollectiveMemoryEngine
from core.distributed_cognition import DistributedCognitiveNetwork


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "collective_cognition.db"


class CollectiveCognitiveNetwork:
    """Federates multiple reasoning ecosystems into collaborative cognition clusters."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        memory: CollectiveMemoryEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("collective_cognition", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory = memory or CollectiveMemoryEngine(self.config)
        self.networks: dict[str, DistributedCognitiveNetwork] = {}
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS cognition_clusters (
                    name TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL,
                    capacity INTEGER DEFAULT 4,
                    metadata TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS federation_runs (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def register_cluster(self, name: str, purpose: str, capacity: int = 4, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.networks.setdefault(name, DistributedCognitiveNetwork(self.config))
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO cognition_clusters VALUES (?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                  purpose=excluded.purpose,
                  capacity=excluded.capacity,
                  metadata=excluded.metadata,
                  updated_at=excluded.updated_at
                """,
                (name, purpose, max(1, int(capacity)), json.dumps(metadata or {}, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        return self.cluster(name)

    def ensure_default_clusters(self) -> None:
        for name, purpose in {
            "coding": "code reasoning and test generation",
            "automation": "workflow and tool automation",
            "research": "knowledge discovery and experiment design",
            "optimization": "resource and architecture optimization",
        }.items():
            self.register_cluster(name, purpose)

    async def federated_reason(self, objective: str, clusters: list[str] | None = None) -> dict[str, Any]:
        self.ensure_default_clusters()
        clusters = clusters or [cluster["name"] for cluster in self.list_clusters()]
        tasks = [{"task": objective, "context": {"cluster": name}} for name in clusters]

        async def run(item: dict[str, Any]) -> dict[str, Any]:
            name = item["context"]["cluster"]
            network = self.networks.setdefault(name, DistributedCognitiveNetwork(self.config))
            return await network.run_pipeline(item["task"], item["context"])

        results = await asyncio.gather(*(run(item) for item in tasks))
        synthesis = self._synthesize_results(objective, clusters, results)
        run_id = f"federation-{uuid.uuid4().hex[:12]}"
        record = {"id": run_id, "objective": objective, "clusters": clusters, "results": results, "synthesis": synthesis, "created_at": datetime.now().isoformat()}
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO federation_runs VALUES (?,?,?,?)",
                (run_id, objective, json.dumps(record, ensure_ascii=False, default=str), record["created_at"]),
            )
        self.memory.remember("collective", "federation", objective, synthesis, 0.72, clusters)
        return record

    def distribute_workload(self, workloads: list[dict[str, Any]]) -> dict[str, Any]:
        self.ensure_default_clusters()
        clusters = self.list_clusters()
        assignments: dict[str, list[dict[str, Any]]] = {cluster["name"]: [] for cluster in clusters}
        for idx, workload in enumerate(workloads):
            cluster = clusters[idx % len(clusters)]["name"]
            assignments[cluster].append(workload)
        return {"assignments": assignments, "cluster_count": len(clusters)}

    def cluster(self, name: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT name,purpose,capacity,metadata,updated_at FROM cognition_clusters WHERE name=?", (name,)).fetchone()
        if not row:
            raise KeyError(f"Cognition cluster not found: {name}")
        return {"name": row[0], "purpose": row[1], "capacity": row[2], "metadata": json.loads(row[3] or "{}"), "updated_at": row[4]}

    def list_clusters(self) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT name,purpose,capacity,metadata,updated_at FROM cognition_clusters ORDER BY name").fetchall()
        return [{"name": row[0], "purpose": row[1], "capacity": row[2], "metadata": json.loads(row[3] or "{}"), "updated_at": row[4]} for row in rows]

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT result FROM federation_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0] or "{}") for row in rows]

    def snapshot(self) -> dict[str, Any]:
        return {"clusters": self.list_clusters(), "federation_runs": self.recent_runs()}

    @staticmethod
    def _synthesize_results(objective: str, clusters: list[str], results: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "objective": objective,
            "participating_clusters": clusters,
            "route_count": sum(len(item.get("route", [])) for item in results),
            "recommendation": "combine cluster outputs through governed simulation before deployment",
        }
