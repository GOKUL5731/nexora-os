"""
JARVIS Phase 2 — Multimodal Memory System
==========================================
Unified memory architecture combining:
  - Text memory (interactions, notes, facts)
  - Vision memory (camera captures, screen events)
  - Behavior memory (routines, patterns)
  - Task memory (completed/pending tasks)

Uses:
  - SQLite for persistent storage
  - Sentence-transformer embeddings for semantic search
  - FAISS/numpy vector similarity search
  - Fallback to keyword search if embeddings unavailable

Usage:
    from core.phase2.multimodal_memory import MultimodalMemory
    mem = MultimodalMemory()
    mem.store_text("User was working on Python project at 3pm")
    mem.store_vision_event("webcam", "User detected at desk", "/path/to/img.jpg")
    results = mem.search("python project")
    context = mem.get_relevant_context("what was I doing earlier?")
"""

import hashlib
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("jarvis.phase2.multimodal_memory")

ROOT   = Path(__file__).resolve().parent.parent.parent
DB_DIR = ROOT / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_DB   = DB_DIR / "multimodal_memory.db"
VECTORS_DIR = DB_DIR / "vectors"
VECTORS_DIR.mkdir(parents=True, exist_ok=True)


# ─── Schema ─────────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS text_memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    category    TEXT DEFAULT 'general',
    content     TEXT NOT NULL,
    source      TEXT DEFAULT '',
    importance  REAL DEFAULT 1.0,
    embedding_id TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS vision_memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    description TEXT NOT NULL,
    image_path  TEXT DEFAULT '',
    objects     TEXT DEFAULT '[]',
    embedding_id TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS behavior_memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    pattern     TEXT NOT NULL,
    details     TEXT DEFAULT '{}',
    frequency   INTEGER DEFAULT 1,
    last_seen   TEXT
);

