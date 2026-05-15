"""Real-time cognitive observability infrastructure."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "observability.db"


class ObservabilityEngine:
    """Records metrics, traces, communication events, and latency samples."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("observability", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    labels TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS traces (
                    id TEXT PRIMARY KEY,
                    trace_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    duration_ms REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON metrics(name, created_at);
                """
            )

    def record_metric(self, name: str, value: float, labels: dict[str, Any] | None = None) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO metrics(name,value,labels,created_at) VALUES(?,?,?,?)",
                (name, float(value), json.dumps(labels or {}, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )

    def record_trace(
        self,
        trace_type: str,
        payload: dict[str, Any],
        duration_ms: float = 0,
    ) -> dict[str, Any]:
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        trace = {
            "id": trace_id,
            "type": trace_type,
            "payload": payload,
            "duration_ms": round(float(duration_ms), 3),
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO traces VALUES (?,?,?,?,?)",
                (trace_id, trace_type, json.dumps(payload, ensure_ascii=False, default=str), trace["duration_ms"], trace["created_at"]),
            )
        return trace

    def time_block(self, trace_type: str):
        engine = self

        class Timer:
            def __enter__(self):
                self.started = time.perf_counter()
                return self

            def __exit__(self, exc_type, exc, _tb):
                duration = (time.perf_counter() - self.started) * 1000
                engine.record_trace(trace_type, {"error": str(exc) if exc else ""}, duration)

        return Timer()

    def ingest_autonomy_snapshot(self, snapshot: dict[str, Any]) -> None:
        resources = snapshot.get("resources", {})
        self.record_metric("resource.pressure", resources.get("pressure_score", 0.0))
        self.record_metric("resource.cpu_percent", resources.get("cpu_percent", 0.0))
        self.record_metric("resource.memory_percent", resources.get("memory_percent", 0.0))
        loop = snapshot.get("loop", {}).get("last_cycle") or {}
        self.record_metric("cognition.cycle_duration_ms", loop.get("duration_ms", 0.0))
        self.record_metric("goals.total", snapshot.get("goals", {}).get("total", 0))
        self.record_trace("autonomy_snapshot", {"keys": sorted(snapshot.keys())}, loop.get("duration_ms", 0.0))

    def dashboard(self, limit: int = 100) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            metric_rows = db.execute(
                "SELECT name,value,labels,created_at FROM metrics ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            trace_rows = db.execute(
                "SELECT id,trace_type,payload,duration_ms,created_at FROM traces ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        latest_by_metric: dict[str, dict[str, Any]] = {}
        for row in metric_rows:
            latest_by_metric.setdefault(
                row[0],
                {"name": row[0], "value": row[1], "labels": json.loads(row[2] or "{}"), "created_at": row[3]},
            )
        return {
            "latest_metrics": latest_by_metric,
            "metrics": [
                {"name": row[0], "value": row[1], "labels": json.loads(row[2] or "{}"), "created_at": row[3]}
                for row in metric_rows
            ],
            "traces": [
                {"id": row[0], "type": row[1], "payload": json.loads(row[2] or "{}"), "duration_ms": row[3], "created_at": row[4]}
                for row in trace_rows
            ],
        }
