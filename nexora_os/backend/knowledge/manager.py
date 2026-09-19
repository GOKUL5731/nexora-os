from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from ..core.event_bus import EventBus
from ..memory.engine import MemoryEngine

DOMAIN_SEEDS: dict[str, list[dict[str, Any]]] = {
    "python": [
        {
            "title": "Python language fundamentals",
            "source": "Python official documentation",
            "content": "Python is a high-level language focused on readability. Core topics include syntax, data types, control flow, functions, modules, packages, exceptions, classes, virtual environments, and testing.",
            "tags": ["language", "syntax", "stdlib"],
        },
        {
            "title": "Python project practice",
            "source": "Python Packaging User Guide and pytest documentation",
            "content": "Practical Python work should use isolated environments, clear package structure, dependency files, tests, formatting, and explicit error handling. Common web server choices include FastAPI, Flask, and Django.",
            "tags": ["packaging", "testing", "web"],
        },
    ],
    "fastapi": [
        {
            "title": "FastAPI fundamentals",
            "source": "FastAPI official documentation",
            "content": "FastAPI builds Python web APIs with type hints, Pydantic models, dependency injection, async handlers, automatic OpenAPI schemas, and ASGI servers such as Uvicorn.",
            "tags": ["python", "api", "async"],
        }
    ],
    "java": [
        {
            "title": "Java application foundations",
            "source": "Oracle Java documentation and OpenJDK documentation",
            "content": "Java projects commonly use packages, classes, interfaces, exceptions, collections, streams, Maven or Gradle builds, JUnit tests, and JVM diagnostics.",
            "tags": ["language", "jvm", "testing"],
        }
    ],
    "quantum physics": [
        {
            "title": "Quantum physics foundations",
            "source": "OpenStax and university quantum mechanics course notes",
            "content": "Quantum physics studies systems described by state vectors, wavefunctions, operators, observables, measurement probabilities, superposition, uncertainty, spin, and time evolution through the Schrodinger equation.",
            "tags": ["physics", "math", "foundations"],
        }
    ],
}


