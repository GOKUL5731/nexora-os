"""Adaptive ontology and knowledge ecosystem evolution."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "adaptive_ontology.db"


class AdaptiveOntologyEngine:
    """Maintains evolving concepts, relationships, and missing capability gaps."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("adaptive_ontology", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS concepts (
                    id TEXT PRIMARY KEY,
                    label TEXT UNIQUE NOT NULL,
                    concept_type TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    confidence REAL DEFAULT 0.6,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS concept_edges (
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(source,target,relation)
                );
                """
            )

    def upsert_concept(self, label: str, concept_type: str, metadata: dict[str, Any] | None = None, confidence: float = 0.6) -> dict[str, Any]:
        concept_id = f"concept:{label.lower().replace(' ', '_')[:120]}"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO concepts VALUES (?,?,?,?,?,?)
                ON CONFLICT(label) DO UPDATE SET
                  concept_type=excluded.concept_type,
                  metadata=excluded.metadata,
                  confidence=excluded.confidence,
                  updated_at=excluded.updated_at
                """,
                (
                    concept_id,
                    label,
                    concept_type,
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    max(0.0, min(1.0, confidence)),
                    datetime.now().isoformat(),
                ),
            )
        return self.get_concept(label)

    def connect(self, source: str, target: str, relation: str, weight: float = 1.0) -> None:
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO concept_edges VALUES (?,?,?,?,?)
                ON CONFLICT(source,target,relation) DO UPDATE SET
                  weight=excluded.weight,
                  updated_at=excluded.updated_at
                """,
                (source, target, relation, max(0.0, min(1.0, weight)), datetime.now().isoformat()),
            )

    def evolve_from_sources(self, sources: list[dict[str, Any]]) -> dict[str, Any]:
        concepts = []
        for source in sources:
            for term in source.get("terms", []):
                concepts.append(self.upsert_concept(term, source.get("type", "knowledge"), {"source": source.get("name", "")}, 0.65))
        for idx in range(len(concepts) - 1):
            self.connect(concepts[idx]["id"], concepts[idx + 1]["id"], "contextually_related", 0.6)
        return {"concepts_added": len(concepts)}

    def missing_capabilities(self, required: list[str]) -> list[dict[str, Any]]:
        labels = {c["label"].lower() for c in self.list_concepts(limit=1000)}
        return [{"capability": item, "gap": "missing_ontology_concept"} for item in required if item.lower() not in labels]

    def get_concept(self, label: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT id,label,concept_type,metadata,confidence,updated_at FROM concepts WHERE label=?", (label,)).fetchone()
        if not row:
            raise KeyError(f"Concept not found: {label}")
        return self._concept_row(row)

    def list_concepts(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,label,concept_type,metadata,confidence,updated_at FROM concepts ORDER BY confidence DESC,updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._concept_row(row) for row in rows]

    def snapshot(self) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            edges = db.execute("SELECT source,target,relation,weight,updated_at FROM concept_edges ORDER BY updated_at DESC LIMIT 200").fetchall()
        return {
            "concepts": self.list_concepts(limit=200),
            "edges": [
                {"source": row[0], "target": row[1], "relation": row[2], "weight": row[3], "updated_at": row[4]}
                for row in edges
            ],
        }

    @staticmethod
    def _concept_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "label": row[1],
            "type": row[2],
            "metadata": json.loads(row[3] or "{}"),
            "confidence": row[4],
            "updated_at": row[5],
        }
