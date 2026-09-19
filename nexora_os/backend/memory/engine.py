from __future__ import annotations

import hashlib
import json
import math
import queue
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from ..core.event_bus import EventBus
from ..core.cache import Cache

TOKEN_RE = re.compile(r"[\w\u0B80-\u0BFF]+", re.UNICODE)


class ConnectionPool:
    """Simple connection pool for SQLite database"""
    
    def __init__(self, database: Path, pool_size: int = 5, check_same_thread: bool = False) -> None:
        self.database = database
        self.pool_size = pool_size
        self.check_same_thread = check_same_thread
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._initialized = False
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection"""
        conn = sqlite3.connect(self.database, check_same_thread=self.check_same_thread)
        conn.row_factory = sqlite3.Row
        return conn
    
    def initialize(self) -> None:
        """Initialize the connection pool"""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            # Create initial connections
            for _ in range(self.pool_size):
                conn = self._create_connection()
                self._pool.put(conn)
            
            self._initialized = True
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool"""
        if not self._initialized:
            self.initialize()
        
        try:
            conn = self._pool.get(timeout=5)
            return conn
        except queue.Empty:
            # Pool exhausted, create a temporary connection
            return self._create_connection()
    
    def return_connection(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool"""
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            # Pool full, close the connection
            conn.close()
    
    def close_all(self) -> None:
        """Close all connections in the pool"""
        with self._lock:
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except queue.Empty:
                    break
            self._initialized = False


class MemoryEngine:
    def __init__(self, database: Path, bus: EventBus, llm: Any | None = None, pool_size: int = 5, enable_cache: bool = True) -> None:
        self.database = database
        self.bus = bus
        self.llm = llm
        database.parent.mkdir(parents=True, exist_ok=True)
        
        # Use connection pool for better performance
        self._pool = ConnectionPool(database, pool_size=pool_size, check_same_thread=False)
        self._pool.initialize()
        
        # Initialize database schema using a connection from pool
        conn = self._pool.get_connection()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS memories(
                id INTEGER PRIMARY KEY, content TEXT NOT NULL, summary TEXT NOT NULL,
                memory_type TEXT NOT NULL, tags TEXT NOT NULL, embedding TEXT NOT NULL,
                created_at REAL NOT NULL, reflection TEXT NOT NULL DEFAULT '')"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS episodes(
                id INTEGER PRIMARY KEY, goal TEXT NOT NULL, action TEXT NOT NULL,
                result TEXT NOT NULL, outcome TEXT NOT NULL, evidence TEXT NOT NULL,
                confidence REAL NOT NULL, importance REAL NOT NULL, tags TEXT NOT NULL,
                created_at REAL NOT NULL)"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS procedures(
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                steps TEXT NOT NULL, validators TEXT NOT NULL, source_evidence TEXT NOT NULL,
                version INTEGER NOT NULL, confidence REAL NOT NULL, success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0, tags TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL)"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_outcome ON episodes(outcome)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_procedures_name ON procedures(name)")
            conn.commit()
        finally:
            self._pool.return_connection(conn)
        
        # Cache for search results
        self._cache = Cache(default_ttl=60, max_size=500) if enable_cache else None

    def _embed(self, text: str) -> list[float]:
        if self.llm and callable(getattr(self.llm, "embed", None)):
            vector = self.llm.embed(text)
            if vector:
                norm = math.sqrt(sum(value * value for value in vector)) or 1.0
                return [value / norm for value in vector]

        dimensions = 256
        vector = [0.0] * dimensions
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % dimensions
            vector[index] += -1.0 if digest[4] & 1 else 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        return sum(x * y for x, y in zip(a, b))

    @staticmethod
    def _chunks(text: str, size: int = 700, overlap: int = 100) -> list[str]:
        clean = " ".join(text.split())
        if not clean:
            return []
        return [clean[start:start + size] for start in range(0, len(clean), size - overlap)]

    def store(self, text: str, memory_type: str = "semantic", tags: list[str] | None = None) -> dict[str, Any]:
        ids: list[int] = []
        conn = self._pool.get_connection()
        try:
            for chunk in self._chunks(text):
                summary = chunk[:157] + ("..." if len(chunk) > 157 else "")
                cur = conn.execute(
                    "INSERT INTO memories(content,summary,memory_type,tags,embedding,created_at) VALUES(?,?,?,?,?,?)",
                    (chunk, summary, memory_type, json.dumps(tags or []), json.dumps(self._embed(chunk)), time.time()),
                )
                ids.append(cur.lastrowid)
            conn.commit()
        finally:
            self._pool.return_connection(conn)
        
        result = {"ok": True, "ids": ids, "chunks": len(ids)}
        self.bus.publish("memory.stored", result, "memory_engine")
        self._sync()
        return result

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        # Check cache first
        if self._cache:
            cache_key = f"search:{query}:{limit}"
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        
        conn = self._pool.get_connection()
        try:
            rows = conn.execute("SELECT * FROM memories ORDER BY created_at DESC LIMIT 500").fetchall()
            if not query.strip():
                selected = [(1.0, row) for row in rows[:limit]]
            else:
                query_vector = self._embed(query)
                selected = sorted(
                    ((self._similarity(query_vector, json.loads(row["embedding"])), row) for row in rows),
                    key=lambda item: item[0],
                    reverse=True,
                )[:limit]
            result = [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "summary": row["summary"],
                    "memory_type": row["memory_type"],
                    "tags": json.loads(row["tags"]),
                    "reflection": row["reflection"],
                    "score": round(score, 4),
                    "created_at": row["created_at"],
                }
                for score, row in selected
            ]
            
            # Cache the result
            if self._cache:
                self._cache.set(cache_key, result)
            
            return result
        finally:
            self._pool.return_connection(conn)

    def reflect(self, query: str = "") -> dict[str, Any]:
        memories = self.search(query, 20)
        if not memories:
            return {"reflection": "No memories are available for reflection.", "memory_ids": []}
        types: dict[str, int] = {}
        for item in memories:
            types[item["memory_type"]] = types.get(item["memory_type"], 0) + 1
        reflection = f"Reviewed {len(memories)} memories. Dominant categories: " + ", ".join(
            f"{name} ({count})" for name, count in sorted(types.items(), key=lambda item: -item[1])
        )
        ids = [item["id"] for item in memories]
        conn = self._pool.get_connection()
        try:
            conn.executemany("UPDATE memories SET reflection=? WHERE id=?", [(reflection, item_id) for item_id in ids])
            conn.commit()
        finally:
            self._pool.return_connection(conn)
        self.bus.publish("memory.reflected", {"memory_ids": ids, "reflection": reflection}, "memory_engine")
        return {"reflection": reflection, "memory_ids": ids}

    def count(self) -> int:
        conn = self._pool.get_connection()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
        finally:
            self._pool.return_connection(conn)

    def network(self) -> dict[str, list[dict[str, Any]]]:
        items = self.search("", 30)
        nodes = [{"id": str(item["id"]), "label": item["summary"], "type": item["memory_type"]} for item in items]
        edges = [
            {"source": str(items[index]["id"]), "target": str(items[index + 1]["id"])}
            for index in range(len(items) - 1)
        ]
        return {"nodes": nodes, "edges": edges}

    def record_episode(
        self,
        goal: str,
        action: str,
        result: str,
        outcome: str = "observed",
        evidence: list[dict[str, Any]] | None = None,
        confidence: float = 0.7,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Persist an episodic memory with explicit outcome and evidence."""
        normalized_outcome = outcome.strip().lower() or "observed"
        created_at = time.time()
        payload = {
            "goal": goal,
            "action": action,
            "result": result,
            "outcome": normalized_outcome,
            "evidence": evidence or [],
            "confidence": max(0.0, min(1.0, float(confidence))),
            "importance": max(0.0, min(1.0, float(importance))),
            "tags": tags or [],
            "created_at": created_at,
        }
        conn = self._pool.get_connection()
        try:
            cur = conn.execute(
                """INSERT INTO episodes(goal, action, result, outcome, evidence, confidence, importance, tags, created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    payload["goal"],
                    payload["action"],
                    payload["result"],
                    payload["outcome"],
                    json.dumps(payload["evidence"]),
                    payload["confidence"],
                    payload["importance"],
                    json.dumps(payload["tags"]),
                    payload["created_at"],
                ),
            )
            conn.commit()
            payload["id"] = cur.lastrowid
        finally:
            self._pool.return_connection(conn)
        self.store(
            f"Goal: {goal}\nAction: {action}\nOutcome: {normalized_outcome}\nResult: {result}",
            "episodic",
            ["episode", normalized_outcome, *(tags or [])],
        )
        self.bus.publish("memory.episode_recorded", payload, "memory_engine")
        return {"ok": True, "episode": payload}

    def list_episodes(self, query: str = "", outcome: str = "", limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        filters: list[str] = []
        params: list[Any] = []
        if outcome:
            filters.append("outcome=?")
            params.append(outcome.strip().lower())
        if query.strip():
            filters.append("(goal LIKE ? OR action LIKE ? OR result LIKE ?)")
            needle = f"%{query.strip()}%"
            params.extend([needle, needle, needle])
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        conn = self._pool.get_connection()
        try:
            rows = conn.execute(
                f"SELECT * FROM episodes {where} ORDER BY importance DESC, created_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
            return [self._episode_row(row) for row in rows]
        finally:
            self._pool.return_connection(conn)

    def upsert_procedure(
        self,
        name: str,
        description: str,
        steps: list[str],
        validators: list[str] | None = None,
        source_evidence: list[dict[str, Any]] | None = None,
        confidence: float = 0.6,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        clean_name = " ".join(name.split())
        now = time.time()
        conn = self._pool.get_connection()
        try:
            existing = conn.execute(
                "SELECT * FROM procedures WHERE lower(name)=lower(?) ORDER BY version DESC LIMIT 1",
                (clean_name,),
            ).fetchone()
            version = int(existing["version"]) + 1 if existing else 1
            cur = conn.execute(
                """INSERT INTO procedures(name, description, steps, validators, source_evidence, version,
                confidence, success_count, failure_count, tags, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    clean_name,
                    description,
                    json.dumps(steps),
                    json.dumps(validators or []),
                    json.dumps(source_evidence or []),
                    version,
                    max(0.0, min(1.0, float(confidence))),
                    0,
                    0,
                    json.dumps(tags or []),
                    now,
                    now,
                ),
            )
            conn.commit()
            procedure = self._procedure_row(
                conn.execute("SELECT * FROM procedures WHERE id=?", (cur.lastrowid,)).fetchone()
            )
        finally:
            self._pool.return_connection(conn)
        self.store(
            f"Procedure {clean_name} v{version}: {description}\nSteps: {'; '.join(steps)}",
            "procedural",
            ["procedure", clean_name.lower(), *(tags or [])],
        )
        self.bus.publish("memory.procedure_upserted", procedure, "memory_engine")
        return {"ok": True, "procedure": procedure}

    def list_procedures(self, query: str = "", limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        params: list[Any] = []
        where = ""
        if query.strip():
            where = "WHERE name LIKE ? OR description LIKE ?"
            needle = f"%{query.strip()}%"
            params.extend([needle, needle])
        conn = self._pool.get_connection()
        try:
            rows = conn.execute(
                f"SELECT * FROM procedures {where} ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
            return [self._procedure_row(row) for row in rows]
        finally:
            self._pool.return_connection(conn)

    def score_procedure(self, procedure_id: int, succeeded: bool, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        conn = self._pool.get_connection()
        try:
            row = conn.execute("SELECT * FROM procedures WHERE id=?", (procedure_id,)).fetchone()
            if row is None:
                return {"ok": False, "error": "procedure_not_found"}
            success_count = int(row["success_count"]) + (1 if succeeded else 0)
            failure_count = int(row["failure_count"]) + (0 if succeeded else 1)
            total = max(1, success_count + failure_count)
            confidence = max(0.1, min(0.99, success_count / total))
            conn.execute(
                """UPDATE procedures SET success_count=?, failure_count=?, confidence=?, updated_at=?
                WHERE id=?""",
                (success_count, failure_count, confidence, time.time(), procedure_id),
            )
            conn.commit()
            procedure = self._procedure_row(conn.execute("SELECT * FROM procedures WHERE id=?", (procedure_id,)).fetchone())
        finally:
            self._pool.return_connection(conn)
        self.bus.publish(
            "memory.procedure_evaluated",
            {"procedure_id": procedure_id, "succeeded": succeeded, "evidence": evidence or {}, "procedure": procedure},
            "memory_engine",
        )
        return {"ok": True, "procedure": procedure}

    @staticmethod
    def _episode_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "goal": row["goal"],
            "action": row["action"],
            "result": row["result"],
            "outcome": row["outcome"],
            "evidence": json.loads(row["evidence"]),
            "confidence": row["confidence"],
            "importance": row["importance"],
            "tags": json.loads(row["tags"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def _procedure_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "steps": json.loads(row["steps"]),
            "validators": json.loads(row["validators"]),
            "source_evidence": json.loads(row["source_evidence"]),
            "version": row["version"],
            "confidence": row["confidence"],
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "tags": json.loads(row["tags"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def categorize_and_store(self, text: str, tags: list[str] | None = None) -> dict[str, Any]:
        """Auto-classify text into a memory_type, then store it.

        Classification priority order:
            preference  → 'prefer', 'i like', 'i use', 'my project', 'i always'
            failure     → 'error', 'failed', 'exception', 'bug', 'crash'
            workflow    → 'workflow', 'automate', 'schedule', 'repeat'
            episodic    → 'learned', 'discovered', 'found that', 'realized'
            semantic    → 'python', 'javascript', 'react', 'fastapi', 'code', 'function', 'class'
            general     → fallback
        """
        lowered = text.lower()
        if any(s in lowered for s in ("prefer", "i like", "i use", "my project", "i always")):
            memory_type = "preference"
        elif any(s in lowered for s in ("error", "failed", "exception", "bug", "crash")):
            memory_type = "failure"
        elif any(s in lowered for s in ("workflow", "automate", "schedule", "repeat")):
            memory_type = "workflow"
        elif any(s in lowered for s in ("learned", "discovered", "found that", "realized")):
            memory_type = "episodic"
        elif any(s in lowered for s in ("python", "javascript", "react", "fastapi", "code", "function", "class")):
            memory_type = "semantic"
        else:
            memory_type = "general"
        return self.store(text, memory_type, tags)

    def get_by_type(self, memory_type: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return memories filtered by memory_type, newest first."""
        conn = self._pool.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM memories WHERE memory_type=? ORDER BY created_at DESC LIMIT ?",
                (memory_type, limit),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "summary": row["summary"],
                    "memory_type": row["memory_type"],
                    "tags": json.loads(row["tags"]),
                    "reflection": row["reflection"],
                    "score": 1.0,
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        finally:
            self._pool.return_connection(conn)

    def _sync(self) -> None:
        self.bus.set_state("memory", {"count": self.count()}, "memory_engine")