class KnowledgeManager:
    """Persistent knowledge base layered on top of memory retrieval.

    This does not retrain the underlying model. It stores structured,
    source-attributed domain knowledge and makes it searchable for future tasks.
    """

    def __init__(self, database: Path, memory: MemoryEngine, bus: EventBus, llm: Any | None = None) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self.memory = memory
        self.bus = bus
        self.llm = llm
        self._db = sqlite3.connect(database, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS domains(
            name TEXT PRIMARY KEY, status TEXT NOT NULL, summary TEXT NOT NULL,
            sources TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)"""
        )
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS knowledge_entries(
            id INTEGER PRIMARY KEY, domain TEXT NOT NULL, title TEXT NOT NULL,
            content TEXT NOT NULL, source TEXT NOT NULL, tags TEXT NOT NULL,
            created_at REAL NOT NULL)"""
        )
        self._db.execute("""CREATE TABLE IF NOT EXISTS knowledge_nodes(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, node_type TEXT NOT NULL,
            summary TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 0.5,
            importance REAL NOT NULL DEFAULT 0.5, metadata TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS knowledge_edges(
            id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, target_id INTEGER NOT NULL,
            relationship TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 0.5,
            evidence TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
            UNIQUE(source_id, target_id, relationship))""")
        # Migration: add embedding column if it doesn't exist yet
        try:
            self._db.execute("ALTER TABLE knowledge_entries ADD COLUMN embedding TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass  # Column already exists
        self._db.commit()

    def learn_domain(self, domain: str, resources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        normalized = self._normalize_domain(domain)
        if not normalized:
            return {"ok": False, "error": "Knowledge domain is required."}
        entries = resources or DOMAIN_SEEDS.get(normalized) or [self._generic_learning_entry(normalized)]
        stored_ids: list[int] = []
        memory_ids: list[int] = []
        now = time.time()
        for entry in entries:
            content_text = str(entry.get("content") or "")
            embedding = self._embed(content_text)
            cur = self._db.execute(
                "INSERT INTO knowledge_entries(domain,title,content,source,tags,created_at,embedding) VALUES(?,?,?,?,?,?,?)",
                (
                    normalized,
                    str(entry.get("title") or normalized.title()),
                    content_text,
                    str(entry.get("source") or "user-approved seed"),
                    json.dumps(entry.get("tags") or []),
                    now,
                    json.dumps(embedding),
                ),
            )
            stored_ids.append(int(cur.lastrowid))
            memory_text = self._memory_text(normalized, entry)
            mem = self.memory.store(memory_text, "knowledge", ["knowledge", normalized, *entry.get("tags", [])])
            memory_ids.extend(mem.get("ids", []))
            self._upsert_graph(normalized, entry, now)
        sources = sorted({str(entry.get("source") or "user-approved seed") for entry in entries})
        summary = f"Knowledge domain '{normalized}' indexed with {len(entries)} source-attributed entries."
        self._db.execute(
            """INSERT INTO domains(name,status,summary,sources,created_at,updated_at) VALUES(?,?,?,?,?,?)
            ON CONFLICT(name) DO UPDATE SET status=excluded.status, summary=excluded.summary,
            sources=excluded.sources, updated_at=excluded.updated_at""",
            (normalized, "READY", summary, json.dumps(sources), now, now),
        )
        self._db.commit()
        result = {"ok": True, "domain": normalized, "entries": len(entries), "entry_ids": stored_ids, "memory_ids": memory_ids, "sources": sources, "message": summary}
        self.bus.publish("knowledge.domain.learned", result, "knowledge_manager")
        self._sync()
        return result

    def _upsert_graph(self, domain: str, entry: dict[str, Any], now: float) -> None:
        domain_id = self._upsert_node(domain.title(), "Concept", f"Knowledge domain: {domain}", now)
        labels = [str(tag).strip() for tag in entry.get("tags", []) if str(tag).strip()]
        title_terms = [term for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", str(entry.get("title", ""))) if term.lower() != domain.lower()]
        for label in dict.fromkeys(labels + title_terms):
            node_id = self._upsert_node(label, "Concept", f"Concept related to {domain}", now)
            self._db.execute(
                "INSERT OR IGNORE INTO knowledge_edges(source_id,target_id,relationship,confidence,evidence,created_at) VALUES(?,?,?,?,?,?)",
                (domain_id, node_id, "RELATED_TO", 0.7, str(entry.get("source", "")), now),
            )

    def _upsert_node(self, name: str, node_type: str, summary: str, now: float) -> int:
        self._db.execute(
            "INSERT INTO knowledge_nodes(name,node_type,summary,created_at,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET summary=excluded.summary, updated_at=excluded.updated_at",
            (name, node_type, summary, now, now),
        )
        return int(self._db.execute("SELECT id FROM knowledge_nodes WHERE name=?", (name,)).fetchone()[0])

    def graph(self, node: str = "", limit: int = 200) -> dict[str, Any]:
        if node:
            rows = self._db.execute("SELECT * FROM knowledge_nodes WHERE lower(name) LIKE ? ORDER BY updated_at DESC LIMIT ?", (f"%{node.lower()}%", limit)).fetchall()
        else:
            rows = self._db.execute("SELECT * FROM knowledge_nodes ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        ids = {int(row["id"]) for row in rows}
        edges = self._db.execute("SELECT * FROM knowledge_edges ORDER BY created_at DESC LIMIT ?", (limit * 2,)).fetchall()
        return {"nodes": [dict(row) for row in rows], "edges": [dict(edge) for edge in edges if int(edge["source_id"]) in ids or int(edge["target_id"]) in ids]}

    def index_text(self, domain: str, title: str, content: str, source: str = "user provided", tags: list[str] | None = None) -> dict[str, Any]:
        if not content.strip():
            return {"ok": False, "error": "Content is required."}
        return self.learn_domain(self._normalize_domain(domain), [{"title": title, "content": content, "source": source, "tags": tags or ["user_indexed"]}])

    def search(self, query: str, domain: str = "", limit: int = 8) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM knowledge_entries WHERE (?='' OR domain=?) ORDER BY created_at DESC LIMIT 500",
            (self._normalize_domain(domain), self._normalize_domain(domain)),
        ).fetchall()

        if not rows:
            return []

        # Try semantic search first
        query_vec = self._embed(query)
        if query_vec:
            scored: list[tuple[float, Any]] = []
            for row in rows:
                try:
                    row_vec = json.loads(row["embedding"] or "[]")
                except Exception:
                    row_vec = []
                if row_vec and len(row_vec) == len(query_vec):
                    score = self._cosine_similarity(query_vec, row_vec)
                else:
                    score = 0.0
                if score > 0:
                    scored.append((score, row))
            if scored:
                scored.sort(key=lambda item: item[0], reverse=True)
                return [self._entry(row, round(sc, 4)) for sc, row in scored[:limit]]

        # Fallback: keyword scoring
        terms = set(re.findall(r"[\w\u0B80-\u0BFF]+", query.lower(), re.UNICODE))
        kw_scored: list[tuple[int, Any]] = []
        for row in rows:
            haystack = f"{row['domain']} {row['title']} {row['content']} {row['source']}".lower()
            score = sum(1 for term in terms if term in haystack) if terms else 1
            if score > 0:
                kw_scored.append((score, row))
        kw_scored.sort(key=lambda item: (item[0], item[1]["created_at"]), reverse=True)
        return [self._entry(row, score) for score, row in kw_scored[:limit]]

    def domains(self) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT * FROM domains ORDER BY updated_at DESC").fetchall()
        return [{**dict(row), "sources": json.loads(row["sources"])} for row in rows]

    def status(self) -> dict[str, Any]:
        domain_count = int(self._db.execute("SELECT COUNT(*) FROM domains").fetchone()[0])
        entry_count = int(self._db.execute("SELECT COUNT(*) FROM knowledge_entries").fetchone()[0])
        return {"domains": domain_count, "entries": entry_count, "database": str(self.database)}

    def _sync(self) -> None:
        self.bus.set_state("knowledge", {"status": self.status(), "domains": self.domains()}, "knowledge_manager")

    def _embed(self, text: str) -> list[float]:
        """Return semantic embedding via LLM, or empty list on failure."""
        if self.llm and callable(getattr(self.llm, "embed", None)):
            try:
                return self.llm.embed(text)
            except Exception:
                pass
        return []

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a)) or 1.0
        mag_b = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (mag_a * mag_b)

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        text = domain.lower().strip()
        text = re.sub(r"^(learn|study|update|index)\s+", "", text).strip()
        text = re.sub(r"\s+knowledge$", "", text).strip()
        return " ".join(text.split())

    @staticmethod
    def _generic_learning_entry(domain: str) -> dict[str, Any]:
        return {
            "title": f"Learning plan for {domain}",
            "source": "local knowledge seed",
            "content": f"No approved external source bundle is configured for {domain}. The domain is registered with a starter learning plan: collect trusted references, extract concepts, store examples, record provenance, and refresh over time.",
            "tags": ["learning_plan", "needs_sources"],
        }

    @staticmethod
    def _memory_text(domain: str, entry: dict[str, Any]) -> str:
        return f"Knowledge domain: {domain}\nTitle: {entry.get('title')}\nSource: {entry.get('source')}\nContent: {entry.get('content')}"

    @staticmethod
    def _entry(row: sqlite3.Row, score: int) -> dict[str, Any]:
        return {
            "id": row["id"],
            "domain": row["domain"],
            "title": row["title"],
            "content": row["content"],
            "source": row["source"],
            "tags": json.loads(row["tags"]),
            "created_at": row["created_at"],
            "score": score,
        }

    def web_learn_domain(self, domain: str) -> dict[str, Any]:
        """Fetch real documentation from trusted web sources, summarize, and index it.

        This does NOT retrain the language model. It expands the knowledge base.
        """
        normalized = self._normalize_domain(domain)
        if not normalized:
            return {"ok": False, "error": "Domain is required."}

        entries = self._fetch_web_entries(normalized)
        if entries:
            return self.learn_domain(normalized, entries)
        # Fall back to seed data
        return self.learn_domain(normalized)

    def _fetch_web_entries(self, domain: str) -> list[dict[str, Any]]:
        """Fetch and extract text from trusted documentation URLs for the given domain."""
        url_map: dict[str, list[str]] = {
            "python": [
                "https://docs.python.org/3/tutorial/introduction.html",
                "https://docs.python.org/3/library/functions.html",
            ],
            "fastapi": [
                "https://fastapi.tiangolo.com/tutorial/first-steps/",
            ],
            "javascript": [
                "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Introduction",
            ],
            "react": [
                "https://react.dev/learn",
            ],
            "typescript": [
                "https://www.typescriptlang.org/docs/handbook/typescript-in-5-minutes.html",
            ],
            "git": [
                "https://git-scm.com/book/en/v2/Getting-Started-About-Version-Control",
            ],
        }

        urls = url_map.get(domain, [])
        if not urls:
            domain_slug = domain.replace(" ", "_").lower()
            urls = [
                f"https://en.wikipedia.org/wiki/{domain_slug.capitalize()}",
            ]

        entries: list[dict[str, Any]] = []
        for url in urls[:2]:  # Limit to 2 URLs per learning session
            entry = self._fetch_url(url, domain)
            if entry:
                entries.append(entry)
        return entries

    @staticmethod
    def _fetch_url(url: str, domain: str) -> dict[str, Any] | None:
        """Fetch a URL, strip HTML tags, and return a knowledge entry."""
        try:
            import urllib.request
            import html
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Jarvis-Knowledge-Fetcher/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            # Strip tags
            import re as _re
            text = _re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=_re.DOTALL | _re.IGNORECASE)
            text = _re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=_re.DOTALL | _re.IGNORECASE)
            text = _re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text)
            text = _re.sub(r"\s+", " ", text).strip()
            text = text[:4000]  # Cap at 4000 chars per URL

            if len(text) < 100:
                return None

            return {
                "title": f"{domain.title()} — web documentation",
                "source": url,
                "content": text,
                "tags": [domain, "web", "documentation"],
            }
        except Exception:
            return None