CREATE TABLE IF NOT EXISTS task_memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created     TEXT NOT NULL,
    updated     TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT DEFAULT '',
    status      TEXT DEFAULT 'pending',
    result      TEXT DEFAULT '',
    context     TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS embeddings (
    id          TEXT PRIMARY KEY,
    vector_blob BLOB NOT NULL,
    dim         INTEGER NOT NULL,
    source_type TEXT,
    source_id   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_text_ts    ON text_memory(timestamp);
CREATE INDEX IF NOT EXISTS idx_text_cat   ON text_memory(category);
CREATE INDEX IF NOT EXISTS idx_vision_ts  ON vision_memory(timestamp);
CREATE INDEX IF NOT EXISTS idx_task_status ON task_memory(status);
"""


def _init_db(db_path: Path = MEMORY_DB):
    with sqlite3.connect(db_path) as c:
        c.executescript(SCHEMA)


def _uid(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


# ─── Embedding Engine ────────────────────────────────────────────────────────────
class EmbeddingEngine:
    """
    Produces vector embeddings for semantic search.
    Uses sentence-transformers if available; falls back to TF-IDF-style bag-of-words.
    """

    def __init__(self):
        self._model        = None
        self._fallback_idf = {}
        self._lock         = threading.Lock()
        self._dim          = 384  # default ST dimension
        self._try_load()

    def _try_load(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._dim   = 384
            logger.info("[Memory] Sentence-transformer loaded (all-MiniLM-L6-v2)")
        except ImportError:
            logger.info("[Memory] sentence-transformers not installed. Using BoW fallback.")
            logger.info("[Memory] Install: pip install sentence-transformers")
        except Exception as e:
            logger.warning(f"[Memory] ST load failed: {e}")

    def embed(self, text: str) -> np.ndarray:
        if self._model is not None:
            try:
                vec = self._model.encode([text], normalize_embeddings=True)[0]
                return vec.astype(np.float32)
            except Exception as e:
                logger.warning(f"[Memory] Embedding error: {e}")

        # Fallback: simple character n-gram hash embedding
        return self._bow_embed(text)

    def _bow_embed(self, text: str, dim: int = 128) -> np.ndarray:
        """Deterministic character n-gram bag-of-words embedding."""
        vec = np.zeros(dim, dtype=np.float32)
        tokens = text.lower().split()
        for tok in tokens:
            for n in (2, 3):
                for i in range(len(tok) - n + 1):
                    ngram = tok[i:i+n]
                    idx   = abs(hash(ngram)) % dim
                    vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        if a.shape != b.shape:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    @property
    def dim(self) -> int:
        return self._dim if self._model else 128


# ─── Multimodal Memory ───────────────────────────────────────────────────────────
class MultimodalMemory:
    """
    Persistent memory system combining all modalities with semantic search.
    Thread-safe.
    """

    def __init__(self, config: dict = None, db_path: Path = MEMORY_DB):
        self.config     = config or {}
        self.db_path    = db_path
        self._embedder  = EmbeddingEngine()
        self._lock      = threading.Lock()
        _init_db(db_path)
        logger.info("[Memory] MultimodalMemory initialized")

    # ── Embedding Helpers ──────────────────────────────────────────────────────
    def _store_embedding(self, uid: str, text: str, source_type: str, source_id: int):
        try:
            vec  = self._embedder.embed(text)
            blob = vec.tobytes()
            with sqlite3.connect(self.db_path) as c:
                c.execute(
                    "INSERT OR REPLACE INTO embeddings (id, vector_blob, dim, source_type, source_id) "
                    "VALUES (?,?,?,?,?)",
                    (uid, blob, len(vec), source_type, source_id)
                )
        except Exception as e:
            logger.warning(f"[Memory] Embedding store error: {e}")

    def _load_all_embeddings(self, source_type: str) -> List[Tuple[str, np.ndarray, int]]:
        """Load (uid, vector, source_id) tuples for a given source type."""
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT id, vector_blob, dim, source_id FROM embeddings WHERE source_type=?",
                    (source_type,)
                ).fetchall()
            result = []
            for uid, blob, dim, src_id in rows:
                vec = np.frombuffer(blob, dtype=np.float32)
                if len(vec) == dim:
                    result.append((uid, vec, src_id))
            return result
        except Exception:
            return []

    # ── Text Memory ───────────────────────────────────────────────────────────
    def store_text(
        self,
        content: str,
        category: str = "general",
        source: str = "",
        importance: float = 1.0,
    ) -> int:
        """
        Store a text memory item and create its embedding.

        Returns: inserted row ID
        """
        try:
            now = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as c:
                cursor = c.execute(
                    "INSERT INTO text_memory (timestamp, category, content, source, importance) "
                    "VALUES (?,?,?,?,?)",
                    (now, category, content[:2000], source, importance)
                )
                row_id = cursor.lastrowid

            uid = _uid(f"text:{row_id}")
            self._store_embedding(uid, content, "text", row_id)
            return row_id
        except Exception as e:
            logger.error(f"[Memory] store_text error: {e}")
            return -1

    def store_conversation(self, user_input: str, jarvis_response: str, context: str = ""):
        """Store a conversation exchange as a text memory."""
        content = f"User: {user_input}\nJARVIS: {jarvis_response}"
        return self.store_text(content, category="conversation", source=context)

    def store_fact(self, fact: str, source: str = ""):
        """Store a learned fact with high importance."""
        return self.store_text(fact, category="fact", source=source, importance=1.5)

    # ── Vision Memory ─────────────────────────────────────────────────────────
    def store_vision_event(
        self,
        event_type: str,
        description: str,
        image_path: str = "",
        objects: List[str] = None,
    ) -> int:
        """
        Store a vision event (camera capture, screen analysis, object detection).

        Args:
            event_type:  'webcam', 'screen', 'object_detection', 'user_presence'
            description: Human-readable description
            image_path:  Path to the captured image
            objects:     List of detected object labels
        """
        try:
            now = datetime.now().isoformat()
            obj_json = json.dumps(objects or [])
            with sqlite3.connect(self.db_path) as c:
                cursor = c.execute(
                    "INSERT INTO vision_memory (timestamp, event_type, description, image_path, objects) "
                    "VALUES (?,?,?,?,?)",
                    (now, event_type, description[:1000], image_path, obj_json)
                )
                row_id = cursor.lastrowid

            uid = _uid(f"vision:{row_id}")
            embed_text = f"{event_type}: {description}"
            if objects:
                embed_text += " Objects: " + " ".join(objects)
            self._store_embedding(uid, embed_text, "vision", row_id)
            return row_id
        except Exception as e:
            logger.error(f"[Memory] store_vision_event error: {e}")
            return -1

    # ── Behavior Memory ───────────────────────────────────────────────────────
    def store_behavior(self, pattern: str, details: dict = None):
        """Store a detected behavior pattern."""
        try:
            now = datetime.now().isoformat()
            details_json = json.dumps(details or {})
            with sqlite3.connect(self.db_path) as c:
                existing = c.execute(
                    "SELECT id, frequency FROM behavior_memory WHERE pattern=?", (pattern,)
                ).fetchone()
                if existing:
                    c.execute(
                        "UPDATE behavior_memory SET frequency=frequency+1, last_seen=?, details=? WHERE id=?",
                        (now, details_json, existing[0])
                    )
                else:
                    c.execute(
                        "INSERT INTO behavior_memory (timestamp, pattern, details, frequency, last_seen) "
                        "VALUES (?,?,?,1,?)",
                        (now, pattern, details_json, now)
                    )
        except Exception as e:
            logger.error(f"[Memory] store_behavior error: {e}")

    # ── Task Memory ───────────────────────────────────────────────────────────
    def create_task(
        self,
        title: str,
        description: str = "",
        context: dict = None,
    ) -> int:
        """Create a new task record."""
        try:
            now = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as c:
                cursor = c.execute(
                    "INSERT INTO task_memory (created, updated, title, description, context) "
                    "VALUES (?,?,?,?,?)",
                    (now, now, title[:200], description[:1000], json.dumps(context or {}))
                )
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"[Memory] create_task error: {e}")
            return -1

    def update_task(self, task_id: int, status: str, result: str = ""):
        """Update task status and result."""
        try:
            with sqlite3.connect(self.db_path) as c:
                c.execute(
                    "UPDATE task_memory SET status=?, result=?, updated=? WHERE id=?",
                    (status, result[:500], datetime.now().isoformat(), task_id)
                )
        except Exception as e:
            logger.error(f"[Memory] update_task error: {e}")

    # ── Semantic Search ────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        source_types: List[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.25,
    ) -> List[Dict]:
        """
        Semantic similarity search across all memory types.

        Args:
            query:        Natural language query
            source_types: Filter by ['text', 'vision', 'task'] or None for all
            top_k:        Max results to return
            min_similarity: Minimum cosine similarity threshold

        Returns:
            List of dicts with content, similarity, type, timestamp
        """
        q_vec   = self._embedder.embed(query)
        types   = source_types or ["text", "vision"]
        results = []

        for src_type in types:
            embeddings = self._load_all_embeddings(src_type)
            for uid, vec, src_id in embeddings:
                if vec.shape != q_vec.shape:
                    continue
                sim = self._embedder.cosine_similarity(q_vec, vec)
                if sim >= min_similarity:
                    record = self._fetch_record(src_type, src_id)
                    if record:
                        record["similarity"]   = round(sim, 3)
                        record["source_type"]  = src_type
                        record["source_id"]    = src_id
                        results.append(record)

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def _fetch_record(self, src_type: str, src_id: int) -> Optional[Dict]:
        try:
            with sqlite3.connect(self.db_path) as c:
                if src_type == "text":
                    row = c.execute(
                        "SELECT content, category, source, timestamp FROM text_memory WHERE id=?",
                        (src_id,)
                    ).fetchone()
                    if row:
                        return {"content": row[0], "category": row[1],
                                "source": row[2], "timestamp": row[3]}

                elif src_type == "vision":
                    row = c.execute(
                        "SELECT description, event_type, image_path, objects, timestamp "
                        "FROM vision_memory WHERE id=?",
                        (src_id,)
                    ).fetchone()
                    if row:
                        return {"content": row[0], "event_type": row[1],
                                "image_path": row[2],
                                "objects": json.loads(row[3] or "[]"),
                                "timestamp": row[4]}
        except Exception as e:
            logger.warning(f"[Memory] Fetch record error: {e}")
        return None

    def get_relevant_context(self, query: str, max_tokens: int = 800) -> str:
        """
        Retrieve relevant memory as a formatted context string for LLM prompts.
        Designed to be inserted into system prompts.
        """
        results = self.search(query, top_k=6, min_similarity=0.3)
        if not results:
            return ""

        parts = ["[JARVIS MEMORY CONTEXT]"]
        tokens = 0
        for r in results:
            ts      = r.get("timestamp", "")[:16]
            content = r.get("content", "")
            line    = f"• [{ts}] {content}"
            tokens += len(line.split())
            if tokens > max_tokens:
                break
            parts.append(line)

        return "\n".join(parts)

    # ── Recent Memory ──────────────────────────────────────────────────────────
    def get_recent_text(self, limit: int = 20, category: str = None) -> List[Dict]:
        """Retrieve recent text memories."""
        try:
            with sqlite3.connect(self.db_path) as c:
                if category:
                    rows = c.execute(
                        "SELECT id, timestamp, category, content, source FROM text_memory "
                        "WHERE category=? ORDER BY id DESC LIMIT ?",
                        (category, limit)
                    ).fetchall()
                else:
                    rows = c.execute(
                        "SELECT id, timestamp, category, content, source FROM text_memory "
                        "ORDER BY id DESC LIMIT ?",
                        (limit,)
                    ).fetchall()
            return [
                {"id": r[0], "timestamp": r[1], "category": r[2],
                 "content": r[3], "source": r[4]}
                for r in rows
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def get_recent_vision(self, limit: int = 10) -> List[Dict]:
        """Retrieve recent vision memory events."""
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT id, timestamp, event_type, description, image_path, objects "
                    "FROM vision_memory ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [
                {"id": r[0], "timestamp": r[1], "event_type": r[2],
                 "description": r[3], "image_path": r[4],
                 "objects": json.loads(r[5] or "[]")}
                for r in rows
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def get_tasks(self, status: str = None, limit: int = 20) -> List[Dict]:
        """Retrieve task memory."""
        try:
            with sqlite3.connect(self.db_path) as c:
                if status:
                    rows = c.execute(
                        "SELECT id, created, updated, title, description, status, result "
                        "FROM task_memory WHERE status=? ORDER BY id DESC LIMIT ?",
                        (status, limit)
                    ).fetchall()
                else:
                    rows = c.execute(
                        "SELECT id, created, updated, title, description, status, result "
                        "FROM task_memory ORDER BY id DESC LIMIT ?",
                        (limit,)
                    ).fetchall()
            return [
                {"id": r[0], "created": r[1], "updated": r[2], "title": r[3],
                 "description": r[4], "status": r[5], "result": r[6]}
                for r in rows
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def get_behaviors(self, limit: int = 20) -> List[Dict]:
        """Get detected behavior patterns sorted by frequency."""
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT pattern, frequency, last_seen, details "
                    "FROM behavior_memory ORDER BY frequency DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [
                {"pattern": r[0], "frequency": r[1], "last_seen": r[2],
                 "details": json.loads(r[3] or "{}")}
                for r in rows
            ]
        except Exception as e:
            return [{"error": str(e)}]

    # ── Stats ──────────────────────────────────────────────────────────────────
    def get_memory_stats(self) -> Dict:
        """Summary statistics for all memory stores."""
        try:
            with sqlite3.connect(self.db_path) as c:
                text_count    = c.execute("SELECT COUNT(*) FROM text_memory").fetchone()[0]
                vision_count  = c.execute("SELECT COUNT(*) FROM vision_memory").fetchone()[0]
                behavior_count = c.execute("SELECT COUNT(*) FROM behavior_memory").fetchone()[0]
                task_count    = c.execute("SELECT COUNT(*) FROM task_memory").fetchone()[0]
                embed_count   = c.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
                pending_tasks = c.execute(
                    "SELECT COUNT(*) FROM task_memory WHERE status='pending'"
                ).fetchone()[0]

            db_size_mb = round(MEMORY_DB.stat().st_size / 1e6, 2) if MEMORY_DB.exists() else 0
            return {
                "text_memories":    text_count,
                "vision_memories":  vision_count,
                "behavior_patterns": behavior_count,
                "total_tasks":      task_count,
                "pending_tasks":    pending_tasks,
                "embeddings":       embed_count,
                "db_size_mb":       db_size_mb,
                "embedding_engine": "sentence-transformers" if self._embedder._model else "bow_fallback",
            }
        except Exception as e:
            return {"error": str(e)}

    def clear_old_memories(self, days: int = 30):
        """Remove memories older than N days (except facts and tasks)."""
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            with sqlite3.connect(self.db_path) as c:
                deleted_text = c.execute(
                    "DELETE FROM text_memory WHERE timestamp < ? AND category != 'fact'",
                    (cutoff,)
                ).rowcount
                deleted_vision = c.execute(
                    "DELETE FROM vision_memory WHERE timestamp < ?", (cutoff,)
                ).rowcount
            logger.info(f"[Memory] Cleared {deleted_text} text + {deleted_vision} vision memories older than {days}d")
            return {"deleted_text": deleted_text, "deleted_vision": deleted_vision}
        except Exception as e:
            return {"error": str(e)}
