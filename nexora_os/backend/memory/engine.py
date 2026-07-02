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
    def __init__(self, database: Path, bus: EventBus, dimensions: int = 256, pool_size: int = 5, enable_cache: bool = True) -> None:
        self.database = database
        self.bus = bus
        self.dimensions = dimensions
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
            conn.commit()
        finally:
            self._pool.return_connection(conn)
        
        # Cache for search results
        self._cache = Cache(default_ttl=60, max_size=500) if enable_cache else None

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            vector[index] += -1.0 if digest[4] & 1 else 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _similarity(a: list[float], b: list[float]) -> float:
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

    def _sync(self) -> None:
        self.bus.set_state("memory", {"count": self.count()}, "memory_engine")
