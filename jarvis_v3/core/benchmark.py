"""
JARVIS Benchmark Engine
Measures response latency, success rates, model speed, memory efficiency.
Runs as a background loop and produces JSON reports.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.benchmark")


class BenchmarkEngine:
    def __init__(self, config: dict, db_dir: str = "database"):
        self.config  = config
        self.db_path = Path(db_dir) / "benchmarks.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._timers: dict[str, float] = {}

    def _init_db(self):
        with sqlite3.connect(self.db_path) as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS perf_records (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          TEXT NOT NULL,
                    operation   TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    success     INTEGER DEFAULT 1,
                    model       TEXT DEFAULT '',
                    tokens      INTEGER DEFAULT 0,
                    extra       TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS model_stats (
                    model       TEXT PRIMARY KEY,
                    total_calls INTEGER DEFAULT 0,
                    total_ms    REAL DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    successes   INTEGER DEFAULT 0,
                    failures    INTEGER DEFAULT 0,
                    updated_at  TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_perf_op ON perf_records(operation);
                CREATE INDEX IF NOT EXISTS idx_perf_ts ON perf_records(ts);
            """)

    # ── Timer context manager pattern ────────────────────────────────────────
    def start(self, label: str):
        """Start a named timer."""
        self._timers[label] = time.perf_counter()

    def stop(self, label: str, operation: str = None, success: bool = True,
             model: str = "", tokens: int = 0, extra: dict = None) -> float:
        """Stop timer, record result, return elapsed ms."""
        start = self._timers.pop(label, None)
        if start is None:
            return 0.0
        elapsed = (time.perf_counter() - start) * 1000  # ms
        self.record(operation or label, elapsed, success, model, tokens, extra or {})
        return elapsed

    # ── Direct recording ─────────────────────────────────────────────────────
    def record(self, operation: str, duration_ms: float, success: bool = True,
               model: str = "", tokens: int = 0, extra: dict = None):
        ts = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT INTO perf_records(ts,operation,duration_ms,success,model,tokens,extra)"
                " VALUES(?,?,?,?,?,?,?)",
                (ts, operation, duration_ms, int(success), model, tokens,
                 json.dumps(extra or {}))
            )
            # Update model stats
            if model:
                c.execute("""
                    INSERT INTO model_stats(model,total_calls,total_ms,total_tokens,successes,failures,updated_at)
                    VALUES(?,1,?,?,?,?,?)
                    ON CONFLICT(model) DO UPDATE SET
                      total_calls=total_calls+1,
                      total_ms=total_ms+?,
                      total_tokens=total_tokens+?,
                      successes=successes+?,
                      failures=failures+?,
                      updated_at=?
                """, (
                    model, duration_ms, tokens, int(success), int(not success), ts,
                    duration_ms, tokens, int(success), int(not success), ts
                ))

    # ── Statistics ───────────────────────────────────────────────────────────
    def get_stats(self, operation: str = None, hours: int = 24) -> dict:
        """Get aggregated stats for a time window."""
        since = datetime.now().isoformat()[:10]  # simple day filter
        with sqlite3.connect(self.db_path) as c:
            if operation:
                rows = c.execute(
                    "SELECT duration_ms, success FROM perf_records "
                    "WHERE operation=? AND ts>=? ORDER BY ts DESC LIMIT 100",
                    (operation, since)
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT duration_ms, success FROM perf_records "
                    "WHERE ts>=? ORDER BY ts DESC LIMIT 200",
                    (since,)
                ).fetchall()

        if not rows:
            return {"count": 0}

        durations = [r[0] for r in rows]
        successes = sum(1 for r in rows if r[1])
        return {
            "count":       len(rows),
            "avg_ms":      round(sum(durations) / len(durations), 1),
            "min_ms":      round(min(durations), 1),
            "max_ms":      round(max(durations), 1),
            "p95_ms":      round(sorted(durations)[int(len(durations) * 0.95)], 1),
            "success_rate": round(successes / len(rows) * 100, 1),
        }

    def get_model_stats(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT model,total_calls,total_ms,total_tokens,successes,failures,updated_at "
                "FROM model_stats ORDER BY total_calls DESC"
            ).fetchall()
        results = []
        for r in rows:
            calls = r[1] or 1
            results.append({
                "model":        r[0],
                "total_calls":  r[1],
                "avg_ms":       round((r[2] or 0) / calls, 1),
                "total_tokens": r[3],
                "success_rate": round((r[4] or 0) / calls * 100, 1),
                "failures":     r[5],
                "last_used":    r[6],
            })
        return results

    def get_recent(self, limit: int = 20) -> list[dict]:
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT ts,operation,duration_ms,success,model FROM perf_records "
                "ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"ts": r[0], "op": r[1], "ms": round(r[2], 1),
             "ok": bool(r[3]), "model": r[4]}
            for r in rows
        ]

    def generate_report(self) -> dict:
        """Full benchmark report."""
        return {
            "generated_at": datetime.now().isoformat(),
            "overall":      self.get_stats(),
            "llm_calls":    self.get_stats("llm_complete"),
            "voice_stt":    self.get_stats("stt"),
            "voice_tts":    self.get_stats("tts"),
            "tool_exec":    self.get_stats("tool_execute"),
            "models":       self.get_model_stats(),
            "recent":       self.get_recent(10),
        }
