"""
JARVIS Memory Manager
Uses SQLite (built into Python — zero extra installs).
ChromaDB vector search is optional — falls back to keyword search.
"""

import hashlib
import json
import logging
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.memory")


class MemoryManager:
    def __init__(self, config: dict):
        db_path = config.get("memory", {}).get("db_path", "database/memory.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Short-term in-memory store (current session)
        self._session: list[dict] = []
        self._context: dict = {}

        self._init_db()
        logger.info(f"Memory ready: {self.db_path}")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id          TEXT PRIMARY KEY,
                    timestamp   TEXT NOT NULL,
                    user_input  TEXT NOT NULL,
                    jarvis_resp TEXT NOT NULL,
                    task_id     TEXT DEFAULT '',
                    outcome     TEXT DEFAULT 'success',
                    tags        TEXT DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS facts (
                    id          TEXT PRIMARY KEY,
                    category    TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    UNIQUE(category, key)
                );
                CREATE TABLE IF NOT EXISTS skills (
                    id          TEXT PRIMARY KEY,
                    name        TEXT UNIQUE NOT NULL,
                    description TEXT DEFAULT '',
                    steps       TEXT DEFAULT '[]',
                    uses        INTEGER DEFAULT 0,
                    updated_at  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS episodic_events (
                    id          TEXT PRIMARY KEY,
                    timestamp   TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    summary     TEXT NOT NULL,
                    data        TEXT DEFAULT '{}',
                    importance  REAL DEFAULT 0.5
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    confidence  REAL DEFAULT 0.5,
                    source      TEXT DEFAULT '',
                    updated_at  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS error_solutions (
                    signature   TEXT PRIMARY KEY,
                    solution    TEXT DEFAULT '',
                    context     TEXT DEFAULT '{}',
                    resolved    INTEGER DEFAULT 0,
                    count       INTEGER DEFAULT 1,
                    updated_at  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vector_memory (
                    id          TEXT PRIMARY KEY,
                    namespace   TEXT NOT NULL,
                    text        TEXT NOT NULL,
                    embedding   TEXT NOT NULL,
                    metadata    TEXT DEFAULT '{}',
                    created_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_inter_time ON interactions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_facts_cat  ON facts(category);
                CREATE INDEX IF NOT EXISTS idx_events_time ON episodic_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_vector_ns ON vector_memory(namespace);
            """)

    # ── Session (short-term) ────────────────────────────────────────────────
    def add_turn(self, role: str, text: str):
        self._session.append({"role": role, "text": text, "ts": datetime.now().isoformat()})
        if len(self._session) > 30:
            self._session = self._session[-30:]

    def get_session(self, n: int = 10) -> list[dict]:
        return self._session[-n:]

    def set_context(self, key: str, value):
        self._context[key] = value

    def get_ctx(self, key: str, default=None):
        return self._context.get(key, default)

    # ── Long-term (SQLite) ──────────────────────────────────────────────────
    def store_interaction(self, user_input: str, jarvis_resp: str,
                          task_id: str = "", outcome: str = "success",
                          tags: list = None):
        iid = hashlib.md5(f"{task_id}{user_input}{datetime.now().isoformat()}".encode()).hexdigest()
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT OR REPLACE INTO interactions VALUES (?,?,?,?,?,?,?)",
                (iid, datetime.now().isoformat(), user_input[:500], jarvis_resp[:1000],
                 task_id, outcome, json.dumps(tags or []))
            )

    def retrieve_relevant(self, query: str, limit: int = 5) -> list[dict]:
        """Keyword search over recent interactions."""
        words = [w for w in query.lower().split() if len(w) > 3][:6]
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT user_input, jarvis_resp, timestamp, outcome FROM interactions "
                "ORDER BY timestamp DESC LIMIT 200"
            ).fetchall()

        results = []
        for user_in, resp, ts, outcome in rows:
            score = sum(1 for w in words if w in user_in.lower())
            if score > 0:
                results.append({"score": score, "summary": f"Q: {user_in[:80]}  A: {resp[:80]}",
                                 "timestamp": ts, "outcome": outcome})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_interaction_count(self) -> int:
        with sqlite3.connect(self.db_path) as c:
            return c.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]

    # ── Facts ───────────────────────────────────────────────────────────────
    def store_fact(self, category: str, key: str, value: str):
        fid = hashlib.md5(f"{category}{key}".encode()).hexdigest()
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT OR REPLACE INTO facts VALUES (?,?,?,?,?)",
                (fid, category, key, value, datetime.now().isoformat())
            )

    def get_facts(self, category: str) -> dict:
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT key, value FROM facts WHERE category=?", (category,)
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def get_user_profile(self) -> dict:
        profile = {}
        for cat in ["preferences", "habits", "projects", "contacts"]:
            f = self.get_facts(cat)
            if f:
                profile[cat] = f
        learned_preferences = self.get_preferences()
        if learned_preferences:
            profile["learned_preferences"] = learned_preferences
        profile["total_interactions"] = self.get_interaction_count()
        return profile

    # Cognitive memory categories
    def store_event(self, event_type: str, summary: str, data: dict = None,
                    importance: float = 0.5) -> str:
        eid = hashlib.md5(f"{event_type}{summary}{datetime.now().isoformat()}".encode()).hexdigest()
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT INTO episodic_events VALUES (?,?,?,?,?,?)",
                (
                    eid,
                    datetime.now().isoformat(),
                    event_type,
                    summary[:1000],
                    json.dumps(data or {}, ensure_ascii=False),
                    float(max(0.0, min(1.0, importance))),
                ),
            )
        return eid

    def recent_events(self, limit: int = 20, event_type: str = None) -> list[dict]:
        with sqlite3.connect(self.db_path) as c:
            if event_type:
                rows = c.execute(
                    "SELECT id,timestamp,event_type,summary,data,importance "
                    "FROM episodic_events WHERE event_type=? ORDER BY timestamp DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id,timestamp,event_type,summary,data,importance "
                    "FROM episodic_events ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "event_type": r[2],
                "summary": r[3],
                "data": json.loads(r[4] or "{}"),
                "importance": r[5],
            }
            for r in rows
        ]

    def learn_preference(self, key: str, value: str, source: str = "",
                         confidence: float = 0.6):
        safe_key = key.strip().lower().replace(" ", "_")[:80]
        with sqlite3.connect(self.db_path) as c:
            c.execute("""
                INSERT INTO preferences(key,value,confidence,source,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                  value=excluded.value,
                  confidence=MAX(confidence, excluded.confidence),
                  source=excluded.source,
                  updated_at=excluded.updated_at
            """, (
                safe_key,
                value[:1000],
                float(max(0.0, min(1.0, confidence))),
                source[:500],
                datetime.now().isoformat(),
            ))
        self.store_fact("preferences", safe_key, value[:1000])

    def get_preferences(self) -> dict:
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT key,value,confidence,updated_at FROM preferences ORDER BY updated_at DESC"
            ).fetchall()
        return {
            r[0]: {"value": r[1], "confidence": r[2], "updated_at": r[3]}
            for r in rows
        }

    def remember_error(self, signature: str, solution: str = "",
                       context: dict = None, resolved: bool = False):
        sig = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:32]
        with sqlite3.connect(self.db_path) as c:
            c.execute("""
                INSERT INTO error_solutions(signature,solution,context,resolved,count,updated_at)
                VALUES(?,?,?,?,1,?)
                ON CONFLICT(signature) DO UPDATE SET
                  solution=CASE WHEN excluded.solution != '' THEN excluded.solution ELSE solution END,
                  context=excluded.context,
                  resolved=MAX(resolved, excluded.resolved),
                  count=count+1,
                  updated_at=excluded.updated_at
            """, (
                sig,
                solution[:2000],
                json.dumps(context or {}, ensure_ascii=False),
                int(resolved),
                datetime.now().isoformat(),
            ))

    def find_solution(self, signature: str) -> Optional[dict]:
        sig = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:32]
        with sqlite3.connect(self.db_path) as c:
            row = c.execute(
                "SELECT solution,context,resolved,count,updated_at FROM error_solutions WHERE signature=?",
                (sig,),
            ).fetchone()
        if not row:
            return None
        return {
            "solution": row[0],
            "context": json.loads(row[1] or "{}"),
            "resolved": bool(row[2]),
            "count": row[3],
            "updated_at": row[4],
        }

    # Local vector memory: deterministic hashed bag-of-words embeddings.
    # It is intentionally dependency-free and can be swapped for a neural
    # embedding provider later without changing the SQLite schema.
    def store_vector_memory(self, text: str, metadata: dict = None,
                            namespace: str = "general") -> str:
        vid = hashlib.md5(f"{namespace}{text}{datetime.now().isoformat()}".encode()).hexdigest()
        emb = self._embed_text(text)
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT INTO vector_memory VALUES (?,?,?,?,?,?)",
                (
                    vid,
                    namespace,
                    text[:4000],
                    json.dumps(emb),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )
        return vid

    def search_vector_memory(self, query: str, limit: int = 5,
                             namespace: str = "general") -> list[dict]:
        q = self._embed_text(query)
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute(
                "SELECT id,text,embedding,metadata,created_at FROM vector_memory "
                "WHERE namespace=? ORDER BY created_at DESC LIMIT 300",
                (namespace,),
            ).fetchall()
        results = []
        for rid, text, embedding, metadata, created in rows:
            try:
                score = self._cosine(q, json.loads(embedding))
            except Exception:
                score = 0.0
            if score > 0:
                results.append({
                    "id": rid,
                    "text": text,
                    "score": round(score, 4),
                    "metadata": json.loads(metadata or "{}"),
                    "created_at": created,
                })
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def _embed_text(self, text: str, dims: int = 128) -> list[float]:
        vec = [0.0] * dims
        words = [w for w in text.lower().split() if len(w) > 2]
        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            vec[h % dims] += 1.0
            vec[(h >> 8) % dims] += 0.5
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [round(v / norm, 6) for v in vec]

    def _cosine(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        return sum(x * y for x, y in zip(a, b))

    # ── Skills ──────────────────────────────────────────────────────────────
    def store_skill(self, name: str, description: str, steps: list):
        sid = hashlib.md5(name.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as c:
            c.execute("""
                INSERT INTO skills VALUES (?,?,?,?,0,?)
                ON CONFLICT(name) DO UPDATE SET
                  description=excluded.description,
                  steps=excluded.steps,
                  uses=uses+1,
                  updated_at=excluded.updated_at
            """, (sid, name, description, json.dumps(steps), datetime.now().isoformat()))

    def recall_skill(self, name: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as c:
            r = c.execute(
                "SELECT name,description,steps,uses FROM skills WHERE name=?", (name,)
            ).fetchone()
        if not r:
            return None
        return {"name": r[0], "description": r[1], "steps": json.loads(r[2]), "uses": r[3]}
